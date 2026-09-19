"""Research Reader: an MCP App for browsing and reading the portal's research.

`list_blog_posts` and `get_blog_post` work, but reading through a model means asking for a
list, choosing by number, then waiting for prose to be relayed back. The app lists what is
there, opens a post in place, and - the part a chat cannot do well - marks which posts
mention a ticker the user's portfolios actually hold.

That last part is first-party only: our own research joined to our own holdings. No outside
data, no prices, no performance.
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

RESEARCH_URI = "ui://financial-portfolios-ai/research-reader.html"
RESEARCH_HTML = "research_reader.html"

PAGE_SIZE = 20


def register_research_reader(apps: Apps) -> None:
    """Register the Research Reader app on an existing Apps extension."""

    @apps.tool(
        resource_uri=RESEARCH_URI,
        name="open_research_reader",
        title="Research Reader",
        description=(
            "Open the Research Reader: browse Financial Portfolios AI research and market "
            "commentary, search it, read a post in place, and see which posts mention tickers "
            "held in the user's own model portfolios. Use it when the user wants to read, "
            "browse or search the research rather than have a single answer summarised. "
            "Optionally pass `search` to open on a topic. Informational only."
        ),
        annotations=ToolAnnotations(
            title="Research Reader",
            read_only_hint=True,
            open_world_hint=True,
        ),
    )
    async def open_research_reader(search: str = "") -> dict[str, Any]:
        settings = get_settings()
        query = search.strip() or None

        async def fetch_posts() -> dict[str, Any]:
            async with get_async_client() as client:
                return (await client.list_blog_posts(page=1, page_size=PAGE_SIZE, search=query)).model_dump()

        try:
            listing = await portal.read(
                "list_blog_posts",
                settings.cache_ttl_research,
                fetch_posts,
                page=1,
                page_size=PAGE_SIZE,
                search=query,
            )
        except FinancialPortfoliosAIError as e:
            return {"error": "Unable to open the Research Reader", "message": str(e), "disclaimer": DISCLAIMER}
        except Exception as e:
            logger.exception("Unexpected error opening the Research Reader")
            return {"error": "Internal Error", "message": str(e), "disclaimer": DISCLAIMER}

        return {
            "posts": listing.get("items") or [],
            "total": listing.get("total"),
            "page": listing.get("page"),
            "page_size": listing.get("page_size"),
            "search": query or "",
            "disclaimer": DISCLAIMER,
        }

    apps.add_html_resource(
        RESEARCH_URI,
        load_app_html(RESEARCH_HTML),
        name="research-reader",
        title="Research Reader",
        description="Browse and read Financial Portfolios AI research, including posts that mention your holdings.",
        prefers_border=True,
    )
