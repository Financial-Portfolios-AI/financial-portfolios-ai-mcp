"""Tool definitions for Financial Portfolios AI MCP Server."""

import logging
from typing import Any

from financial_portfolios_ai.exceptions import (
    AuthenticationError,
    FinancialPortfoliosAIError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from mcp.types import ToolAnnotations

from financial_portfolios_ai_mcp import portal
from financial_portfolios_ai_mcp.auth import get_async_client, resolve_api_token
from financial_portfolios_ai_mcp.config import get_settings
from financial_portfolios_ai_mcp.disclosure import DISCLAIMER

logger = logging.getLogger(__name__)

# Personal API tokens carry this prefix; any other bearer credential is an OAuth access token.
API_TOKEN_PREFIX = "aqat_v1_"


def access_error(e: AuthenticationError, portfolio_code: str = "") -> dict[str, Any]:
    """Tell a missing subscription apart from a failed sign-in.

    The portal answers both with 401/403, and "Authentication failed" read as a broken
    connection to users on free access - who are signed in fine and simply have no
    subscription to this portfolio.
    """
    portal_url = get_settings().portal_base_url.rstrip("/")
    if getattr(e, "status_code", None) == 403 or "subscription" in str(e).lower():
        return {
            "error": "Subscription required",
            "portfolio": portfolio_code,
            "message": (
                "This needs a subscription to the portfolio. The connection is signed in and "
                "working; free access covers every portfolio's public book, delayed about 45 days."
            ),
            "pricing": f"{portal_url}/#pricing",
            "disclaimer": DISCLAIMER,
        }
    return {
        "error": "Not signed in",
        "portfolio": portfolio_code,
        "message": str(e),
        "hint": (
            "Reconnect the connector to sign in again. Command-line clients using a personal "
            f"API token can check or replace it at {portal_url}/settings/api-tokens."
        ),
        "disclaimer": DISCLAIMER,
    }


def register_tools(server: Any) -> None:
    """Register all Financial Portfolios AI tools with the MCP server."""

    @server.tool(
        name="list_portfolios",
        title="List model portfolios",
        description=(
            "List every active model portfolio on Financial Portfolios AI (e.g. AQA_AGGRESSIVE, "
            "AQA_BALANCED, AQA_DEFENSIVE). Each entry carries `access`: `subscribed` means the user's "
            "subscription covers it and the live book is available; `public_delayed` means only the "
            "public book is available, with holdings delayed by about 45 days. Call this first when the "
            "user refers to 'my portfolios', 'my holdings', or 'my positions' without naming a specific "
            "portfolio, then use `get_portfolio_allocation` to show the holdings of each - preferring "
            "the `subscribed` ones when the user says 'my'. If the user asks what they can do here, "
            "offer the journeys in the `start_here` prompt rather than a list of tools."
        ),
        annotations=ToolAnnotations(
            title="List model portfolios",
            read_only_hint=True,
            open_world_hint=True,
        ),
    )
    async def list_portfolios() -> dict[str, Any]:
        """
        List every active quantitative investment portfolio.

        Includes products the user is not subscribed to; those are marked
        `access: "public_delayed"` and expose only the delayed book.

        :return: JSON formatted list of portfolios with access level, risk level, theme, and description.
        """
        try:
            async def fetch() -> dict[str, Any]:
                async with get_async_client() as client:
                    return (await client.list_portfolios()).model_dump()

            data = await portal.read("list_portfolios", get_settings().cache_ttl_portfolios, fetch)
            return {**data, "disclaimer": DISCLAIMER}
        except AuthenticationError as e:
            return {
                "error": "Authentication or Subscription required",
                "message": str(e),
                "hint": "Please generate an API token at https://financial-portfolios.ai/settings/api-tokens after logging in with Google.",
                "disclaimer": DISCLAIMER,
            }
        except RateLimitError as e:
            return {"error": "Rate Limit Exceeded", "message": str(e), "disclaimer": DISCLAIMER}
        except FinancialPortfoliosAIError as e:
            return {"error": "Portal API Error", "message": str(e), "disclaimer": DISCLAIMER}
        except Exception as e:
            logger.exception("Unexpected error in list_portfolios")
            return {"error": "Internal Error", "message": str(e), "disclaimer": DISCLAIMER}

    @server.tool(
        name="get_portfolio_allocation",
        title="Portfolio holdings and target allocation",
        description=(
            "Show the current holdings and positions of a model portfolio: the stocks/tickers it "
            "holds and their target weights. USE THIS whenever a user asks to see 'my portfolio', "
            "'my holdings', 'my positions', 'what's in my portfolio', 'what stocks do I hold', or the "
            "current/latest allocation for a portfolio (e.g. 'AQA_AGGRESSIVE', 'AQA_BALANCED', "
            "'AQA_DEFENSIVE'). If the user does not name a portfolio, call `list_portfolios` first to "
            "find the portfolio codes, then call this for each. For a subscribed portfolio this returns "
            "the LATEST book: target weights, tickers, sectors, expected return, volatility, equity "
            "exposure, cash allocation and effective N. For a portfolio the user is not subscribed to it "
            "returns the PUBLIC DELAYED book instead - holdings as of roughly 45 days ago, with only "
            "ticker, weight and sector per position, and null for expected return, expected volatility, "
            "equity exposure, cash allocation and effective N. The response's `access`, `delayed`, "
            "`as_of` and `lag_days` fields say which book was served; state the effective date to the "
            "user whenever `delayed` is true rather than presenting a delayed book as current. Can also "
            "fetch a historical snapshot via `as_of`. Output represents mathematical target-model "
            "allocation arithmetic, not personalized investment advice."
            " To add context, pair the holdings with a connected market-data or news tool (company, news, filings) and attribute what it says; to compare against the user's own account, read positions from a connected brokerage tool."
        ),
        annotations=ToolAnnotations(
            title="Portfolio holdings and target allocation",
            read_only_hint=True,
            open_world_hint=True,
        ),
    )
    async def get_portfolio_allocation(
        portfolio_code: str,
        as_of: str | None = None,
    ) -> dict[str, Any]:
        """
        Get portfolio target allocation and risk metrics.

        Subscribers receive the latest book; everyone else receives the public book
        delayed by `lag_days` (~45 days), with premium signal fields stripped. An
        unknown code - or one that is not an active public product - is a 404.

        :param portfolio_code: Portfolio identifier (e.g., 'AQA_AGGRESSIVE', 'AQA_BALANCED')
        :param as_of: Optional historical snapshot date (YYYY-MM-DD or ISO 8601 format)
        """
        try:
            async def fetch() -> dict[str, Any]:
                async with get_async_client() as client:
                    snapshot = await client.get_portfolio(portfolio_code=portfolio_code, as_of=as_of)
                    return snapshot.model_dump()

            data = await portal.read(
                "get_portfolio_allocation",
                get_settings().cache_ttl_allocation,
                fetch,
                portfolio_code=portfolio_code.upper(),
                as_of=as_of,
            )
            return {**data, "disclaimer": DISCLAIMER}
        except AuthenticationError as e:
            return access_error(e, portfolio_code)
        except NotFoundError as e:
            return {
                "error": "Portfolio Not Found",
                "portfolio": portfolio_code,
                "message": str(e),
                "hint": "No active product with this code is available to you. Call `list_portfolios` for the codes that are.",
                "disclaimer": DISCLAIMER,
            }
        except RateLimitError as e:
            return {"error": "Rate Limit Exceeded", "message": str(e), "disclaimer": DISCLAIMER}
        except FinancialPortfoliosAIError as e:
            return {"error": "Portal API Error", "message": str(e), "disclaimer": DISCLAIMER}
        except Exception as e:
            logger.exception("Unexpected error in get_portfolio_allocation")
            return {"error": "Internal Error", "message": str(e), "disclaimer": DISCLAIMER}

    @server.tool(
        name="get_portfolio_history",
        title="Allocation history",
        description=(
            "Retrieve historical allocation snapshots for up to 365 days for a specific portfolio. "
            "For what changed at a rebalance, prefer `get_portfolio_changes`, which does the diff. "
            "Useful for tracking historical model changes and target allocation evolution. For a "
            "subscribed portfolio this returns the full history; otherwise it returns only the public "
            "delayed entries - nothing more recent than about 45 days ago - with equity exposure, cash "
            "allocation and effective N null on those entries. The response's `access`, `delayed` and "
            "`lag_days` fields say which history was served."
        ),
        annotations=ToolAnnotations(
            title="Allocation history",
            read_only_hint=True,
            open_world_hint=True,
        ),
    )
    async def get_portfolio_history(
        portfolio_code: str,
        days: int = 30,
    ) -> dict[str, Any]:
        """
        Get portfolio allocation history.

        Subscribers receive the full history; everyone else receives only entries at or
        before `today - lag_days` (~45 days). An unknown code - or one that is not an
        active public product - is a 404.

        :param portfolio_code: Portfolio identifier (e.g., 'AQA_AGGRESSIVE')
        :param days: Number of calendar days of history (1-365, default: 30)
        """
        try:
            async def fetch() -> dict[str, Any]:
                async with get_async_client() as client:
                    history = await client.get_portfolio_history(
                        portfolio_code=portfolio_code, days=days
                    )
                    return history.model_dump()

            data = await portal.read(
                "get_portfolio_history",
                get_settings().cache_ttl_history,
                fetch,
                portfolio_code=portfolio_code.upper(),
                days=days,
            )
            return {**data, "disclaimer": DISCLAIMER}
        except AuthenticationError as e:
            return access_error(e)
        except NotFoundError as e:
            return {"error": "Portfolio Not Found", "message": str(e), "disclaimer": DISCLAIMER}
        except RateLimitError as e:
            return {"error": "Rate Limit Exceeded", "message": str(e), "disclaimer": DISCLAIMER}
        except FinancialPortfoliosAIError as e:
            return {"error": "Portal API Error", "message": str(e), "disclaimer": DISCLAIMER}
        except Exception as e:
            logger.exception("Unexpected error in get_portfolio_history")
            return {"error": "Internal Error", "message": str(e), "disclaimer": DISCLAIMER}

    @server.tool(
        name="rebalance_portfolio",
        title="Model alignment arithmetic",
        description=(
            "Calculate mathematical target-model alignment arithmetic (share quantity differences) "
            "between current user holdings and the chosen portfolio model (e.g. 'AQA_AGGRESSIVE'). "
            "Accepts holdings as a list of dicts (with ticker, quantity, price) or CSV string (max 200 rows, 512 KB). "
            "Requires an active subscription covering the target portfolio: unlike the allocation and "
            "history tools, this has no public delayed mode and returns a 403 when the user is not "
            "entitled. "
            "Note: Uploaded holdings data is processed solely for model alignment calculations. "
            "Output represents mathematical calculations, not trade execution or individualized investment advice. "
            "Read the holdings from a connected brokerage or aggregator tool (e.g. SnapTrade, IBKR) "
            "rather than asking the user to type them, and prefer `open_rebalance_studio` so they can "
            "check them first. Never run this unattended to prepare orders."
        ),
        annotations=ToolAnnotations(
            title="Model alignment arithmetic",
            read_only_hint=True,
            open_world_hint=True,
        ),
    )
    async def rebalance_portfolio(
        portfolio_code: str,
        holdings: list[dict[str, Any]] | str,
        as_of: str | None = None,
    ) -> dict[str, Any]:
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
                return data
        except AuthenticationError as e:
            return access_error(e, portfolio_code)
        except ValidationError as e:
            return {"error": "Invalid Holdings Format", "message": str(e), "disclaimer": DISCLAIMER}
        except RateLimitError as e:
            return {"error": "Rate Limit Exceeded", "message": str(e), "disclaimer": DISCLAIMER}
        except FinancialPortfoliosAIError as e:
            return {
                "error": "Rebalancing Calculation Error",
                "message": str(e),
                "disclaimer": DISCLAIMER,
            }
        except Exception as e:
            logger.exception("Unexpected error in rebalance_portfolio")
            return {"error": "Internal Error", "message": str(e), "disclaimer": DISCLAIMER}

    @server.tool(
        name="get_rebalance_template",
        title="Holdings CSV template",
        description=(
            "Download the sample CSV template format and guidelines for uploading portfolio holdings "
            "for model alignment calculations (limits: max 200 rows, max 512 KB)."
        ),
        annotations=ToolAnnotations(
            title="Holdings CSV template",
            read_only_hint=True,
            open_world_hint=True,
        ),
    )
    async def get_rebalance_template() -> dict[str, Any]:
        """
        Get holdings CSV template and limits.
        """
        try:
            async with get_async_client() as client:
                template_csv = await client.get_rebalance_template()
                return {
                    "template_csv": template_csv,
                    "required_columns": ["ticker", "quantity"],
                    "optional_columns": ["price", "value"],
                    "limits": {
                        "max_rows": 200,
                        "max_upload_size_kb": 512,
                    },
                    "notes": "Cash can be specified with ticker CASH or USD. Headers: ticker, quantity (or shares/units).",
                    "disclaimer": DISCLAIMER,
                }
        except Exception as e:
            logger.exception("Unexpected error in get_rebalance_template")
            return {"error": "Failed to get template", "message": str(e), "disclaimer": DISCLAIMER}

    @server.tool(
        name="list_blog_posts",
        title="Search research and market commentary",
        description=(
            "List published quantitative research articles, market commentaries, and investment "
            "insights from Financial Portfolios AI. This is the publisher's own research; for third-party "
            "news on a holding, use a connected news or market-data tool and attribute it."
        ),
        annotations=ToolAnnotations(
            title="Search research and market commentary",
            read_only_hint=True,
            open_world_hint=True,
        ),
    )
    async def list_blog_posts(
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
    ) -> dict[str, Any]:
        """
        List published research posts.

        :param page: Page number (default: 1)
        :param page_size: Items per page (default: 20, max: 100)
        :param search: Optional keyword search filter
        """
        try:
            async def fetch() -> dict[str, Any]:
                async with get_async_client() as client:
                    posts = await client.list_blog_posts(page=page, page_size=page_size, search=search)
                    return posts.model_dump()

            data = await portal.read(
                "list_blog_posts",
                get_settings().cache_ttl_research,
                fetch,
                page=page,
                page_size=page_size,
                search=search,
            )
            return {**data, "disclaimer": DISCLAIMER}
        except AuthenticationError as e:
            return {
                "error": "Authentication required",
                "message": str(e),
                "hint": "Please generate an API token at https://financial-portfolios.ai/settings/api-tokens after logging in with Google.",
                "disclaimer": DISCLAIMER,
            }
        except FinancialPortfoliosAIError as e:
            return {"error": "Portal API Error", "message": str(e), "disclaimer": DISCLAIMER}
        except Exception as e:
            logger.exception("Unexpected error in list_blog_posts")
            return {"error": "Internal Error", "message": str(e), "disclaimer": DISCLAIMER}

    @server.tool(
        name="get_blog_post",
        title="Read a research article",
        description=(
            "Retrieve full content of a published quantitative research article or post "
            "by slug from Financial Portfolios AI."
        ),
        annotations=ToolAnnotations(
            title="Read a research article",
            read_only_hint=True,
            open_world_hint=True,
        ),
    )
    async def get_blog_post(slug: str) -> dict[str, Any]:
        """
        Get full blog post content.

        :param slug: Post slug identifier
        """
        try:
            async def fetch() -> dict[str, Any]:
                async with get_async_client() as client:
                    return (await client.get_blog_post(slug=slug)).model_dump()

            data = await portal.read(
                "get_blog_post", get_settings().cache_ttl_research, fetch, slug=slug
            )
            return {**data, "disclaimer": DISCLAIMER}
        except NotFoundError as e:
            return {"error": "Post Not Found", "message": str(e), "disclaimer": DISCLAIMER}
        except AuthenticationError as e:
            return {
                "error": "Authentication or active subscription required to read this post",
                "message": str(e),
                "hint": "Please generate an API token at https://financial-portfolios.ai/settings/api-tokens after logging in with Google.",
                "disclaimer": DISCLAIMER,
            }
        except FinancialPortfoliosAIError as e:
            return {"error": "Portal API Error", "message": str(e), "disclaimer": DISCLAIMER}
        except Exception as e:
            logger.exception("Unexpected error in get_blog_post")
            return {"error": "Internal Error", "message": str(e), "disclaimer": DISCLAIMER}

    @server.tool(
        name="get_token_info",
        title="API token details",
        description=(
            "Retrieve metadata about the personal API token in use: its name, prefix, creation "
            "and last-used times, and whether it is active. Only meaningful for clients configured "
            "with an API token (command-line and local stdio). A connector signed in with OAuth "
            "has no API token, and this tool says so - that is normal, not an error. Do NOT use "
            "this to check whether the connection works: call `list_portfolios` for that. It does "
            "not report subscriptions either; `list_portfolios` shows those in its `access` field."
        ),
        annotations=ToolAnnotations(
            title="API token details",
            read_only_hint=True,
            open_world_hint=True,
        ),
    )
    async def get_token_info() -> dict[str, Any]:
        """
        Get API token metadata.

        `/api/tokens/me` only understands personal API tokens, so an OAuth-connected
        client gets a 403 that reads like a broken connection - and a model reading it
        will ask the user to paste a token into the chat. Answer those cases here
        instead of calling the portal.
        """
        token = resolve_api_token()
        if not token:
            return {
                "connected": False,
                "authentication": "none",
                "message": (
                    "This connection is not signed in. Ask the user to reconnect the "
                    "connector and sign in when prompted. Never ask the user to paste a "
                    "token or password into the conversation."
                ),
                "disclaimer": DISCLAIMER,
            }
        if not token.startswith(API_TOKEN_PREFIX):
            return {
                "connected": True,
                "authentication": "oauth",
                "message": (
                    "This connection uses OAuth sign-in, so there is no personal API token "
                    "to describe. That is expected and does not indicate a problem. To check "
                    "what the account can access, call list_portfolios."
                ),
                "disclaimer": DISCLAIMER,
            }
        try:
            async with get_async_client() as client:
                info = await client.get_api_token_info()
                data = info.model_dump()
                data["disclaimer"] = DISCLAIMER
                return data
        except AuthenticationError as e:
            return {
                "error": "API token rejected",
                "message": str(e),
                "hint": (
                    "The personal API token configured in this client was rejected. The user "
                    "can generate a new one under Settings > API Tokens on the portal and "
                    "update their client configuration themselves. Never ask the user to "
                    "paste a token into the conversation."
                ),
                "disclaimer": DISCLAIMER,
            }
        except FinancialPortfoliosAIError as e:
            return {"error": "Portal API Error", "message": str(e), "disclaimer": DISCLAIMER}
        except Exception as e:
            logger.exception("Unexpected error in get_token_info")
            return {"error": "Internal Error", "message": str(e), "disclaimer": DISCLAIMER}
