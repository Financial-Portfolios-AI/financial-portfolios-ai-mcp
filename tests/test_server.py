"""Unit tests for Server setup, ASGI HTTP app, and remote multi-tenant auth propagation."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from financial_portfolios_ai_mcp.app import create_app
from financial_portfolios_ai_mcp.auth import resolve_api_token
from financial_portfolios_ai_mcp.config import get_settings
from financial_portfolios_ai_mcp.manifests import MANIFESTS, PLACEHOLDER
from financial_portfolios_ai_mcp.manifests import render as render_manifest
from financial_portfolios_ai_mcp.server import mcp_server


def test_server_metadata():
    """Verify MCPServer attributes and configuration."""
    assert mcp_server.name == "financial-portfolios-ai"
    assert mcp_server.title == "Financial Portfolios AI"
    assert mcp_server.website_url == "https://financial-portfolios.ai"
    assert mcp_server.version == "1.0.0"


@pytest.mark.asyncio
async def test_tool_registration():
    """Verify that all 8 required tools are registered."""
    tools = await mcp_server.list_tools()
    tool_names = {t.name for t in tools}
    expected_tools = {
        "list_portfolios",
        "get_portfolio_allocation",
        "get_portfolio_history",
        "rebalance_portfolio",
        "get_rebalance_template",
        "list_blog_posts",
        "get_blog_post",
        "get_token_info",
    }
    assert expected_tools.issubset(tool_names)


@pytest.mark.asyncio
async def test_resource_registration():
    """Verify that catalog and research resources are registered."""
    resources = await mcp_server.list_resources()
    resource_uris = {r.uri for r in resources}
    assert "portfolios://catalog" in resource_uris
    assert "research://posts/latest" in resource_uris

    templates = await mcp_server.list_resource_templates()
    template_uris = {t.uri_template for t in templates}
    assert "portfolios://{portfolio_code}/allocation" in template_uris


@pytest.mark.asyncio
async def test_prompt_registration():
    """Verify prompt templates are registered."""
    prompts = await mcp_server.list_prompts()
    prompt_names = {p.name for p in prompts}
    assert {"portfolio_review", "rebalance_advisor", "market_research_digest"}.issubset(prompt_names)


def test_app_health_endpoints():
    """Test ASGI FastAPI health endpoints."""
    app = create_app()
    client = TestClient(app)

    root_resp = client.get("/")
    assert root_resp.status_code == 200
    assert root_resp.json()["service"] == "financial-portfolios-ai-mcp"
    assert root_resp.json()["status"] == "online"

    healthz_resp = client.get("/healthz")
    assert healthz_resp.status_code == 200
    assert healthz_resp.json()["status"] == "ok"

    livez_resp = client.get("/livez")
    assert livez_resp.status_code == 200
    assert livez_resp.json()["status"] == "alive"

    openapi_resp = client.get("/openapi.yaml")
    assert openapi_resp.status_code == 200
    assert "openapi: 3.1.0" in openapi_resp.text


def test_inbound_auth_middleware_headers():
    """Test that inbound X-API-Key and Authorization Bearer headers are extracted by ASGI middleware."""
    app = create_app()

    @app.get("/test-auth-context")
    async def check_token():
        return {"resolved_token": resolve_api_token()}

    client = TestClient(app)

    # 1. With X-API-Key header
    resp = client.get("/test-auth-context", headers={"X-API-Key": "aqat_v1_header_key_123"})
    assert resp.status_code == 200
    assert resp.json()["resolved_token"] == "aqat_v1_header_key_123"

    # 2. With Authorization: Bearer header
    resp2 = client.get(
        "/test-auth-context", headers={"Authorization": "Bearer aqat_v1_bearer_key_456"}
    )
    assert resp2.status_code == 200
    assert resp2.json()["resolved_token"] == "aqat_v1_bearer_key_456"


def test_query_param_token_is_rejected_for_security():
    """Verify that tokens passed in query string (?api_key=...) are rejected and not extracted (R2-4)."""
    app = create_app()

    @app.get("/test-query-reject")
    async def check_token():
        return {"resolved_token": resolve_api_token()}

    client = TestClient(app)

    resp = client.get("/test-query-reject?api_key=aqat_v1_leaked_in_url")
    assert resp.status_code == 200
    # Must be None, not extracted from URL query
    assert resp.json()["resolved_token"] is None


def test_e2e_mounted_mcp_app_auth_propagation(mock_portfolio_list):
    """
    End-to-end test (R2-1): Verifies that when an HTTP request carrying an X-API-Key header hits
    the mounted Starlette sub-app, the ContextVar propagates into the tool execution context.
    """
    app = create_app()

    with patch("financial_portfolios_ai_mcp.tools.get_async_client") as mock_client_factory:
        mock_client = AsyncMock()
        mock_client.list_portfolios.return_value = mock_portfolio_list
        mock_client.__aenter__.return_value = mock_client
        mock_client_factory.return_value = mock_client

        # Create test endpoint that calls tool inside the ASGI request lifecycle
        @app.get("/test-mcp-e2e-tool")
        async def run_mcp_tool():
            # Tool executes resolve_api_token internally
            res = await mcp_server.call_tool("list_portfolios", {})
            return {"result": json.loads(res.content[0].text)}

        client = TestClient(app)

        # 1. Authenticated user A
        resp_a = client.get("/test-mcp-e2e-tool", headers={"X-API-Key": "aqat_v1_user_a_token"})
        assert resp_a.status_code == 200
        assert "disclaimer" in resp_a.json()["result"]

        # 2. Authenticated user B in same process
        resp_b = client.get("/test-mcp-e2e-tool", headers={"X-API-Key": "aqat_v1_user_b_token"})
        assert resp_b.status_code == 200
        assert "disclaimer" in resp_b.json()["result"]


def test_server_advertises_icons():
    """The MCP Implementation must carry brand icons for provider UIs."""
    icons = getattr(mcp_server, "icons", None)
    assert icons, "MCPServer should advertise icons"
    srcs = [icon.src for icon in icons]
    # An inline icon so stdio clients render a logo with no HTTP fetch, plus
    # absolute URLs built from the deployment's own public origin (never hardcoded).
    assert any(s.startswith("data:image/png;base64,") for s in srcs)
    origin = get_settings().public_origin()
    assert any(s == f"{origin}/assets/icon-512.png" for s in srcs)


def test_asset_routes_served_without_auth():
    """Icon assets are public so connector directories can render the logo."""
    client = TestClient(create_app())

    resp = client.get("/assets/icon-512.png")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"

    resp = client.get("/favicon.ico")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/x-icon"

    assert client.get("/assets/does-not-exist.png").status_code == 404
    assert client.get("/assets/../config.py").status_code == 404


def test_root_metadata_includes_icons():
    resp = TestClient(create_app()).get("/")
    assert resp.status_code == 200
    icons = resp.json()["icons"]
    assert icons and icons[0]["mimeType"] == "image/png"


def test_root_icon_urls_follow_request_origin():
    """Dev and prod each advertise their own hostname - no baked-in origin."""
    client = TestClient(create_app())
    resp = client.get("/", headers={"X-Forwarded-Proto": "https", "X-Forwarded-Host": "dev.financial-portfolios.ai"})
    assert resp.status_code == 200
    remote = [i["src"] for i in resp.json()["icons"] if i["src"].startswith("http")]
    assert remote
    assert all(s.startswith("https://dev.financial-portfolios.ai/assets/") for s in remote)


def test_manifest_templates_carry_no_environment_origin():
    """The committed manifests must stay origin-agnostic."""
    for name in MANIFESTS:
        text = (Path(__file__).resolve().parent.parent / name).read_text(encoding="utf-8")
        assert PLACEHOLDER in text, f"{name} has no origin placeholder"
        assert "https://financial-portfolios.ai" not in text, f"{name} hardcodes prod"
        assert "https://dev.financial-portfolios.ai" not in text, f"{name} hardcodes dev"


def test_manifests_rendered_for_request_origin():
    """A dev deployment hands out a manifest pointing at dev."""
    client = TestClient(create_app())
    resp = client.get(
        "/manifests/claude_connector.json",
        headers={"X-Forwarded-Proto": "https", "X-Forwarded-Host": "dev.financial-portfolios.ai"},
    )
    assert resp.status_code == 200
    doc = resp.json()
    assert doc["icon_url"] == "https://dev.financial-portfolios.ai/assets/icon-512.png"
    assert doc["website_url"] == "https://dev.financial-portfolios.ai"
    assert "$comment" not in doc
    assert PLACEHOLDER not in resp.text

    assert client.get("/manifests/nope.json").status_code == 404


def test_render_manifests_script_matches_served_document():
    """The offline renderer and the live endpoint agree."""
    rendered = render_manifest("gemini_extension.json", "https://dev.financial-portfolios.ai")
    resp = TestClient(create_app()).get(
        "/manifests/gemini_extension.json",
        headers={"X-Forwarded-Proto": "https", "X-Forwarded-Host": "dev.financial-portfolios.ai"},
    )
    assert resp.json() == rendered
