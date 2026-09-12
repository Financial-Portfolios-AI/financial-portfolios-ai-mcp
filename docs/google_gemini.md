# Registering with Google Gemini & Google Cloud Vertex AI

This guide details how to register and deploy **Financial Portfolios AI** as a **Google Vertex AI Extension**, **Google Cloud Marketplace Listing**, and within **Gemini Agent Workspaces**.

---

## 1. Registering as a Google Vertex AI Extension

Google Cloud's **Vertex AI Extensions** allow Gemini models (e.g. Gemini 1.5 Pro, Gemini Ultra) to call external tools and retrieve private quantitative portfolio data.

### Step 1: Open Google Cloud Console
1. Log in to [console.cloud.google.com](https://console.cloud.google.com).
2. Ensure your GCP project is selected (where your Cloud Run instance is deployed).
3. In the search bar, navigate to **Vertex AI** -> **Extensions** (or [console.cloud.google.com/vertex-ai/extensions](https://console.cloud.google.com/vertex-ai/extensions)).

### Step 2: Create a New Extension
1. Click **"Create Extension"**.
2. **Extension Details:**
   - **Name:** `financial-portfolios-ai`
   - **Display Name:** `Financial Portfolios AI Extension`
   - **Description:** `Quantitative portfolio manager: access model asset allocations, calculate rebalancing orders, and read market research.`
3. **API Specification:**
   - Choose **OpenAPI 3.0 (YAML/JSON)**.
   - Upload [`openapi.yaml`](../openapi.yaml) or provide the URL: `https://<your-cloud-run-domain>/openapi.yaml`.
4. **Authentication Configuration:**
   - **Type:** `API_KEY`
   - **Key Location:** `HEADER`
   - **Key Name:** `X-API-Key`
5. Click **Create Extension**.

### Step 3: Test with Gemini via Vertex AI Studio
1. Open **Vertex AI Studio** -> **Chat**.
2. Under **Model Parameters**, enable your newly created **`financial-portfolios-ai`** Extension.
3. Test a query: *"Show me the asset allocation of AQA_AGGRESSIVE and the required rebalance orders for my portfolio."*

---

## 2. Using with Google Gemini CLI

The **Gemini CLI** natively supports Model Context Protocol (MCP) servers:

```bash
# Register the remote MCP server in Gemini CLI
gemini mcp add \
  --transport http \
  financial-portfolios-ai \
  https://<your-cloud-run-domain>/mcp \
  --header "X-API-Key: aqat_v1_your_token_here"
```

Once added, any prompt run through `gemini` can autonomously discover and execute your portfolio tools.

---

## 3. Publishing to the Google Cloud Marketplace

If you want enterprise Google Cloud customers to subscribe and provision your solution directly from their GCP billing accounts:

### Step 1: Register as a Google Cloud Partner
1. Join the [Google Cloud Partner Advantage Program](https://cloud.google.com/partners).
2. Access the [Google Cloud Marketplace Publishing Portal](https://console.cloud.google.com/producer).

### Step 2: Create a SaaS Listing
1. In the Producer Portal, click **"Add Product"** -> **"SaaS Integration"**.
2. Provide listing assets:
   - Product Name: `Financial Portfolios AI MCP Integration`
   - Short Description & Feature List
   - Logo: 512×512 PNG
   - Support URL: `https://financial-portfolios.ai/contact`
   - Privacy Policy: `https://financial-portfolios.ai/legal/privacy`
3. Link your Cloud Run service URL and Stripe/GCP Marketplace billing integration.
4. Submit for Google Cloud Marketplace technical and commercial review.

---

## 4. Useful Links

- **Google Cloud Console:** [console.cloud.google.com](https://console.cloud.google.com)
- **Vertex AI Extensions Documentation:** [cloud.google.com/vertex-ai/docs/extensions](https://cloud.google.com/vertex-ai/docs/extensions)
- **Google AI Studio:** [aistudio.google.com](https://aistudio.google.com)
- **Google Cloud Marketplace Portal:** [console.cloud.google.com/producer](https://console.cloud.google.com/producer)
