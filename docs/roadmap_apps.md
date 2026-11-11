# Roadmap: app UX, prompts and metrics

What to build next on the MCP App, the prompt surface and the derived metrics, and why.
Written 2026-09-19 against 1.3.0.

Everything proposed here is computable from data the portal already returns. Nothing here
needs a new endpoint, a market-data feed or a schema change.

## 1. What the hosts actually do

Not assumptions - `explorer_host_report` records from the deployed service. Query them with
the service's log filter (kept in the private operations runbook).

As of 2026-09-18, three reports exist, all from one host:

| | |
| :--- | :--- |
| host | `chatgpt` 0.0.1, `platform: mobile` |
| capabilities declared | `serverTools`, `updateModelContext`, `message`, `openLinks`, `serverResources`, `logging` |
| display | `displayMode: inline`, `availableDisplayModes: [inline, fullscreen]` |
| device | `touch: true`, **`hover: false`** |
| theme variables supplied | 68 |

Two conclusions:

- **ChatGPT renders the app.** That was an open question through 1.2.x; it is answered.
- **The page uses four of the six capabilities it is offered.** `openLinks` and
  `serverResources` are declared by the host and never consulted.

And one gap: **no Claude host report exists**, though Claude is the client this was
developed against. Either Claude does not execute `visibility: ["app"]` tool calls, or the
Explorer has not been opened there since 1.3.0 deployed. Do not build provider-conditional
behaviour until a single test open settles which.

## 2. The performance firewall

`server.py` is explicit, and `test_server.py:318`, `test_prompts.py:229` and
`test_release.py:52` enforce it:

> Never offer, compute, estimate or chart performance, returns, gains, drawdowns, best or
> worst contributors, or benchmark comparisons - not even approximately, and not by pricing
> the holdings with data from another source.

This rules out "best and worst performing holdings" in the ordinary sense, and it rules out
reaching the same answer by joining our weights to a price feed from another connector.

It does **not** rule out news, company description, or research about holdings, provided
none of it is turned into return arithmetic. The distinction to hold: *what the model owns
and how that changed* is ours to publish; *what it earned* is not.

The substitute for "best / worst" is **conviction change** - the largest weight increases
and decreases the model itself made. That is the strategy's own decision, published in its
own units, and it is often the more interesting question.

## 3. Metric catalogue

Notation: a snapshot is a set of positions with weights `w_i`. The page already detects
whether weights arrive as fractions or percent (`weightScale`); all formulas below assume
**fractions summing to ~1**, so normalise first: `w_i <- w_i / Σw`.

`effective_n` is returned by the portal but is **null on the public delayed book**, as are
`equity_exposure`, `cash_allocation`, `expected_return` and `expected_volatility`. Metrics
marked *derivable* can be computed from weights alone, so they work on the delayed book too
- which is most of the value here, since delayed users currently see the fewest numbers.

### Within one snapshot

| Metric | Formula | Notes |
| :--- | :--- | :--- |
| Position HHI | `Σ w_i²` | concentration; 1/n at equal weight, 1 at single holding |
| Effective N *(derivable)* | `1 / Σ w_i²` | compute when `effective_n` is null - gives delayed users the number |
| Top-N weight | `Σ` of the N largest `w_i` | already shown for N = 5, 10 |
| Max weight | `max w_i` | single-name risk in one number |
| Gini dispersion | `(Σ_i Σ_j \|w_i − w_j\|) / (2n Σ w)` | 0 = equal weight, →1 = one name dominates |
| Sector weight | `w_s = Σ_{i ∈ s} w_i` | already shown |
| **Dominant sector share** | `max_s w_s` | with its name - the "dominant sector" ask |
| **Sector HHI** | `Σ_s w_s²` | sector concentration, distinct from position concentration |
| Effective sectors | `1 / Σ_s w_s²` | "this book is really N sector bets" |
| Unclassified share | `Σ_{i: sector = null} w_i` | honesty check - `sector` is often null |

