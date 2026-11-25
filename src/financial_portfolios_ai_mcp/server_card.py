"""MCP Server Card and AI Catalog (SEP-2127, Server Card extension).

A server card is a public, static document that tells a client where this server is and
how to connect, before any connection exists. It deliberately carries no tools, resources
or prompts (those are listed at runtime, per user) and no credentials.

    GET <streamable-http-url>/server-card   ->  application/mcp-server-card+json
    GET /.well-known/ai-catalog.json         ->  application/ai-catalog+json

The identity fields mirror ``server.json`` (the registry entry); a test pins that so the two
cannot drift. Schema: https://github.com/modelcontextprotocol/experimental-ext-server-card
"""

import hashlib
import json
from typing import Any

from financial_portfolios_ai_mcp._version import __version__
from financial_portfolios_ai_mcp.icons import icon_specs

SCHEMA_URL = "https://static.modelcontextprotocol.io/schemas/v1/server-card.schema.json"
CARD_MEDIA_TYPE = "application/mcp-server-card+json"
CATALOG_MEDIA_TYPE = "application/ai-catalog+json"
CARD_PATH = "/mcp/server-card"
CATALOG_PATH = "/.well-known/ai-catalog.json"

NAME = "ai.financial-portfolios/financial-portfolios-ai"
# Measured against the live server: it answers each of these with the same version, and
# answers anything newer with 2025-11-25.
SUPPORTED_PROTOCOL_VERSIONS = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"]

CARD_CACHE_CONTROL = "public, max-age=3600"
CARD_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET",
    "Access-Control-Allow-Headers": "Content-Type, If-None-Match",
    "Access-Control-Expose-Headers": "ETag",
}

_DISCLOSURE = (
    "Informational and educational purposes only. Not investment, legal, or tax advice, and not a "
    "recommendation or solicitation. No suitability assessment has been performed. All outputs "
    "represent mathematical target-model alignment arithmetic."
)


def build_card(origin: str) -> dict[str, Any]:
    origin = origin.rstrip("/")
    return {
        "$schema": SCHEMA_URL,
        "name": NAME,
        "version": __version__,
        "title": "Financial Portfolios AI",
        "description": (
            "Systematic model portfolios: allocations, holdings history, "
            "model-alignment arithmetic, research."
        ),
        "websiteUrl": "https://financial-portfolios.ai",
        "repository": {
            "url": "https://github.com/Financial-Portfolios-AI/financial-portfolios-ai-mcp",
            "source": "github",
        },
        "icons": icon_specs(origin),
        "remotes": [
            {
                "type": "streamable-http",
                "url": f"{origin}/mcp",
                "supportedProtocolVersions": SUPPORTED_PROTOCOL_VERSIONS,
                "headers": [
                    {
                        "name": "X-API-Key",
                        "description": (
                            "Personal API token (aqat_v1_...) from financial-portfolios.ai/api-access, "
                            "for clients that cannot run the OAuth sign-in. Clients that can should use "
                            "OAuth 2.1 and omit this header."
                        ),
                        "isRequired": False,
                        "isSecret": True,
                        "format": "string",
                    }
                ],
            },
            {
                "type": "sse",
                "url": f"{origin}/sse",
                "supportedProtocolVersions": SUPPORTED_PROTOCOL_VERSIONS,
            },
        ],
        "_meta": {
            "ai.financial-portfolios/publisher": {
                "developer": {
                    "name": "Financial Portfolios AI",
                    "legalEntity": "Autonomous Intelligent Agents LLC",
                    "url": "https://financial-portfolios.ai",
                    "supportEmail": "support@financial-portfolios.ai",
                },
                "documentationUrl": "https://financial-portfolios.ai/docs",
                "privacyPolicyUrl": "https://financial-portfolios.ai/legal/privacy",
                "termsUrl": "https://financial-portfolios.ai/legal/terms",
                "authentication": "oauth2",
                "disclosure": _DISCLOSURE,
            }
        },
    }


def build_catalog(origin: str) -> dict[str, Any]:
    origin = origin.rstrip("/")
    return {
        "specVersion": "1.0",
        "entries": [
            {
                "identifier": "urn:air:financial-portfolios.ai:mcp:financial-portfolios-ai",
                "type": CARD_MEDIA_TYPE,
                "url": f"{origin}{CARD_PATH}",
            }
        ],
    }


def encode(document: dict[str, Any]) -> tuple[bytes, str]:
    """Stable serialisation and its strong ETag (so If-None-Match can answer 304)."""
    body = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return body, '"' + hashlib.sha256(body).hexdigest()[:32] + '"'
