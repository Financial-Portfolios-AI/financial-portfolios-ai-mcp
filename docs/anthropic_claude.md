# Submitting to the Anthropic Claude Connectors Directory

This guide details the submission process to register **Financial Portfolios AI** in the official **Anthropic Claude Connectors Directory** ([claude.com/docs/connectors/building](https://claude.com/docs/connectors/building)).

---

## 1. Prerequisites

Before initiating the submission:
1. **Live Production Endpoint:** Deploy your MCP server to Google Cloud Run (e.g. `https://financial-portfolios-ai-mcp-<project-id>.a.run.app/mcp`).
2. **Authentication Ready:** The user must be able to log in to `https://financial-portfolios.ai` (via Google Social Login) and generate an API key (`aqat_v1_...`) from `https://financial-portfolios.ai/settings/api-tokens`.
3. **Connector Manifest:** [`claude_connector.json`](../claude_connector.json) contains the metadata, tools, resources, and prompts.
4. **Legal Pages:**
   - Privacy Policy: `https://financial-portfolios.ai/privacy`
   - Terms of Service: `https://financial-portfolios.ai/terms`
5. **Logo:** 512×512 PNG at `https://financial-portfolios.ai/assets/logo-512.png`.

---

## 2. In-Product Submission Process

Anthropic conducts connector reviews through the integrated in-product submission portal:

### Step 1: Access the Submission Portal
1. Log in to your [Claude.ai](https://claude.ai) account (Team, Enterprise, or Developer account).
2. Go to **Settings** -> **Customize** -> **Connectors**.
3. Under the **Developer** or **Directory** section, click **"Submit a Connector"** (or **"Manage Connectors"** -> **"Publish to Directory"**).

### Step 2: Configure Server Details
- **Connector Name:** `Financial Portfolios AI`
- **Description:** `Access quantitative model portfolios, inspect target asset allocations, calculate rebalancing buy/sell orders, and explore institutional investment research.`
- **Transport Type:** Select `Streamable HTTP` (or `SSE`).
- **Endpoint URL:** `https://<your-cloud-run-domain>/mcp`
- **Website URL:** `https://financial-portfolios.ai`
- **Documentation URL:** `https://financial-portfolios.ai/docs`

### Step 3: Configure Authentication
- **Auth Type:** `API Key` / `Bearer Token`
- **Header Name:** `X-API-Key`
- **Help / Instructions for Users:**
  > Sign in to https://financial-portfolios.ai using Google Social Login, go to Settings > API Tokens, generate a personal API Token (`aqat_v1_...`), and paste it here.

### Step 4: Validate Tools & Schema
1. The submission portal will ping your `/mcp` endpoint and execute an automated JSON-RPC handshake (`tools/list`, `resources/list`, `prompts/list`).
2. Verify that all 8 tools are recognized:
   - `list_portfolios`
   - `get_portfolio_allocation`
   - `get_portfolio_history`
   - `rebalance_portfolio`
   - `get_rebalance_template`
   - `list_blog_posts`
   - `get_blog_post`
   - `get_token_info`
3. Provide a test account API key in the reviewer credentials field so Anthropic's team can test execution.

### Step 5: Submit for Review
- Accept the Anthropic Connector Directory Developer Agreement.
- Click **Submit for Review**.
- Review typically takes 3–5 business days.

---

## 3. Reviewer Verification Criteria

During the review process, Anthropic verifies:
1. **Security & Privacy:** Requests use HTTPS; tokens are handled via standard headers (`X-API-Key`); no user credentials are leaked.
2. **Tool Reliability:** Tool calls return valid, typed JSON responses without unhandled 500 exceptions.
3. **Accurate Descriptions:** Each tool has clear docstrings and parameter schemas so Claude knows when and how to invoke it.
4. **Data Isolation:** User permissions are enforced on the backend via the user's personal API token.

---

## 4. Useful Links

- **Anthropic Connector Building Docs:** [claude.com/docs/connectors/building](https://claude.com/docs/connectors/building)
- **Anthropic Help Center:** [support.anthropic.com](https://support.anthropic.com)
- **Model Context Protocol Specification:** [modelcontextprotocol.io](https://modelcontextprotocol.io)
