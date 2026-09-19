# Providers, automation, and the end-to-end experience

What Claude, ChatGPT and Gemini actually support, what can be automated on each, and how our
connector fits beside the market-data, brokerage and news connectors a customer already has.

Researched 2026-09-19 against primary sources. Claims are marked **confirmed** (vendor
documentation or source code) or **unverified** (undocumented, or only community reports).
Vendor surfaces move quickly - re-check before relying on a row.

## 1. What each host supports

| | Claude web / desktop / mobile | Claude Code | ChatGPT | Gemini CLI | Gemini consumer app | Gemini Enterprise |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Tools | yes | yes | yes | yes | yes | yes (called "actions", max 100) |
| Prompts | **disputed** | yes (slash commands) | **effectively no** | yes (slash commands) | unverified | no |
| Resources | manual attach only | yes (`@` mentions) | `ui://` and skills only | yes | unverified | no |
| Elicitation | **no** | yes | **yes** | **no** (absent in source) | unverified | no |
| Sampling | no | no | no | no | unverified | no |
| MCP Apps (`io.modelcontextprotocol/ui`) | **yes** | no | **yes** | no | no | no (Google backs A2UI) |
| Skills extension | no | n/a | partial (5 skills max) | n/a | n/a | n/a |

Three findings matter more than the rest.

