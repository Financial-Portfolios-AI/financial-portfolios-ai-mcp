"""Tool definitions for Financial Portfolios AI MCP Server."""

import json
import logging
from typing import Any

from financial_portfolios_ai.exceptions import (
    AuthenticationError,
    FinancialPortfoliosAIError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)

from financial_portfolios_ai_mcp.auth import get_async_client

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "Informational and educational purposes only. Not investment, legal, or tax advice, "
    "and not a recommendation or solicitation. No suitability assessment has been performed. "
    "All outputs represent mathematical target-model alignment arithmetic."
)


def register_tools(server: Any) -> None:
    """Register all Financial Portfolios AI tools with the MCP server."""

    @server.tool(
        name="list_portfolios",
        description=(
            "List all quantitative investment portfolios accessible under the user's active "
            "subscription on Financial Portfolios AI (e.g. AQA_AGGRESSIVE, AQA_BALANCED, AQA_DEFENSIVE)."
        ),
    )
    async def list_portfolios() -> str:
        """
        List accessible quantitative investment portfolios.

        :return: JSON formatted list of portfolios with risk level, theme, and description.
        """
        try:
            async with get_async_client() as client:
                result = await client.list_portfolios()
                data = result.model_dump()
                data["disclaimer"] = DISCLAIMER
                return json.dumps(data, indent=2, default=str)
        except AuthenticationError as e:
            return json.dumps(
                {
                    "error": "Authentication or Subscription required",
                    "message": str(e),
                    "hint": "Please generate an API token at https://financial-portfolios.ai/settings/api-tokens after logging in with Google.",
                    "disclaimer": DISCLAIMER,
                },
                indent=2,
            )
        except RateLimitError as e:
            return json.dumps(
                {"error": "Rate Limit Exceeded", "message": str(e), "disclaimer": DISCLAIMER},
                indent=2,
            )
        except FinancialPortfoliosAIError as e:
            return json.dumps(
                {"error": "Portal API Error", "message": str(e), "disclaimer": DISCLAIMER}, indent=2
            )
        except Exception as e:
            logger.exception("Unexpected error in list_portfolios")
            return json.dumps(
                {"error": "Internal Error", "message": str(e), "disclaimer": DISCLAIMER}, indent=2
            )

    @server.tool(
        name="get_portfolio_allocation",
        description=(
            "Retrieve current or historical target allocation snapshot for a specific portfolio "
            "(e.g. 'AQA_AGGRESSIVE', 'AQA_BALANCED', 'AQA_DEFENSIVE'). Returns target asset weights, "
            "tickers, sectors, expected return, volatility, equity exposure, and cash allocation. "
            "Output represents mathematical target-model allocation arithmetic, not personalized investment advice."
        ),
    )
    async def get_portfolio_allocation(
        portfolio_code: str,
        as_of: str | None = None,
    ) -> str:
        """
        Get portfolio target allocation and risk metrics.

        :param portfolio_code: Portfolio identifier (e.g., 'AQA_AGGRESSIVE', 'AQA_BALANCED')
        :param as_of: Optional historical snapshot date (YYYY-MM-DD or ISO 8601 format)
        """
        try:
            async with get_async_client() as client:
                snapshot = await client.get_portfolio(portfolio_code=portfolio_code, as_of=as_of)
                data = snapshot.model_dump()
                data["disclaimer"] = DISCLAIMER
                return json.dumps(data, indent=2, default=str)
        except AuthenticationError as e:
            return json.dumps(
                {
                    "error": "Authentication or subscription access denied",
                    "portfolio": portfolio_code,
                    "message": str(e),
                    "hint": "Ensure your account has an active subscription covering this portfolio at https://financial-portfolios.ai",
                    "disclaimer": DISCLAIMER,
                },
                indent=2,
            )
        except NotFoundError as e:
            return json.dumps(
                {"error": "Portfolio Not Found", "message": str(e), "disclaimer": DISCLAIMER},
                indent=2,
            )
        except RateLimitError as e:
            return json.dumps(
                {"error": "Rate Limit Exceeded", "message": str(e), "disclaimer": DISCLAIMER},
                indent=2,
            )
        except FinancialPortfoliosAIError as e:
            return json.dumps(
                {"error": "Portal API Error", "message": str(e), "disclaimer": DISCLAIMER}, indent=2
            )
        except Exception as e:
            logger.exception("Unexpected error in get_portfolio_allocation")
            return json.dumps(
                {"error": "Internal Error", "message": str(e), "disclaimer": DISCLAIMER}, indent=2
            )

    @server.tool(
        name="get_portfolio_history",
        description=(
            "Retrieve historical allocation snapshots for up to 365 days for a specific portfolio. "
            "Useful for tracking historical model changes and target allocation evolution."
        ),
    )
    async def get_portfolio_history(
        portfolio_code: str,
        days: int = 30,
    ) -> str:
        """
        Get portfolio allocation history.

        :param portfolio_code: Portfolio identifier (e.g., 'AQA_AGGRESSIVE')
        :param days: Number of calendar days of history (1-365, default: 30)
        """
        try:
            async with get_async_client() as client:
                history = await client.get_portfolio_history(
                    portfolio_code=portfolio_code, days=days
                )
                data = history.model_dump()
                data["disclaimer"] = DISCLAIMER
                return json.dumps(data, indent=2, default=str)
        except AuthenticationError as e:
            return json.dumps(
                {
                    "error": "Authentication or subscription required",
                    "message": str(e),
                    "disclaimer": DISCLAIMER,
                },
                indent=2,
            )
        except NotFoundError as e:
            return json.dumps(
                {"error": "Portfolio Not Found", "message": str(e), "disclaimer": DISCLAIMER},
                indent=2,
            )
        except RateLimitError as e:
            return json.dumps(
                {"error": "Rate Limit Exceeded", "message": str(e), "disclaimer": DISCLAIMER},
                indent=2,
            )
        except FinancialPortfoliosAIError as e:
            return json.dumps(
                {"error": "Portal API Error", "message": str(e), "disclaimer": DISCLAIMER}, indent=2
            )
        except Exception as e:
            logger.exception("Unexpected error in get_portfolio_history")
            return json.dumps(
                {"error": "Internal Error", "message": str(e), "disclaimer": DISCLAIMER}, indent=2
            )

    @server.tool(
        name="rebalance_portfolio",
        description=(
            "Calculate mathematical target-model alignment arithmetic (share quantity differences) "
            "between current user holdings and the chosen portfolio model (e.g. 'AQA_AGGRESSIVE'). "
            "Accepts holdings as a list of dicts (with ticker, quantity, price) or CSV string (max 200 rows, 512 KB). "
            "Note: Uploaded holdings data is processed solely for model alignment calculations. "
            "Output represents mathematical calculations, not trade execution or individualized investment advice."
        ),
    )
    async def rebalance_portfolio(
        portfolio_code: str,
        holdings: list[dict[str, Any]] | str,
        as_of: str | None = None,
    ) -> str:
        """
        Calculate target-model alignment arithmetic for user holdings.

        :param portfolio_code: Target portfolio identifier (e.g., 'AQA_AGGRESSIVE')
        :param holdings: Current holdings as list of objects [{'ticker': 'AAPL', 'quantity': 10}, ...] or CSV string (max 200 rows, 512 KB)
        :param as_of: Optional historical target snapshot date
        """
        try:
            async with get_async_client() as client:
                result = await client.rebalance_portfolio(
                    portfolio_code=portfolio_code,
                    holdings=holdings,
                    as_of=as_of,
                )
                data = result.model_dump()
                data["disclaimer"] = DISCLAIMER
                return json.dumps(data, indent=2, default=str)
        except AuthenticationError as e:
            return json.dumps(
                {
                    "error": "Authentication or subscription required",
                    "message": str(e),
                    "disclaimer": DISCLAIMER,
                },
                indent=2,
            )
        except ValidationError as e:
            return json.dumps(
                {"error": "Invalid Holdings Format", "message": str(e), "disclaimer": DISCLAIMER},
                indent=2,
            )
        except RateLimitError as e:
            return json.dumps(
                {"error": "Rate Limit Exceeded", "message": str(e), "disclaimer": DISCLAIMER},
                indent=2,
            )
        except FinancialPortfoliosAIError as e:
            return json.dumps(
                {
                    "error": "Rebalancing Calculation Error",
                    "message": str(e),
                    "disclaimer": DISCLAIMER,
                },
                indent=2,
            )
        except Exception as e:
            logger.exception("Unexpected error in rebalance_portfolio")
            return json.dumps(
                {"error": "Internal Error", "message": str(e), "disclaimer": DISCLAIMER}, indent=2
            )

    @server.tool(
        name="get_rebalance_template",
        description=(
            "Download the sample CSV template format and guidelines for uploading portfolio holdings "
            "for model alignment calculations (limits: max 200 rows, max 512 KB)."
        ),
    )
    async def get_rebalance_template() -> str:
        """
        Get holdings CSV template and limits.
        """
        try:
            async with get_async_client() as client:
                template_csv = await client.get_rebalance_template()
                return json.dumps(
                    {
                        "template_csv": template_csv,
                        "required_columns": ["ticker", "quantity"],
                        "optional_columns": ["price", "value"],
                        "limits": {
                            "max_rows": 200,
                            "max_upload_size_kb": 512,
                        },
                        "notes": "Cash can be specified with ticker CASH or USD. Headers: ticker, quantity (or shares/units).",
                        "disclaimer": DISCLAIMER,
                    },
                    indent=2,
                )
        except Exception as e:
            logger.exception("Unexpected error in get_rebalance_template")
            return json.dumps(
                {"error": "Failed to get template", "message": str(e), "disclaimer": DISCLAIMER},
                indent=2,
            )

    @server.tool(
        name="list_blog_posts",
        description=(
            "List published quantitative research articles, market commentaries, and investment "
            "insights from Financial Portfolios AI."
        ),
    )
    async def list_blog_posts(
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
    ) -> str:
        """
        List published research posts.

        :param page: Page number (default: 1)
        :param page_size: Items per page (default: 20, max: 100)
        :param search: Optional keyword search filter
        """
        try:
            async with get_async_client() as client:
                posts = await client.list_blog_posts(page=page, page_size=page_size, search=search)
                data = posts.model_dump()
                data["disclaimer"] = DISCLAIMER
                return json.dumps(data, indent=2, default=str)
        except AuthenticationError as e:
            return json.dumps(
                {
                    "error": "Authentication required",
                    "message": str(e),
                    "hint": "Please generate an API token at https://financial-portfolios.ai/settings/api-tokens after logging in with Google.",
                    "disclaimer": DISCLAIMER,
                },
                indent=2,
            )
        except FinancialPortfoliosAIError as e:
            return json.dumps(
                {"error": "Portal API Error", "message": str(e), "disclaimer": DISCLAIMER}, indent=2
            )
        except Exception as e:
            logger.exception("Unexpected error in list_blog_posts")
            return json.dumps(
                {"error": "Internal Error", "message": str(e), "disclaimer": DISCLAIMER}, indent=2
            )

    @server.tool(
        name="get_blog_post",
        description=(
            "Retrieve full content of a published quantitative research article or post "
            "by slug from Financial Portfolios AI."
        ),
    )
    async def get_blog_post(slug: str) -> str:
        """
        Get full blog post content.

        :param slug: Post slug identifier
        """
        try:
            async with get_async_client() as client:
                post = await client.get_blog_post(slug=slug)
                data = post.model_dump()
                data["disclaimer"] = DISCLAIMER
                return json.dumps(data, indent=2, default=str)
        except NotFoundError as e:
            return json.dumps(
                {"error": "Post Not Found", "message": str(e), "disclaimer": DISCLAIMER}, indent=2
            )
        except AuthenticationError as e:
            return json.dumps(
                {
                    "error": "Authentication or active subscription required to read this post",
                    "message": str(e),
                    "hint": "Please generate an API token at https://financial-portfolios.ai/settings/api-tokens after logging in with Google.",
                    "disclaimer": DISCLAIMER,
                },
                indent=2,
            )
        except FinancialPortfoliosAIError as e:
            return json.dumps(
                {"error": "Portal API Error", "message": str(e), "disclaimer": DISCLAIMER}, indent=2
            )
        except Exception as e:
            logger.exception("Unexpected error in get_blog_post")
            return json.dumps(
                {"error": "Internal Error", "message": str(e), "disclaimer": DISCLAIMER}, indent=2
            )

    @server.tool(
        name="get_token_info",
        description=(
            "Retrieve metadata about the currently configured API token, including use count, "
            "rate limits, expiration, and subscription status."
        ),
    )
    async def get_token_info() -> str:
        """
        Get API token metadata.
        """
        try:
            async with get_async_client() as client:
                info = await client.get_api_token_info()
                data = info.model_dump()
                data["disclaimer"] = DISCLAIMER
                return json.dumps(data, indent=2, default=str)
        except AuthenticationError as e:
            return json.dumps(
                {
                    "error": "Invalid or missing API token",
                    "message": str(e),
                    "hint": "Provide a valid personal API token (aqat_v1_...) generated via https://financial-portfolios.ai/settings/api-tokens",
                    "disclaimer": DISCLAIMER,
                },
                indent=2,
            )
        except FinancialPortfoliosAIError as e:
            return json.dumps(
                {"error": "Portal API Error", "message": str(e), "disclaimer": DISCLAIMER}, indent=2
            )
        except Exception as e:
            logger.exception("Unexpected error in get_token_info")
            return json.dumps(
                {"error": "Internal Error", "message": str(e), "disclaimer": DISCLAIMER}, indent=2
            )
