# What's new in Financial Portfolios AI for Claude and ChatGPT

Plain-language notes for customers. The full technical history is in
[CHANGELOG.md](CHANGELOG.md).

All information is provided for informational and educational purposes only. It is not
investment, legal, or tax advice, and not a recommendation or solicitation. No
suitability assessment has been performed.

---

## Version 1.4.7 — October 2026

- **Clearer tool labels:** every tool now states that it only reads data and never changes or deletes anything.
- **Your holdings, your input:** to compare against a model, share your holdings in the conversation or the Rebalance Studio.

## Version 1.4.6 — October 2026

- **Fixed:** the "get an API token" link now opens the right page (API access) instead of a page that did not exist.

## Version 1.4.5 — October 2026

- **Fixed:** the "Interactive portfolio report", "What changed" and digest starters no longer fail when the number of days is left blank.
- **Easier choices:** starters accept portfolio names such as *Defensive* or *Quality*, and offer drop-downs for the portfolio, the number of days and the research topic.

## Version 1.4.4 — October 2026

- **Shorter setup commands.** The connection is now named `fpai`, so the commands you copy are shorter and your assistant's tool names are easier to read. Connections you have already set up keep working.

---

## Version 1.4.3 — September 2026

- **Clearer messages when something needs a subscription.** Aligning holdings to a model
  needs a subscription to it; your assistant now says exactly that, instead of suggesting
  your sign-in failed.

---

## Version 1.4.2 — September 2026

- **Free access is treated as what it is.** If you read the delayed portfolios without a
  subscription, your assistant now says you're on free access rather than suggesting
  something is wrong with your account.

---

## Version 1.4.1 — September 2026

- **"What can I do?" now has a proper answer.** Ask it, or choose *Start here*, and your
  assistant shows the things you can do with your portfolios, and which ones need a news or
  brokerage connection added first.
- **Check how far your account has drifted** from a model portfolio. It reports the gaps and
  stops there: it never proposes trades, so it is safe to run on a schedule.
- **Ready-made summaries** for performance, for what your portfolios hold in common, and a short
  digest of what changed, written to run on a schedule.
- **Scheduled runs stay read-only.** A task that runs while you are away reports; it never
  prepares or places orders.
- **Acting on an alignment at your broker** always needs your confirmation of each batch of
  orders. There is no standing permission, whatever the broker allows.
- **Fix:** the Portfolio Explorer no longer stays blank if a result arrives in an unexpected shape.

---

## Version 1.4.0 — September 2026

- **Performance is now available**, matching what the website shows: how a model portfolio
  has done against its benchmark, its risk statistics, and which holdings helped and hurt
  most. These figures are hypothetical and simulated - they come from the model's published
  holdings and total-return prices, not from any real account - and the assistant will show
  that notice with them every time.
- **Which stocks the models hold most**, with company names, and how often each appears.
- **Three new interactive panels**, alongside the Portfolio Explorer:
  - *Access & Connection* - what your subscription covers, which books are live and which
    are delayed by about 45 days, and exactly which figures a delayed book leaves out.
  - *Rebalance Studio* - compare your own holdings against a model. If your assistant can
    read your positions from a brokerage connector, it fills them in for you to check;
    otherwise paste them from a spreadsheet. Nothing is calculated until you have looked.
  - *Research Reader* - browse and read the research, with posts flagged when they mention
    a stock your portfolios hold.
  - *Breadth Board* - what your portfolios have in common: the most widely held names, how
    much any two overlap, and which sector dominates each.
- **Concentration and sector figures for delayed books too.** These are worked out from the
  published weights, so a delayed book now shows the same shape a live one does.
- **"What changed"** - which holdings a model opened, closed, raised and cut over a period.
- **The panels work properly on a phone.** Buttons and table headers are large enough to
  tap, and sorting no longer depends on hovering.
- **Your assistant knows what you are looking at.** Ask "why is this one so large?" about a
  row on screen and it follows, without you restating which portfolio or holding.
- **Gemini CLI** is now supported through an installable extension.

Nothing about who can see what has changed: live books still require a subscription, and
everything else remains delayed by about 45 days.

---

## Version 1.3.0 — September 2026

- **Fewer hiccups.** A brief glitch reaching the portal is now retried automatically
  instead of surfacing as an error.
- **Faster to browse.** Switching tabs and comparing portfolios in the Explorer reuses
  data just fetched, so it responds more quickly.

Nothing about your portfolios or what you can see has changed.

---

## Version 1.2.1 — September 2026

- The assistant no longer mistakes a working sign-in for a connection problem.
- You will not be asked for an API token in the conversation. If an assistant ever
  asks you to paste a token or password into a chat, don't - reconnect the connector
  and sign in instead.

---

## Version 1.2.0 — September 2026

- **Ask about this.** A button in the Portfolio Explorer sends a question about what
  you're looking at - a portfolio's holdings, its recent changes, a comparison, or a
  stock search - straight into the conversation.
- **The assistant knows what you're viewing.** Questions like "why did this change?" work
  without describing the screen.
- **Expand.** Open the Explorer full screen for more room on the holdings and comparison
  tables.
- **Looks at home.** The Explorer now matches your assistant's own fonts and colours.

These appear only where your assistant supports them.

---

## Version 1.1.1 — September 2026

- The Portfolio Explorer no longer leaves a large empty area below its content when you
  switch between tabs.

---

## Version 1.1.0 — September 2026

### Explore your portfolios interactively

Ask the assistant to **open the Portfolio Explorer**. An interactive page opens right in
the conversation, where you can:

- **Switch between portfolios** from a dropdown, with each one marked Live or Delayed.
- **Browse holdings** in a table you can sort and filter.
- **See sector weights and concentration** as charts.
- **Check what changed** — positions added, removed, and the biggest weight shifts over
  the last 30 days to a year.
- **Compare two or three portfolios** side by side, including the holdings they share.
- **Find a stock** and see which portfolios hold it, and at what weight.

The Explorer opens in assistants that can display interactive apps, such as Claude. Where
an assistant can't display it, you get the same information as a text answer.

### Ready-made starters

Pick one from the prompt menu instead of typing a question:

| Starter | What it does |
| :--- | :--- |
| My portfolios at a glance | Your subscriptions and what each one holds right now |
| What changed in a portfolio | Positions added and removed, and weight shifts |
| Compare model portfolios | Holdings, sectors and overlap, side by side |
| Which portfolios hold a stock | Every portfolio holding a ticker, with its weight |
| Interactive portfolio report | A shareable page with tables and charts |
| Review a model portfolio | An in-depth look at one portfolio |
| My access and subscription | What your account can see, and why |
| Align my holdings to a model | Compare your own holdings with a model (subscribers) |
| Research digest | A summary of recent research, optionally on one topic |

Leave the portfolio box blank and the starter uses the portfolios you subscribe to.

### See every portfolio, even without a subscription

Signed-in users can now see every model portfolio. Portfolios you subscribe to show the
latest holdings. Other portfolios show their holdings as of about 45 days ago, and are
clearly labelled as delayed.

### Simpler connection to Claude

Add the connector in Claude and sign in when prompted. There is no API key to copy and
paste.

### Good to know

- This connector shows model portfolio holdings, sectors and research. It **does not
  provide prices, returns or performance**, and the assistant should say so if you ask.
- If you connected before this update, remove and re-add the connector so the assistant
  picks up the new features.
