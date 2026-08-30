"""FastAPI ASGI application wrapping the MCP server for Cloud Run / HTTP hosting."""

import importlib.resources
import logging
from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from financial_portfolios_ai_mcp.auth import reset_request_token, set_request_token
from financial_portfolios_ai_mcp.config import get_settings
from financial_portfolios_ai_mcp.server import mcp_server

logger = logging.getLogger(__name__)

# Transport mounts that carry MCP traffic. A tokenless request to one of these is
# challenged with a 401 so OAuth-capable clients begin the authorization flow;
# the well-known/health/root/openapi routes are always public.
_PROTECTED_PREFIXES = ("/mcp", "/sse")


def _header(scope, name: bytes) -> str | None:
    for h_name, h_val in scope.get("headers", []):
        if h_name.lower() == name:
            return h_val.decode("latin1").strip()
    return None


def _resource_metadata_url(scope) -> str:
    """Public URL of THIS server's RFC 9728 protected-resource metadata, derived
    from the request so it is correct behind a proxy (X-Forwarded-Proto/Host)."""
    proto = _header(scope, b"x-forwarded-proto")
    host = _header(scope, b"x-forwarded-host") or _header(scope, b"host")
    if host:
        scheme = (proto or scope.get("scheme") or "https").split(",")[0].strip()
        return f"{scheme}://{host}/.well-known/oauth-protected-resource"
    # Fallback to the configured public resource origin.
    origin = get_settings().public_resource_url.rstrip("/")
    for suffix in ("/mcp", "/sse"):
        if origin.endswith(suffix):
            origin = origin[: -len(suffix)]
    return f"{origin.rstrip('/')}/.well-known/oauth-protected-resource"


class InboundAuthHeaderASGIMiddleware:
    """
    Pure ASGI middleware that extracts the incoming API token from HTTP headers
    (X-API-Key or Authorization: Bearer) and binds it to the current
    asynchronous request context (ContextVar) before dispatching to mounted apps or routes.

    It ALSO issues the OAuth 2.1 challenge (RFC 9728 / MCP authorization spec): a
    tokenless request to an MCP transport path gets `401` with
    `WWW-Authenticate: Bearer resource_metadata="…"`, which is what makes an
    OAuth-capable client (Claude, ChatGPT) discover the authorization server and
    start the flow. Requests that already carry a credential (an `aqat_v1_` key or
    an OAuth Bearer token) pass straight through and are validated downstream by the
    portal `/api/v1` resource server (`get_api_or_oauth_user`). The challenge can be
    disabled with OAUTH_CHALLENGE_ENABLED=false for pure header-token deployments.

    Security note: Query parameter tokens are intentionally NOT accepted to prevent
    credential leakage into server access logs, browser history, and proxy logs.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            token = None

            # Iterate over raw ASGI header tuples: (bytes, bytes)
            for h_name, h_val in scope.get("headers", []):
                name_str = h_name.decode("latin1").lower()
                if name_str == "x-api-key":
                    token = h_val.decode("latin1").strip()
                    break
                elif name_str == "authorization":
                    val_str = h_val.decode("latin1").strip()
                    if val_str.lower().startswith("bearer "):
                        token = val_str[7:].strip()
                        break

            # OAuth challenge: tokenless MCP request → 401 pointing at our
            # protected-resource metadata (skip CORS preflight and public routes).
            path = scope.get("path", "")
            method = scope.get("method", "GET").upper()
            if (
                not token
                and method != "OPTIONS"
                and any(path.startswith(p) for p in _PROTECTED_PREFIXES)
                and get_settings().oauth_challenge_enabled
            ):
                await self._challenge(scope, send)
                return

            # Bind token to context variable for downstream tools in mounted apps
            token_ctx = set_request_token(token)
            try:
                await self.app(scope, receive, send)
            finally:
                reset_request_token(token_ctx)
            return

        await self.app(scope, receive, send)

    async def _challenge(self, scope, send) -> None:
        meta = _resource_metadata_url(scope)
        body = (
            b'{"error":"unauthorized",'
            b'"error_description":"Authentication required. Present an OAuth 2.1 Bearer '
            b'token or an X-API-Key (aqat_v1_...).",'
            b'"resource_metadata":"' + meta.encode("latin1") + b'"}'
        )
        headers = [
            (b"content-type", b"application/json"),
            (b"www-authenticate", f'Bearer resource_metadata="{meta}"'.encode("latin1")),
            (b"content-length", str(len(body)).encode("latin1")),
        ]
        await send({"type": "http.response.start", "status": 401, "headers": headers})
        await send({"type": "http.response.body", "body": body})


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context."""
    settings = get_settings()
    logger.info(
        f"Starting Financial Portfolios AI MCP Server on {settings.host}:{settings.port} "
        f"(Target Portal: {settings.portal_base_url})"
    )
    yield
    logger.info("Stopping Financial Portfolios AI MCP Server")


