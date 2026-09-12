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
  2. Enter the server URL `https://financial-portfolios.ai/mcp` and sign in when prompted.
     Authentication is OAuth 2.1 - there is no API key to paste. A tokenless request is
     answered with a `401` + `WWW-Authenticate: Bearer resource_metadata=...` (RFC 9728),
     which is what starts the sign-in flow.
  3. Command-line clients (Claude Code) do not run that flow: they pass a personal token as
     an `X-API-Key` header instead (see [Authentication](#authentication)).
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
| `list_portfolios` | List every active quantitative portfolio, each marked `access` = `subscribed` or `public_delayed`. | `api_token` (optional) |
| `get_portfolio_allocation` | Retrieve a target allocation snapshot: the latest book when subscribed, otherwise the public book delayed ~45 days. | `portfolio_code`, `as_of` (optional), `api_token` (optional) |
| `get_portfolio_history` | Retrieve historical allocation timeline for up to 365 days (delayed entries only for non-subscribers). | `portfolio_code`, `days` (1-365), `api_token` (optional) |
| `rebalance_portfolio` | Calculate BUY/SELL rebalancing orders to match target allocation given current user holdings. **Requires an active subscription.** | `portfolio_code`, `holdings` (JSON list or CSV), `as_of` (optional) |
| `get_rebalance_template` | Download sample holdings CSV template and formatting instructions. | `api_token` (optional) |
| `list_blog_posts` | Search and list published research articles, macro updates, and commentaries. | `page`, `page_size`, `search` (optional) |
| `get_blog_post` | Read full content of a published research article by slug. | `slug`, `api_token` (optional) |
| `get_token_info` | Inspect API token metadata, usage rate limits, and subscription status. | `api_token` (optional) |

#### Access levels

Portfolio reads serve one of two books, and every response says which via `access`, `delayed`,
`as_of` and `lag_days`:

| | `subscribed` | `public_delayed` |
| :--- | :--- | :--- |
| Holdings | latest book | dated `<= today - 45 days` (`PUBLIC_HOLDINGS_LAG_DAYS`) |
| Position fields | ticker, weight, sector, expected return, expected volatility | ticker, weight, sector only |
| `equity_exposure` / `cash_allocation` / `effective_n` | populated | `null` |
| `rebalance_portfolio` | allowed | 403 - subscription required |

A portfolio code that is not an active public product returns **404**, deliberately
indistinguishable from an unknown code.

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
- `GET /mcp/assets/{filename}` - Public brand icons (`icon-16|32|48|64|128|192|256|512.png`, `favicon.ico`)
- `GET /mcp/manifests/{filename}` - Provider manifest rendered for the requesting origin
- `GET /favicon.ico` - Favicon

---

## Branding & Icons

The server ships its logo so Claude, ChatGPT, Gemini and IDE clients render it next
to the connector and its tool calls:

- **In the protocol** - `initialize` returns `serverInfo.icons` (MCP `Implementation.icons`,
  spec revision 2025-11-25). The first entry is an inline 48x48 `data:` URI, so the icon
  also appears for local **stdio** clients with no HTTP server to fetch from; 192x192 and
  512x512 follow as absolute HTTPS URLs.
- **Over HTTP** - the PNG/ICO set is served unauthenticated from `/mcp/assets/` with a
  one-week immutable cache header. It sits under `/mcp` because that is the prefix the
  portal load balancer routes to this service; top-level `/assets/*` belongs to the portal
  backend's own assets router, so an icon URL there would never reach us. The OAuth
  challenge explicitly exempts `/mcp/assets` and `/mcp/manifests` so directories can fetch
  them with no credential.
- **In the manifests** - `claude_connector.json`, `chatgpt_manifest.json` and
  `gemini_extension.json` point their `icon_url` / `logo_url` / `icon_uri` at the same files,
  through the `${PUBLIC_ORIGIN}` placeholder (see [Manifests](#manifests)).

Sources live in `src/financial_portfolios_ai_mcp/assets/` and ship inside the wheel.

No environment hostname is hardcoded. The absolute URLs resolve in this order:

1. the origin the request arrived on (`X-Forwarded-Proto` / `X-Forwarded-Host`, set by
   the load balancer and Cloud Run) - so `/` always advertises the hostname the caller used;
2. `MCP_PUBLIC_BASE_URL`, for the `initialize` handshake, which has no request origin to
   read (set it when the MCP service answers on its own hostname rather than through the portal);
3. `MCP_PUBLIC_URL` with the transport path stripped.

A dev deployment therefore advertises `https://dev.financial-portfolios.ai/assets/...`
purely from its deploy substitution:

```bash
gcloud builds submit --config cloudbuild.yaml \
  --substitutions=_PORTAL_ORIGIN=https://dev.financial-portfolios.ai,_MCP_PUBLIC_BASE_URL=https://dev.financial-portfolios.ai
```

## Manifests

The three provider manifests are **templates**, not environment-specific files: every
absolute URL in them is written as `${PUBLIC_ORIGIN}/...`, so one document per provider
serves prod, dev and anything else. Nothing in the repo hardcodes a deployment hostname.

Get a submittable manifest either way:

```bash
# offline, for directory submission
python scripts/render_manifests.py --env prod        # -> build/manifests/prod/
python scripts/render_manifests.py --env dev         # -> build/manifests/dev/
python scripts/render_manifests.py --origin https://staging.financial-portfolios.ai

# or from a running deployment, rendered against the origin you reached it on
curl https://dev.financial-portfolios.ai/mcp/manifests/claude_connector.json
```

`GET /mcp/manifests/<name>` is the authoritative rendering: it fills in the origin the
request arrived on, so the dev deployment always hands out dev URLs and the prod
deployment prod URLs, with no build step and nothing to keep in sync. `GET /` lists the
available manifests. A test asserts the committed templates never regain a hardcoded
origin, and another asserts the script and the endpoint produce identical documents.

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

### End-to-end smoke test

`scripts/smoke_test.py` exercises a running server over Streamable HTTP with the
standard library only (no deps): `/healthz` → `initialize` → `tools/list`, and —
if you pass an API token — real `tools/call` round-trips (`list_portfolios` →
`get_portfolio_allocation`). It also regression-checks that
`get_portfolio_allocation` advertises the words "holdings"/"positions" so that a
prompt like *"show me my portfolio holdings"* actually invokes it.

```bash
# Handshake + tools/list + phrasing check (no credentials needed)
python scripts/smoke_test.py

# Full path incl. entitled data (generate a token at the portal /api-access)
python scripts/smoke_test.py --token aqat_v1_xxxxx
# or:  MCP_URL=http://localhost:8090/mcp/ MCP_TOKEN=aqat_v1_xxxxx python scripts/smoke_test.py
```

Exit code is 0 only if every executed check passes.

> **Local docker-compose:** the compose file defaults `FINANCIAL_PORTFOLIOS_BASE_URL`
> to the production origin. To point the server at a local portal backend on the
> shared docker network, create a (gitignored) `.env` next to `docker-compose.yml`
> with `FINANCIAL_PORTFOLIOS_BASE_URL=http://aqa-portal-backend:8000` and
> `docker compose up -d`.

---

## License

MIT License. Copyright (c) 2026 Financial Portfolios AI Team.
