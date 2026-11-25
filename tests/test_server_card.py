"""MCP Server Card and AI Catalog (SEP-2127): public, schema-conformant, and in step with server.json."""

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from financial_portfolios_ai_mcp import server_card
from financial_portfolios_ai_mcp._version import __version__
from financial_portfolios_ai_mcp.app import create_app

SERVER_JSON = json.loads((Path(__file__).resolve().parent.parent / "server.json").read_text(encoding="utf-8"))

_NAME = re.compile(r"^[a-zA-Z0-9.-]+/[a-zA-Z0-9._-]+$")
_REMOTE_URL = re.compile(r"^(https?://[^\s]+|\{[a-zA-Z_][a-zA-Z0-9_]*\}[^\s]*)$")
_VERSION_RANGE = re.compile(r"[\^~<>=*]|\.x\b")


@pytest.fixture()
def http():
    with TestClient(create_app(), base_url="https://financial-portfolios.ai") as client:
        yield client


def _card(http):
    r = http.get(server_card.CARD_PATH)
    assert r.status_code == 200
    return r.json()


def test_card_is_public_and_typed(http):
    """No credential: the connector directory and crawlers fetch it before any sign-in."""
    r = http.get(server_card.CARD_PATH)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(server_card.CARD_MEDIA_TYPE)


def test_card_cors_cache_and_etag(http):
    r = http.get(server_card.CARD_PATH)
    assert r.headers["access-control-allow-origin"] == "*"
    assert r.headers["access-control-expose-headers"] == "ETag"
    assert r.headers["cache-control"] == "public, max-age=3600"
    assert r.headers["etag"].startswith('"')


def test_card_revalidates_with_304(http):
    etag = http.get(server_card.CARD_PATH).headers["etag"]
    r = http.get(server_card.CARD_PATH, headers={"If-None-Match": etag})
    assert r.status_code == 304
    assert r.headers["etag"] == etag


def test_card_preflight_allows_conditional_request(http):
    r = http.options(
        server_card.CARD_PATH,
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "if-none-match",
        },
    )
    assert r.status_code == 200
    assert "if-none-match" in r.headers["access-control-allow-headers"].lower()


def test_card_head(http):
    assert http.head(server_card.CARD_PATH).status_code == 200


def test_card_matches_the_published_schema(http):
    card = _card(http)
    assert card["$schema"] == server_card.SCHEMA_URL
    assert 3 <= len(card["name"]) <= 200 and _NAME.match(card["name"])
    assert len(card["version"]) <= 255 and not _VERSION_RANGE.search(card["version"])
    assert 1 <= len(card["description"]) <= 100
    assert 1 <= len(card["title"]) <= 100
    assert card["repository"]["url"] and card["repository"]["source"]
    for remote in card["remotes"]:
        assert remote["type"] in {"streamable-http", "sse"}
        assert _REMOTE_URL.match(remote["url"])
        for header in remote.get("headers", []):
            assert header["name"]
    for icon in card["icons"]:
        assert icon["src"]


def test_card_version_is_the_release_version(http):
    assert _card(http)["version"] == __version__


def test_card_identity_matches_server_json(http):
    """The card and the registry entry describe the same server; they must not drift."""
    card = _card(http)
    for key in ("name", "title", "description", "websiteUrl", "repository"):
        assert card[key] == SERVER_JSON[key], key
    assert [r["url"].removeprefix("https://financial-portfolios.ai") for r in card["remotes"]] == [
        r["url"].removeprefix("https://financial-portfolios.ai") for r in SERVER_JSON["remotes"]
    ]


def test_card_points_at_the_origin_it_was_fetched_from():
    with TestClient(create_app(), base_url="https://dev.financial-portfolios.ai") as dev:
        urls = [r["url"] for r in dev.get(server_card.CARD_PATH).json()["remotes"]]
    assert urls == ["https://dev.financial-portfolios.ai/mcp", "https://dev.financial-portfolios.ai/sse"]


def test_card_carries_no_primitives_and_no_secrets(http):
    """Cards are public: no tools/resources/prompts (listed at runtime per user) and no credential."""
    text = http.get(server_card.CARD_PATH).text
    card = json.loads(text)
    assert not {"tools", "resources", "prompts", "capabilities"} & set(card)
    assert "aqat_v1_" not in text.replace("(aqat_v1_...)", "")
    assert "Bearer" not in text


def test_catalog_lists_the_card(http):
    r = http.get(server_card.CATALOG_PATH)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(server_card.CATALOG_MEDIA_TYPE)
    (entry,) = r.json()["entries"]
    assert entry["type"] == server_card.CARD_MEDIA_TYPE
    assert entry["url"] == "https://financial-portfolios.ai/mcp/server-card"
    assert http.get(entry["url"].removeprefix("https://financial-portfolios.ai")).status_code == 200


@pytest.mark.parametrize("version", server_card.SUPPORTED_PROTOCOL_VERSIONS)
def test_advertised_protocol_versions_are_accepted(version):
    """Every version the card claims is one the transport answers with itself."""
    headers = {"X-API-Key": "aqat_v1_test", "Accept": "application/json, text/event-stream"}
    with TestClient(create_app(), base_url="http://localhost") as local:
        r = local.post("/mcp", headers=headers, json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": version, "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}})
    assert f'"protocolVersion":"{version}"' in r.text.replace(" ", "")