**Prompts are not a delivery surface.** ChatGPT's plugin documentation never mentions
`prompts/list` and states "Plugins primarily use tools". On claude.ai the position is
contradictory: an Anthropic collaborator said in February 2026 that prompts are supported and
user-attachable, while [claude-ai-mcp#333](https://github.com/anthropics/claude-ai-mcp/issues/333)
- open, reproduced August 2026 - reports custom-connector prompts appearing nowhere in the UI.
Anything a customer needs to reach must therefore ship as a **tool**, with the prompt as a
convenience for the hosts that do surface them.

**Elicitation is the opposite of what we assumed.** It works in ChatGPT and Claude Code, and
**not** in claude.ai, Claude Desktop or Claude mobile
([claude-ai-mcp#153](https://github.com/anthropics/claude-ai-mcp/issues/153), open since April
2026). Gemini CLI does not register an elicitation handler at all - visible in
`packages/core/src/tools/mcp-client.ts`, which declares only `roots`. So a server-driven
dropdown reaches some hosts and not others, while an **MCP App** reaches both of the hosts our
customers actually use. Apps stay the answer for anything needing a choice.

**Our two real hosts both render apps.** ChatGPT announced full MCP Apps compatibility on
2026-02-22, and `_meta["openai/outputTemplate"]` is now documented as a compatibility alias for
the standard `_meta.ui.resourceUri` we already emit. Our own logs confirm it: ChatGPT mobile
completed an ext-apps `ui/initialize` against this server on 2026-09-18. No Gemini surface is
confirmed to render MCP Apps; Google's equivalent is **A2UI**, and only Gemini Enterprise
renders that. On Gemini we are text-only, which is why every app tool must return a useful JSON
result on its own.

### Host details worth designing around

- **Claude** shows an "Open external link" confirmation for every `ui/open-link` unless the
  connector is directory-listed with the origin declared. Tool results are capped around
  150,000 characters, beyond which the app receives a file pointer and fails to hydrate.
  Mobile renders apps in a native WebView rather than a sandboxed iframe.
- **ChatGPT** reads server `instructions` but advises putting what matters in the **first 512
  characters**. `readOnlyHint` is what makes a tool eligible to run without a prompt; a
  remembered approval lasts only for the conversation. Its UI guidance warns against hover-only
  actions and nested scrolling.
- **Gemini Enterprise** is Streamable HTTP only, tools only, and needs a publicly-trusted TLS
  certificate. The consumer app's custom MCP connections are US-only, 18+, personal Google
  accounts, English, added on web.

## 2. Automation

| Surface | Can it call our connector? | Constraints |
| :--- | :--- | :--- |
| **Claude Code Routines** | yes - connectors are included by default | Minimum interval **1 hour**; within a run Claude may use every tool of an included connector, **including writes, without asking**; research preview |
| **Claude Cowork scheduled tasks** | yes - "connected tools, skills, and installed plugins" | Hourly to weekly; runs remotely; tasks needing local files run locally only |
| **Claude artifacts with connectors** | yes - the page calls connectors when viewed | Each viewer uses their own account and approves; **never shareable by public link** |
| **ChatGPT scheduled tasks** | yes - plugins and connected tools are available | Web tasks only; uses `approval_policy = "never"` where org policy allows, otherwise an approval-needing tool **stalls the run** |
| **ChatGPT event-triggered tasks** | yes | Web and mobile only; plan- and admin-gated |
| **Gemini scheduled actions** | **unverified** | Max 10 active; the docs never say whether a custom MCP app can be used - needs an experiment |

**There is no push.** No host offers server-initiated triggering over MCP; a timer is the only
primitive. The SDK's WebSocket event stream (`portfolio.updated`, `blog.published`) cannot reach
a host, so if we want "tell me when the model changes", that notification has to come from the
portal by its own channel - the MCP side can only answer when asked.

**What automation asks of the server**, all of which is cheap:

1. **Every tool `readOnlyHint`** - already true - which is what lets an unattended run proceed
   without an approval prompt on both Claude and ChatGPT.
2. **A digest-shaped tool.** A scheduled task wants one call that answers "what changed in my
   portfolios since last week" - the conviction-change and turnover work in
   [roadmap_apps.md](roadmap_apps.md) is exactly that payload, and is worth building as a tool
   for this reason alone.
3. **Stable tool names**, since a routine references them by name.
4. **Front-loaded instructions.** Ours open with a sentence of positioning. For ChatGPT, the
   delayed-book rule and the performance boundary should be inside the first 512 characters,
   not below the capability list.

## 3. The customer journey, and where it breaks

Our connector answers one question well - *what does this model hold, and how has it changed*.
Everything else a customer wants comes from their other connectors, with the model joining them.
The boundary in `server.py` holds throughout: context from anywhere, **no performance arithmetic
for these model portfolios, whatever the source of the prices**.

| Stage | Ours | Theirs | Status |
| :--- | :--- | :--- | :--- |
| Discover | directory listing | - | listing work tracked in [directory_listings.md](directory_listings.md) |
| Connect | OAuth 2.1, RFC 9728 | - | done |
| Understand access | **Access & Connection app** | - | done - live vs delayed, and what delayed withholds |
| Explore holdings | **Portfolio Explorer** | - | done |
| Understand a holding | ticker, weight, sector | market-data / news connector resolves the company, its filings and its news | instructions now permit this; ticker → company is the weak link, since we publish no company name |
| Compare to own portfolio | **Rebalance Studio** | brokerage connector supplies positions | done - model reads positions, user confirms them |
| Act | - | brokerage | **deliberately not ours**; Claude's directory rejects connectors that transfer financial assets |
| Keep up | digest tool (to build) | - | scheduled task on either host |

Two gaps worth naming:

- **No company name anywhere in our schema.** Every cross-connector join starts from a bare
  ticker, which models resolve well for US large caps and unreliably elsewhere. Either the
  portal adds a name (and ideally an ISIN) to `Position`, or every joined answer carries that
  risk. This is the single highest-value schema change for the ecosystem story.
- **`sector` is frequently null**, and the apps bucket it as "Unclassified". Sector-level answers
  are only as good as that field.

## 4. Done: a real Gemini CLI extension

We shipped `gemini_extension.json`, which matched the **legacy Vertex AI Extensions** manifest -
`display_name`, `runtime_environment`, `service_endpoint`, `api_spec`. Vertex AI Extensions is
deprecated and shuts down after **2026-11-26**, and no current Google surface read that file.
It has been replaced by [`gemini-extension.json`](../gemini-extension.json) (hyphen), the
documented **Gemini CLI** format, with [`GEMINI.md`](../GEMINI.md) as its context file.

Two details that are easy to get wrong:

- **`httpUrl`, not `url`.** `url` is the SSE key; `httpUrl` is Streamable HTTP, which is what
  this server speaks. The token comes from a declared `settings` entry
  (`FINANCIAL_PORTFOLIOS_API_TOKEN`, `sensitive: true`), so it is never written into the
  manifest; the origin renderer substitutes `${PUBLIC_ORIGIN}` only and leaves that placeholder
  for the CLI.
- **`excludeTools` carries the page-only tool.** Gemini CLI does not implement MCP Apps and so
  does not honour `_meta.ui.visibility`; without the exclusion, `report_explorer_host` would
  appear in its tool list as something to call. The UI-opening app tools are excluded too,
  since they carry no data a text client cannot get from another tool - `open_breadth_board`
  and `open_access_centre` stay, because their results are computed server-side and have no
  other source.

**Published** to the public marketplace repo, since `gemini extensions install` clones one and
this repository is private:

```bash
gemini extensions install https://github.com/Financial-Portfolios-AI/financial-portfolios-ai-marketplace
```

### Publishing is a command, not a hand edit

Two public artifacts hardcode an endpoint - the Gemini extension and the Claude Code plugin's
`.mcp.json` - and they live in a different repository from their templates. Retarget both with:

```bash
python scripts/publish_marketplace.py --env dev     # or --env prod
python scripts/publish_marketplace.py --env dev --check   # verify, write nothing
```

It refuses to publish against an origin that is not serving MCP: a tokenless `POST /mcp` must
answer `401` with an RFC 9728 challenge. Running it with `--env prod` today fails with
`POST /mcp returned 404`, which is exactly the mistake that reached the published artifacts
when they were edited by hand. `--no-verify` overrides it for a deployment that is not up yet.

`ENVIRONMENTS` lives in `manifests.py` so the renderer, the publisher and their tests cannot
disagree about what `dev` means.

**It points at dev, deliberately.** `https://financial-portfolios.ai/mcp` returns `404` - the apex
domain still serves a placeholder page, and its `/.well-known/oauth-protected-resource` returns that
page's HTML rather than metadata - while `https://dev.financial-portfolios.ai/mcp` answers a
tokenless request with the correct `401`. Publishing against production would have installed cleanly
and failed on every call.

The same gap blocks the directory submissions in [directory_listings.md](directory_listings.md):
`--env prod` currently renders all three manifests against a domain that serves none of this
service, so any reviewer fetching those URLs would fail the listing. It is the portal's CP-3
routing decision plus the domain not yet pointing at the portal.

Remote MCP from the **Gemini API / Vertex** is blocked regardless: Google's own limitations page
states "Gemini 3 does not support remote MCP, this is coming soon."

## 5. Open questions worth one experiment each

| Question | How to settle it |
| :--- | :--- |
| Does Claude report a host context to our apps at all? | Open any app in Claude once and check for an `explorer_host_report` record - we have three from ChatGPT and none from Claude |
| Does ChatGPT ever call `prompts/list`? | Log the method; the docs are silent rather than negative |
| Can a Gemini scheduled action invoke a custom MCP app? | Undocumented either way; try it |
| Does our server reach ChatGPT mobile as a dev-mode connector, or only once published? | Developer mode is documented web-only, yet our logs show mobile |
