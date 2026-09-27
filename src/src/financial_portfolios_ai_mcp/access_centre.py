"""Access & Connection: an MCP App answering "what am I looking at, and why is it dated?".

The single most repeated confusion this connector produces is the delayed book. A portfolio
the user is not subscribed to comes back about 45 days old, with `effective_n`,
`equity_exposure`, `cash_allocation`, `expected_return` and `expected_volatility` all null -
and a model relaying that in prose either buries it or repeats it every turn. Shown once, as
a badge per portfolio and a list of what is missing, it stops being a surprise.

It also answers the connection question without inviting the failure mode that the
`get_token_info` hint used to cause: a model reading an auth error and asking the user to
paste a token into the chat. Here the state is displayed, and the remedy is "reconnect".
"""

import logging
from typing import Any

from financial_portfolios_ai.exceptions import FinancialPortfoliosAIError
from mcp.server.apps import Apps
from mcp.types import ToolAnnotations

from financial_portfolios_ai_mcp import portal
from financial_portfolios_ai_mcp.app_assets import load_app_html
from financial_portfolios_ai_mcp.auth import get_async_client, resolve_api_token
from financial_portfolios_ai_mcp.config import get_settings
from financial_portfolios_ai_mcp.disclosure import DISCLAIMER

logger = logging.getLogger(__name__)

ACCESS_URI = "ui://financial-portfolios-ai/access-centre.html"
ACCESS_HTML = "access_centre.html"

# Kept in step with tools.get_token_info, which branches on the same prefix.
API_TOKEN_PREFIX = "aqat_v1_"

# What the portal sends as null when a book is delayed. Named here so the page can list them
# rather than leaving the user to notice the blanks.
DELAYED_HIDES = [
    "Effective N (concentration)",
    "Equity exposure and cash",
    "Expected return per holding",
    "Expected volatility per holding",
]


def connection_state() -> dict[str, Any]:
    """How this client is authenticated, without calling the portal.

    `/api/tokens/me` understands personal API tokens only, so asking it about an OAuth
    connection returns a 403 that reads like a fault. The distinction is visible locally.
    """
    token = resolve_api_token()
    if not token:
        return {
            "connected": False,
            "authentication": "none",
            "detail": "Not signed in. Reconnect the connector and sign in when prompted.",
        }
    if not token.startswith(API_TOKEN_PREFIX):
        return {
            "connected": True,
            "authentication": "oauth",
            "detail": "Signed in with OAuth. There is no API token to manage for this connection.",
        }
    return {
        "connected": True,
        "authentication": "api_token",
        "detail": "Signed in with a personal API token from the portal settings.",
    }


def register_access_centre(apps: Apps) -> None:
    """Register the Access & Connection app on an existing Apps extension."""

    @apps.tool(
        resource_uri=ACCESS_URI,
        name="open_access_centre",
        title="Access & Connection",
        description=(
            "Open the Access & Connection panel: which model portfolios this account can see, "
            "which are live versus delayed by about 45 days, exactly what the delayed book "
            "leaves out, and how this client is signed in. Use it when the user asks what they "
            "have access to, why a portfolio is dated or missing figures, what their "
            "subscription covers, or whether the connector is connected. Informational only."
        ),
        annotations=ToolAnnotations(
            title="Access & Connection",
            read_only_hint=True,
            open_world_hint=True,
        ),
    )
    async def open_access_centre() -> dict[str, Any]:
        settings = get_settings()
        base = settings.portal_base_url.rstrip("/")
        links = {
            "portal": base,
            "pricing": f"{base}/#pricing",
            "api_tokens": f"{base}/settings/api-tokens",
        }

        async def fetch_list() -> dict[str, Any]:
            async with get_async_client() as client:
                return (await client.list_portfolios()).model_dump()

        try:
            listing = await portal.read("list_portfolios", settings.cache_ttl_portfolios, fetch_list)
        except FinancialPortfoliosAIError as e:
            # A failed listing is itself the answer to "am I connected?", so the panel still
            # opens and says so rather than returning a bare error the model has to narrate.
            return {
                "connection": {**connection_state(), "connected": False, "detail": str(e)},
                "portfolios": [],
                "links": links,
                "delayed_hides": DELAYED_HIDES,
                "disclaimer": DISCLAIMER,
            }
        except Exception as e:
            logger.exception("Unexpected error opening the Access & Connection panel")
            return {"error": "Internal Error", "message": str(e), "disclaimer": DISCLAIMER}

        portfolios = listing.get("portfolios") or []
        subscribed = sum(1 for p in portfolios if p.get("access") == "subscribed")
        return {
            "connection": connection_state(),
            # Named, so the model reads zero subscriptions as the free tier rather than a fault.
            "plan": "subscriber" if subscribed else "free_delayed",
            "plan_detail": (
                "Live book for the subscribed portfolios; the delayed public book for the rest."
                if subscribed
                else "Free access: every portfolio's public book, delayed about 45 days. This is "
                "normal, not an account problem. A subscription adds the live book."
            ),
            "portfolios": portfolios,
            "subscribed": subscribed,
            "delayed": sum(1 for p in portfolios if p.get("delayed")),
            "links": links,
            "delayed_hides": DELAYED_HIDES,
            "disclaimer": DISCLAIMER,
        }

    apps.add_html_resource(
        ACCESS_URI,
        load_app_html(ACCESS_HTML),
        name="access-centre",
        title="Access & Connection",
        description="What this account can see, what the delayed book omits, and how it is signed in.",
        prefers_border=True,
    )
