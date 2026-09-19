"""Rebalance Studio: an MCP App for the connector's most awkward flow.

`rebalance_portfolio` needs the user's own holdings, and in a chat that means dictating rows
or hand-building a CSV - error-prone to type, tedious to correct, and impossible to review
before sending. The app takes a paste from a spreadsheet or broker export, shows what it
parsed, and lets the user fix it before anything is calculated.

What it computes is arithmetic against a published target model: the difference between the
weights the user holds and the weights the model carries. It is not a recommendation to
trade, no suitability assessment has been made, and nothing here places an order.
"""

import logging
from typing import Any

from financial_portfolios_ai.exceptions import FinancialPortfoliosAIError
from mcp.server.apps import Apps
from mcp.types import ToolAnnotations

from financial_portfolios_ai_mcp import portal
from financial_portfolios_ai_mcp.app_assets import load_app_html
from financial_portfolios_ai_mcp.auth import get_async_client
from financial_portfolios_ai_mcp.config import get_settings
from financial_portfolios_ai_mcp.disclosure import DISCLAIMER

logger = logging.getLogger(__name__)

REBALANCE_URI = "ui://financial-portfolios-ai/rebalance-studio.html"
REBALANCE_HTML = "rebalance_studio.html"

# Mirrors the portal's upload limits, which `get_rebalance_template` also reports. Stated up
# front so the page can refuse an over-long paste before a round trip rather than after one.
LIMITS = {"max_rows": 200, "max_upload_size_kb": 512}
COLUMNS = {"required": ["ticker", "quantity"], "optional": ["price", "value"]}


def holdings_text(holdings: list[dict[str, Any]] | str | None) -> str:
    """Normalise holdings the model passes in into the lines the page's editor shows.

    The model is the integrator here: if the user has a brokerage connector, it reads the
    positions from there and hands them over, and the app's job is to show what arrived so
    the user can correct it before any arithmetic runs. Typing or pasting is the fallback,
    not the expected path.

    Accepts the same shapes `rebalance_portfolio` does - a list of objects, or CSV text -
    and never raises: a malformed prefill should open an editable page, not an error.
    """
    if not holdings:
        return ""
    if isinstance(holdings, str):
        return holdings.strip()
    lines = []
    for row in holdings:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or row.get("symbol") or "").strip().upper()
        quantity = row.get("quantity", row.get("qty", row.get("shares")))
        if not ticker or quantity is None:
            continue
        price = row.get("price")
        cells = [ticker, str(quantity)]
        if price is not None:
            cells.append(str(price))
        lines.append(",".join(cells))
    return "\n".join(lines)


def _pick_target(portfolios: list[dict[str, Any]], requested: str) -> str | None:
    """The requested code if subscribed, else the first subscribed portfolio.

    Alignment needs a subscription, so a delayed portfolio is never preselected: offering one
    would send the user into a calculation that can only fail.
    """
    subscribed = [p for p in portfolios if p.get("access") == "subscribed"]
    wanted = requested.strip().upper()
    for p in subscribed:
        if p["code"].upper() == wanted:
            return p["code"]
    return subscribed[0]["code"] if subscribed else None


def register_rebalance_studio(apps: Apps) -> None:
    """Register the Rebalance Studio app on an existing Apps extension."""

    @apps.tool(
        resource_uri=REBALANCE_URI,
        name="open_rebalance_studio",
        title="Rebalance Studio",
        description=(
            "Open the Rebalance Studio to compare the user's own holdings with a target model "
            "portfolio: which positions are over- and under-weight, and the share quantities "
            "that would align them. Use it when the user asks to rebalance, align, or see what "
            "to change against a model. "
            "If the user has a brokerage or portfolio-tracking connector available, read their "
            "current positions from it first and pass them as `holdings` - the user should not "
            "be asked to retype what another connector already holds. Pass "
            "[{'ticker': 'AAPL', 'quantity': 40}, ...] or CSV text; they open in an editable "
            "table so the user can check and correct them before anything is calculated. Omit "
            "`holdings` and the user enters them by hand instead. Never ask the user for "
            "brokerage credentials. "
            "Needs a subscription to the target portfolio. Arithmetic only: it is not advice, "
            "not a recommendation to trade, and it places no orders."
        ),
        annotations=ToolAnnotations(
            title="Rebalance Studio",
            read_only_hint=True,
            open_world_hint=True,
        ),
    )
    async def open_rebalance_studio(
        portfolio_code: str = "",
        holdings: list[dict[str, Any]] | str = "",
    ) -> dict[str, Any]:
        settings = get_settings()
        prefill = holdings_text(holdings)

        async def fetch_list() -> dict[str, Any]:
            async with get_async_client() as client:
                return (await client.list_portfolios()).model_dump()

        try:
            listing = await portal.read("list_portfolios", settings.cache_ttl_portfolios, fetch_list)
        except FinancialPortfoliosAIError as e:
            return {"error": "Unable to open the Rebalance Studio", "message": str(e), "disclaimer": DISCLAIMER}
        except Exception as e:
            logger.exception("Unexpected error opening the Rebalance Studio")
            return {"error": "Internal Error", "message": str(e), "disclaimer": DISCLAIMER}

        portfolios = listing.get("portfolios") or []
        return {
            "portfolios": portfolios,
            "selected": _pick_target(portfolios, portfolio_code),
            "holdings_text": prefill,
            "prefilled": bool(prefill),
            "limits": LIMITS,
            "columns": COLUMNS,
            "disclaimer": DISCLAIMER,
        }

    apps.add_html_resource(
        REBALANCE_URI,
        load_app_html(REBALANCE_HTML),
        name="rebalance-studio",
        title="Rebalance Studio",
        description="Paste current holdings and compare them with a target model portfolio.",
        prefers_border=True,
    )
