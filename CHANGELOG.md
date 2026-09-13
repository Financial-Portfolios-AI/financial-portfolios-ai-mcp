# Changelog

All notable changes to the Financial Portfolios AI MCP server. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/). The version is defined once, in
`pyproject.toml`; see [docs/RELEASING.md](docs/RELEASING.md).

Customer-facing notes for each release are in [RELEASE_NOTES.md](RELEASE_NOTES.md).

## [Unreleased]

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

[Unreleased]: https://github.com/Financial-Portfolios-AI/financial-portfolios-ai-mcp/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/Financial-Portfolios-AI/financial-portfolios-ai-mcp/compare/v1.1.1...v1.2.0
[1.1.1]: https://github.com/Financial-Portfolios-AI/financial-portfolios-ai-mcp/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/Financial-Portfolios-AI/financial-portfolios-ai-mcp/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Financial-Portfolios-AI/financial-portfolios-ai-mcp/releases/tag/v1.0.0
