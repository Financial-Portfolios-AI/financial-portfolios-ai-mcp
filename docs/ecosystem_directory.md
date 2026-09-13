# Ecosystem directory: market data and brokerage MCP servers

Third-party MCP servers a customer can connect **alongside** the Financial Portfolios AI
connector, to fill gaps our connector deliberately does not cover: prices, news,
performance data, a view of their own accounts, and order execution.

**Status: internal draft for compliance review. Not customer-facing yet.** Read
[Compliance review required](#compliance-review-required) before publishing any of this,
and especially before publishing the brokerage section.

- Verified against each provider's own documentation on **2026-09-12**, except where a
  row says otherwise. MCP offerings in this space change monthly: re-verify before
  publishing and at least quarterly after.
- Only **official, first-party** servers are listed. Community-built servers for a
  brokerage are excluded on purpose: they hold customer credentials and can place
  trades, and the brokerage has not vetted them.
- Listed alphabetically within each section. No ranking, no "best": order is not a
  recommendation.
- Financial Portfolios AI is **not affiliated** with any provider below and receives no
  compensation from them. If that ever changes, this document and anything derived
  from it must disclose it. See the compliance section.

---

## Why customers need these

Our connector serves model-portfolio holdings, weights, sectors, allocation history and
research. It has **no prices, returns, news or execution**, by design, so a customer
asking "how did this model do?", "what's the news on its top holdings?" or "buy these
for me" hits a wall. The servers below each fill one of those gaps with the customer's
own account and API key. We never proxy, store or redistribute their data.

| Customer need | Our connector | Fill with |
| :--- | :--- | :--- |
| What does the model hold? How did it change? | ✅ | — |
| Prices, charts, fundamentals, news on holdings | ❌ | [Market data](#market-data-providers) |
| Performance of holdings or a benchmark | ❌ | Market data. See the note on [performance](#3-performance-computed-from-third-party-prices) |
| View my own accounts and holdings | ❌ | [Account aggregators](#account-aggregators-read-only), read-only and preferred, or [Brokerage](#brokerage-firms) |
| Place trades | ❌ | [Brokerage](#brokerage-firms). See the [compliance boundary](#1-publisher-exclusion-listing-vs-integrating) |

---

## Market data providers

Retail-accessible: self-serve signup, free or low-cost tiers.

| Provider | Official | How to connect | Auth | Coverage | Cost |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Alpha Vantage** | ✅ [alphavantage/alpha_vantage_mcp](https://github.com/alphavantage/alpha_vantage_mcp) | Remote: `https://mcp.alphavantage.co/mcp?apikey=YOUR_KEY` · Local: `uvx av-mcp YOUR_KEY` | API key **in the URL** | Stocks, options, news and sentiment, fundamentals, technical indicators, forex, crypto, commodities, economic indicators | Free API key; paid tiers raise limits |
| **EODHD** | ✅ [eodhd.com](https://eodhd.com/lp/eodhd-mcp-server) | Remote (recommended): `https://mcp.eodhd.com/v2/mcp` · Legacy: `https://mcp.eodhd.com/v1/mcp?apikey=YOUR_KEY` · Local from source | **OAuth 2.1** (v2) or API key (v1) | 72 tools in 15 categories: end-of-day and intraday prices, US tick data, fundamentals, news and sentiment, technicals, US options, Treasury rates, ESG, macro, calendars | Free plan; MCP calls count against the normal API quota |
| **Financial Modeling Prep** | ✅ [FMP MCP docs](https://site.financialmodelingprep.com/developer/docs/mcp-server) | HTTP `/mcp` endpoint, per FMP docs | API key | Fundamentals, financial statements, ratios, filings, transcripts | Plan-dependent. ⚠️ Endpoint and tier details **not independently verified**: FMP's docs blocked automated retrieval |
| **Massive** (formerly Polygon.io) | ✅ [massive-com/mcp_massive](https://github.com/massive-com/mcp_massive) | **Local install only** | API key (`MASSIVE_API_KEY`) | Stocks, options, crypto, forex, via four composable tools over the full API | Plan-dependent. Third-party hosted gateways exist but are not Massive's own, so they are not listed |

**Best fit for Claude connector users:** EODHD v2. It's the only one above that
authenticates with OAuth, so the customer signs in instead of pasting a key, and its
news, sentiment and fundamentals map directly onto our holdings.

**Security note for key-in-URL servers** (Alpha Vantage, EODHD v1): the URL *is* the
credential. Tell customers not to share screenshots of their connector settings, and to
rotate the key if the URL leaks.

### Institutional platforms (enterprise licences)

FactSet, S&P Global (Capital IQ / Kensho), LSEG, Morningstar and MSCI offer official
Claude connectors, but require an enterprise data licence. They are relevant only for
institutional or advisor customers who already hold that licence, not for retail
subscribers.

---

## Account aggregators (read-only)

These connect a customer's existing accounts, often several brokerages at once, and
expose them to the AI **strictly read-only**. Neither can place trades, move money or
change account settings; both say so explicitly. For a customer who wants to see their
real holdings next to our models, this is the lower-risk route: it gives the view
without the execution. See compliance point 6 below.

| Aggregator | Official | How to connect | Auth | What it returns | Accounts covered | Cost |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SnapTrade** | ✅ [SnapTrade MCP docs](https://docs.snaptrade.com/docs/mcp-server) | `https://mcp.snaptrade.com/mcp` | **OAuth 2.0 with PKCE** and dynamic client registration; short-lived, read-scoped tokens; brokerage credentials never reach the AI | Connections, accounts, balances, positions, orders, historical activity, reference data; can also generate a link to connect a new brokerage | Brokerage accounts. The MCP doc does not enumerate which brokerages, so confirm against SnapTrade's supported list before publishing | Free **SnapTrade Personal** account with at least one linked brokerage. Aimed at individuals, not developer API keys |
| **Truthifi** | ✅ [truthifi.com/features/mcp](https://truthifi.com/features/mcp) | Server URL issued during setup; ⚠️ **not published on the page** | ⚠️ **Not stated** on the page | Holdings, balances, performance, returns, fees, allocation and composition, tax opportunities | "18,000+" providers: brokerages, banks, retirement accounts. Named guides include Fidelity, Schwab, Merrill, Robinhood, Chase, Bank of America, Capital One, Citibank | Included in paid memberships; a standalone MCP option (Truthifi Connect) is marketed as free to start |

Quoted safeguards:
- SnapTrade: "The MCP server is **read-only**. It can retrieve account data and generate a
  link to connect a new brokerage, but it cannot place trades, move money, or change
  account settings."
- Truthifi: "Your AI can retrieve and reason about your financial data, but it cannot move
  money, place trades, execute transactions, or modify your accounts in any way."

**Gaps to close before publishing:**
- **Truthifi:** endpoint, authentication method and how account credentials are held
  (which underlying aggregator, and whether credentials are stored) are not on its MCP
  page. Get them from Truthifi in writing.
- **Both:** neither page states regional availability.

Worth noting for customers: aggregators also cover **Fidelity, Schwab and Merrill**,
which have no official MCP server of their own. For many customers an aggregator is the
*only* official way to bring those accounts into Claude.

---

## Brokerage firms

⚠️ **Every broker below except Interactive Brokers lets an AI agent place live orders.**
The "Order control" column is the most important one: it ranges from "the agent can
only draft, you submit" to "the agent trades unattended".

| Broker | Official | How to connect | Auth | Order control | Assets | Availability |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Alpaca** | ✅ [alpacahq/alpaca-mcp-server](https://github.com/alpacahq/alpaca-mcp-server) | **Local install only**; Alpaca provides no hosted server | API key + secret | **Paper trading by default**; live requires an explicit switch | Stocks, ETFs, options, crypto; also market data and news | Developer-oriented; region not restricted in docs |
| **Interactive Brokers** | ✅ [IBKR announcement, 2026-07-28](https://www.interactivebrokers.com/en/general/about/mediaRelations/7-28-26.php) | `api.ibkr.com/v1/api/mcp-public` ¹ | IBKR account sign-in | **Drafts only.** The agent prepares orders; the customer reviews and submits them on an IBKR platform | 170+ markets | Global; no extra charge |
| **Public.com** | ✅ [public.com/mcp-trading](https://public.com/mcp-trading) | `https://mcp.public.com/mcp` | OAuth | **Can trade unattended.** Public states trades "may be executed by your AI agent without your direct input" | Stocks, ETFs, options, crypto, bonds | **US only**; Claude, ChatGPT, Perplexity |
| **Robinhood** | ✅ [Robinhood agentic trading](https://robinhood.com/us/en/support/articles/agentic-trading-overview/) | `https://agent.robinhood.com/mcp/trading` | OAuth via the connector | Trades only in a **separate Robinhood Agentic account**; can read all account data; per-trade review is optional | Stocks, options (beta), crypto via Robinhood Crypto (state limits; not NY) | **US**; needs a primary account in good standing; desktop setup |
| **TradeStation** | ✅ ¹ | Not published in the source | — | **Confirmation enforced** | Stocks, options, futures | Reportedly needs a $10k minimum and a paid AI plan. ⚠️ **Not independently verified** |
| **Webull** | ✅ [webull-inc/webull-mcp-server](https://github.com/webull-inc/webull-mcp-server) | Local server; hosted `api.webull.com/mcp` ¹ | API key + secret | **Sandbox by default**; live requires an explicit switch; configurable caps and whitelist | Stocks, ETFs, options, futures, crypto | Multi-region: US, UK, EU, AU, HK, JP, SG and others |

¹ From StockBrokers.com's hands-on MCP test ([updated 2026-07-31](https://www.stockbrokers.com/guides/ai-agent-brokers)).
Confirm against the broker's own documentation before publishing.

**Not listed, and why:**
- **Charles Schwab, E\*TRADE, tastytrade:** official APIs, but only community-built MCP
  servers that the broker has not endorsed.
- **Fidelity, Merrill Edge, Ally Invest:** no public retail API.
- **Moomoo, eToro, Firstrade:** not MCP, or not available in the US.

---

## Compliance review required

These are the questions to put to counsel before anything here reaches a customer.
They are issues to review, not legal conclusions.

### 1. Publisher exclusion: listing vs. integrating
Financial Portfolios AI publishes impersonal model portfolios under the publisher
exclusion (ADR-0161). A neutral list of providers is plausibly consistent with that. The
risk is integration: a flow where our model, our `rebalance_portfolio` arithmetic on
the customer's *own* holdings, and a broker's order tool run together, so that a
customer effectively auto-copies our model into their account. That looks much less
like impersonal publishing and much more like individualized advice or trade
facilitation.

**Engineering position until counsel rules:**
- No prompt, tool or instruction from our connector will pass rebalance output to a
  brokerage order tool, or ask the model to place trades.
- No "copy this model" or auto-rebalance feature.
- Our prompts already forbid buy, sell and hold recommendations, and `rebalance_advisor`
  already tells the user that trading decisions are theirs alone. That stays.

### 2. Endorsement, referrals and compensation
Any list implies endorsement. Questions for counsel: the required disclaimer wording;
whether to name brokers at all or describe criteria only; and, if referral fees or
affiliate links are ever considered, the solicitation and disclosure obligations that
brings. Today there is no compensation, and this document must say so wherever it is
published.

### 3. Performance computed from third-party prices
With a data provider connected, a customer or Claude can price our model's holdings and
compute a "performance" figure. That is **hypothetical model performance**, a heavily
regulated presentation, and one we currently prevent: `portfolio_report` forbids
computing returns "from other sources". Counsel should decide whether this may be shown
at all, to whom (subscribers or the public), and with which disclosures, before that
guard is relaxed.

### 4. Unattended trading
Public.com executes without per-trade confirmation. Robinhood makes confirmation
optional. Presenting those next to a model portfolio could encourage exactly the
unattended copy-trading in point 1. Counsel should decide whether to list them, and with
what warning.

### 5. Availability and suitability of the brokers themselves
Most brokers here are US-only, and several require minimums, specific account types or
paid AI plans. A customer-facing version must state availability and must not suggest
any broker suits a particular customer.



### 6. Real holdings next to our models, even without execution
Read-only aggregators remove the execution risk in points 1 and 4, but not all of the
advice question. With one connected, Claude can see a customer's actual positions and set
them against our model, which is exactly the individualized comparison that
`rebalance_advisor` already frames carefully as "alignment arithmetic". Counsel should
confirm that framing still holds when the customer's real account data arrives
automatically rather than being typed in, and whether our prompts need an explicit rule
for when an aggregator is present.

---

## Recommended rollout

1. **Market data section**: publish after a light compliance read. Low risk; the
   customer uses their own key and data, and nothing executes.
2. **Account aggregators**: publish once counsel confirms point 6, and after Truthifi's
   missing details are filled in. This is the recommended way to give customers an
   account view: read-only, and it covers brokerages with no MCP of their own.
3. **Brokerage section**: hold until counsel answers points 1, 2 and 4.
4. **Integration of any kind** (prompts or tools that reach into these servers): only
   after counsel defines the boundary in point 1, and never the rebalance-to-order path
   without explicit sign-off.

## Sources

- [EODHD MCP server](https://eodhd.com/lp/eodhd-mcp-server)
- [Alpha Vantage MCP (GitHub)](https://github.com/alphavantage/alpha_vantage_mcp)
- [Financial Modeling Prep MCP docs](https://site.financialmodelingprep.com/developer/docs/mcp-server)
- [Massive MCP (GitHub)](https://github.com/massive-com/mcp_massive)
- [Public.com MCP trading](https://public.com/mcp-trading)
- [Robinhood agentic trading overview](https://robinhood.com/us/en/support/articles/agentic-trading-overview/)
- [Alpaca MCP server (GitHub)](https://github.com/alpacahq/alpaca-mcp-server)
- [Interactive Brokers MCP announcement, 2026-07-28](https://www.interactivebrokers.com/en/general/about/mediaRelations/7-28-26.php)
- [Webull MCP server (GitHub)](https://github.com/webull-inc/webull-mcp-server)
- [StockBrokers.com: Best Brokers for AI Trading Agents, MCP tested (updated 2026-07-31)](https://www.stockbrokers.com/guides/ai-agent-brokers)
- [SnapTrade MCP server docs](https://docs.snaptrade.com/docs/mcp-server)
- [Truthifi MCP](https://truthifi.com/features/mcp)
- [Anthropic: Agents for financial services](https://www.anthropic.com/news/finance-agents)
