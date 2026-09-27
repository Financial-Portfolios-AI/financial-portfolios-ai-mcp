"""Portfolio Explorer: an MCP App (interactive UI rendered inline by the host).

Prompt inputs cannot offer choices - an MCP prompt argument has only a name, title,
description and required flag - so a real dropdown needs an MCP App: a tool bound to
a `ui://` HTML resource that the host renders in a sandboxed iframe.

`open_portfolio_explorer` returns the portfolio list plus one allocation. A host that
supports MCP Apps renders `assets/portfolio_explorer.html` with that result; the page
then calls the existing read-only tools (`get_portfolio_allocation`,
`get_portfolio_history`) back through the host as the user picks from its dropdowns.

A host without MCP Apps support still gets useful output: the tool result is the same
JSON the model reads for any other tool, per SEP-2133's graceful-degradation rule.

The page is fully self-contained - inline script and styles, no network - because the
host's default Content-Security-Policy for an app allows nothing else.
"""

import logging
from typing import Any

from financial_portfolios_ai.exceptions import FinancialPortfoliosAIError
from mcp.server.apps import Apps
from mcp.types import ToolAnnotations

from financial_portfolios_ai_mcp import portal
from financial_portfolios_ai_mcp.app_assets import VERSION_PLACEHOLDER, load_app_html, read_app_html
from financial_portfolios_ai_mcp.auth import get_async_client
from financial_portfolios_ai_mcp.config import get_settings
from financial_portfolios_ai_mcp.disclosure import DISCLAIMER

logger = logging.getLogger(__name__)

EXPLORER_URI = "ui://financial-portfolios-ai/portfolio-explorer.html"
EXPLORER_HTML = "portfolio_explorer.html"

__all__ = [
    "EXPLORER_HTML",
    "EXPLORER_URI",
    "VERSION_PLACEHOLDER",
    "build_explorer",
    "summarize_host",
]


def _read_html() -> str:
    return read_app_html(EXPLORER_HTML)


def _load_html() -> str:
    return load_app_html(EXPLORER_HTML)


def _pick_initial(portfolios: list[dict[str, Any]], requested: str) -> str | None:
    """The requested code if listed, else the first subscribed portfolio, else the first."""
    codes = {p["code"].upper(): p["code"] for p in portfolios}
    if requested and requested.strip().upper() in codes:
        return codes[requested.strip().upper()]
    for p in portfolios:
        if p.get("access") == "subscribed":
            return p["code"]
    return portfolios[0]["code"] if portfolios else None


# Only these host-context fields are recorded: enough to know what to build, and nothing
# that identifies the user (no locale, time zone or dimensions).
_CONTEXT_FIELDS = ("theme", "displayMode", "availableDisplayModes", "platform", "deviceCapabilities")


def summarize_host(
    capabilities: dict[str, Any] | None,
    context: dict[str, Any] | None,
    info: dict[str, Any] | None,
) -> dict[str, Any]:
    """Reduce a host's self-description to feature flags safe to log.

    Capabilities are recorded as which flags are present (and one level of their keys),
    never as full values; context keeps only `_CONTEXT_FIELDS`, plus whether the host
    supplies theme variables and how many; host info keeps name and version.
    """
    caps = capabilities if isinstance(capabilities, dict) else {}
    ctx = context if isinstance(context, dict) else {}
    meta = info if isinstance(info, dict) else {}

    flags = {
        str(name)[:64]: sorted(str(k)[:64] for k in value)[:20] if isinstance(value, dict) else bool(value)
        for name, value in list(caps.items())[:30]
    }
    styles = ctx.get("styles")
    variables = styles.get("variables") if isinstance(styles, dict) else None
    return {
        "host": {k: str(meta.get(k))[:64] for k in ("name", "version") if meta.get(k) is not None},
        "capabilities": flags,
        "context": {k: ctx[k] for k in _CONTEXT_FIELDS if k in ctx},
        "style_variables": len(variables) if isinstance(variables, dict) else 0,
    }


def build_explorer() -> Apps:
    """Build the Apps extension carrying the Portfolio Explorer tool and its UI."""
    apps = Apps()

    @apps.tool(
        resource_uri=EXPLORER_URI,
        name="open_portfolio_explorer",
        title="Portfolio Explorer",
        description=(
            "Open the interactive Portfolio Explorer: a dropdown of the user's model portfolios, "
            "a sortable holdings table, sector and concentration charts, changes over time, a "
            "side-by-side comparison of two or three portfolios (sector mix and shared holdings), "
            "and a search showing which portfolios hold a given stock. Use it when the user wants to "
            "browse, explore, visualise, compare or search across portfolios interactively rather "
            "than read a single answer. Optionally pass `portfolio_code` to open on a "
            "specific portfolio; otherwise it opens on the user's first subscribed portfolio. "
            "Informational only: it displays model data and makes no recommendations."
        ),
        annotations=ToolAnnotations(
            title="Portfolio Explorer",
            read_only_hint=True,
            open_world_hint=True,
        ),
    )
    async def open_portfolio_explorer(portfolio_code: str = "") -> dict[str, Any]:
        settings = get_settings()

        async def fetch_list() -> dict[str, Any]:
            async with get_async_client() as client:
                return (await client.list_portfolios()).model_dump()

        try:
            # Same cache keys as the tools, so opening the Explorer warms the reads its
            # page then makes, and vice versa.
            listing = await portal.read("list_portfolios", settings.cache_ttl_portfolios, fetch_list)
            portfolios = listing.get("portfolios") or []
            selected = _pick_initial(portfolios, portfolio_code)
            allocation = None
            if selected:
                async def fetch_allocation() -> dict[str, Any]:
                    async with get_async_client() as client:
                        return (await client.get_portfolio(portfolio_code=selected)).model_dump()

                allocation = await portal.read(
                    "get_portfolio_allocation",
                    settings.cache_ttl_allocation,
                    fetch_allocation,
                    portfolio_code=selected.upper(),
                    as_of=None,
                )
        except FinancialPortfoliosAIError as e:
            return {"error": "Unable to open the Portfolio Explorer", "message": str(e), "disclaimer": DISCLAIMER}
        except Exception as e:
            logger.exception("Unexpected error opening the Portfolio Explorer")
            return {"error": "Internal Error", "message": str(e), "disclaimer": DISCLAIMER}

        return {
            "portfolios": portfolios,
            "selected": selected,
            "allocation": allocation,
            "disclaimer": DISCLAIMER,
        }

    @apps.tool(
        resource_uri=EXPLORER_URI,
        visibility=["app"],
        name="report_explorer_host",
        title="Explorer host capabilities (internal)",
        description=(
            "Internal: called by the Portfolio Explorer page to record which MCP Apps features "
            "the host supports. Not for use in conversation."
        ),
        annotations=ToolAnnotations(
            title="Explorer host capabilities (internal)",
            read_only_hint=True,
            open_world_hint=False,
        ),
    )
    async def report_explorer_host(
        host_capabilities: dict[str, Any] | None = None,
        host_context: dict[str, Any] | None = None,
        host_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # Page-only (visibility "app"): the host hides it from the model. It records which
        # optional MCP Apps features each host advertises, so the Explorer is built against
        # what Claude and ChatGPT actually support rather than what the spec allows.
        logger.info("explorer_host_report", extra=summarize_host(host_capabilities, host_context, host_info))
        return {"recorded": True}

    apps.add_html_resource(
        EXPLORER_URI,
        _load_html(),
        name="portfolio-explorer",
        title="Portfolio Explorer",
        description="Interactive explorer for Financial Portfolios AI model portfolios.",
        prefers_border=True,
    )
    return apps
