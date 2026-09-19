"""Derived-analysis tools: the same arithmetic the apps show, as plain tool calls.

These exist as tools rather than only as prompts because prompts are not a delivery
surface. OpenAI's plugin documentation never mentions `prompts/list` and states that
plugins primarily use tools; on claude.ai Anthropic says prompts are supported while an
open bug report says custom-connector prompts appear nowhere in the UI. A tool is surfaced
by every host, so anything a customer needs to reach ships as one. See
docs/providers_and_automation.md.

They are also the shape scheduled automation needs - one call that answers "what changed in
this portfolio since last week" - because no host offers server-initiated triggering, so a
timer firing a single tool is the whole automation primitive.

Everything here is computed from published weights by `metrics.py`. No prices are involved
and nothing estimates a return.
"""

import logging
from typing import Any

from financial_portfolios_ai.exceptions import (
    AuthenticationError,
    FinancialPortfoliosAIError,
    NotFoundError,
    RateLimitError,
)
from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from financial_portfolios_ai_mcp import metrics, portal
from financial_portfolios_ai_mcp.auth import get_async_client
from financial_portfolios_ai_mcp.config import get_settings
from financial_portfolios_ai_mcp.disclosure import DISCLAIMER

logger = logging.getLogger(__name__)

WEIGHT_NOTE = "Weights are on the same scale as `get_portfolio_allocation` returns them."

# The portal failures every tool maps the same way, matching `tools.py` so a model sees one
# error vocabulary across the whole server.
PORTAL_ERRORS = (AuthenticationError, NotFoundError, RateLimitError, FinancialPortfoliosAIError)
_LABELS = (
    (AuthenticationError, "Authentication or subscription required"),
    (NotFoundError, "Portfolio Not Found"),
    (RateLimitError, "Rate Limit Exceeded"),
)


def _portal_failure(exc: FinancialPortfoliosAIError) -> dict[str, Any]:
    label = next((text for kind, text in _LABELS if isinstance(exc, kind)), "Portal API Error")
    return {"error": label, "message": str(exc), "disclaimer": DISCLAIMER}


