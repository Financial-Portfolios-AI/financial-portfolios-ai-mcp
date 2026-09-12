# Submitting to the OpenAI ChatGPT Marketplace (GPT Store & MCP Apps)

This guide details how to publish **Financial Portfolios AI** to the **OpenAI GPT Store** and register it in the **OpenAI Apps / MCP Directory**.

---

## 1. Publishing to the OpenAI GPT Store (Custom GPTs)

Custom GPTs allow any ChatGPT user (Free, Plus, Team, Enterprise) to find and use your application in the public **GPT Store**.

### Step 1: Create a New Custom GPT
1. Log in to [ChatGPT](https://chatgpt.com).
2. Click on **Explore GPTs** -> **+ Create** (or navigate directly to [chatgpt.com/gpts/editor](https://chatgpt.com/gpts/editor)).
3. Switch to the **Configure** tab.

### Step 2: Fill in GPT Details
- **Name:** `Financial Portfolios AI`
- **Description:** `Quantitative portfolio manager: analyze target allocations, calculate rebalancing buy/sell orders, and access institutional market research.`
- **Instructions:**
  ```markdown
  You are the official Financial Portfolios AI assistant.
  Your role is to help investors analyze quantitative model portfolios, review asset allocation snapshots, and calculate brokerage rebalancing orders.

  Guidelines:
  1. When asked about available strategies, call `listPortfolios`.
  2. When asked about current holdings or allocation, call `getPortfolioAllocation` with the portfolio code (e.g. AQA_AGGRESSIVE).
  3. When the user provides their current holdings, invoke `rebalancePortfolio` to generate buy/sell recommendations.
  4. Always present financial data in clean markdown tables.
  ```
- **Conversation Starters:**
  - *"Show me the current allocation for the Aggressive Growth portfolio."*
  - *"Help me rebalance my portfolio to match AQA_BALANCED."*
  - *"What are the latest quantitative research articles?"*
  - *"List all available investment models."*
- **Logo / Icon:** Upload your 512×512 logo from `https://financial-portfolios.ai/assets/logo-512.png`.

### Step 3: Add OpenAPI Actions
1. Scroll to **Actions** -> click **Create new action**.
2. Open [`openapi.yaml`](../openapi.yaml) from this repository, copy its entire contents, and paste it into the **Schema** box.
3. Under **Authentication**:
   - Authentication Type: `API Key`
   - Auth Type: `Custom`
   - Custom Header Name: `X-API-Key`
4. Under **Privacy Policy**:
   - URL: `https://financial-portfolios.ai/privacy`

### Step 4: Verify Builder Profile (Domain Verification)
To list your GPT publicly on the GPT Store under your verified brand:
1. In ChatGPT, click your profile name (bottom left) -> **Settings** -> **Builder Profile**.
2. Under **Links**, toggle **Select a domain** and click **Verify a new domain**.
3. Enter `financial-portfolios.ai`.
4. Copy the generated `TXT` record and add it to your DNS settings (Cloudflare / Google Cloud DNS).
5. Click **Verify**. Once verified, your GPT will display the badge `By financial-portfolios.ai`.

### Step 5: Publish to the GPT Store
1. In the top right corner of the GPT Builder, click **Publish** (or **Update**).
2. Under "Who can access this GPT?", select **"Everyone"** (Public).
3. Select the **Finance & Investing** category.
4. Click **Confirm**. Your GPT is now live in the GPT Store!

---

## 2. Registering with OpenAI MCP Apps (Enterprise & Workspace)

For organizations and enterprise workspaces using OpenAI's **Model Context Protocol (MCP)** integration:

### Step 1: Open OpenAI Developer Dashboard
1. Go to [platform.openai.com/apps](https://platform.openai.com).
2. Under **Workspace Integrations** -> **MCP Apps**, click **"Add Remote MCP App"**.

### Step 2: Configure Endpoint & Manifest
- **App Name:** `Financial Portfolios AI`
- **Transport:** `Streamable HTTP`
- **MCP Endpoint URL:** `https://<your-cloud-run-domain>/mcp`
- **App Manifest URL:** `https://financial-portfolios.ai/mcp/manifests/chatgpt_manifest.json` - served by the deployment itself and rendered for its own origin (use `https://dev.financial-portfolios.ai/...` for dev). The repo copy [`chatgpt_manifest.json`](../chatgpt_manifest.json) is an origin-agnostic template; render it with `python scripts/render_manifests.py --env prod` rather than submitting it as-is.
- **Authentication:** `API Key` (`X-API-Key`).

---

## 3. Useful Links

- **OpenAI GPT Builder:** [chatgpt.com/gpts/editor](https://chatgpt.com/gpts/editor)
- **OpenAI Actions Documentation:** [platform.openai.com/docs/actions](https://platform.openai.com/docs/actions)
- **OpenAI Developer Platform:** [platform.openai.com](https://platform.openai.com)
- **GPT Store Guidelines:** [openai.com/policies/usage-policies](https://openai.com/policies/usage-policies)
