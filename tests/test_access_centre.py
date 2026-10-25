"""Access & Connection MCP App: binding, payload, connection state, and page guardrails."""

import json
import re
from unittest.mock import AsyncMock, patch

import pytest
from financial_portfolios_ai.exceptions import AuthenticationError
from financial_portfolios_ai.models import PortfolioListResponse, PortfolioSummary

from financial_portfolios_ai_mcp.access_centre import ACCESS_URI, DELAYED_HIDES, connection_state
from financial_portfolios_ai_mcp.server import mcp_server

APP_MIME = "text/html;profile=mcp-app"


def _text(result) -> str:
    if hasattr(result, "content") and result.content:
        return result.content[0].text
    return str(result)


async def _html() -> tuple[str, str]:
    item = (await mcp_server.read_resource(ACCESS_URI))[0]
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
            PortfolioSummary(code="AQA_DEFENSIVE", product_name="Defensive", access="subscribed", delayed=False),
            PortfolioSummary(code="AQA_BALANCED", product_name="Balanced", access="public_delayed", delayed=True),
        ],
    )


async def _open(client) -> dict:
    with patch("financial_portfolios_ai_mcp.access_centre.get_async_client", return_value=client):
        return json.loads(_text(await mcp_server.call_tool("open_access_centre", {})))


# --------------------------------------------------------------------------- #
# Binding
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_tool_is_bound_to_its_ui_resource():
    tool = {t.name: t for t in await mcp_server.list_tools()}["open_access_centre"]
    assert tool.meta == {"ui": {"resourceUri": ACCESS_URI}}
    assert tool.title == "Access & Connection"
    assert tool.annotations.read_only_hint is True


@pytest.mark.asyncio
async def test_ui_resource_is_served_as_an_mcp_app():
    html, mime = await _html()
    assert mime == APP_MIME
    for method in ("ui/initialize", "ui/notifications/initialized", "ui/notifications/tool-result"):
        assert method in html, f"App never uses {method}"


@pytest.mark.asyncio
async def test_ui_is_self_contained():
    """A host's default CSP for an App blocks all network and external scripts."""
    html, _ = await _html()
    assert not re.search(r"<script[^>]+src=", html), "external script"
    assert not re.search(r"<link[^>]+href=", html), "external stylesheet"
    assert "fetch(" not in html and "XMLHttpRequest" not in html, "network call"


@pytest.mark.asyncio
async def test_ui_opens_links_through_the_host():
    """Sandboxed pages cannot navigate; `ui/open-link` is the only route to the portal.

    Claude shows an "Open external link" confirmation for every one of these unless the
    connector is directory-listed with the origin declared, so the page must degrade to
    showing the URL rather than relying on the click.
    """
    html, _ = await _html()
    assert "ui/open-link" in html
    assert "hostCaps.openLinks" in html
    assert "<a href" not in html, "a plain link would be dead inside the sandbox"


# --------------------------------------------------------------------------- #
# Connection state - answered locally, never by asking the portal
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("token", "expected", "connected"),
    [(None, "none", False), ("oauth-bearer-token", "oauth", True), ("aqat_v1_abc", "api_token", True)],
)
def test_connection_state_reads_the_credential_without_calling_the_portal(token, expected, connected):
    """`/api/tokens/me` understands personal tokens only.

    Asking it about an OAuth connection returns a 403 that reads like a fault - which is
    what once led a model to ask the user to paste a token into the chat.
    """
    with patch("financial_portfolios_ai_mcp.access_centre.resolve_api_token", return_value=token):
        state = connection_state()
    assert state["authentication"] == expected
    assert state["connected"] is connected
    assert state["detail"]


# --------------------------------------------------------------------------- #
# Payload
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_panel_reports_access_counts_and_links():
    data = await _open(_client(_listing()))
    assert [p["code"] for p in data["portfolios"]] == ["AQA_DEFENSIVE", "AQA_BALANCED"]
    assert data["subscribed"] == 1 and data["delayed"] == 1
    assert data["plan"] == "subscriber"
    assert data["links"]["pricing"].endswith("/#pricing")
    assert data["links"]["portal"] and data["links"]["api_tokens"].endswith("/api-access")
    # Naming what the delayed book withholds is the whole point of the panel.
    assert data["delayed_hides"] == DELAYED_HIDES
    assert "disclaimer" in data


@pytest.mark.asyncio
async def test_a_failed_listing_still_opens_the_panel():
    """A rejected read is the answer to "am I connected?", so the panel must not error out.

    Returning a bare error would leave the model to narrate the failure - the exact
    situation where one previously invented a "paste your token" instruction.
    """
    data = await _open(_client(error=AuthenticationError("session expired")))
    assert data["connection"]["connected"] is False
    assert "session expired" in data["connection"]["detail"]
    assert data["portfolios"] == []
    assert data["links"]["portal"]


@pytest.mark.asyncio
async def test_page_never_invites_a_token_paste():
    html, _ = await _html()
    assert "Never type or paste an API token into the chat" in html
    assert "reconnect the connector" in html.lower()


def test_free_access_is_named_as_a_plan_not_a_fault():
    from financial_portfolios_ai_mcp.server import SERVER_INSTRUCTIONS

    assert "Free access is a normal way to use this service" in SERVER_INSTRUCTIONS
    assert "never" in SERVER_INSTRUCTIONS.split("Free access is a normal way")[1][:400]
