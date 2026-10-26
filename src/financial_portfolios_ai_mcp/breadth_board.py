"""Breadth Board: what the model portfolios have in common, across all of them at once.

Answers the questions a single-portfolio view cannot: which names the strategies agree on,
how much of the money two books share, and which sector dominates each. Every figure comes
from `metrics.py` - weights only, no prices, no performance.

The arithmetic runs on the server rather than in the page so that a host without MCP Apps
support still receives the numbers as ordinary JSON. That is not hypothetical: no Gemini
surface renders MCP Apps today.
"""

import asyncio
import logging
from typing import Any

from financial_portfolios_ai.exceptions import FinancialPortfoliosAIError
from mcp.server.apps import Apps
from mcp.types import ToolAnnotations

from financial_portfolios_ai_mcp import metrics, portal
from financial_portfolios_ai_mcp.app_assets import load_app_html
from financial_portfolios_ai_mcp.auth import get_async_client
from financial_portfolios_ai_mcp.config import get_settings
from financial_portfolios_ai_mcp.disclosure import DISCLAIMER

logger = logging.getLogger(__name__)

BREADTH_URI = "ui://financial-portfolios-ai/breadth-board.html"
BREADTH_HTML = "breadth_board.html"

# Enough to show the agreement between books without turning the result into a data dump;
# Claude drops an app's result entirely past ~150,000 characters.
MAX_ROWS = 60


async def _allocation(code: str) -> dict[str, Any]:
    settings = get_settings()

    async def fetch() -> dict[str, Any]:
        async with get_async_client() as client:
            return (await client.get_portfolio(portfolio_code=code)).model_dump()

    # Same cache key as `get_portfolio_allocation`, so this shares reads with the other apps.
    return await portal.read(
        "get_portfolio_allocation",
        settings.cache_ttl_allocation,
        fetch,
        portfolio_code=code.upper(),
        as_of=None,
    )


def summarise(books: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Breadth, per-book concentration and sector mix, and the pairwise overlaps."""
    codes = sorted(books)
    rows = metrics.breadth(books)
    pairs = [
        {"left": left, "right": right, **metrics.overlap(books[left], books[right])}
        for index, left in enumerate(codes)
        for right in codes[index + 1:]
    ]
    return {
        "most_held": [row for row in rows if row["count"] > 1][:MAX_ROWS],
        "only_in_one": sum(1 for row in rows if row["count"] == 1),
        "distinct_holdings": len(rows),
        "books": {
            code: {
                "concentration": metrics.concentration(positions),
                "sectors": metrics.sector_mix(positions),
            }
            for code, positions in books.items()
        },
        "overlaps": pairs,
    }


def register_breadth_board(apps: Apps) -> None:
    """Register the Breadth Board app on an existing Apps extension."""

    @apps.tool(
        resource_uri=BREADTH_URI,
        name="open_breadth_board",
        title="Breadth Board",
        description=(
            "Open the Breadth Board: which stocks are held across several of the user's model "
            "portfolios and at what weight, how much each pair of portfolios overlaps by name "
            "and by weight, and the dominant sector and concentration of each. Use it for "
            "questions spanning portfolios - what is most widely held, what the strategies "
            "agree on, which sector dominates, how concentrated the books are. "
            "It reports what the models hold, never how anything performed. Informational only."
        ),
        annotations=ToolAnnotations(
            title="Breadth Board",
            read_only_hint=True,
            destructive_hint=False,
            open_world_hint=True,
        ),
    )
    async def open_breadth_board() -> dict[str, Any]:
        settings = get_settings()

        async def fetch_list() -> dict[str, Any]:
            async with get_async_client() as client:
                return (await client.list_portfolios()).model_dump()

        try:
            listing = await portal.read("list_portfolios", settings.cache_ttl_portfolios, fetch_list)
            portfolios = listing.get("portfolios") or []
            codes = [p["code"] for p in portfolios]
            # Concurrently, because this is the one view that needs every book at once; the
            # portal cache de-duplicates whatever the other apps have already read.
            results = await asyncio.gather(*(_allocation(code) for code in codes), return_exceptions=True)
        except FinancialPortfoliosAIError as e:
            return {"error": "Unable to open the Breadth Board", "message": str(e), "disclaimer": DISCLAIMER}
        except Exception as e:
            logger.exception("Unexpected error opening the Breadth Board")
            return {"error": "Internal Error", "message": str(e), "disclaimer": DISCLAIMER}

        books: dict[str, list[dict[str, Any]]] = {}
        unavailable = []
        meta = {}
        for code, result in zip(codes, results):
            # One unreadable book should narrow the comparison, not lose it. Which ones were
            # skipped is reported, because a breadth count computed over fewer portfolios
            # than the user has would otherwise read as fact.
            if isinstance(result, Exception):
                logger.warning("breadth_board_skipped_portfolio", extra={"portfolio": code, "reason": str(result)})
                unavailable.append(code)
                continue
            books[code] = result.get("positions") or []
            meta[code] = {
                "name": next((p.get("product_name") for p in portfolios if p["code"] == code), None) or code,
                "access": result.get("access"),
                "delayed": bool(result.get("delayed")),
                "as_of": str(result.get("as_of") or result.get("date") or "")[:10],
            }

        return {
            "portfolios": meta,
            "unavailable": unavailable,
            **summarise(books),
            "disclaimer": DISCLAIMER,
        }

    apps.add_html_resource(
        BREADTH_URI,
        load_app_html(BREADTH_HTML),
        name="breadth-board",
        title="Breadth Board",
        description="What the model portfolios hold in common: most-held stocks, overlap, and sector dominance.",
        prefers_border=True,
    )
