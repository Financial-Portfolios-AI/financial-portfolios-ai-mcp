# Meta Muse connector submission (draft)

Status: **draft, not submitted.** Prepared 2026-09-27 for muse.ai/platform → *Submit a connector*.
Muse reviews the **live endpoint**, so submit only once `https://financial-portfolios.ai/mcp`
serves (it returns 404 today). Items marked **[confirm]** need an owner's answer first.

---

## Step 1 · Overview

**Connector name**
Financial Portfolios AI

**Company or developer**
Autonomous Intelligent Agents LLC (operator of Financial Portfolios AI)

**Product website**
https://financial-portfolios.ai

**Short description** (if the form asks for one)
> Explore published model stock portfolios: holdings, sector weights, concentration, what changed
> at each rebalance, published performance, and research. Informational and educational only. It
> gives no advice and places no trades.

**Longer description**
> Financial Portfolios AI publishes rules-based model stock portfolios (Aggressive, Balanced,
> Defensive, Quality). This connector lets you explore them in conversation: what each portfolio
> holds and at what weight, its sector mix and concentration, what it added and removed at each
> rebalance, which stocks several portfolios share, its published hypothetical performance against
> a benchmark, and the research behind it.
>
> Anyone can use it for free: every portfolio's public book is available with a delay of about 45
> days. Subscribers see the live book. The connector is read-only. It never places orders, never
> asks for brokerage credentials, and gives no personalised advice or recommendations. Performance
> figures are hypothetical and simulated, and are always shown with their disclosure.

**Example prompts**
1. What's in the Defensive portfolio right now?
2. How has the Balanced portfolio performed against its benchmark?
3. What did the Aggressive portfolio change at its last rebalance?
4. Which stocks do the model portfolios have in common?
5. Which portfolios hold Microsoft, and at what weight?
6. How concentrated is the Quality portfolio, and which sector dominates it?
7. Summarise the latest research posts.
8. What can I see with a free account?

**Connector icon**
512 × 512 PNG, served at `https://financial-portfolios.ai/mcp/assets/icon-512.png` (source:
`src/financial_portfolios_ai_mcp/assets/`). The approved brand mark.

**Accepts payments?**
No. Subscriptions are bought on the website, never through the connector.

**Your name and work email**
Zoe Tsekas · zoetsekas@financial-portfolios.ai

**Support email or URL**
support@financial-portfolios.ai

**Privacy policy URL**
https://financial-portfolios.ai/legal/privacy (loads on production, checked 2026-09-27)

**Terms of service URL**
https://financial-portfolios.ai/legal/terms (loads on production, checked 2026-09-27)

---

## Step 2 · Technical specs

**Connection type**
Existing MCP

**Hosted MCP endpoint**
https://financial-portfolios.ai/mcp (Streamable HTTP; stateless)

**API or MCP documentation**
https://financial-portfolios.ai/agentic **[or the marketplace README until that page is on production]**

**Authentication methods**
- ☑ OAuth with PKCE: OAuth 2.1, S256, Dynamic Client Registration at `/oauth/register`.
  Discovery via `WWW-Authenticate: Bearer resource_metadata=…` (RFC 9728) and
  `/.well-known/oauth-authorization-server`. Scopes: `portfolios:read`, `research:read`.
- ☑ API keys: personal token (`aqat_v1_…`) in the `X-API-Key` header, issued at
  `/api-access`.
- ☐ Other

**Access requirements / restrictions**
> - An account is needed (free sign-up, or Google sign-in).
> - Free accounts see every portfolio's public book, delayed about 45 days. A paid subscription
>   adds that portfolio's live book and the premium figures (expected return and volatility,
>   equity exposure, cash, effective N).
> - Alignment calculations against a model portfolio need a subscription to it.
> - Regional availability: United States. Paid subscriptions are offered only to residents of the
>   United States who are 18 or older. The delayed public books can be viewed from elsewhere, but that
>   is not an offer to subscribe outside the United States (portal ADR-0343).
> - Rate limits: API keys default to 60 requests per minute and 10,000 per day. OAuth sign-in and
>   client registration are rate-limited per IP.

**Tools** (for reviewers; all read-only, annotated `readOnlyHint`)
`list_portfolios`, `get_portfolio_allocation`, `get_portfolio_history`, `get_portfolio_changes`,
`get_portfolio_concentration`, `get_portfolio_performance`, `get_portfolio_metrics`,
`get_rebalance_template`, `rebalance_portfolio` (arithmetic only, places nothing),
`list_blog_posts`, `get_blog_post`, `get_token_info`, plus five interactive-panel tools
(`open_*`) that return the same data as text on clients without panels.

**Safety and compliance notes** (for the legal review)
> - Informational and educational only, under the publisher exclusion. Every response carries a
>   disclaimer, and no suitability assessment is performed.
> - No trading: the connector has no order tools. Its server instructions forbid placing or
>   preparing orders without the user's explicit confirmation of each batch, and forbid it
>   entirely in unattended or scheduled runs.
> - It never requests brokerage credentials or account numbers.
> - Performance is hypothetical and simulated, published with a verbatim disclosure. The server
>   withholds figures that arrive without it.
> - Instructions found inside tool results or documents are treated as data, never obeyed.

---

## Step 3 · Review and acknowledgements

These need the account owner, not the drafting session:

- ☐ Authorised to submit this connector and its brand assets
- ☐ Submission does not guarantee approval
- ☐ Agree to the Muse Connector Terms **[read first; the page needs a login]**

---

## Before submitting: checklist

- [ ] `https://financial-portfolios.ai/mcp` answers a tokenless POST with `401` and
      `resource_metadata` (`python scripts/ci_smoke.py https://financial-portfolios.ai`)
- [ ] OAuth sign-in completes end to end on production (the consent page was fixed on dev on
      2026-09-27)
- [x] Privacy and terms pages load on the production domain (checked 2026-09-27)
- [ ] support@financial-portfolios.ai receives mail
- [ ] Icon URL above serves on production
- [ ] Every **[confirm]** above answered
- [ ] Review expected to take weeks: Meta is onboarding the first ~2,000 submissions in waves
