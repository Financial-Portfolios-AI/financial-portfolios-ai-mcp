"""Performance tools: the figures the portal publishes, relayed with its disclosure.

These exist because the connector was, until now, stricter than the product. The website
shows performance, best and worst performers and most-held names on its public product
pages, disclosed as simulated and hypothetical. The connector refused the whole category,
so a customer read a figure on the site and was told by the assistant that it did not
exist. That was an inconsistency, not a safety margin.

The boundary that remains is **authorship, not subject**. A figure the publisher computed
and labelled is the publisher's to publish, and this relays it. A figure derived here by
pricing holdings with a market-data connector would be one nobody vetted, carrying no
hypothetical labelling and not matching the website - that stays out of scope, and
`server.py` tells the model so.

Each response carries its own `disclaimer` from the portal - a different statement from the
ADR-0161 constant on allocation and history, because these numbers need a different one.
It is relayed verbatim and never composed here. `_require_disclosure` makes that a
guarantee rather than an intention: a payload carrying figures without the portal's
disclosure is refused rather than returned.
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

from financial_portfolios_ai_mcp import portal
from financial_portfolios_ai_mcp.auth import get_async_client
from financial_portfolios_ai_mcp.config import get_settings
from financial_portfolios_ai_mcp.disclosure import DISCLAIMER

logger = logging.getLogger(__name__)

PORTAL_ERRORS = (AuthenticationError, NotFoundError, RateLimitError, FinancialPortfoliosAIError)
_LABELS = (
    (AuthenticationError, "Authentication or subscription required"),
    (NotFoundError, "Portfolio Not Found"),
    (RateLimitError, "Rate Limit Exceeded"),
)

# Sent to the model alongside every performance payload. The portal's own `disclaimer` is
# the disclosure; this is the instruction for what to do with it.
RELAY_NOTE = (
    "These figures are hypothetical and simulated. Present the `disclaimer` field with them, "
    "in full and unaltered, and never restate it in your own words."
)


def _portal_failure(exc: FinancialPortfoliosAIError) -> dict[str, Any]:
    label = next((text for kind, text in _LABELS if isinstance(exc, kind)), "Portal API Error")
    return {"error": label, "message": str(exc), "disclaimer": DISCLAIMER}


def _require_disclosure(payload: dict[str, Any], operation: str) -> dict[str, Any]:
    """Refuse to hand back performance figures that arrived without their disclosure.

    The portal attaches one to every performance response. If a deployment ever stops, the
    honest failure is to say the figures are unavailable - publishing them bare, or pasting
    in wording composed here, is how an unlabelled hypothetical return reaches a customer.
    """
    if payload.get("available") and not payload.get("disclaimer"):
        logger.error("performance_disclosure_missing", extra={"operation": operation})
        return {
            "error": "Performance disclosure missing",
            "message": (
                "The portal returned performance figures without their required disclosure, so "
                "they are withheld. Tell the user performance is temporarily unavailable."
            ),
            "disclaimer": DISCLAIMER,
        }
    return payload


def register_performance_tools(server: MCPServer) -> None:
    """Register the portal-backed performance tools."""

    @server.tool(
        name="get_portfolio_performance",
        title="Performance and risk statistics",
        description=(
            "Hypothetical, simulated performance for a model portfolio: the indexed curve "
            "against its benchmark, and since-inception statistics - total and annualized "
            "return, volatility, Sharpe, Sortino, maximum drawdown, and beta, alpha, "
            "information ratio, tracking error and correlation against the benchmark. "
            "These are the same figures the website publishes, computed from the model's "
            "published target holdings and total-return prices; they are not the results of "
            "any account. A subscriber gets the live curve, anyone else the public book's, "
            "delayed about 45 days. Check `available` first - while price history is "
            "backfilling it is false with a `reason`. Always present the `disclaimer` field "
            "with the numbers, unaltered."
        ),
        annotations=ToolAnnotations(
            title="Performance and risk statistics",
            read_only_hint=True,
            open_world_hint=True,
        ),
    )
    async def get_portfolio_performance(portfolio_code: str) -> dict[str, Any]:
        """
        Hypothetical, simulated performance and risk statistics for one portfolio.

        :param portfolio_code: Portfolio identifier (e.g., 'AQA_AGGRESSIVE')
        """
        try:

            async def fetch() -> dict[str, Any]:
                async with get_async_client() as client:
                    result = await client.get_portfolio_performance(portfolio_code=portfolio_code)
                    return result.model_dump()

            data = await portal.read(
                "get_portfolio_performance",
                get_settings().cache_ttl_history,
                fetch,
                portfolio_code=portfolio_code.upper(),
            )
        except PORTAL_ERRORS as e:
            return _portal_failure(e)
        except Exception as e:
            logger.exception("Unexpected error in get_portfolio_performance")
            return {"error": "Internal Error", "message": str(e), "disclaimer": DISCLAIMER}

        return _require_disclosure({**data, "note": RELAY_NOTE}, "get_portfolio_performance")

    @server.tool(
        name="get_portfolio_metrics",
        title="Best and worst performers",
        description=(
            "Which holdings helped and hurt a model portfolio, and which names it has held "
            "most persistently: best and worst performers with their simulated return, "
            "most-held tickers with company names and average weight, and win rates by name "
            "and by invested capital. Returns are measured only over the periods each name "
            "was actually held and are hypothetical, not the results of any account. A "
            "subscriber gets live figures, anyone else the public book's, delayed about 45 "
            "days. Check `available` first. Always present the `disclaimer` field with the "
            "numbers, unaltered. For concentration and sector mix instead, use "
            "`get_portfolio_concentration`."
        ),
        annotations=ToolAnnotations(
            title="Best and worst performers",
            read_only_hint=True,
            open_world_hint=True,
        ),
    )
    async def get_portfolio_metrics(portfolio_code: str) -> dict[str, Any]:
        """
        Best and worst performers, most-held names and win rates for one portfolio.

        :param portfolio_code: Portfolio identifier (e.g., 'AQA_AGGRESSIVE')
        """
        try:

            async def fetch() -> dict[str, Any]:
                async with get_async_client() as client:
                    result = await client.get_portfolio_metrics(portfolio_code=portfolio_code)
                    return result.model_dump()

            data = await portal.read(
                "get_portfolio_metrics",
                get_settings().cache_ttl_history,
                fetch,
                portfolio_code=portfolio_code.upper(),
            )
        except PORTAL_ERRORS as e:
            return _portal_failure(e)
        except Exception as e:
            logger.exception("Unexpected error in get_portfolio_metrics")
            return {"error": "Internal Error", "message": str(e), "disclaimer": DISCLAIMER}

        return _require_disclosure({**data, "note": RELAY_NOTE}, "get_portfolio_metrics")
