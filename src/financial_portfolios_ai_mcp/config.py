"""Configuration settings for Financial Portfolios AI MCP Server."""

from functools import lru_cache
from urllib.parse import urlparse

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from financial_portfolios_ai_mcp.environments import ENVIRONMENTS


class Settings(BaseSettings):
    """MCP Server Settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Which deployment to talk to. There is deliberately no default: the target is chosen
    # when the server is deployed or run, never baked into the code. Naming an environment
    # fills in every URL below; any URL set explicitly still wins.
    environment: str | None = Field(
        default=None,
        validation_alias="FINANCIAL_PORTFOLIOS_ENV",
        description="Target deployment: " + " or ".join(sorted(ENVIRONMENTS)),
    )

    # Portal API Endpoint
    portal_base_url: str = Field(
        default="",
        validation_alias="FINANCIAL_PORTFOLIOS_BASE_URL",
        description="Base URL for Financial Portfolios AI portal backend",
    )

    # Optional default API token (for local/single-user MCP usage)
    api_token: str | None = Field(
        default=None,
        validation_alias="FINANCIAL_PORTFOLIOS_API_TOKEN",
        description="Personal API Token (aqat_v1_...) from portal",
    )

    # OAuth 2.1 (for listed/marketplace connectors). The PUBLIC authorization-server
    # origin (the portal's issuer) advertised in /.well-known/oauth-protected-resource,
    # and this server's own PUBLIC URL (the protected resource / audience).
    authorization_server_url: str = Field(
        default="",
        validation_alias="OAUTH_AUTHORIZATION_SERVER",
        description="Public OAuth 2.1 authorization-server origin (issuer)",
    )
    public_resource_url: str = Field(
        default="",
        validation_alias="MCP_PUBLIC_URL",
        description="This MCP server's public URL (OAuth protected-resource identifier)",
    )
    public_base_url: str | None = Field(
        default=None,
        validation_alias="MCP_PUBLIC_BASE_URL",
        description=(
            "Public origin this server is reachable at, used to build absolute icon "
            "URLs (/assets/...) advertised to MCP clients. Defaults to the origin of "
            "MCP_PUBLIC_URL with the transport path stripped."
        ),
    )
    oauth_challenge_enabled: bool = Field(
        default=True,
        validation_alias="OAUTH_CHALLENGE_ENABLED",
        description=(
            "Return a 401 WWW-Authenticate challenge on tokenless MCP requests so "
            "OAuth-capable clients begin the authorization flow. Set false for pure "
            "header-token (aqat_v1_) deployments where no client performs OAuth."
        ),
    )

    # Server runtime settings
    host: str = Field(
        default="0.0.0.0",
        validation_alias="MCP_HOST",
        description="Host to bind HTTP/SSE server",
    )
    port: int = Field(
        default=8080,
        validation_alias="MCP_PORT",
        description="Port to listen on",
    )
    # Transient portal failures (5xx, dropped connections) are retried; 4xx never is.
    portal_retries: int = Field(
        default=2,
        validation_alias="MCP_PORTAL_RETRIES",
        description="Retries for a failed portal read (0 disables)",
    )
    portal_retry_base_delay: float = Field(
        default=0.25,
        validation_alias="MCP_PORTAL_RETRY_BASE_DELAY",
        description="First retry delay in seconds; doubles per attempt, with jitter",
    )
    # Short per-credential caches. The Explorer reads every portfolio for its search and
    # comparison views, and each tab switch would otherwise ask the portal again.
    cache_ttl_portfolios: float = Field(
        default=30.0,
        validation_alias="MCP_CACHE_TTL_PORTFOLIOS",
        description="Seconds to cache the portfolio list (0 disables)",
    )
    cache_ttl_allocation: float = Field(
        default=60.0,
        validation_alias="MCP_CACHE_TTL_ALLOCATION",
        description="Seconds to cache an allocation snapshot (0 disables)",
    )
    cache_ttl_history: float = Field(
        default=120.0,
        validation_alias="MCP_CACHE_TTL_HISTORY",
        description="Seconds to cache allocation history (0 disables)",
    )
    cache_ttl_research: float = Field(
        default=120.0,
        validation_alias="MCP_CACHE_TTL_RESEARCH",
        description="Seconds to cache research listings and articles (0 disables)",
    )
    log_level: str = Field(
        default="INFO",
        validation_alias="MCP_LOG_LEVEL",
        description="Logging level",
    )
    request_timeout: float = Field(
        default=30.0,
        validation_alias="MCP_REQUEST_TIMEOUT",
        description="HTTP request timeout in seconds",
    )

    # DNS-rebinding / Host-header allow-list for the Streamable-HTTP + SSE transports
    # (mcp.server.transport_security). The SDK rejects any request whose Host header
    # is not on this list with 421 Misdirected Request. Behind the portal load
    # balancer the forwarded Host is the public portal domain (e.g.
    # dev.financial-portfolios.ai), which must be present or the connector handshake
    # silently fails AFTER OAuth. Leave unset to auto-derive from the configured
    # portal / resource / issuer URLs (plus localhost); set MCP_ALLOWED_HOSTS to a
    # comma-separated list to override (e.g. add a custom domain).
    allowed_hosts_override: str | None = Field(
        default=None,
        validation_alias="MCP_ALLOWED_HOSTS",
        description="Comma-separated Host allow-list override for the MCP transports",
    )

    @model_validator(mode="after")
    def _resolve_target(self) -> "Settings":
        """Fill the URLs from FINANCIAL_PORTFOLIOS_ENV, and refuse to start without a target."""
        if self.environment:
            env = self.environment.strip().lower()
            if env not in ENVIRONMENTS:
                raise ValueError(
                    f"FINANCIAL_PORTFOLIOS_ENV={self.environment!r} is not one of {sorted(ENVIRONMENTS)}"
                )
            origin = ENVIRONMENTS[env]
            self.portal_base_url = self.portal_base_url or origin
            self.authorization_server_url = self.authorization_server_url or origin
            self.public_resource_url = self.public_resource_url or f"{origin}/mcp"
        if not self.portal_base_url:
            raise ValueError(
                "No target deployment. Set FINANCIAL_PORTFOLIOS_ENV to "
                + " or ".join(sorted(ENVIRONMENTS))
                + ", or FINANCIAL_PORTFOLIOS_BASE_URL explicitly."
            )
        # An explicit portal URL alone (local stdio, tests) serves as issuer and resource too.
        self.authorization_server_url = self.authorization_server_url or self.portal_base_url
        self.public_resource_url = self.public_resource_url or f"{self.portal_base_url.rstrip('/')}/mcp"
        return self

    @property
    def allowed_hosts(self) -> list[str]:
        """Resolved Host allow-list for the transport security middleware.

        Exact-match only in the SDK (plus a `host:*` any-port form), so every host
        is added both bare and with `:*`. Origin is not enforced here — Claude's
        server-to-server POST sends no Origin, and the SDK allows an absent Origin.
        """
        if self.allowed_hosts_override:
            return [h.strip() for h in self.allowed_hosts_override.split(",") if h.strip()]
        hosts: set[str] = {"localhost", "127.0.0.1"}
        # public_base_url is included because it is precisely the case where this
        # server answers on its own hostname rather than the portal's: leaving it
        # out would 421 every MCP request to that host.
        for url in (
            self.public_resource_url,
            self.portal_base_url,
            self.authorization_server_url,
            self.public_base_url or self.public_resource_url,
        ):
            hostname = urlparse(url).hostname
            if hostname:
                hosts.add(hostname)
        # Add an any-port form for each so a Host with an explicit port also matches.
        return sorted(hosts | {f"{h}:*" for h in hosts})

    def public_origin(self) -> str:
        """Public origin of this server (no transport path), used for absolute
        asset and well-known URLs."""
        if self.public_base_url:
            return self.public_base_url.rstrip("/")
        origin = self.public_resource_url.rstrip("/")
        for suffix in ("/mcp", "/sse"):
            origin = origin.removesuffix(suffix)
        return origin.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
