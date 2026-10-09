# Changelog

All notable changes to the Financial Portfolios AI MCP server. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/). The version is defined once, in
`pyproject.toml`; see [docs/RELEASING.md](docs/RELEASING.md).

Customer-facing notes for each release are in [RELEASE_NOTES.md](RELEASE_NOTES.md).

## [Unreleased]

## [1.4.4] - 2026-10-09

### Changed

- **Shorter server key and install commands.** The client-side server key is `fpai` (was
  `financial-portfolios-ai`), so tool names in Claude Code shrink by 19 characters, e.g.
  `mcp__plugin_financial-portfolios_fpai__get_portfolio_allocation`. The install snippets use the short
  flags and read the token from `FINANCIAL_PORTFOLIOS_API_TOKEN`:
  `claude mcp add -t http fpai <url> -H "X-API-Key: $FINANCIAL_PORTFOLIOS_API_TOKEN"`.
  **Migration:** an existing install keeps working under its old key; to adopt the new one, remove it
  (`claude mcp remove financial-portfolios-ai`), add it again, and update any `mcp__...__financial-portfolios-ai__*`
  permission rules. The extension name (`gemini extensions config financial-portfolios-ai`) and the
  package, image and service names are unchanged.

- **No default target deployment.** The server no longer falls back to production: it needs
  `FINANCIAL_PORTFOLIOS_ENV=dev|prod` (which sets every URL) or an explicit
  `FINANCIAL_PORTFOLIOS_BASE_URL`, and refuses to start otherwise - the image exits at once
  rather than sitting unhealthy. `cloudbuild.yaml` takes `_ENV` and stops before building
  without it; `docker-compose.yml` has no default either. Deployments that already set the
  URLs explicitly, like the current dev service, are unaffected.
- **Client snippets per deployment.** `mcp_clients.json` is now a template;
  `clients/mcp_clients.dev.json` and `clients/mcp_clients.prod.json` are generated from it
  (`scripts/render_manifests.py --clients`, checked by a test), and a running server serves the
  right one at `/mcp/manifests/mcp_clients.json`.

## [1.4.3] - 2026-09-26

### Fixed

- **A missing subscription is no longer reported as a failed sign-in.** The portal answers
  both with 401/403, so `rebalance_portfolio` told free users "Authentication failed". Tool
  errors now say "Subscription required" (the connection is working; free access covers the
  delayed books) or "Not signed in" (reconnect), and the hint no longer hard-codes the
  production URL.
