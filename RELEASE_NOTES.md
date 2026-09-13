# What's new in Financial Portfolios AI for Claude and ChatGPT

Plain-language notes for customers. The full technical history is in
[CHANGELOG.md](CHANGELOG.md).

All information is provided for informational and educational purposes only. It is not
investment, legal, or tax advice, and not a recommendation or solicitation. No
suitability assessment has been performed.

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
