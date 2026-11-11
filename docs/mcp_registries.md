# Submitting to MCP Community Registries & IDE Marketplaces

In addition to first-party model providers (Anthropic, OpenAI, Google), registering your MCP server in the open **Model Context Protocol (MCP) Registries** ensures maximum discoverability across AI IDEs (Cursor, Windsurf, VS Code), agent frameworks (LangChain, LlamaIndex), and multi-model interfaces.

---

## 1. The Official MCP Registry (`registry.modelcontextprotocol.io`) — published

The listing is `ai.financial-portfolios/financial-portfolios-ai`, driven by [`server.json`](../server.json)
(details in [directory_listings.md](directory_listings.md)). It is live: 1.4.6 on 2026-10-25, 1.4.7 on
2026-11-11.

> **The `modelcontextprotocol/servers` README list is retired.** Its CONTRIBUTING.md now says server
> listings moved to the Registry, so do not open a PR adding a line there. (This section used to describe
> that PR.)

### Re-publish on each release
1. Bump `version` in `server.json` to match `pyproject.toml` (the registry rejects a version it already has).
2. Install `mcp-publisher` from the [registry releases](https://github.com/modelcontextprotocol/registry/releases)
   and check its SHA-256 against the digest GitHub shows for the asset.
3. Log in over DNS: `mcp-publisher login dns --domain financial-portfolios.ai --private-key <hex>`. The apex
   domain carries the `v=MCPv1; k=ed25519; p=...` TXT record; the private key is held in the prod secret store, never in this
   repository. Pass it on the command line without echoing it.
4. Run `mcp-publisher publish` in the repository root, then confirm `status: active` and `isLatest: true`:
   `curl "https://registry.modelcontextprotocol.io/v0/servers?search=financial-portfolios"`.

---

## 2. Smithery.ai Registry (`smithery.ai`) — optional, not pursued

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

## 3. PulseMCP Directory (`pulsemcp.com`) — optional, not pursued

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

- **Official MCP Registry:** [registry.modelcontextprotocol.io](https://registry.modelcontextprotocol.io) ([quickstart](https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/quickstart.mdx))
- **Smithery Registry:** [smithery.ai](https://smithery.ai)
- **PulseMCP Registry:** [pulsemcp.com](https://pulsemcp.com)
- **MCP Community Discord & Forum:** [modelcontextprotocol.io](https://modelcontextprotocol.io)
