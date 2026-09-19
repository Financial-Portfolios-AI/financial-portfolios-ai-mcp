<!-- Template: ${PUBLIC_ORIGIN} is substituted at publish time by
     scripts/publish_marketplace.py. Do not hardcode an environment origin here. -->
# Financial Portfolios AI

Connects to `${PUBLIC_ORIGIN}/mcp`.

Systematic, AI-driven model portfolios. This extension connects Gemini CLI to the Financial
Portfolios AI MCP server so you can inspect published model portfolios, see how they change,
and compare your own holdings against them.

## Three rules that govern every answer

1. **Informational and educational only.** Nothing here is individualized investment advice, a
   recommendation, or a solicitation, and no suitability assessment has been performed.
2. **Some books are delayed.** A portfolio you are not subscribed to comes back on the public
   book, roughly 45 days behind. Always state the `as_of` date and say it is delayed; never
   present it as the current allocation.
3. **There is no price, return or performance data behind any tool.** Do not compute or
   estimate performance, returns, gains, drawdowns or benchmark comparisons for these model
   portfolios - not even from another source.

## What the tools give you

| Tool | Use it for |
| :--- | :--- |
| `list_portfolios` | Every active model strategy, each marked `subscribed` or `public_delayed` |
| `get_portfolio_allocation` | Target weights, tickers and sectors for one portfolio |
| `get_portfolio_history` | Allocation snapshots over time (up to 365 days) |
| `get_portfolio_concentration` | Concentration (top 5/10, largest, effective N), sector weights, dominant sector |
| `get_portfolio_changes` | What the model opened, closed, raised and cut, plus turnover |
| `open_breadth_board` | Across all your portfolios: most widely held stocks, overlap, dominant sectors |
| `open_access_centre` | What this account can see, what the delayed book withholds, connection state |
| `rebalance_portfolio` | Share-quantity differences between your holdings and a target model |
| `get_rebalance_template` | The holdings CSV format (max 200 rows, 512 KB) |
| `list_blog_posts`, `get_blog_post` | Quantitative research and market commentary |

### Notes for this client

- Gemini CLI does not render MCP Apps, so `open_breadth_board` and `open_access_centre` return
  their data as JSON. That is the full answer, not a degraded one - read it directly.
- The interactive-only tools are excluded from this extension because they carry no data a
  text client cannot get elsewhere.
- `expected_return` and `expected_volatility` are per-position model metadata and are `null`
  on the public delayed book, along with `effective_n`, `equity_exposure` and
  `cash_allocation`. `get_portfolio_concentration` derives concentration and sector figures from the
  weights, so those remain available on a delayed book.

## Your own holdings

The server holds published model portfolios and never your positions. `rebalance_portfolio`
compares holdings you supply against a target model - pass them as
`[{"ticker": "AAPL", "quantity": 40}, ...]` or as CSV. If another connected tool can read your
brokerage positions, take them from there rather than asking the user to retype them. Never ask
anyone for brokerage credentials or account numbers.

The result is arithmetic: the difference between the weights you hold and the weights the model
publishes. It is not a recommendation to trade, and it places no orders.

## Combining with other tools

You may use other connected tools and your own knowledge for context about the companies in a
portfolio - what a company does, recent news, filings, industry background - and should say
where each outside fact came from.

The boundary is arithmetic, not sources: turning outside data into a return, gain, drawdown or
benchmark comparison for these model portfolios is out of scope however the prices are obtained.
Tickers here carry no company name, so resolve a ticker with a connected tool where you can
rather than assuming which company it is - especially outside large US listings.

## Setup

Set your personal API token before use:

```bash
gemini extensions config financial-portfolios-ai
```

It is stored in the extension's `.env` and sent as `X-API-Key`. Generate one at
<${PUBLIC_ORIGIN}/settings/api-tokens>. Without a token the server answers `401`
and no portfolio is visible.

---

Informational and educational purposes only. Not investment, legal, or tax advice, and not a
recommendation or solicitation. No suitability assessment has been performed.
