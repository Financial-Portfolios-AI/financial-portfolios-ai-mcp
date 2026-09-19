"""MCPServer initialization and setup for Financial Portfolios AI."""

import logging

from mcp.server import MCPServer

from financial_portfolios_ai_mcp._version import __version__
from financial_portfolios_ai_mcp.apps import build_apps
from financial_portfolios_ai_mcp.config import get_settings
from financial_portfolios_ai_mcp.disclosure import SERVICE_DESCRIPTION
from financial_portfolios_ai_mcp.icons import icon_specs
from financial_portfolios_ai_mcp.prompts import register_prompts
from financial_portfolios_ai_mcp.resources import register_resources
from financial_portfolios_ai_mcp.tools import register_tools

logger = logging.getLogger(__name__)

SERVER_INSTRUCTIONS = """
Financial Portfolios AI MCP Server enables AI assistants to interface with
quantitative portfolio management tools, target asset allocation snapshots, model alignment arithmetic,
and institutional-grade market research.

IMPORTANT REGULATORY & USAGE NOTICE:
All outputs, tools, allocations, and rebalancing calculations are provided strictly for
INFORMATIONAL AND EDUCATIONAL PURPOSES ONLY under the publisher exclusion.
They DO NOT constitute individualized investment, financial, legal, or tax advice, and DO NOT represent
a solicitation, recommendation, or endorsement to buy or sell any security.
No assessment of suitability, risk tolerance, or financial situation has been conducted for any individual user.
Model alignment calculations represent mathematical target-model arithmetic.

Key Capabilities:
1. Portfolio Discovery: Use `list_portfolios` to inspect every active model strategy (e.g. AQA_AGGRESSIVE, AQA_BALANCED, AQA_DEFENSIVE). Each entry is marked `access`: `subscribed` or `public_delayed`.
2. Allocation Details: Use `get_portfolio_allocation` to inspect target weights, individual tickers, equity/cash ratio, and risk indicators. When a user asks to see "my portfolio", "my holdings", "my positions", or "what's in my portfolio", that means the holdings of their subscribed model portfolio(s): call `list_portfolios` if no code is given, then `get_portfolio_allocation` for each.
3. Model Alignment Arithmetic: Use `rebalance_portfolio` to compute calculated share quantity differences between user holdings and target model allocation (max 200 rows, 512 KB). This one requires an active subscription for the target portfolio.
4. Research & Analysis: Use `list_blog_posts` and `get_blog_post` to access quantitative commentaries and macro analysis.

Access Levels:
Portfolio reads come in two flavours and the response says which one was served via `access`,
`delayed`, `as_of` and `lag_days`:
- `subscribed`: the latest book, with expected return, expected volatility, equity exposure,
  cash allocation and effective N.
- `public_delayed`: the public book for an active product the user is not subscribed to. Holdings
  are no more recent than roughly 45 days ago, positions carry only ticker/weight/sector, and the
  premium metrics are null.
When `delayed` is true, tell the user the book is delayed and give its effective date rather than
presenting it as the current allocation. A portfolio code that is not an active public product
returns "not found".

Credentials:
Never ask the user to share, paste or type an API token, password or other credential in the
conversation. If a tool reports an authentication problem, tell the user to reconnect the connector
and sign in. To check whether the connection works, call `list_portfolios`: `get_token_info`
describes personal API tokens only, and an OAuth-connected client has none.

What This Connector Does Not Provide:
There is no price, return or performance data behind any tool. Never offer, compute, estimate or
chart performance, returns, gains, drawdowns, best or worst contributors, or benchmark comparisons
for these model portfolios - not even approximately, and not by pricing the holdings with data from
another source. Doing so would present hypothetical model performance, which this service does not
publish. If the user asks for performance, say it is not available through this connector.

Using Other Connected Tools:
You may combine these holdings with other tools the user has connected - market data, company
profiles, filings, news - and with your own knowledge, to give context about the companies in a
model portfolio: what a company does, its sector, recent news, industry background. Say where each
outside fact came from, and keep it separate from this connector's data.
The boundary is arithmetic, not sources. Context about holdings is fine; turning any outside data
into a return, gain, loss, performance figure, drawdown or benchmark comparison for these model
portfolios is not, however it is obtained. "Which of my holdings had the best month" is a
performance question and stays unavailable no matter which tool could price it. If the user wants
that framing, offer what the model itself did instead: which weights it raised and cut, what it
added and removed, and how concentrated it is.
Tickers here carry no company name, so resolve a ticker with a connected tool where possible rather
than assuming which company it is - especially outside large US listings.

Authentication:
Remote connectors (Claude web/desktop) sign in with OAuth 2.1: a tokenless request is answered
with a 401 and WWW-Authenticate: Bearer resource_metadata=... (RFC 9728), and the client completes
the flow against the portal. There is no API key for the user to paste.
Command-line and local stdio clients instead pass a personal API token (format: aqat_v1_...),
generated at https://financial-portfolios.ai/settings/api-tokens, as an X-API-Key or
Authorization header, or via FINANCIAL_PORTFOLIOS_API_TOKEN for stdio.
"""


def create_mcp_server() -> MCPServer:
    """Create and configure a new MCPServer instance."""
    settings = get_settings()
    kwargs: dict = {
        "name": "financial-portfolios-ai",
        "title": "Financial Portfolios AI",
        # Human-facing: this is what a provider directory prints under the listing, so it
        # describes the service and carries the disclosure. `instructions` below is the
        # model-facing text and is never shown to someone browsing a directory.
        "description": SERVICE_DESCRIPTION,
        "instructions": SERVER_INSTRUCTIONS.strip(),
        # The portal site for THIS deployment - a dev server must not advertise the prod
        # site. portal_base_url (not public_origin) because this is the website, which
        # stays correct even when the MCP service answers on a hostname of its own.
        "website_url": settings.portal_base_url.rstrip("/"),
        "version": __version__,
        # MCP Apps: interactive UIs a supporting host renders inline. Hosts without Apps
        # support still get each tool's JSON result, so nothing is lost by not rendering.
        # One extension carries every app; each app owns a `ui://` resource and its tools.
        "extensions": [build_apps()],
    }

    # Brand icons surfaced by LLM providers in connector pickers and tool-call UI.
    # `Implementation.icons` landed in MCP 2025-11-25; on an older SDK (no `Icon`
    # type, or an MCPServer that rejects the kwarg) start without icons rather
    # than failing outright.
    try:
        from mcp.types import Icon

        icons = [
            Icon(src=spec["src"], mime_type=spec["mimeType"], sizes=spec["sizes"])
            for spec in icon_specs(settings.public_origin())
        ]
        server = MCPServer(icons=icons, **kwargs) if icons else MCPServer(**kwargs)
    except (ImportError, TypeError):
        logger.warning("Installed mcp SDK does not support Implementation.icons; omitting icons")
        server = MCPServer(**kwargs)

    # Register capabilities
    register_tools(server)
    register_resources(server)
    register_prompts(server)

    return server


# Default singleton instance
mcp_server = create_mcp_server()
