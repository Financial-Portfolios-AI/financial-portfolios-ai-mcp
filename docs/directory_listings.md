# Directory listing metadata, per provider

Where "Developer" and "Category" actually come from, provider by provider — checked
against each provider's current documentation rather than assumed. The short version:
**only the MCP registry takes them from a file in this repo.** Claude and ChatGPT collect
them in a submission portal, and no code change moves them.

Keep the values in the table at the bottom identical across every surface.

---

## Official MCP registry — file-driven ✅

[`server.json`](../server.json) in the repo root, validated against
`https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json`.

| Listing concept | Where it lives |
| :--- | :--- |
| Developer identity | The reverse-DNS `name` namespace (`ai.financial-portfolios/...`) plus `repository` — the registry derives publisher from namespace ownership, so the namespace must be a domain we control |
| Category | Not a core schema field. Carried in `_meta` |
| Everything custom | `_meta["io.modelcontextprotocol.registry/publisher-provided"]` — **the only `_meta` key the registry preserves**; every other key is silently dropped on publish. 4 KB limit |

Constraints worth knowing before editing: `description` is capped at **100 characters**
(ours is 97), and `name` must be reverse-DNS with **exactly one slash**, 200 chars max.

Publish with `mcp-publisher`; namespace ownership is proven via DNS or GitHub.

---

## Claude Connectors Directory — portal-driven, but tools must be annotated

Listing fields are entered in the submission portal at
`claude.ai/admin-settings/directory/submissions/new` (Team/Enterprise org, Owner or a role
with the Directory permission). Nothing in this repo sets them:

- Server name (100 chars), tagline (**55 chars**), description (2,000 chars)
- **One to five categories**
- Documentation URL, privacy policy URL, support contact, icon, permanent URL slug
- Company name and website, primary contact — the "Developer" equivalent

What the repo *must* get right, because review checks the live server:

- **Every tool needs a `title` and the applicable `readOnlyHint` / `destructiveHint`.**
  This is a hard requirement — the portal flags tools missing them and groups
  unannotated tools separately. Ours are set in [`tools.py`](../src/financial_portfolios_ai_mcp/tools.py):
  all eight are `readOnlyHint: true`, `openWorldHint: true` (they read through the portal
  API and persist nothing, `rebalance_portfolio` included — it computes share differences
  and stores nothing).
- **OAuth 2.0/2.1 for authenticated services** — we serve the RFC 9728 challenge.
- A public privacy policy. *Missing or incomplete privacy policy is an immediate rejection.*

---

## ChatGPT app directory — portal-driven ❌

Submitted through the OpenAI developer platform; metadata (app name, description,
**category**, screenshots, privacy statement) is entered there, and the **developer name
comes from the verified OpenAI organization account**, not from any file. Neither
`chatgpt_manifest.json` nor `serverInfo` can set them.

`chatgpt_manifest.json` remains useful for what it does carry — `name_for_human`,
`description_for_human`/`_for_model`, `logo_url`, `contact_email`, `legal_info_url` — but
a directory listing's Developer and Category fields are not among them.

---

## Gemini — no such fields

`gemini-extension.json` (Gemini CLI) documents only `name`, `version`, `description`,
`mcpServers`, `contextFileName`, `excludeTools`, `migratedTo`, `plan`, `settings` and
`themes`. There is no `publisher`, `author` or `category` field.

Our [`gemini_extension.json`](../gemini_extension.json) is a Vertex AI-style manifest and
carries its own `category: FINANCE_AND_INVESTING`, which is ours to keep consistent but is
not read by the Gemini CLI extension loader.

---

## MCP `serverInfo` — not a listing surface

`Implementation` (what `initialize` returns) has exactly `name`, `title`, `version`,
`description`, `websiteUrl` and `icons`. There is no developer or category field in the
protocol, so a directory showing "Developer: App developer" is reading its own submission
record, not us.

---

## Canonical values — paste these into every portal

| Field | Value |
| :--- | :--- |
| Server name | Financial Portfolios AI |
| Tagline (≤55) | Systematic model portfolios, allocations and research |
| Developer / company | Financial Portfolios AI (legal entity: **Autonomous Intelligent Agents LLC**, the name the published privacy policy is issued under — use whichever the portal asks for, and keep it consistent with the policy) |
| Company website | https://financial-portfolios.ai |
| Categories | Finance / Investing / Research / Data analysis (pick up to 5) |
| Documentation URL | https://financial-portfolios.ai/docs |
| Privacy policy URL | https://financial-portfolios.ai/legal/privacy (dev: https://dev.financial-portfolios.ai/legal/privacy) |
| Support contact | support@financial-portfolios.ai |
| Icon | `/mcp/assets/icon-512.png` |
| Authentication | OAuth 2.1 (RFC 9728); API key only for CLI/stdio |
| Description | `SERVICE_DESCRIPTION` in [`disclosure.py`](../src/financial_portfolios_ai_mcp/disclosure.py) — includes the ADR-0161 disclosure, which a financial listing must carry |

The tagline above is 53 characters. The description must keep the disclosure sentences:
`instructions` is model-facing and never shown to someone browsing a directory.

---

## Before submitting anywhere: production is not serving these pages yet

Checked on 2026-09-12. `https://financial-portfolios.ai` serves a "We're under
construction" placeholder for **every** path, so the URLs above return HTTP 200 with the
placeholder rather than the real page — `/legal/privacy` included. Status codes are
useless here: a nonsense path returns 200 too, and `/mcp/assets/icon-512.png` returns
`text/html` instead of a PNG.

The same pages are live and correct on dev (`https://dev.financial-portfolios.ai/legal/privacy`
renders the full policy, dated 2026-08-22, issued by Autonomous Intelligent Agents LLC).

This blocks submission rather than delaying it: a missing or incomplete privacy policy is
an immediate rejection at Claude review, and every provider's reviewer fetches the
production URLs. Ship the production site, re-check each URL in the table above, then
submit.
