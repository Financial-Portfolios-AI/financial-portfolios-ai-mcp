# Financial Portfolios AI Model Context Protocol (MCP) Server

[![MCP Standard](https://img.shields.io/badge/MCP-2.0.0-blue.svg)](https://modelcontextprotocol.io)
[![Claude Connectors](https://img.shields.io/badge/Claude-Connectors%20Ready-6B46C1.svg)](https://claude.com/docs/connectors/building)
[![OpenAI Compatible](https://img.shields.io/badge/OpenAI-GPT%20Actions%20%26%20MCP-412991.svg)](https://platform.openai.com/docs/actions)
[![Google Vertex AI](https://img.shields.io/badge/Google%20Cloud-Vertex%20AI%20Extension-4285F4.svg)](https://cloud.google.com/vertex-ai)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Official Model Context Protocol (MCP) server for [Financial Portfolios AI](https://financial-portfolios.ai).

This MCP server connects **Claude**, **ChatGPT**, and **Google Gemini** directly to institutional-grade quantitative portfolio strategies, target asset allocation snapshots, portfolio rebalancing engine, and proprietary quantitative research.

---

## Universal Architecture Overview

```
 ┌────────────────────────────────────────────────────────────────────────┐
 │        AI Ecosystem: Claude · ChatGPT · Gemini · Cursor · Windsurf     │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │
                     MCP / OpenAPI Protocols (HTTP / stdio)
                                     │
 ┌───────────────────────────────────▼────────────────────────────────────┐
 │           Financial Portfolios AI MCP Server (Google Cloud Run)        │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │
                            REST & WebSocket API
                                     │
 ┌───────────────────────────────────▼────────────────────────────────────┐
 │         Customer Portal Backend (https://financial-portfolios.ai)      │
 └────────────────────────────────────────────────────────────────────────┘
```

- **Remote MCP (Claude Connectors & ChatGPT Apps):** Streamable HTTP (`/mcp`) and Server-Sent Events (`/sse`), hosted on **Google Cloud Run**.
- **OpenAPI REST Actions (ChatGPT Custom GPTs & Google Vertex AI):** Defined via [`openapi.yaml`](openapi.yaml).
- **Local MCP (Claude Desktop, Gemini CLI, Cursor, Windsurf):** Runs via standard I/O (`stdio`).

---

## Authentication

1. Visit [financial-portfolios.ai](https://financial-portfolios.ai) and sign in using **Google Social Login** (or email credentials).
2. Go to **Settings > API Tokens** (or [financial-portfolios.ai/settings/api-tokens](https://financial-portfolios.ai/settings/api-tokens)).
3. Click **Generate API Token**.
4. Copy your token (starts with `aqat_v1_...`).

---

## Multi-Platform Ecosystem Setup

### 1. Claude AI (`claude.ai` Connectors & Claude Desktop)

- **Claude Web Custom Connector:**
  1. Go to **Customize > Connectors** -> **Add custom connector**.
  2. Enter URL `https://<your-cloud-run-domain>/mcp` and header `X-API-Key: aqat_v1_<token>`.
- **Directory Manifest:** Uses [`claude_connector.json`](claude_connector.json).
- **Claude Desktop Config:** See [`mcp_clients.json`](mcp_clients.json) for `claude_desktop_config.json`.

---

### 2. OpenAI ChatGPT (Custom GPTs & MCP Apps)

- **ChatGPT Custom GPT Actions (GPT Store):**
  1. Open [ChatGPT GPT Builder](https://chatgpt.com/gpts/editor) -> **Configure** -> **Actions** -> **Create new action**.
  2. Paste the contents of [`openapi.yaml`](openapi.yaml).
  3. Under **Authentication**, choose **API Key**, Auth Type: **Custom**, Header Name: `X-API-Key`.
- **ChatGPT MCP Apps (Enterprise & Workspace):**
  - Add Remote MCP endpoint `https://<your-cloud-run-domain>/mcp` with [`chatgpt_manifest.json`](chatgpt_manifest.json).

---

### 3. Google Gemini & Google Cloud Vertex AI

- **Google Vertex AI Agent Builder & Extensions:**
  - Import [`gemini_extension.json`](gemini_extension.json) alongside [`openapi.yaml`](openapi.yaml) to register the extension.
- **Gemini CLI:**
  ```bash
  gemini mcp add --transport http financial-portfolios-ai https://<your-domain>/mcp --header 'X-API-Key: aqat_v1_<token>'
  ```

---

### 4. Developer IDEs (Cursor & Windsurf)

- **Cursor IDE (`.cursor/mcp.json`):**
  ```json
  {
    "mcpServers": {
      "financial-portfolios-ai": {
        "url": "https://<your-cloud-run-domain>/mcp",
        "headers": { "X-API-Key": "aqat_v1_your_token_here" }
      }
    }
  }
  ```
- **Windsurf IDE (`~/.codeium/windsurf/mcp_config.json`):**
  See [`mcp_clients.json`](mcp_clients.json) for details.

---

## Capabilities Reference

### 🛠️ Tools

| Tool Name | Description | Arguments |
| :--- | :--- | :--- |
| `list_portfolios` | List all accessible quantitative portfolios under active subscription. | `api_token` (optional) |
| `get_portfolio_allocation` | Retrieve latest or historical target allocation snapshot, position weights, expected return, and volatility. | `portfolio_code`, `as_of` (optional), `api_token` (optional) |
| `get_portfolio_history` | Retrieve historical allocation timeline for up to 365 days. | `portfolio_code`, `days` (1-365), `api_token` (optional) |
| `rebalance_portfolio` | Calculate BUY/SELL rebalancing orders to match target allocation given current user holdings. | `portfolio_code`, `holdings` (JSON list or CSV), `as_of` (optional) |
| `get_rebalance_template` | Download sample holdings CSV template and formatting instructions. | `api_token` (optional) |
| `list_blog_posts` | Search and list published research articles, macro updates, and commentaries. | `page`, `page_size`, `search` (optional) |
| `get_blog_post` | Read full content of a published research article by slug. | `slug`, `api_token` (optional) |
| `get_token_info` | Inspect API token metadata, usage rate limits, and subscription status. | `api_token` (optional) |

### 📦 Resources

| URI | Name | Description |
| :--- | :--- | :--- |
| `portfolios://catalog` | Portfolio Catalog | Live catalog of all available quantitative portfolios. |
| `portfolios://{portfolio_code}/allocation` | Portfolio Allocation | Dynamic resource for current allocation of any portfolio. |
| `research://posts/latest` | Latest Research | Most recent quantitative market research publications. |

### 💡 Prompts

| Prompt Name | Description | Parameters |
| :--- | :--- | :--- |
| `portfolio_review` | Step-by-step prompt guiding Claude to perform an in-depth analysis of risk, sector exposure, and top holdings. | `portfolio_code` (e.g. `AQA_AGGRESSIVE`) |
| `rebalance_advisor` | Interactive workflow guiding the investor through comparing current holdings with target model and reviewing buy/sell orders. | `portfolio_code` (e.g. `AQA_AGGRESSIVE`) |
| `market_research_digest` | Synthesizes recent quantitative research articles into an executive macro and factor summary. | None |

---

## Google Cloud Run Deployment

```bash
# 1. Build and push container with Cloud Build
gcloud builds submit --config=cloudbuild.yaml

# 2. Deploy to Cloud Run
gcloud run deploy financial-portfolios-ai-mcp \
  --image gcr.io/<YOUR_PROJECT_ID>/financial-portfolios-ai-mcp:latest \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars FINANCIAL_PORTFOLIOS_BASE_URL=https://financial-portfolios.ai
```

### Health Endpoints

- `GET /` - Root status, version, and endpoints metadata
- `GET /healthz` - Health and readiness check
- `GET /livez` - Kubernetes/Cloud Run liveness probe
- `POST /mcp` - Streamable HTTP MCP endpoint
- `GET /sse` - Server-Sent Events MCP endpoint

---

## Local Development & Testing

```bash
# 1. Install dependencies
uv sync --all-extras

# 2. Run unit tests
uv run pytest tests/ -v

# 3. Run linter
uv run ruff check .

# 4. Start local development server (Streamable HTTP & SSE on port 8080)
uv run financial-portfolios-ai-mcp http --port 8080 --reload
```

---

## License

MIT License. Copyright (c) 2026 Financial Portfolios AI Team.