def register_analysis_tools(server: MCPServer) -> None:
    """Register the derived-analysis tools."""

    @server.tool(
        name="get_portfolio_metrics",
        title="Concentration and sector mix",
        description=(
            "Summarise how a model portfolio is shaped: how concentrated it is (top-5 and top-10 "
            "weight, largest holding, effective number of holdings), its weight by sector, its "
            "dominant sector, and how much of it carries no sector label. Use it for questions "
            "about concentration, diversification, sector exposure or which sector dominates. "
            "These are derived from the published weights, so they are available for the public "
            "delayed book too - where the portal itself returns effective N, equity exposure and "
            "cash allocation as null. No prices are involved and nothing here is a return or a "
            "performance figure."
        ),
        annotations=ToolAnnotations(
            title="Concentration and sector mix",
            read_only_hint=True,
            open_world_hint=True,
        ),
    )
    async def get_portfolio_metrics(portfolio_code: str) -> dict[str, Any]:
        """
        Concentration and sector mix for one portfolio, derived from its weights.

        :param portfolio_code: Portfolio identifier (e.g., 'AQA_AGGRESSIVE')
        """
        try:
            async def fetch() -> dict[str, Any]:
                async with get_async_client() as client:
                    return (await client.get_portfolio(portfolio_code=portfolio_code)).model_dump()

            # Same cache key as `get_portfolio_allocation`, so asking for the metrics after the
            # allocation (the usual order) costs no extra portal read.
            data = await portal.read(
                "get_portfolio_allocation",
                get_settings().cache_ttl_allocation,
                fetch,
                portfolio_code=portfolio_code.upper(),
                as_of=None,
            )
        except PORTAL_ERRORS as e:
            return _portal_failure(e)
        except Exception as e:
            # Logged inline rather than through a helper: ruff only exempts a blind
            # handler from BLE001 when it can see the logging call.
            logger.exception("Unexpected error in get_portfolio_metrics")
            return {"error": "Internal Error", "message": str(e), "disclaimer": DISCLAIMER}

        positions = data.get("positions") or []
        return {
            "portfolio_code": data.get("portfolio_code", portfolio_code.upper()),
            "as_of": str(data.get("as_of") or data.get("date") or "")[:10],
            "access": data.get("access"),
            "delayed": bool(data.get("delayed")),
            "concentration": metrics.concentration(positions),
            "sectors": metrics.sector_mix(positions),
            "note": WEIGHT_NOTE,
            "disclaimer": DISCLAIMER,
        }

    @server.tool(
        name="get_portfolio_changes",
        title="What the model changed",
        description=(
            "Compare the oldest and newest allocation snapshots in a period and report what the "
            "model did: which holdings it opened and closed, which weights it raised and cut "
            "most, and how much of the book moved (one-way turnover). Use it for 'what changed', "
            "'what's new', 'what did it buy or sell', or a recurring digest of recent activity. "
            "This is what the model decided, not how anything performed: there are no prices "
            "behind it, so it reports weight changes, never returns or gains. For a portfolio the "
            "user is not subscribed to, the history ends about 45 days ago and recent changes are "
            "not visible."
        ),
        annotations=ToolAnnotations(
            title="What the model changed",
            read_only_hint=True,
            open_world_hint=True,
        ),
    )
    async def get_portfolio_changes(portfolio_code: str, days: int = 30) -> dict[str, Any]:
        """
        What a model portfolio added, removed and re-weighted over a period.

        :param portfolio_code: Portfolio identifier (e.g., 'AQA_AGGRESSIVE')
        :param days: Number of calendar days to look back (1-365, default: 30)
        """
        try:
            async def fetch() -> dict[str, Any]:
                async with get_async_client() as client:
                    history = await client.get_portfolio_history(portfolio_code=portfolio_code, days=days)
                    return history.model_dump()

            data = await portal.read(
                "get_portfolio_history",
                get_settings().cache_ttl_history,
                fetch,
                portfolio_code=portfolio_code.upper(),
                days=days,
            )
        except PORTAL_ERRORS as e:
            return _portal_failure(e)
        except Exception as e:
            # Logged inline rather than through a helper: ruff only exempts a blind
            # handler from BLE001 when it can see the logging call.
            logger.exception("Unexpected error in get_portfolio_changes")
            return {"error": "Internal Error", "message": str(e), "disclaimer": DISCLAIMER}

        snapshots = sorted(data.get("snapshots") or [], key=lambda s: str(s.get("date") or ""))
        if len(snapshots) < 2:
            # Not an error: a short window, or a delayed book whose history has not yet caught
            # up, legitimately has nothing to compare. Say which, rather than returning zeros
            # that read as "the model changed nothing".
            return {
                "portfolio_code": data.get("portfolio_code", portfolio_code.upper()),
                "days": days,
                "snapshots": len(snapshots),
                "comparable": False,
                "message": (
                    "Fewer than two snapshots in this period, so there is nothing to compare. "
                    "Try a longer period."
                    + (" This is the public delayed book, whose history ends about 45 days ago."
                       if data.get("delayed") else "")
                ),
                "access": data.get("access"),
                "delayed": bool(data.get("delayed")),
                "disclaimer": DISCLAIMER,
            }

        earliest, latest = snapshots[0], snapshots[-1]
        return {
            "portfolio_code": data.get("portfolio_code", portfolio_code.upper()),
            "days": days,
            "comparable": True,
            "snapshots": len(snapshots),
            "from": str(earliest.get("date") or "")[:10],
            "to": str(latest.get("date") or "")[:10],
            "access": data.get("access"),
            "delayed": bool(data.get("delayed")),
            **metrics.changes(earliest.get("positions") or [], latest.get("positions") or []),
            "note": WEIGHT_NOTE,
            "disclaimer": DISCLAIMER,
        }
