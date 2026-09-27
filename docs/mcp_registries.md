# Submitting to MCP Community Registries & IDE Marketplaces

In addition to first-party model providers (Anthropic, OpenAI, Google), registering your MCP server in the open **Model Context Protocol (MCP) Registries** ensures maximum discoverability across AI IDEs (Cursor, Windsurf, VS Code), agent frameworks (LangChain, LlamaIndex), and multi-model interfaces.

---

## 1. The Official Model Context Protocol Registry (`modelcontextprotocol/servers`)

The official GitHub directory maintained by Anthropic and the MCP community.

### Submission Process:
1. Fork the official MCP repository: [github.com/modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers).
2. Add your server entry under the `Community Servers` section in `README.md`:
   ```markdown
   - [Financial Portfolios AI](https://github.com/Financial-Portfolios-AI/financial-portfolios-ai-mcp) - Connect Claude, ChatGPT, and Gemini to quantitative investment portfolios, model allocations, rebalancing calculations, and proprietary financial research.
   ```
3. Create a descriptive pull request:
   - **Title:** `Add Financial Portfolios AI MCP Server`
   - **Description:** Include a short summary of tools, website link ([financial-portfolios.ai](https://financial-portfolios.ai)), and authentication requirements.
4. Once merged, your server will be featured in the official MCP directory.

---

## 2. Smithery.ai Registry (`smithery.ai`)

[Smithery](https://smithery.ai) is the leading automated registry and package installer for MCP servers.

### Submission Process:
1. Visit [smithery.ai/new](https://smithery.ai/new).
2. Connect your GitHub account and select the repository `Financial-Portfolios-AI/financial-portfolios-ai-mcp`.
3. Smithery will automatically parse [`pyproject.toml`](../pyproject.toml) and [`claude_connector.json`](../claude_connector.json) to generate an installation recipe:
   ```bash
   npx -y @smithery/cli install financial-portfolios-ai-mcp --client claude
   ```
4. Click **Publish to Registry**.

---

## 3. PulseMCP Directory (`pulsemcp.com`)

[PulseMCP](https://pulsemcp.com) tracks verified MCP servers and provides automated health monitoring.

### Submission Process:
1. Visit [pulsemcp.com/submit](https://pulsemcp.com/submit).
2. Submit your repository URL: `https://github.com/Financial-Portfolios-AI/financial-portfolios-ai-mcp`.
3. Provide your production Cloud Run endpoint: `https://<your-cloud-run-domain>/mcp`.
4. PulseMCP will verify uptime and list your server in the Finance category.

---

## 4. Cursor & Windsurf IDE Marketplaces

### Cursor IDE
Users install your server directly via the **Cursor Settings** -> **Features** -> **MCP**:
- **Type:** `command` (local) or `http` (remote).
- **Configuration snippet:** Per deployment in [`clients/`](../clients) (`mcp_clients.dev.json`, `mcp_clients.prod.json`), generated from the [`mcp_clients.json`](../mcp_clients.json) template.

### Windsurf IDE (Codeium)
Users add your server to `~/.codeium/windsurf/mcp_config.json`:
- Supports remote Streamable HTTP and stdio transports.

---

## 5. Useful Links

- **Official MCP Servers Repo:** [github.com/modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers)
- **Smithery Registry:** [smithery.ai](https://smithery.ai)
- **PulseMCP Registry:** [pulsemcp.com](https://pulsemcp.com)
- **MCP Community Discord & Forum:** [modelcontextprotocol.io](https://modelcontextprotocol.io)
