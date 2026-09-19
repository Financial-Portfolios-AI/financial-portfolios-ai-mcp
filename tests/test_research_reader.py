"""Research Reader MCP App: binding, listing payload, and how the page handles portal content."""

import json
import re
from unittest.mock import AsyncMock, patch

import pytest
from financial_portfolios_ai.exceptions import FinancialPortfoliosAIError
from financial_portfolios_ai.models import BlogPostListResponse, BlogPostSummary

from financial_portfolios_ai_mcp.research_reader import RESEARCH_URI
from financial_portfolios_ai_mcp.server import mcp_server

APP_MIME = "text/html;profile=mcp-app"


def _text(result) -> str:
    if hasattr(result, "content") and result.content:
        return result.content[0].text
    return str(result)


async def _html() -> tuple[str, str]:
    item = (await mcp_server.read_resource(RESEARCH_URI))[0]
    return (item.content if hasattr(item, "content") else item.text), item.mime_type


def _client(listing=None, error=None):
    client = AsyncMock()
    if error:
        client.list_blog_posts.side_effect = error
    else:
        client.list_blog_posts.return_value = listing
    client.__aenter__.return_value = client
    return client


def _listing():
    return BlogPostListResponse(
        total=1, page=1, page_size=20, total_pages=1,
        items=[BlogPostSummary(id=1, title="Rates and the book", slug="rates", is_gated=False, is_accessible=True)],
    )


async def _open(client, **args) -> dict:
    with patch("financial_portfolios_ai_mcp.research_reader.get_async_client", return_value=client):
        return json.loads(_text(await mcp_server.call_tool("open_research_reader", args)))


@pytest.mark.asyncio
async def test_tool_is_bound_to_its_ui_resource():
    tool = {t.name: t for t in await mcp_server.list_tools()}["open_research_reader"]
    assert tool.meta == {"ui": {"resourceUri": RESEARCH_URI}}
    assert tool.title == "Research Reader"
    assert tool.annotations.read_only_hint is True


@pytest.mark.asyncio
async def test_ui_resource_is_served_as_an_mcp_app_and_is_self_contained():
    html, mime = await _html()
    assert mime == APP_MIME
    assert "ui/initialize" in html and "ui/notifications/tool-result" in html
    assert not re.search(r"<script[^>]+src=", html), "external script"
    assert "fetch(" not in html and "XMLHttpRequest" not in html, "network call"


@pytest.mark.asyncio
async def test_listing_is_returned_with_the_search_that_produced_it():
    client = _client(_listing())
    data = await _open(client, search="  rates  ")
    assert [p["slug"] for p in data["posts"]] == ["rates"]
    assert data["search"] == "rates"
    client.list_blog_posts.assert_awaited_once_with(page=1, page_size=20, search="rates")


@pytest.mark.asyncio
async def test_an_empty_search_asks_the_portal_for_everything():
    client = _client(_listing())
    data = await _open(client)
    assert data["search"] == ""
    client.list_blog_posts.assert_awaited_once_with(page=1, page_size=20, search=None)


@pytest.mark.asyncio
async def test_portal_errors_are_returned_as_json():
    data = await _open(_client(error=FinancialPortfoliosAIError("upstream down")))
    assert data["error"] == "Unable to open the Research Reader"
    assert "upstream down" in data["message"]


# --------------------------------------------------------------------------- #
# Page behaviour that protects the frame and the reader
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_post_bodies_are_re_emitted_as_text_never_as_markup():
    """Portal content may be HTML. The page parses it and emits only `textContent`.

    Rendering it as markup would let anything written in the CMS run as script inside
    the app's frame, which shares an origin with the rest of the app.
    """
    html, _ = await _html()
    assert "DOMParser" in html, "post bodies must be parsed, not trusted"
    assert "textContent" in html
    # Every rendered fragment of a post goes through the escaper.
    assert "esc(b.text)" in html


@pytest.mark.asyncio
async def test_the_holdings_filter_matches_whole_tickers_only():
    """A substring match would make the filter useless.

    Tickers like ALL or IT appear inside ordinary prose, so a bare `includes` would mark
    every post as mentioning a holding. Single-character tickers are skipped entirely.
    """
    html, _ = await _html()
    assert "(^|[^A-Z0-9])" in html, "ticker matching must be anchored to word boundaries"
    assert "ticker.length < 2" in html, "single letters must be skipped"


@pytest.mark.asyncio
async def test_page_says_a_mention_is_not_a_view():
    html, _ = await _html()
    assert "Nothing here is a recommendation to buy or sell" in html
    assert "appearance in a post is not a view on owning it" in html
