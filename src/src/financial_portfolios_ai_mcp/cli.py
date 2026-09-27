"""CLI entry point for running the Financial Portfolios AI MCP Server."""

import asyncio
import logging

import click
import uvicorn

from financial_portfolios_ai_mcp.config import get_settings
from financial_portfolios_ai_mcp.server import mcp_server


def setup_logging(level: str = "INFO") -> None:
    """Configure basic logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


@click.group(invoke_without_command=True)
@click.pass_context
@click.option(
    "--log-level",
    default=None,
    help="Logging level (DEBUG, INFO, WARNING, ERROR)",
)
def main(ctx: click.Context, log_level: str | None) -> None:
    """Financial Portfolios AI MCP Server CLI."""
    settings = get_settings()
    active_log_level = log_level or settings.log_level
    setup_logging(active_log_level)

    if ctx.invoked_subcommand is None:
        # Default to stdio mode when launched without subcommand (e.g. by Claude Desktop)
        asyncio.run(run_stdio())


@main.command(name="stdio")
def stdio_command() -> None:
    """Run MCP server over standard input/output (stdio)."""
    asyncio.run(run_stdio())


async def run_stdio() -> None:
    """Execute MCP server over stdio."""
    await mcp_server.run_stdio_async()


@main.command(name="http")
@click.option("--host", default=None, help="Host to bind (default: 0.0.0.0)")
@click.option("--port", default=None, type=int, help="Port to listen on (default: 8080)")
@click.option("--reload", is_flag=True, default=False, help="Enable auto-reload for development")
def http_command(host: str | None, port: int | None, reload: bool) -> None:
    """Run MCP server via Streamable HTTP & SSE using FastAPI and Uvicorn."""
    settings = get_settings()
    bind_host = host or settings.host
    bind_port = port or settings.port

    uvicorn.run(
        "financial_portfolios_ai_mcp.app:app",
        host=bind_host,
        port=bind_port,
        reload=reload,
        log_level=settings.log_level.lower(),
    )


@main.command(name="sse")
@click.option("--host", default=None, help="Host to bind (default: 0.0.0.0)")
@click.option("--port", default=None, type=int, help="Port to listen on (default: 8080)")
def sse_command(host: str | None, port: int | None) -> None:
    """Run MCP server over Server-Sent Events (SSE)."""
    settings = get_settings()
    bind_host = host or settings.host
    bind_port = port or settings.port

    asyncio.run(mcp_server.run_sse_async(host=bind_host, port=bind_port))


if __name__ == "__main__":
    main()
