"""get_token_info must not make a healthy OAuth connection look broken."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from financial_portfolios_ai_mcp.auth import reset_request_token, set_request_token
from financial_portfolios_ai_mcp.server import mcp_server


def _text(result) -> str:
    if hasattr(result, "content") and result.content:
        return result.content[0].text
    if isinstance(result, list) and result:
        return getattr(result[0], "text", str(result[0]))
    return str(result)


async def _call_with_token(token):
    ctx = set_request_token(token)
    try:
        with (
            patch("financial_portfolios_ai_mcp.auth.get_settings") as settings,
            patch("financial_portfolios_ai_mcp.tools.get_async_client") as factory,
        ):
            settings.return_value.api_token = None
            client = AsyncMock()
            client.__aenter__.return_value = client
            factory.return_value = client
            data = json.loads(_text(await mcp_server.call_tool("get_token_info", {})))
            return data, client
    finally:
        reset_request_token(ctx)


@pytest.mark.asyncio
async def test_oauth_connection_reports_connected_without_calling_the_token_endpoint():
    """ChatGPT called this to check the connection, got the portal's 403 for an OAuth
    token, and asked the user to paste an API token into the chat."""
    data, client = await _call_with_token("eyJhbGciOiJSUzI1NiJ9.oauth-access-token")
    assert data["connected"] is True
    assert data["authentication"] == "oauth"
    assert "list_portfolios" in data["message"]
    client.get_api_token_info.assert_not_awaited()


@pytest.mark.asyncio
async def test_api_token_connection_still_returns_token_metadata():
    _, client = await _call_with_token("aqat_v1_abc123")
    client.get_api_token_info.assert_awaited_once()


@pytest.mark.asyncio
async def test_no_credential_says_reconnect_and_never_asks_for_a_token():
    data, client = await _call_with_token(None)
    assert data["connected"] is False
    assert "reconnect" in data["message"].lower()
    assert "never ask the user to paste" in data["message"].lower()
    client.get_api_token_info.assert_not_awaited()


def test_instructions_forbid_asking_for_credentials_in_chat():
    text = mcp_server.instructions
    assert "Never ask the user to share, paste or type an API token" in text
    assert "call `list_portfolios`" in text