def create_app() -> FastAPI:
    """Create FastAPI application with MCP endpoints, auth middleware, and health checks."""
    settings = get_settings()

    # Build the transport sub-apps with ROOT internal paths so that mounting at
    # /mcp and /sse yields the advertised public URLs (default path is /mcp, which
    # mounted at /mcp would produce /mcp/mcp).
    #
    # stateless_http=True: this server is a pure, stateless tool proxy (no
    # server-initiated messages, no subscriptions). Stateful mode keeps per-session
    # state in memory and intermittently 404s "Session not found" when a client
    # (e.g. LM Studio) POSTs `notifications/initialized`/`tools/list` right after
    # `initialize`, before the session is registered — a race clients don't retry.
    # Stateless mode makes every request self-contained, so that error is
    # impossible, and it is also required for correctness on multi-instance /
    # autoscaled hosts (Cloud Run) where in-memory sessions don't survive
    # cross-instance routing.
    streamable_app = mcp_server.streamable_http_app(
        streamable_http_path="/",
        stateless_http=True,
    )
    sse_app = mcp_server.sse_app(sse_path="/", message_path="/messages/")

    # Combined lifespan: mounting a Starlette sub-app into FastAPI does NOT run the
    # sub-app's lifespan, and the MCP StreamableHTTP/SSE session managers start their
    # task group there — without this every /mcp request 500s with
    # "Task group is not initialized". Enter both sub-app lifespans for the app's life.
    @asynccontextmanager
    async def combined_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        logger.info(
            f"Starting Financial Portfolios AI MCP Server on {settings.host}:{settings.port} "
            f"(Target Portal: {settings.portal_base_url})"
        )
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(streamable_app.router.lifespan_context(streamable_app))
            await stack.enter_async_context(sse_app.router.lifespan_context(sse_app))
            yield
        logger.info("Stopping Financial Portfolios AI MCP Server")

    app = FastAPI(
        title="Financial Portfolios AI MCP Server",
        description="Remote Model Context Protocol (MCP) server for Claude Connectors, ChatGPT, and Gemini.",
        version="1.0.0",
        lifespan=combined_lifespan,
    )

    # Inbound auth header extractor (pure ASGI middleware for reliable ContextVar propagation into mounts)
    app.add_middleware(InboundAuthHeaderASGIMiddleware)

    # Enable open CORS for web-based clients (e.g. Claude Web, ChatGPT)
    # allow_credentials is intentionally False because authentication is header-based (no cookies)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["X-API-Key", "Authorization", "Content-Type"],
    )

    @app.get("/", summary="Root status and metadata")
    async def root() -> JSONResponse:
        return JSONResponse({
            "service": "financial-portfolios-ai-mcp",
            "version": "1.0.0",
            "portal": settings.portal_base_url,
            "status": "online",
            "transports": {
                "streamable_http": "/mcp",
                "sse": "/sse",
            },
            "docs": "https://financial-portfolios.ai/docs",
            "openapi": {
                "yaml": "/openapi.yaml",
                "json": "/openapi.json",
            },
        })

    @app.get("/.well-known/oauth-protected-resource", summary="OAuth 2.1 protected-resource metadata")
    async def protected_resource_metadata() -> JSONResponse:
        # Tells OAuth clients (Claude directory, ChatGPT Apps) which authorization
        # server issues tokens for this resource. RFC 9728.
        return JSONResponse({
            "resource": settings.public_resource_url,
            "authorization_servers": [settings.authorization_server_url.rstrip("/")],
            "bearer_methods_supported": ["header"],
            "scopes_supported": ["portfolios:read", "research:read", "rebalance:write"],
        })

    @app.get("/healthz", summary="Liveness & Readiness probe")
    async def healthz() -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "financial-portfolios-ai-mcp"})

    @app.get("/livez", summary="Kubernetes / Cloud Run liveness probe")
    async def livez() -> JSONResponse:
        return JSONResponse({"status": "alive"})

    @app.get("/openapi.yaml", summary="Serve OpenAPI specification in YAML format")
    async def get_openapi_yaml() -> Response:
        # 1. Try loading via package resources (reliable in site-packages and container builds)
        try:
            traversable = importlib.resources.files("financial_portfolios_ai_mcp") / "openapi.yaml"
            if traversable.is_file():
                return PlainTextResponse(
                    traversable.read_text(encoding="utf-8"), media_type="text/yaml"
                )
        except (FileNotFoundError, ModuleNotFoundError, TypeError, ValueError, OSError) as exc:
            logger.debug("Package resource openapi.yaml not found: %s", exc)

        # 2. Fallback to local file candidates
        for candidate in [
            Path("openapi.yaml"),
            Path(__file__).resolve().parent / "openapi.yaml",
            Path(__file__).resolve().parent.parent.parent / "openapi.yaml",
        ]:
            if candidate.exists():
                return PlainTextResponse(
                    candidate.read_text(encoding="utf-8"), media_type="text/yaml"
                )

        return PlainTextResponse("OpenAPI specification not found", status_code=404)

    # Mount the transport sub-apps (built above with root paths; their lifespans
    # are run by combined_lifespan). Public URLs: /mcp (Streamable HTTP) and /sse.
    app.mount("/mcp", streamable_app)
    app.mount("/sse", sse_app)

    return app


app = create_app()
