"""Authentication and SDK Client management for MCP Server."""

import contextvars
import logging
from typing import Any

from financial_portfolios_ai import AsyncFinancialPortfoliosAIClient, FinancialPortfoliosAIClient

from financial_portfolios_ai_mcp.config import get_settings

logger = logging.getLogger(__name__)

# Context variable to hold per-request API token extracted from inbound HTTP headers (e.g. X-API-Key, Authorization)
current_request_token: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_request_token", default=None
)


def set_request_token(token: str | None) -> contextvars.Token:
    """Set the API token for the current asynchronous request context."""
    return current_request_token.set(token)


def reset_request_token(token_ctx: contextvars.Token) -> None:
    """Reset the API token context variable."""
    current_request_token.reset(token_ctx)


def resolve_api_token(
    explicit_token: str | None = None,
    request_headers: dict[str, Any] | None = None,
) -> str | None:
    """
    Resolve active API token with precedence:
    1. Explicit parameter (if passed programmatically)
    2. Explicit request headers dictionary (if passed directly)
    3. Per-request token from inbound HTTP transport headers (ContextVar)
    4. Settings / Environment variable FINANCIAL_PORTFOLIOS_API_TOKEN (for local stdio)
    """
    if explicit_token and explicit_token.strip():
        return explicit_token.strip()

    if request_headers:
        for header_name in ("x-api-key", "X-API-Key", "authorization", "Authorization"):
            val = request_headers.get(header_name)
            if val and isinstance(val, str) and val.strip():
                clean_val = val.strip()
                if clean_val.lower().startswith("bearer "):
                    clean_val = clean_val[7:].strip()
                if clean_val:
                    return clean_val

    request_token = current_request_token.get()
    if request_token and request_token.strip():
        return request_token.strip()

    settings = get_settings()
    if settings.api_token and settings.api_token.strip():
        return settings.api_token.strip()

    return None


def get_sync_client(
    api_token: str | None = None,
    request_headers: dict[str, Any] | None = None,
) -> FinancialPortfoliosAIClient:
    """Create a synchronous FinancialPortfoliosAIClient with resolved token."""
    settings = get_settings()
    token = resolve_api_token(explicit_token=api_token, request_headers=request_headers)
    return FinancialPortfoliosAIClient(
        base_url=settings.portal_base_url,
        api_token=token,
        timeout=settings.request_timeout,
    )


def get_async_client(
    api_token: str | None = None,
    request_headers: dict[str, Any] | None = None,
) -> AsyncFinancialPortfoliosAIClient:
    """Create an asynchronous AsyncFinancialPortfoliosAIClient with resolved token."""
    settings = get_settings()
    token = resolve_api_token(explicit_token=api_token, request_headers=request_headers)
    return AsyncFinancialPortfoliosAIClient(
        base_url=settings.portal_base_url,
        api_token=token,
        timeout=settings.request_timeout,
    )
