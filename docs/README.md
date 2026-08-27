# AI Model Provider Marketplace & Directory Registration Guides

This directory contains comprehensive, step-by-step registration and submission guides to publish the **Financial Portfolios AI MCP Server** to the public directories and marketplaces of major AI model providers.

---

## Directory Guides

| Model Provider | Marketplace / Feature | Guide | Direct Submission Link |
| :--- | :--- | :--- | :--- |
| **Anthropic** | **Claude Connectors Directory** | [Anthropic Claude Guide](anthropic_claude.md) | [Claude Connectors Portal](https://claude.com/docs/connectors/building) |
| **OpenAI** | **ChatGPT Store (Custom GPTs & Apps)** | [OpenAI ChatGPT Guide](openai_chatgpt.md) | [OpenAI GPT Builder](https://chatgpt.com/gpts/editor) |
| **Google** | **Vertex AI Extensions & Marketplace** | [Google Gemini Guide](google_gemini.md) | [Google Cloud Marketplace](https://console.cloud.google.com/marketplace) |
| **Community & IDEs** | **MCP Registry, Cursor, Windsurf, Smithery** | [Community MCP Registries](mcp_registries.md) | [Official MCP Registry](https://github.com/modelcontextprotocol/servers) |

---

## Required Artifacts Checklist

Before starting any submission process, ensure you have the following repository artifacts prepared:

- [x] **Production Cloud Run Endpoint:** `https://<your-cloud-run-domain>/mcp` (Streamable HTTP) and `/sse` (SSE).
- [x] **Claude Connector Manifest:** [`claude_connector.json`](../claude_connector.json).
- [x] **OpenAPI 3.1 Specification:** [`openapi.yaml`](../openapi.yaml) (for ChatGPT Actions & Google Vertex AI).
- [x] **ChatGPT Plugin Manifest:** [`chatgpt_manifest.json`](../chatgpt_manifest.json).
- [x] **Google Vertex AI Manifest:** [`gemini_extension.json`](../gemini_extension.json).
- [x] **Terms of Service:** `https://financial-portfolios.ai/terms`
- [x] **Privacy Policy:** `https://financial-portfolios.ai/privacy`
- [x] **High-Resolution Logo:** 512×512 PNG (`https://financial-portfolios.ai/assets/logo-512.png`).
- [x] **Google Social Login & API Token Generation:** `https://financial-portfolios.ai/settings/api-tokens`.
