"""Breadth Board MCP App: cross-portfolio summary, and what happens when one book fails."""

import json
import re
from unittest.mock import AsyncMock, patch

import pytest
from financial_portfolios_ai.exceptions import FinancialPortfoliosAIError
from financial_portfolios_ai.models import (
    PortfolioListResponse,
    PortfolioSnapshot,
    PortfolioSummary,
    Position,
)

from financial_portfolios_ai_mcp.breadth_board import BREADTH_URI, summarise
from financial_portfolios_ai_mcp.server import mcp_server

APP_MIME = "text/html;profile=mcp-app"


def _text(result) -> str:
    if hasattr(result, "content") and result.content:
        return result.content[0].text
    return str(result)


async def _html() -> tuple[str, str]:
    item = (await mcp_server.read_resource(BREADTH_URI))[0]
    return (item.content if hasattr(item, "content") else item.text), item.mime_type


def _snapshot(code, positions):
    return PortfolioSnapshot(
        portfolio_code=code, date="2026-09-10T00:00:00", total_positions=len(positions),
        positions=[Position(ticker=t, weight=w, sector=s) for t, w, s in positions],
        access="subscribed", delayed=False, as_of="2026-09-10",
    )


def _client(books: dict, failures: tuple = ()):
    client = AsyncMock()
    client.list_portfolios.return_value = PortfolioListResponse(
        total=len(books),
        portfolios=[PortfolioSummary(code=code, product_name=code.title(), access="subscribed") for code in books],
    )

    async def get_portfolio(portfolio_code):
        if portfolio_code in failures:
            raise FinancialPortfoliosAIError(f"{portfolio_code} unavailable")
        return _snapshot(portfolio_code, books[portfolio_code])

    client.get_portfolio.side_effect = get_portfolio
    client.__aenter__.return_value = client
    return client


BOOKS = {
    "AQA_DEFENSIVE": [("MSFT", 0.4, "Technology"), ("KO", 0.6, "Staples")],
    "AQA_BALANCED": [("MSFT", 0.5, "Technology"), ("NVDA", 0.5, "Technology")],
}


async def _open(client) -> dict:
    with patch("financial_portfolios_ai_mcp.breadth_board.get_async_client", return_value=client):
        return json.loads(_text(await mcp_server.call_tool("open_breadth_board", {})))


# --------------------------------------------------------------------------- #
# Binding
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_tool_is_bound_to_its_ui_resource():
    tool = {t.name: t for t in await mcp_server.list_tools()}["open_breadth_board"]
    assert tool.meta == {"ui": {"resourceUri": BREADTH_URI}}
    assert tool.title == "Breadth Board"
    assert tool.annotations.read_only_hint is True


@pytest.mark.asyncio
async def test_ui_resource_is_served_as_an_mcp_app_and_is_self_contained():
    html, mime = await _html()
    assert mime == APP_MIME
    assert "ui/initialize" in html
    assert not re.search(r"<script[^>]+src=", html), "external script"
    assert "fetch(" not in html and "XMLHttpRequest" not in html, "network call"


# --------------------------------------------------------------------------- #
# The summary is computed on the server, so text-only hosts get it too
# --------------------------------------------------------------------------- #
def test_summary_is_complete_without_a_page_to_render_it():
    """No Gemini surface renders MCP Apps, so the tool result must answer on its own."""
    books = {"A": [{"ticker": "MSFT", "weight": 0.5, "sector": "Technology"}],
             "B": [{"ticker": "MSFT", "weight": 0.3, "sector": "Technology"}, {"ticker": "KO", "weight": 0.7, "sector": "Staples"}]}
    summary = summarise(books)
    assert [row["ticker"] for row in summary["most_held"]] == ["MSFT"]
    assert summary["only_in_one"] == 1
    assert summary["books"]["B"]["sectors"]["dominant"]["sector"] == "Staples"
    assert summary["overlaps"][0]["shared"] == ["MSFT"]


@pytest.mark.asyncio
async def test_board_reports_what_the_books_share():
    data = await _open(_client(BOOKS))
    assert [row["ticker"] for row in data["most_held"]] == ["MSFT"]
    assert data["most_held"][0]["count"] == 2
    assert sorted(data["portfolios"]) == ["AQA_BALANCED", "AQA_DEFENSIVE"]
    assert data["overlaps"][0]["shared"] == ["MSFT"]
    assert "disclaimer" in data


@pytest.mark.asyncio
async def test_one_unreadable_book_narrows_the_comparison_and_says_so():
    """A breadth count over fewer portfolios than the user has would read as fact.

    So a failed read drops that book, keeps the rest, and names what was skipped - the page
    turns that into a banner rather than quietly reporting a smaller number.
    """
    data = await _open(_client(BOOKS, failures=("AQA_BALANCED",)))
    assert data["unavailable"] == ["AQA_BALANCED"]
    assert list(data["portfolios"]) == ["AQA_DEFENSIVE"]
    assert data["most_held"] == [], "nothing is shared when only one book could be read"
    assert "error" not in data


@pytest.mark.asyncio
async def test_page_warns_when_the_books_are_not_comparable():
    html, _ = await _html()
    assert "could not be read, so these counts cover the rest only" in html
    assert "different dates" in html
    assert "delayed about 45 days" in html


@pytest.mark.asyncio
async def test_page_rules_out_the_performance_reading():
    """"Most widely held" invites "so which did best" - the page closes that off."""
    html, _ = await _html()
    assert "nothing here says how a holding or a portfolio performed" in html
    assert "not a recommendation to own it" in html