### Between two snapshots (`get_portfolio_history`)

| Metric | Formula | Notes |
| :--- | :--- | :--- |
| **Conviction change** | `Δw_i = w_i(t₁) − w_i(t₀)`, in pp | the honest "best / worst" - rank both ways |
| **One-way turnover** | `½ Σ_i \|Δw_i\|` | how much of the book actually moved |
| Added / removed | set difference on tickers | already shown |
| Tenure | consecutive snapshots back from `t₁` containing the ticker | separates core holdings from new ideas |
| Sector rotation | `Δw_s` per sector | where the money moved, not just which names |

### Across portfolios

| Metric | Formula | Notes |
| :--- | :--- | :--- |
| **Breadth** | for ticker `t`, count of portfolios holding it | the "mostly held stocks" ask |
| Mean held weight | mean `w_t` over portfolios holding `t` | breadth alone over-weights token positions |
| Weight overlap | `Σ_i min(w_i^A, w_i^B)` | "these two books are 62% the same money" |
| Jaccard overlap | `\|A ∩ B\| / \|A ∪ B\|` | name overlap, ignoring size |

### Deliberately excluded

Portfolio-level aggregation of `expected_return` (`Σ w_i · r_i`) is **not** in this list. Per
position it is model metadata the portal already publishes; aggregated and labelled, it
reads as a return projection for the portfolio. Needs a compliance decision before it ships,
not an engineering one. `expected_volatility` aggregation is worse - a correct figure needs
a covariance matrix we do not have, so any sum would be wrong as well as risky.

## 4. Prompts to add

Existing nine are inventoried in `prompts.py`. Proposed additions:

| Name | Argument | What it does |
| :--- | :--- | :--- |
| `sector_exposure` | `portfolio` | dominant sector, sector HHI, effective sectors, unclassified share |
| `most_held_stocks` | none | breadth across the user's portfolios |
| `conviction_changes` | `portfolio`, `days` | largest weight moves + turnover |
| `research_on_my_holdings` | `portfolio` | joins `list_blog_posts` to held tickers - first-party data only |
| `holdings_news_brief` | `portfolio` | qualitative news on held companies **via whatever market-data connector the host has**; must restate the no-performance boundary |
| `explain_a_holding` | `ticker` | what the company is; description, never recommendation |

Two cheap fixes in the same area:

- `ticker` (on `find_holding`) has **no autocomplete**. It should complete from tickers
  actually held, which we can assemble from the portfolios we already cache.
- The resource template `portfolios://{portfolio_code}/allocation` has **no completion
  handler at all** - `complete_portfolio_code` only answers `PromptReference`. Hosts that
  offer resource pickers cannot autocomplete a portfolio code.

### Ship each as a prompt *and* a tool

Prompt support is confirmed in Claude and **unverified in ChatGPT**. If ChatGPT surfaces no
prompt picker, every prompt above is invisible to those users. A thin tool wrapper per
analysis costs little and removes the dependency on a difference we have not measured.

## 5. Leveraging the model

The division of labour that makes this connector more useful without widening its data
surface:

> We publish **what the model holds and how that changed**. The host's other connectors
> publish news, fundamentals and prices. The LLM joins them. The firewall in §2 stays up:
> no connector's prices may be used to compute our portfolios' returns.

The practical obstacle is that we return **tickers only - no company name** anywhere in the
schema. Ticker → company is a mapping the model does well for US large caps and unreliably
elsewhere. Prompts that cross connectors should say so, and prefer the model asking the
other connector to resolve the ticker over guessing from memory.

## 6. App improvements

Ordered by evidence that they matter.

1. **Touch and mobile.** The one host we have data for reports `hover: false`. Today
   `th.sortable:hover` and `.action:hover` are the only affordances saying those elements are
   interactive, and tap targets run 4-11px of padding. Make sort affordances visible without
   hover; raise targets toward ~44px.
