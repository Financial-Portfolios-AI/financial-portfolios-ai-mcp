"""
Financial Portfolios AI Model Context Protocol (MCP) Server.

Enables Claude Connectors, Claude Desktop, and Claude Code to securely interact
with quantitative portfolios, target asset allocations, rebalancing engine,
and market research from Financial Portfolios AI (https://financial-portfolios.ai).
"""

from financial_portfolios_ai_mcp._version import __version__
from financial_portfolios_ai_mcp.config import Settings, get_settings
from financial_portfolios_ai_mcp.server import create_mcp_server, mcp_server

__all__ = [
    "Settings",
    "__version__",
    "create_mcp_server",
    "get_settings",
    "mcp_server",
]
