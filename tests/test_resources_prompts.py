"""Unit tests for Financial Portfolios AI MCP Resources and Prompts."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from financial_portfolios_ai_mcp.server import mcp_server


def _extract_resource_text(res) -> str:
    """Helper to extract text content from ReadResourceContents."""
    if isinstance(res, list) and res:
        first = res[0]
        if hasattr(first, "content"):
            return first.content
        if hasattr(first, "text"):
            return first.text
        return str(first)
    return str(res)


@pytest.mark.asyncio
async def test_portfolio_catalog_resource(mock_portfolio_list):
    """Test reading portfolios://catalog resource."""
    with patch("financial_portfolios_ai_mcp.resources.get_async_client") as mock_client_factory:
        mock_client = AsyncMock()
        mock_client.list_portfolios.return_value = mock_portfolio_list
        mock_client.__aenter__.return_value = mock_client
        mock_client_factory.return_value = mock_client

        content = await mcp_server.read_resource("portfolios://catalog")
        assert content is not None
        text = _extract_resource_text(content)
        data = json.loads(text)
        assert data["total"] == 2
        assert data["portfolios"][0]["code"] == "AQA_AGGRESSIVE"


@pytest.mark.asyncio
async def test_portfolio_allocation_resource(mock_portfolio_snapshot):
    """Test reading portfolios://{code}/allocation resource."""
    with patch("financial_portfolios_ai_mcp.resources.get_async_client") as mock_client_factory:
        mock_client = AsyncMock()
        mock_client.get_portfolio.return_value = mock_portfolio_snapshot
        mock_client.__aenter__.return_value = mock_client
        mock_client_factory.return_value = mock_client

        content = await mcp_server.read_resource("portfolios://AQA_AGGRESSIVE/allocation")
        assert content is not None
        text = _extract_resource_text(content)
        data = json.loads(text)
        assert data["portfolio_code"] == "AQA_AGGRESSIVE"
        assert len(data["positions"]) == 2


@pytest.mark.asyncio
async def test_latest_research_resource(mock_blog_posts):
    """Test reading research://posts/latest resource."""
    with patch("financial_portfolios_ai_mcp.resources.get_async_client") as mock_client_factory:
        mock_client = AsyncMock()
        mock_client.list_blog_posts.return_value = mock_blog_posts
        mock_client.__aenter__.return_value = mock_client
        mock_client_factory.return_value = mock_client

        content = await mcp_server.read_resource("research://posts/latest")
        assert content is not None
        text = _extract_resource_text(content)
        data = json.loads(text)
        assert data["total"] == 1


@pytest.mark.asyncio
async def test_portfolio_review_prompt():
    """Test generating portfolio_review prompt."""
    prompt_result = await mcp_server.get_prompt(
        "portfolio_review", {"portfolio_code": "AQA_BALANCED"}
    )
    assert prompt_result is not None
    msg_text = (
        prompt_result.messages[0].content.text if prompt_result.messages else str(prompt_result)
    )
    assert "AQA_BALANCED" in msg_text


@pytest.mark.asyncio
async def test_rebalance_advisor_prompt():
    """Test generating rebalance_advisor prompt."""
    prompt_result = await mcp_server.get_prompt(
        "rebalance_advisor", {"portfolio_code": "AQA_AGGRESSIVE"}
    )
    assert prompt_result is not None
    msg_text = (
        prompt_result.messages[0].content.text if prompt_result.messages else str(prompt_result)
    )
    assert "AQA_AGGRESSIVE" in msg_text
    assert "rebalance" in msg_text.lower()


@pytest.mark.asyncio
async def test_market_research_digest_prompt():
    """Test generating market_research_digest prompt."""
    prompt_result = await mcp_server.get_prompt("market_research_digest", {})
    assert prompt_result is not None
    msg_text = (
        prompt_result.messages[0].content.text if prompt_result.messages else str(prompt_result)
    )
    assert "research" in msg_text.lower()