2. **Richer model context.** `ui/update-model-context` is already wired but sends only the
   selection. Sending *what is on screen* - active tab, filter, sort, the visible rows -
   lets the model answer "why is this one so big?" about the row the user is looking at.
   This is the highest-value item on the list and the capability is already declared.
3. **`openLinks`.** Declared, unused. "Open in portal" per portfolio.
4. **Selection → question.** Let rows be selected, then ask about the selection via the
   `ui/message` path that already exists.
5. **Fullscreen on mobile.** `fullscreen` is available and the Expand button exists; on a
   mobile host, offer it up front rather than waiting to be found.
6. **New tabs** once §3 lands: *Breadth* (across portfolios) and *Research* (blog posts
   matching held tickers).

## 7. Order of work

1. ~~App items 1-2~~ **done** - touch affordances, and the Explorer now sends what is on
   screen rather than only the selection.
2. ~~Metrics from §3~~ **done** - `metrics.py`, computed server-side so the apps, any future
   tools and hosts that render nothing all share one implementation and one set of tests.
3. **Prompts and their tool twins from §4** - still open. The provider research in
   [providers_and_automation.md](providers_and_automation.md) strengthens the case: prompts
   are effectively invisible in ChatGPT and disputed on claude.ai, so the tool half is what
   customers will actually reach.
4. ~~App items 3-6~~ mostly done through the three new apps (Access & Connection, Rebalance
   Studio, Research Reader, Breadth Board). `openLinks` is now used by the Access panel;
   selection-to-question and a saved app state remain open.
5. **A digest tool** - "what changed since last week" as a single call, which is the shape a
   scheduled task on either host needs.

Verify before building anything provider-conditional: whether Claude reports a host context
at all, and whether ChatGPT surfaces prompts. See §5 of the provider notes.

## 8. Decisions

### Decided 2026-09-19: parity with the web portal, not a narrower connector

§2 of this document recommended keeping "best / worst" firewalled. **That recommendation was
wrong**, and the reason is worth recording so it is not re-argued.

The premise was that publishing performance for these model portfolios was a line the
business had not crossed. It had. The portal displays performance figures and discloses
them as such - its disclaimer reads *"All performance data, metrics, and figures shown are
simulated or hypothetical and do not represent actual trading results"*, and the public site
repeats it as *"based on simulated, hypothetical, or back-tested results."* Best and worst
performers, most-held stocks and other per-product metrics are shown to customers there.

So the connector was not being cautious, it was being **inconsistent**: a customer sees a
figure on the website and is told by the assistant that it does not exist. The decision is
to surface what the portal surfaces.

The firewall keeps the half that earns something:

| | |
| :--- | :--- |
| **Allowed** | Figures the portal publishes, relayed with the portal's own simulated/hypothetical disclosure attached |
| **Still refused** | Performance this connector computes itself by pricing holdings from a market-data connector |

The distinction is authorship, not subject. A figure the publisher produced and labelled is
the publisher's to publish. A figure we derive from someone else's prices is one nobody
vetted, carries no hypothetical labelling, and would not match the website - three separate
problems in one number.

Consequences to carry through:

- `DISCLAIMER` currently ends "All outputs represent mathematical target-model alignment
  arithmetic", which stops being true the moment a performance figure is returned. That text
  is the portal's ADR-0161 constant, so **the wording change belongs to the portal**, not
  here - we import it.
- The three tests that enforce the ban (`test_server.py`, `test_prompts.py`,
  `test_release.py`) must be rewritten to enforce the new rule rather than deleted: that a
  performance figure never appears without its disclosure, and that the model is still told
  not to compute its own.
- Anything the portal computes in its frontend only has to reach `/api/v1` first. That is a
  Portal-side request, not work we can do here.

### Still open

| Question | Owner |
| :--- | :--- |
| May `expected_return` be aggregated to portfolio level? | compliance |
| Is cross-connector news in scope for a regulated surface? | compliance |
