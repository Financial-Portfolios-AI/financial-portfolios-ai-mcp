# Ecosystem playbook: journeys, automation templates, and onboarding per vendor

Status: 2026-09-26. Companion to `roadmap_apps.md` and `providers_and_automation.md`.

Three questions, answered in order:

1. How a customer combines our portfolios with market data and their brokerage — per surface.
2. Predefined automation templates, per vendor scheduler.
3. How to configure and onboard the server into ChatGPT, Claude, Gemini and Meta Muse.

---

## 1. Customer journeys

The customer's stack has three layers. We own one; the assistant joins them.

| Layer | Provides | Connector type |
| :--- | :--- | :--- |
| **Financial Portfolios AI** | Holdings, weights, changes, concentration, published performance, research | Ours: text tools + 5 MCP Apps |
| Market data & news | Prices, news, filings, fundamentals | Third party, text (EODHD, Alpha Vantage, Finnhub) |
| Brokerage / aggregator | The customer's own positions; order tickets | Third party, text (SnapTrade, Truthifi, IBKR, Robinhood, Alpaca) |

Every journey below is a **named action** a customer can invoke, not a sentence they must compose.
The gap is that the name has to exist on each surface separately, because no two vendors expose
the same mechanism.

### The eight journeys

| # | Journey | Our layer | + Market data | + Broker | Panel |
| :-- | :--- | :--- | :--- | :--- | :--- |
| J1 | *What do I get?* | `open_access_centre` | — | — | Access & Connection |
| J2 | *Show me a portfolio* | allocation, concentration, changes | — | — | Explorer |
| J3 | *How has it done?* | `get_portfolio_performance` (disclaimer verbatim) | — | — | Explorer |
| J4 | *What's the news on what it holds?* | top holdings | news, filings | — | — |
| J5 | *What do the books agree on?* | breadth | — | — | Breadth Board |
| J6 | *How far has my account drifted?* | allocation | — | positions (read) | Rebalance Studio |
| J7 | *Align my account* | `rebalance_portfolio` | — | positions → order tickets, customer confirms | Rebalance Studio |
| J8 | *Keep me posted* | digest / drift, scheduled | optional news | optional positions (read) | — |

### Where each journey is a named action today

