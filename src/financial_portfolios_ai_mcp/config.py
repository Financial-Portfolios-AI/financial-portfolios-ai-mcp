"""Configuration settings for Financial Portfolios AI MCP Server."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """MCP Server Settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Portal API Endpoint
    portal_base_url: str = Field(
        default="https://financial-portfolios.ai",
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
        default="https://financial-portfolios.ai",
        validation_alias="OAUTH_AUTHORIZATION_SERVER",
        description="Public OAuth 2.1 authorization-server origin (issuer)",
    )
    public_resource_url: str = Field(
        default="https://financial-portfolios.ai/mcp",
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
