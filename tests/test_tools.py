"""Unit tests for Financial Portfolios AI MCP tools."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from financial_portfolios_ai.exceptions import (
    AuthenticationError,
    NotFoundError,
)

from financial_portfolios_ai_mcp.server import mcp_server


def _extract_text(tool_result) -> str:
    """Helper to extract text content from CallToolResult."""
    if hasattr(tool_result, "content") and tool_result.content:
        return tool_result.content[0].text
    if isinstance(tool_result, list) and tool_result:
        return getattr(tool_result[0], "text", str(tool_result[0]))
    return str(tool_result)


@pytest.mark.asyncio
async def test_list_portfolios_tool(mock_portfolio_list):
    """Test list_portfolios tool execution."""
    with patch("financial_portfolios_ai_mcp.tools.get_async_client") as mock_client_factory:
        mock_client = AsyncMock()
        mock_client.list_portfolios.return_value = mock_portfolio_list
        mock_client.__aenter__.return_value = mock_client
        mock_client_factory.return_value = mock_client

        result_raw = await mcp_server.call_tool("list_portfolios", {})
        data = json.loads(_extract_text(result_raw))
        assert data["total"] == 2
        assert data["portfolios"][0]["code"] == "AQA_AGGRESSIVE"
        assert "disclaimer" in data


@pytest.mark.asyncio
async def test_get_portfolio_allocation_tool(mock_portfolio_snapshot):
    """Test get_portfolio_allocation tool execution."""
    with patch("financial_portfolios_ai_mcp.tools.get_async_client") as mock_client_factory:
        mock_client = AsyncMock()
        mock_client.get_portfolio.return_value = mock_portfolio_snapshot
        mock_client.__aenter__.return_value = mock_client
        mock_client_factory.return_value = mock_client

        result_raw = await mcp_server.call_tool(
            "get_portfolio_allocation",
            {"portfolio_code": "AQA_AGGRESSIVE"},
        )
        data = json.loads(_extract_text(result_raw))
        assert data["portfolio_code"] == "AQA_AGGRESSIVE"
        assert len(data["positions"]) == 2
        assert data["equity_exposure"] == 0.92
        assert "disclaimer" in data


@pytest.mark.asyncio
async def test_get_portfolio_history_tool(mock_portfolio_history):
    """Test get_portfolio_history tool execution."""
    with patch("financial_portfolios_ai_mcp.tools.get_async_client") as mock_client_factory:
        mock_client = AsyncMock()
        mock_client.get_portfolio_history.return_value = mock_portfolio_history
        mock_client.__aenter__.return_value = mock_client
        mock_client_factory.return_value = mock_client

        result_raw = await mcp_server.call_tool(
            "get_portfolio_history",
            {"portfolio_code": "AQA_AGGRESSIVE", "days": 14},
        )
        data = json.loads(_extract_text(result_raw))
        assert data["portfolio_code"] == "AQA_AGGRESSIVE"
        assert "disclaimer" in data
        mock_client.get_portfolio_history.assert_awaited_once_with(
            portfolio_code="AQA_AGGRESSIVE", days=14
        )


@pytest.mark.asyncio
async def test_rebalance_portfolio_tool(mock_rebalance_result):
    """Test rebalance_portfolio tool execution."""
    with patch("financial_portfolios_ai_mcp.tools.get_async_client") as mock_client_factory:
        mock_client = AsyncMock()
        mock_client.rebalance_portfolio.return_value = mock_rebalance_result
        mock_client.__aenter__.return_value = mock_client
        mock_client_factory.return_value = mock_client

        holdings = [{"ticker": "AAPL", "quantity": 10}]
        result_raw = await mcp_server.call_tool(
            "rebalance_portfolio",
            {"portfolio_code": "AQA_AGGRESSIVE", "holdings": holdings},
        )
        data = json.loads(_extract_text(result_raw))
        assert data["portfolio_code"] == "AQA_AGGRESSIVE"
        assert data["total_orders"] == 2
        assert data["orders"][0]["action"] == "BUY"
        assert "disclaimer" in data


@pytest.mark.asyncio
async def test_get_rebalance_template_tool():
    """Test get_rebalance_template tool execution."""
    with patch("financial_portfolios_ai_mcp.tools.get_async_client") as mock_client_factory:
        mock_client = AsyncMock()
        mock_client.get_rebalance_template.return_value = "ticker,quantity,price,value\nAAPL,10,,\n"
        mock_client.__aenter__.return_value = mock_client
        mock_client_factory.return_value = mock_client

        result_raw = await mcp_server.call_tool("get_rebalance_template", {})
        data = json.loads(_extract_text(result_raw))
        assert "ticker,quantity" in data["template_csv"]
        assert "required_columns" in data
        assert "disclaimer" in data


@pytest.mark.asyncio
async def test_list_blog_posts_tool(mock_blog_posts):
    """Test list_blog_posts tool execution."""
    with patch("financial_portfolios_ai_mcp.tools.get_async_client") as mock_client_factory:
        mock_client = AsyncMock()
        mock_client.list_blog_posts.return_value = mock_blog_posts
        mock_client.__aenter__.return_value = mock_client
        mock_client_factory.return_value = mock_client

        result_raw = await mcp_server.call_tool(
            "list_blog_posts",
            {"page": 1, "page_size": 20, "search": "Outlook"},
        )
        data = json.loads(_extract_text(result_raw))
        assert data["total"] == 1
        assert data["items"][0]["slug"] == "q3-2026-quant-outlook"
        assert "disclaimer" in data


@pytest.mark.asyncio
async def test_get_blog_post_tool(mock_single_blog_post):
    """Test get_blog_post tool execution."""
    with patch("financial_portfolios_ai_mcp.tools.get_async_client") as mock_client_factory:
        mock_client = AsyncMock()
        mock_client.get_blog_post.return_value = mock_single_blog_post
        mock_client.__aenter__.return_value = mock_client
        mock_client_factory.return_value = mock_client

        result_raw = await mcp_server.call_tool(
            "get_blog_post",
            {"slug": "q3-2026-quant-outlook"},
        )
        data = json.loads(_extract_text(result_raw))
        assert data["title"] == "Q3 2026 Quantitative Outlook"
        assert "disclaimer" in data


@pytest.mark.asyncio
async def test_get_token_info_tool(mock_token_info):
    """Test get_token_info tool execution."""
    with patch("financial_portfolios_ai_mcp.tools.get_async_client") as mock_client_factory:
        mock_client = AsyncMock()
        mock_client.get_api_token_info.return_value = mock_token_info
        mock_client.__aenter__.return_value = mock_client
        mock_client_factory.return_value = mock_client

        result_raw = await mcp_server.call_tool("get_token_info", {})
        data = json.loads(_extract_text(result_raw))
        assert data["name"] == "Claude Connector Key"
        assert data["is_active"] is True
        assert "disclaimer" in data


@pytest.mark.asyncio
async def test_tool_auth_error_handling():
    """Test graceful handling of AuthenticationError in tools."""
    with patch("financial_portfolios_ai_mcp.tools.get_async_client") as mock_client_factory:
        mock_client = AsyncMock()
        mock_client.list_portfolios.side_effect = AuthenticationError("Invalid API key")
        mock_client.__aenter__.return_value = mock_client
        mock_client_factory.return_value = mock_client

        result_raw = await mcp_server.call_tool("list_portfolios", {})
        data = json.loads(_extract_text(result_raw))
        assert "error" in data
        assert "Authentication" in data["error"]
        assert "https://financial-portfolios.ai" in data["hint"]


@pytest.mark.asyncio
async def test_tool_not_found_error_handling():
    """Test graceful handling of NotFoundError in tools."""
    with patch("financial_portfolios_ai_mcp.tools.get_async_client") as mock_client_factory:
        mock_client = AsyncMock()
        mock_client.get_portfolio.side_effect = NotFoundError("Portfolio NON_EXISTENT not found")
        mock_client.__aenter__.return_value = mock_client
        mock_client_factory.return_value = mock_client

        result_raw = await mcp_server.call_tool(
            "get_portfolio_allocation",
            {"portfolio_code": "NON_EXISTENT"},
        )
        data = json.loads(_extract_text(result_raw))
        assert data["error"] == "Portfolio Not Found"
