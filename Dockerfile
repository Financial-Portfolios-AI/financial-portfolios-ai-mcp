# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

WORKDIR /app

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy local SDK dependency from build context. Destination must match the
# editable path in pyproject.toml ([tool.uv.sources] financial-portfolios-ai =
# { path = "../financial-portfolios-ai-sdk" } → resolves to /financial-portfolios-ai-sdk
# from WORKDIR /app), otherwise `uv pip install .` fails to resolve the SDK source.
COPY financial-portfolios-ai-sdk /financial-portfolios-ai-sdk

# Copy MCP package definitions from build context
COPY financial-portfolios-ai-mcp/pyproject.toml financial-portfolios-ai-mcp/README.md ./
COPY financial-portfolios-ai-mcp/src/ ./src/
COPY financial-portfolios-ai-mcp/openapi.yaml ./openapi.yaml
# All three provider manifest templates: pyproject force-includes them into the
# wheel so the server can render them at /manifests/<name>.
COPY financial-portfolios-ai-mcp/claude_connector.json financial-portfolios-ai-mcp/chatgpt_manifest.json financial-portfolios-ai-mcp/gemini_extension.json ./

# Create virtualenv and install all dependencies
RUN uv venv /app/.venv
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Install SDK and MCP server
RUN uv pip install /financial-portfolios-ai-sdk
RUN uv pip install .

# ==============================================================================
# Production Runner
# ==============================================================================
FROM python:3.12-slim AS runner

WORKDIR /app

# Create non-root system user for security
RUN groupadd -r mcpuser && useradd -r -g mcpuser -d /app -s /sbin/nologin mcpuser

# Copy virtualenv from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/openapi.yaml ./openapi.yaml
COPY --from=builder /app/claude_connector.json /app/chatgpt_manifest.json /app/gemini_extension.json ./
# The SDK is installed editable ([tool.uv.sources] editable=true), so its source
# tree must exist at the same path at runtime for the .pth import to resolve.
COPY --from=builder /financial-portfolios-ai-sdk /financial-portfolios-ai-sdk

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8080
ENV PORT=8080

USER mcpuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz').read()" || exit 1

# Cloud Run execution entry point
CMD ["uvicorn", "financial_portfolios_ai_mcp.app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
