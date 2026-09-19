"""Rebalance Studio MCP App: binding, prefill from a brokerage connector, and page guardrails."""

import json
import re
from unittest.mock import AsyncMock, patch

import pytest
from financial_portfolios_ai.exceptions import AuthenticationError
from financial_portfolios_ai.models import PortfolioListResponse, PortfolioSummary

from financial_portfolios_ai_mcp.rebalance_studio import REBALANCE_URI, _pick_target, holdings_text
from financial_portfolios_ai_mcp.server import mcp_server

APP_MIME = "text/html;profile=mcp-app"


def _text(result) -> str:
    if hasattr(result, "content") and result.content:
        return result.content[0].text
    return str(result)


async def _html() -> tuple[str, str]:
    item = (await mcp_server.read_resource(REBALANCE_URI))[0]
    return (item.content if hasattr(item, "content") else item.text), item.mime_type


def _client(listing=None, error=None):
    client = AsyncMock()
    if error:
        client.list_portfolios.side_effect = error
    else:
        client.list_portfolios.return_value = listing
    client.__aenter__.return_value = client
    return client


def _listing():
    return PortfolioListResponse(
        total=2,
        portfolios=[
            PortfolioSummary(code="AQA_BALANCED", access="public_delayed", delayed=True),
            PortfolioSummary(code="AQA_DEFENSIVE", product_name="Defensive", access="subscribed", delayed=False),
        ],
    )


async def _open(client, **args) -> dict:
    with patch("financial_portfolios_ai_mcp.rebalance_studio.get_async_client", return_value=client):
        return json.loads(_text(await mcp_server.call_tool("open_rebalance_studio", args)))


# --------------------------------------------------------------------------- #
# Binding
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_tool_is_bound_to_its_ui_resource():
    tool = {t.name: t for t in await mcp_server.list_tools()}["open_rebalance_studio"]
    assert tool.meta == {"ui": {"resourceUri": REBALANCE_URI}}
    assert tool.title == "Rebalance Studio"
    assert tool.annotations.read_only_hint is True


@pytest.mark.asyncio
async def test_ui_resource_is_served_as_an_mcp_app_and_is_self_contained():
    html, mime = await _html()
    assert mime == APP_MIME
    assert "ui/initialize" in html and "ui/notifications/tool-result" in html
    assert not re.search(r"<script[^>]+src=", html), "external script"
    assert "fetch(" not in html and "XMLHttpRequest" not in html, "network call"


# --------------------------------------------------------------------------- #
# Holdings come from a brokerage connector where there is one
# --------------------------------------------------------------------------- #
def test_holdings_from_another_connector_are_normalised_for_the_editor():
    """The model reads positions from the user's brokerage connector and hands them over.

    It may pass either shape `rebalance_portfolio` accepts, and field naming varies between
    connectors, so `symbol`/`shares` are read as well as `ticker`/`quantity`.
    """
    rows = [
        {"ticker": "aapl", "quantity": 40},
        {"symbol": "MSFT", "shares": 25, "price": 402.5},
        {"ticker": "CASH", "quantity": 1500},
    ]
    assert holdings_text(rows) == "AAPL,40\nMSFT,25,402.5\nCASH,1500"
    # CSV text passes through, since that is what `rebalance_portfolio` itself accepts.
    assert holdings_text("AAPL,40\nMSFT,25") == "AAPL,40\nMSFT,25"
    assert holdings_text(None) == "" and holdings_text([]) == ""


def test_a_malformed_prefill_opens_an_editable_page_rather_than_failing():
    """A partial read from another connector must not block the manual path.

    Rows without a ticker or quantity are dropped and the rest still open in the editor:
    the user can see what arrived and fix it, which is the whole point of showing it.
    """
    rows = [{"ticker": "AAPL", "quantity": 40}, {"ticker": ""}, {"quantity": 5}, "not a row", {"ticker": "MSFT"}]
    assert holdings_text(rows) == "AAPL,40"


@pytest.mark.asyncio
async def test_prefilled_holdings_are_returned_for_review_not_calculated():
    """Opening with holdings must not compute anything - it fills the editor.

    Positions read from another service can be stale, partial, or from a different account,
    so the arithmetic waits for the user to look.
    """
    data = await _open(_client(_listing()), holdings=[{"ticker": "AAPL", "quantity": 40}])
    assert data["holdings_text"] == "AAPL,40"
    assert data["prefilled"] is True
    assert "orders" not in data


@pytest.mark.asyncio
async def test_opening_without_holdings_leaves_the_editor_empty():
    data = await _open(_client(_listing()))
    assert data["holdings_text"] == "" and data["prefilled"] is False


@pytest.mark.asyncio
async def test_tool_description_sends_the_model_to_the_brokerage_connector_first():
    tool = {t.name: t for t in await mcp_server.list_tools()}["open_rebalance_studio"]
    assert "brokerage" in tool.description
    assert "should not be asked to retype" in tool.description
    assert "Never ask the user for brokerage credentials" in tool.description


# --------------------------------------------------------------------------- #
# Target selection
# --------------------------------------------------------------------------- #
def test_only_subscribed_portfolios_can_be_a_target():
    """Alignment needs a subscription, so a delayed book is never preselected.

    Offering one would walk the user into a calculation that can only be rejected.
    """
    portfolios = [
        {"code": "AQA_BALANCED", "access": "public_delayed"},
        {"code": "AQA_DEFENSIVE", "access": "subscribed"},
    ]
    assert _pick_target(portfolios, "") == "AQA_DEFENSIVE"
    assert _pick_target(portfolios, "AQA_BALANCED") == "AQA_DEFENSIVE"  # requested, but not subscribed
    assert _pick_target(portfolios, "aqa_defensive") == "AQA_DEFENSIVE"
    assert _pick_target([{"code": "AQA_BALANCED", "access": "public_delayed"}], "") is None


@pytest.mark.asyncio
async def test_panel_reports_the_upload_limits_it_enforces():
    data = await _open(_client(_listing()))
    assert data["selected"] == "AQA_DEFENSIVE"
    assert data["limits"]["max_rows"] == 200
    assert data["columns"]["required"] == ["ticker", "quantity"]


@pytest.mark.asyncio
async def test_portal_errors_are_returned_as_json():
    data = await _open(_client(error=AuthenticationError("session expired")))
    assert data["error"] == "Unable to open the Rebalance Studio"
    assert "session expired" in data["message"]


# --------------------------------------------------------------------------- #
# Page guardrails
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_page_states_what_the_arithmetic_is_not():
    html, _ = await _html()
    assert "not advice or a recommendation to trade" in html
    assert "nothing here places an order" in html
    assert "no suitability assessment has been performed" in html.lower()


@pytest.mark.asyncio
async def test_page_downloads_through_the_host_and_degrades_without_it():
    """A sandboxed page cannot start a download; `ui/download-file` is the only route.

    ChatGPT does not advertise `downloadFile` today, so the CSV must still be reachable -
    a button that silently does nothing is worse than no button.
    """
    html, _ = await _html()
    assert "ui/download-file" in html
    assert "hostCaps.downloadFile" in html
    assert "Show CSV" in html, "no fallback for hosts without downloadFile"
