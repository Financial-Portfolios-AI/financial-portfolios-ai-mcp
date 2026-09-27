"""Resource definitions for Financial Portfolios AI MCP Server."""

import json
import logging
from typing import Any

from financial_portfolios_ai.exceptions import FinancialPortfoliosAIError

from financial_portfolios_ai_mcp.auth import get_async_client
from financial_portfolios_ai_mcp.disclosure import DISCLAIMER

logger = logging.getLogger(__name__)



def register_resources(server: Any) -> None:
    """Register MCP resources with the server."""

    @server.resource(
        "portfolios://catalog",
        name="Portfolio Catalog",
        description=(
            "Catalog of all active quantitative investment portfolios on Financial Portfolios AI, "
            "each marked `access`: subscribed (live book) or public_delayed (~45-day lag)"
        ),
        mime_type="application/json",
    )
    async def get_portfolio_catalog() -> str:
        """Fetch real-time portfolio catalog."""
        try:
            async with get_async_client() as client:
                portfolios = await client.list_portfolios()
                data = portfolios.model_dump()
                data["disclaimer"] = DISCLAIMER
                return json.dumps(data, indent=2, default=str)
        except FinancialPortfoliosAIError as e:
            logger.warning("Portal error fetching portfolio catalog: %s", e)
            return json.dumps(
                {"error": "Unable to fetch catalog", "detail": str(e), "disclaimer": DISCLAIMER},
                indent=2,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Unexpected error fetching portfolio catalog resource: %s", e)
            return json.dumps(
                {"error": "Unable to fetch catalog", "detail": str(e), "disclaimer": DISCLAIMER},
                indent=2,
            )

    @server.resource(
        "portfolios://{portfolio_code}/allocation",
        name="Portfolio Target Allocation",
        description=(
            "Model allocation snapshot, position weights, and risk metrics for a specific portfolio: "
            "the latest book when subscribed, otherwise the public book delayed by ~45 days"
        ),
        mime_type="application/json",
    )
    async def get_portfolio_resource(portfolio_code: str) -> str:
        """Fetch current allocation for specified portfolio."""
        try:
            async with get_async_client() as client:
                snapshot = await client.get_portfolio(portfolio_code=portfolio_code)
                data = snapshot.model_dump()
                data["disclaimer"] = DISCLAIMER
                return json.dumps(data, indent=2, default=str)
        except FinancialPortfoliosAIError as e:
            logger.warning("Portal error fetching allocation for %s: %s", portfolio_code, e)
            return json.dumps(
                {
                    "error": f"Unable to fetch allocation for {portfolio_code}",
                    "detail": str(e),
                    "disclaimer": DISCLAIMER,
                },
                indent=2,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "Unexpected error fetching allocation resource for %s: %s", portfolio_code, e
            )
            return json.dumps(
                {
                    "error": f"Unable to fetch allocation for {portfolio_code}",
                    "detail": str(e),
                    "disclaimer": DISCLAIMER,
                },
                indent=2,
            )

    @server.resource(
        "research://posts/latest",
        name="Latest Research & Market Insights",
        description="Most recent quantitative market commentaries and research publications",
        mime_type="application/json",
    )
    async def get_latest_research() -> str:
        """Fetch latest published blog and research posts."""
        try:
            async with get_async_client() as client:
                posts = await client.list_blog_posts(page=1, page_size=5)
                data = posts.model_dump()
                data["disclaimer"] = DISCLAIMER
                return json.dumps(data, indent=2, default=str)
        except FinancialPortfoliosAIError as e:
            logger.warning("Portal error fetching latest research: %s", e)
            return json.dumps(
                {
                    "error": "Unable to fetch research posts",
                    "detail": str(e),
                    "disclaimer": DISCLAIMER,
                },
                indent=2,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Unexpected error fetching research resource: %s", e)
            return json.dumps(
                {
                    "error": "Unable to fetch research posts",
                    "detail": str(e),
                    "disclaimer": DISCLAIMER,
                },
                indent=2,
            )