| Surface | Mechanism | J1–J8 coverage | Gap |
| :--- | :--- | :--- | :--- |
| Claude Code | plugin commands `/financial-portfolios:*`, MCP prompts | all 8 | Does not render MCP Apps (text fallback) |
| Claude Cowork | same plugins, plus scheduled tasks | all 8 | — |
| claude.ai / Desktop / mobile | MCP prompts **not shown** (issue #333); Skills are | **none named** | Ship claude.ai Skills (§3.2) |
| ChatGPT | plugin skills `$name`, MCP Apps | none named | Publish a ChatGPT plugin with skills (§3.1) |
| Gemini CLI | extension commands + prompts | all 8 as text | No panels |
| Gemini app / Spark | custom Connected App (MCP URL) | tools only | No prompts or skills; describe journeys in tool descriptions |
| Meta Muse | connector platform | not onboarded | §3.4 |

**Recommendation:** treat the eight journeys as the product catalogue. Each one is authored once as
a *skill body* (the portable format: markdown instructions + which tools to call) and packaged per
vendor. We already have most of the bodies as plugin commands; the work is packaging, not writing.

### What to add to the server itself

These help every vendor at once, including the ones that show nothing but tools:

1. **Journey hints in tool descriptions.** Spark and ChatGPT pick tools from descriptions alone.
   `get_portfolio_allocation` should say it pairs with a market-data news tool for J4 and a brokerage
   positions tool for J6. Cheap, and the only lever on surfaces without prompts.
2. **A `start_here` prompt/resource** returning the journey menu, so "what can you do?" gets the
   eight journeys rather than a tool list.
3. **Keep order execution out.** J7 stays propose → confirm → the broker's own tool. This is what
   gets the server through Muse's and OpenAI's legal review.

---

## 2. Automation templates

Every scheduler now runs with connectors attached: Claude Cowork scheduled tasks, ChatGPT scheduled
tasks (tools and connected apps since June 2026), Gemini Spark (time and event triggers, custom MCP
apps), Muse (background jobs). None of them can open an MCP App in a scheduled run, so every
template is **text-out**.

### Rules every template follows

- **Read-only.** No template places, stages or drafts an order. A schedule may *report* drift; it
  may not act on it. Standing authorisation to trade is exactly what we have said we never do.
- **Performance disclaimer verbatim** whenever a figure appears.
- **Delayed books say so**, with the effective date.
- **Quiet when nothing changed** — a digest that says "no changes" every day gets unsubscribed.

### The template set

| Template | Cadence | Needs | Output |
| :--- | :--- | :--- | :--- |
| T1 Weekly portfolio digest | Mon 08:00 | FP.ai | Changes across subscribed books; silent if none |
| T2 Rebalance alert | Daily 07:00 | FP.ai | Only when a new publication appears: adds, removes, turnover |
| T3 Drift watch | Weekly Fri 16:30 | FP.ai + broker (read) | Drift table vs chosen model; threshold, e.g. >2pp |
| T4 Holdings news | Daily 07:30 | FP.ai + news | Top-10 holdings with news in the last 24h, attributed |
| T5 Earnings week | Sun 18:00 | FP.ai + market data | Held names reporting this week |
| T6 Monthly performance note | 1st of month | FP.ai | Published figures + disclaimer, best/worst holdings |
| T7 Research digest | Weekly | FP.ai | New research posts, flagged where they mention held tickers |

### Packaging per vendor

| Vendor | How the template ships | Customer effort |
| :--- | :--- | :--- |
| Claude Cowork / Code | Skills in `financial-portfolios` (`/digest`, `/drift` exist); add `/schedule-template` that prints the prompt and cadence | Pick a template, press schedule |
| ChatGPT | One skill per template in the ChatGPT plugin; scheduled task created from chat ("run $portfolio-automations every Monday") | One sentence |
| Gemini Spark | Copy-paste prompts on the portal's /agentic page with the cadence written in ("Every Monday at 8am, …") | Paste once |
| Muse | Same copy-paste prompts, once onboarded | Paste once |

**Recommendation:** make the portal the single source. A "Templates" section on /agentic with a
*Copy prompt* button per template and per vendor, generated from one YAML file in the marketplace
repo (`automations/templates.yaml`) that also renders the Claude and ChatGPT skills. One file, no
drift between surfaces.

---

## 3. Onboarding per ecosystem

Common prerequisite for every directory below: **production must serve `/mcp`**. Today
`financial-portfolios.ai/mcp` returns 404 (CP-3). Every submission needs a public, stable URL,
and none of them should be pointed at dev.

Auth status, checked 2026-09-26 on dev: OAuth 2.1 with PKCE S256 and **Dynamic Client
Registration** (`/oauth/register`). Client ID Metadata Documents are not advertised; worth adding,
since newer clients prefer them to DCR.

### 3.1 ChatGPT

- **Mechanism:** Apps (MCP server + optional MCP Apps UI), listed in the **Plugin directory**
  (replaced the app directory 9 July 2026). A plugin bundles skills, apps and app templates.
- **Configure:** OAuth 2.1 + DCR (have it); tool annotations `readOnlyHint` on every read tool
  (we set these); widget CSP domains declared; screenshots ≥1000px (have 5).
- **Named actions:** plugin skills become `$skill` in the composer. Skills are a **snapshot at
  submission** — re-submit to update. Keep to the core five: portfolio, performance, drift,
  digest, research.
- **Automation:** scheduled tasks can call connected apps since June 2026 → templates T1–T7.
- **Before submitting:** developer-mode test on a Plus account; financial-services review will
  read the server instructions, so the "no advice, no execution" rules are an asset.

### 3.2 Claude (claude.ai, Desktop, mobile, Cowork, Code)

- **Connectors Directory** for the remote MCP server. Needs OAuth (have), a privacy policy URL,
  tool annotations, and the MCP App screenshots for an interactive listing.
- **Named actions:** MCP prompts don't render on claude.ai. Ship the journeys as **Skills** — they
  appear in the `/` menu — and as the **Cowork/Code plugin** we already have. The marketplace plugin
  is the same package for both.
- **Automation:** Cowork scheduled tasks run with plugins and connectors. Known issue: cloud
  scheduled tasks in Claude Code don't load MCP connectors (#43397); the desktop Cowork scheduler
  does.

### 3.3 Google Gemini

Three separate surfaces, no shared submission:

| Surface | Onboarding | State |
| :--- | :--- | :--- |
| Gemini CLI | Extension from the public repo; add GitHub topic `gemini-cli-extension` for the gallery | **Done** (dev) — topic still to add |
| Gemini app + **Spark** | User adds our MCP URL under Settings → Connected Apps. Personal account, US, 18+. DCR supported, so sign-in just works | **Possible now**, self-serve |
| Gemini Enterprise | Team admin adds a custom MCP server | Self-serve; document the steps |

- Spark confirms write actions manually; ours are all reads, so scheduled runs won't stall.
- No prompts, skills or UI on Spark — tool descriptions carry the journeys (§1).
- **Action:** a "Connect to Gemini" step-by-step on the portal, and a setup doc for Enterprise
  admins. There is no Google directory to submit to for consumer third-party MCPs yet.

### 3.4 Meta Muse

- Connector platform opened **18 Sept 2026** at `muse.ai/platform` → *Submit a connector*. Review is
  functional, security and legal, with end-to-end testing; Meta decides featured placement.
- **Not published:** protocol (MCP is not confirmed), auth, UI, financial-services policy. The
  submission form asks for a *product description*, not code.
- 1,500+ applications in the first week, so the queue is long.
- **Recommendation:** submit now, describing a read-only portfolio data service with an existing
  standards-based MCP endpoint and OAuth. Lead with "no trading, no advice" — legal review of a
  finance connector will turn on it. Wait for the technical spec before building anything
  Muse-specific.

---

## 4. Recommended order

| # | Action | Unblocks | Owner |
| :-- | :--- | :--- | :--- |
| 1 | Production `/mcp` routing (CP-3) | every directory listing | Portal/infra |
| 2 | Journey hints in tool descriptions + `start_here` prompt | Spark, ChatGPT, Muse | MCP |
| 3 | `automations/templates.yaml` → Claude skills + portal copy buttons | automation on every vendor | MCP + Portal |
| 4 | claude.ai Skills pack for the `/` menu | named actions on claude.ai | MCP |
| 5 | Gemini: repo topic + portal "Connect to Gemini" guide | Spark self-serve | MCP + Portal |
| 6 | Submit Muse connector (description only) | queue position | Zoe |
| 7 | ChatGPT plugin with 5 skills, submit | ChatGPT named actions + directory | MCP, after #1 |
| 8 | Claude Connectors Directory submission | claude.ai discovery | MCP, after #1 |
| 9 | Client ID Metadata Document support | newer clients | Portal (auth) |

Items 2–6 don't wait on production.

---

## Naming (decided 2026-09-26)

No "fpai" abbreviation anywhere a customer sees it. The brand name is the namespace:

| Was | Now |
| :--- | :--- |
| plugins `fpai-portfolio` + `fpai-research` | one plugin, **`financial-portfolios`** (`/financial-portfolios:drift`, …) |
| plugin `fpai-broker` | **`financial-portfolios-broker`**, a separate opt-in because it prepares order tickets |
| claude.ai skills `fpai-*` | descriptive names: `portfolio-start`, `portfolio-overview`, `portfolio-performance`, `holdings-news`, `portfolio-breadth`, `portfolio-drift`, `portfolio-align`, `portfolio-automations` |
| env `FPAI_MCP_URL` | `FINANCIAL_PORTFOLIOS_MCP_URL` |
