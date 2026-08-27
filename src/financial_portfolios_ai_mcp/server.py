"""MCPServer initialization and setup for Financial Portfolios AI."""

import logging

from mcp.server import MCPServer

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
1. Portfolio Discovery: Use `list_portfolios` to inspect available model strategies (e.g. AQA_AGGRESSIVE, AQA_BALANCED, AQA_DEFENSIVE).
2. Allocation Details: Use `get_portfolio_allocation` to inspect target weights, individual tickers, equity/cash ratio, and risk indicators.
3. Model Alignment Arithmetic: Use `rebalance_portfolio` to compute calculated share quantity differences between user holdings and target model allocation (max 200 rows, 512 KB).
4. Research & Analysis: Use `list_blog_posts` and `get_blog_post` to access quantitative commentaries and macro analysis.

Authentication:
Operations require an active personal API token (format: aqat_v1_...) generated via https://financial-portfolios.ai/settings/api-tokens.
The token is automatically passed via HTTP headers (X-API-Key or Authorization) for remote connectors, or configured via FINANCIAL_PORTFOLIOS_API_TOKEN for local stdio.
"""


def create_mcp_server() -> MCPServer:
    """Create and configure a new MCPServer instance."""
    server = MCPServer(
        name="financial-portfolios-ai",
        title="Financial Portfolios AI",
        description="Official Model Context Protocol (MCP) server for Financial Portfolios AI.",
        instructions=SERVER_INSTRUCTIONS.strip(),
        website_url="https://financial-portfolios.ai",
        version="1.0.0",
    )

    # Register capabilities
    register_tools(server)
    register_resources(server)
    register_prompts(server)

    return server


# Default singleton instance
mcp_server = create_mcp_server()