- Rebalance Studio's free-access message and Research Reader's empty state ("No research has
  been published yet" rather than "No research matches" when nothing was searched).

## [1.4.2] - 2026-09-26

### Fixed

- **Free access no longer reads as a fault.** An account with no subscriptions is a free user
  reading the delayed public books, but assistants were treating zero subscriptions as a
  problem and guessing at lapsed or unlinked subscriptions. The server instructions now say
  free access is normal, `open_access_centre` returns `plan: "free_delayed"` with an
  explanation, and the Access panel says "You're on free access".

## [1.4.1] - 2026-09-26

### Added

- **`start_here` prompt** - a menu of the eight things a customer can do, which of them need a
  news or brokerage connector added, and how to run them on a schedule. The server instructions
  offer the same menu when the user asks what the connector can do, which matters on surfaces
  that show no prompts at all (claude.ai, ChatGPT, Gemini app).
- **Journey hints in tool descriptions.** Assistants that see only tools (Gemini Spark, ChatGPT)
  now learn from the descriptions to pair holdings with a news tool and to read positions from a
  brokerage tool.
- **Scheduled-run rule** in the server instructions: text only, read-only, never prepare orders,
  and one line when nothing changed.
- **Order-placement rails in the server instructions.** The connector places no orders, but a
  model holding both this and a brokerage connector can prepare them - so the propose-confirm
  rule now lives here rather than only in the Claude Code plugin's skill, where claude.ai and
  ChatGPT users never see it: explicit confirmation per batch, no standing authorization, no
  auto-execute however the user phrases it, no invented prices or balances, no silently
  substituted symbols, and never a request for brokerage credentials. A broker that permits
  unattended execution does not relax any of it.
- **`drift_check`** - compares real holdings against a model and reports how far they have
  drifted. Safe to schedule, because it deliberately stops short of proposing trades: turning
  gaps into share quantities is the step that needs someone looking, and a scheduled run has
  nobody looking.
- **Three prompts** for capabilities that had none:
  - `portfolio_performance` - performance against the benchmark, risk statistics, and best and
    worst performers, with the rule that the disclosure travels with the figures.
  - `most_held_stocks` - what the user's portfolios hold in common, via the Breadth Board.
  - `portfolio_digest` - a short recurring summary of what changed, written to run **unattended**
    on a Claude Cowork task, a Claude Code routine or a ChatGPT task: it asks no questions,
    continues past an unavailable portfolio, and states a quiet period as a result rather than
    returning nothing. See [docs/providers_and_automation.md](docs/providers_and_automation.md).

### Changed

- **The existing prompts use the tools and panels that now exist** rather than hand-computing.
  `portfolio_review` and `compare_portfolios` call `get_portfolio_concentration` instead of
  working out top-N and effective N by hand - which also means those figures now appear for
  delayed books. `portfolio_changes` calls `get_portfolio_changes` instead of diffing history
  itself. `access_help` leads with the Access & Connection panel. `rebalance_advisor` reads
  holdings from a brokerage connector and opens the Rebalance Studio rather than asking the user
  to dictate positions. `portfolio_report` gains performance sections. Each prompt now offers the
  matching interactive panel, while still answering from JSON where the client cannot render one.

## [1.4.0] - 2026-09-19

### Added

- **Performance, at parity with the website** - the connector was stricter than the product.
  The site publishes performance, best and worst performers and most-held names, disclosed as
  simulated; the connector refused the category, so a customer read a figure on the site and
  was told by the assistant it did not exist. The portal added two v1 routes and this relays
  them:
  - `get_portfolio_performance` - the indexed curve against the benchmark and since-inception
    statistics (total and annualized return, volatility, Sharpe, Sortino, max drawdown, and
    relative beta, alpha, information ratio, tracking error, correlation).
  - `get_portfolio_metrics` - best and worst performers, most-held names **with company
    names**, and win rates by name and by invested capital.

  Subscribers get live figures, everyone else the public book's delayed about 45 days. Both
  report `available: false` with a `reason` while price history backfills, rather than failing.

  The figures are hypothetical and simulated, and each response carries the portal's own
  `disclaimer` saying so - a separate field from the ADR-0161 constant, relayed verbatim and
  never composed here. A payload carrying figures **without** that field is withheld rather
  than returned.

  The remaining boundary is **authorship, not subject**: performance derived here by pricing
  holdings with another connector's feed is still out of scope, because it would carry no
  hypothetical labelling and would not match the website.
- **Three new MCP Apps**, alongside the Portfolio Explorer:
  - **Access & Connection** (`open_access_centre`) - which portfolios this account can see,
    which are live versus delayed by about 45 days, exactly what the delayed book withholds,
    and how the client is signed in. Answers "am I connected?" without the `/api/tokens/me`
    403 that once prompted a model to ask the user to paste a token.
  - **Rebalance Studio** (`open_rebalance_studio`) - holdings read from the user's brokerage
    connector where they have one and passed in by the model, or pasted from a spreadsheet
    or broker CSV. Shown in an editable table with per-row problems before anything is
    calculated; export goes through `ui/download-file`, with the CSV shown to copy on hosts
    that do not offer it.
  - **Research Reader** (`open_research_reader`) - browse, search and read research in
    place, with posts marked when they mention a ticker the user's portfolios hold.
  - **Breadth Board** (`open_breadth_board`) - most widely held stocks across the user's
    portfolios, pairwise overlap by name and by weight, and each book's dominant sector and
    concentration.
- **Derived metrics** (`metrics.py`): concentration and effective N, sector mix and dominant
  sector, cross-portfolio breadth, overlap, and turnover and weight changes between
  snapshots. Computed from weights alone, so they are available on the public delayed book -
  where the portal sends `effective_n`, `equity_exposure` and `cash_allocation` as null.
  Computed on the server, so hosts that do not render MCP Apps still receive every figure.
- **Two analysis tools**, so the same answers are reachable where prompts are not:
  - `get_portfolio_concentration` - concentration (top 5, top 10, largest holding, effective N),
    sector weights, dominant sector and the unclassified share.
  - `get_portfolio_changes` - what the model opened, closed, raised and cut over a period,
    with one-way turnover. Fewer than two snapshots reports why rather than returning zeros,
    which would read as "the model changed nothing".

  They are tools rather than prompts because prompts are effectively invisible in ChatGPT
  and disputed on claude.ai (see [docs/providers_and_automation.md](docs/providers_and_automation.md)).
  `get_portfolio_changes` is also the shape a scheduled task needs - one call answering
  "what changed since last week".
- **Autocomplete for `ticker`** on `find_holding`, drawn from the tickers the user's
  portfolios actually hold. Previously the field had none, and a ticker held in no book
  returns an empty search that reads like a broken tool.
- **Autocomplete for the `portfolios://{portfolio_code}/allocation` resource template.** The
  completion handler answered only prompt references, so a host offering a resource picker
  could not complete a portfolio code at all.
- **Continuous integration** (`.github/workflows/ci.yml`): `ruff check` and the full test
  suite on Python 3.12, plus a job that builds the image, runs the container and drives a
  real MCP client against it (`scripts/ci_smoke.py` - handshake, tool list and
  annotations, the Explorer's UI resource, prompts, the tokenless `401` challenge, icons,
  and that the Explorer's HTML is not downloadable over HTTP). Both jobs check out the SDK
  alongside this repository, which needs an `SDK_READ_TOKEN` secret; see
  [docs/CI.md](docs/CI.md).
- Weekly Dependabot updates for Python packages and GitHub Actions.

### Changed

- **Publishing the client-install artifacts is parameterised** (`scripts/publish_marketplace.py
  --env dev|prod`). The Gemini extension, its `GEMINI.md` context file and the Claude Code
  plugin's `.mcp.json` all live in a public repository separate from their templates, and were
  previously retargeted by hand. The script refuses to publish against an origin that is not
  serving MCP - a tokenless `POST /mcp` must answer `401` with an RFC 9728 challenge - which is
  the check that catches a published artifact pointing at a domain returning `404`.
- **A real Gemini CLI extension.** `gemini_extension.json` used the legacy Vertex AI Extensions
  manifest, which no Google surface reads and whose product shuts down after 2026-11-26. It is
  replaced by [`gemini-extension.json`](gemini-extension.json) plus [`GEMINI.md`](GEMINI.md) in
  the documented Gemini CLI format: `httpUrl` (Streamable HTTP, not the SSE `url`), the API
  token supplied through a declared `sensitive` setting rather than written into the manifest,
  and `excludeTools` carrying the page-only tool - Gemini CLI implements no MCP Apps and so
  does not honour `_meta.ui.visibility`, which would otherwise expose `report_explorer_host` as
  something to call. Publishing still needs a public repository, since
  `gemini extensions install` clones one.
- **The Explorer is usable by touch.** Sortable columns advertised themselves only through a
  hover colour, which the one host we have telemetry for (ChatGPT mobile) never shows; every
  sortable column now carries a mark and `aria-sort`, headers are keyboard-reachable, and tap
  targets go to ~44px under `pointer: coarse` or the host's own `deviceCapabilities`.
- **The Explorer tells the model what is on screen.** `ui/update-model-context` previously
  sent only the selection; it now sends the visible rows in their displayed order, the sort
  column, concentration and dominant-sector figures, what changed between compared snapshots,
  and the shared-holding count.
- **Context from other connectors is explicitly allowed.** The instructions now permit
  combining these holdings with market-data, company, filing and news tools the user has
  connected, attributed to their source. The restriction is unchanged where it matters: no
  return, gain, drawdown or benchmark comparison for these model portfolios, however the
  prices are obtained.
- **Holdings come from the user's brokerage connector first.** Retyping what another
  connector already holds is now called out as the wrong path, and asking the user for
  brokerage credentials is prohibited.
- **The instructions lead with the three rules** - informational only, the delayed book, no
  performance - because ChatGPT's guidance is to put what matters in the first 512 characters.

## [1.3.0] - 2026-09-17

### Added

- **Retries for transient portal failures.** `500`, `502`, `503`, `504` and connection or
  timeout errors are retried twice by default with exponential backoff and jitter; a `4xx`
  is never retried, because it is an answer. Previously one dropped connection surfaced to
  the user as a failed tool.
- **Short per-credential caching of portal reads** (portfolio list 30 s, allocation 60 s,
  history 120 s, research 120 s; each `0` to disable). The cache key hashes the caller's
  credential - the portal answers differently per subscriber - and concurrent reads of one
  key share a single fetch, which matters because the Explorer's stock search reads every
  portfolio at once. The Explorer and the tools share the cache.
- **Monitoring** in `financial-portfolios-dev`: an uptime check on the public
  protected-resource metadata, log metrics for errors and retries, and three alert policies
  (endpoint down, error logs, 5xx) notifying the existing ops email. Policy definitions are
  checked into `ops/monitoring`, and `docs/OPERATIONS.md` documents the log filters.

### Changed

- **Tools return objects, so `structuredContent` is the data.** A string return was wrapped
  by the SDK as `structuredContent: {"result": "<the json as a string>"}` - the envelope
  that left the Explorer blank on Claude mobile, and the field ChatGPT's widget guidance
  tells clients to render from. Each tool also declares an output schema now. The text
  content block still carries the same JSON, so clients reading only text are unaffected.
- **Logging is configured for the served app**, as one JSON object per line with a
  `severity` field. The container runs uvicorn directly, so nothing had configured the root
  logger: records reached Cloud Logging through the MCP SDK's console formatter, wrapped at
  console width, and a single report arrived split across a dozen entries. `httpx`'s
  per-request INFO logs are quietened.

## [1.2.1] - 2026-09-13

### Fixed

- `get_token_info` made a working OAuth connection look broken. It always called the
  portal's `/api/tokens/me`, which only understands personal API tokens, so an
  OAuth-connected client got a `403 Not authenticated`. ChatGPT used the tool to check
  its connection, reported authentication as failing, and asked the user to paste an
  API token into the chat - moments after the same session had fetched portfolios
  successfully. The tool now reports an OAuth connection as connected, without calling
  the portal, and reports a missing credential as "reconnect and sign in".

### Security

- Tool hints and server instructions tell the model never to ask the user to share,
  paste or type an API token, password or other credential in the conversation. The
  old `get_token_info` hint read "Provide a valid personal API token", which is what
  prompted the request.

## [1.2.0] - 2026-09-13

### Added

- **Ask about this** in the Portfolio Explorer: posts a follow-up into the conversation
  (`ui/message`) describing the current view - a portfolio's holdings, its changes over
  the chosen period, a comparison, or a stock search. The wording is a neutral request to
  describe what is on screen, and a test rejects advice-like terms.
- **Model context**: the Explorer tells the assistant what the user is looking at
  (`ui/update-model-context`), so follow-up questions need no restating.
- **Expand / Exit full screen** (`ui/request-display-mode`) where the host offers
  fullscreen.
- **Host theming**: surface colours and font follow the host's theme variables
  (`hostContext.styles`), with the Explorer's own values as fallbacks and brand accents
  unchanged. Variables are validated before use.
- **Host logging**: the Explorer's errors are sent to the host's logs
  (`notifications/message`).
- `report_explorer_host`, a page-only tool (`visibility: ["app"]`, hidden from the model)
  that records which optional MCP Apps features each host advertises. It logs feature
  flags, display modes and host name/version only - never locale, time zone,
  dimensions, or theme values.

Every feature above is feature-detected: a host that does not advertise it simply does
not show the corresponding control.

## [1.1.1] - 2026-09-13

### Fixed

- The Portfolio Explorer left empty space below its content. It reported the document's
  `scrollHeight` as its size, and a document is at least as tall as the frame the host
  gives it, so the frame could grow but never shrink - switching from a long tab such as
  Compare back to Holdings kept the taller frame. It now measures its content, and
  re-sends its size once the host handshake completes, in case the host dropped an
  earlier report.

## [1.1.0] - 2026-09-12

### Added

- **Portfolio Explorer**, an MCP App (`open_portfolio_explorer`). An interactive page that
  Claude and ChatGPT render inline: a portfolio dropdown, a sortable holdings table,
  sector and concentration charts, changes over 30–365 days, a side-by-side comparison
  of two or three portfolios, and a search for which portfolios hold a stock. It reads
  data only through the existing read-only tools and has no network access of its own.
- **Six new prompts**: `my_portfolios`, `access_help`, `portfolio_changes`,
  `compare_portfolios`, `find_holding` and `portfolio_report`, for nine in total. Every
  prompt has a display title and help text for its inputs, and portfolio inputs
  autocomplete from the user's live portfolio list.
- **Public delayed book.** Tools, server instructions and `openapi.yaml` describe the
  `access`, `delayed`, `as_of` and `lag_days` fields: subscribers see the latest book,
  and everyone else sees the public book, delayed about 45 days.
- **OAuth 2.1 sign-in.** A tokenless MCP request is answered with a `401` and an RFC 9728
  `WWW-Authenticate` challenge, and `/.well-known/oauth-protected-resource` is published.
- **Brand icons** in `serverInfo.icons` (an inline 48×48 icon plus 192 and 512 px URLs),
  served from `/mcp/assets/` and `/favicon.ico`.
- **Tool annotations** on every tool: `title`, `readOnlyHint` and `openWorldHint`, as
  the Claude connector directory requires.
- **`server.json`** for the official MCP registry.
- **Provider manifests served per deployment** at `/mcp/manifests/<name>`, rendered
  for the origin they are requested on; `scripts/render_manifests.py` renders them
  offline.
- `scripts/smoke_test.py`, an end-to-end MCP smoke test with no dependencies.
- Documentation: per-provider directory listing requirements
  (`docs/directory_listings.md`) and an internal ecosystem directory of data, account
  aggregator and brokerage MCP servers (`docs/ecosystem_directory.md`).

### Changed

- **Prompt inputs renamed**: `portfolio_code` → `portfolio`, and `portfolio_codes` →
  `portfolios` on `compare_portfolios`. Claude labels an input with its name, so the
  labels now read "Portfolio" and "Portfolios". A blank portfolio input now means the
  user's subscribed portfolios; it previously defaulted to `AQA_AGGRESSIVE`.
- `list_portfolios` lists every active product, each marked with its `access` level.
- `serverInfo.description` now describes the service and carries the ADR-0161
  disclosure, and `website_url` follows the deployment instead of always pointing at
  production.
- Server instructions state that no price, return or performance data exists behind
  any tool, and that performance must never be offered, computed or estimated.
- The Claude connector's authentication is documented as OAuth 2.1. API tokens are for
  command-line and stdio clients only.
- The privacy policy and terms URLs moved to `/legal/privacy` and `/legal/terms`.
- Public URLs are derived per environment (`MCP_PUBLIC_BASE_URL`, `MCP_PUBLIC_URL`, the
  request origin) rather than hardcoded to production.
- Production deployment settings advertise the production OAuth authorization server
  and resource URLs, and raise the Cloud Run timeout for SSE.
- **Requires `financial-portfolios-ai` (SDK) 1.1.0 or later** for the delayed-book models.
- The version is single-sourced from `pyproject.toml`.

### Fixed

- **Connectors failed to connect**: `421 Invalid Host header` behind the load balancer,
  and a `307` redirect on a bare `/mcp` request that clients do not follow.
- Intermittent `Session not found` 404s, fixed by moving to stateless Streamable HTTP.
- "My holdings" and "my positions" phrasing now reaches `get_portfolio_allocation`.
- `openapi.yaml` did not parse as YAML (an unquoted colon in a description).
- The Portfolio Explorer rendered empty on Claude mobile: it read the SDK's
  `structuredContent` envelope as the data itself.
- `HEAD` requests for icons and manifests returned 404.
- `get_token_info` claimed to report subscription status, which it does not.
- The Docker build failed to find the manifest templates.
- Prompts used three differently worded disclaimers; they now share the portal's
  ADR-0161 text.

### Security

- `/mcp/assets` serves image types only, and path traversal is rejected.
- The MCP transports enforce a Host allow-list (DNS-rebinding protection).

## [1.0.0] - 2026-08-26

Initial release.

[Unreleased]: https://github.com/Financial-Portfolios-AI/financial-portfolios-ai-mcp/compare/v1.4.4...HEAD
[1.4.4]: https://github.com/Financial-Portfolios-AI/financial-portfolios-ai-mcp/compare/v1.4.3...v1.4.4
[1.4.3]: https://github.com/Financial-Portfolios-AI/financial-portfolios-ai-mcp/compare/v1.4.2...v1.4.3
[1.4.2]: https://github.com/Financial-Portfolios-AI/financial-portfolios-ai-mcp/compare/v1.4.1...v1.4.2
[1.4.1]: https://github.com/Financial-Portfolios-AI/financial-portfolios-ai-mcp/compare/v1.4.0...v1.4.1
[1.4.0]: https://github.com/Financial-Portfolios-AI/financial-portfolios-ai-mcp/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/Financial-Portfolios-AI/financial-portfolios-ai-mcp/compare/v1.2.1...v1.3.0
[1.2.1]: https://github.com/Financial-Portfolios-AI/financial-portfolios-ai-mcp/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/Financial-Portfolios-AI/financial-portfolios-ai-mcp/compare/v1.1.1...v1.2.0
[1.1.1]: https://github.com/Financial-Portfolios-AI/financial-portfolios-ai-mcp/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/Financial-Portfolios-AI/financial-portfolios-ai-mcp/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Financial-Portfolios-AI/financial-portfolios-ai-mcp/releases/tag/v1.0.0
