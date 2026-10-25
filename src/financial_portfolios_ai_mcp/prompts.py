"""Prompt templates for Financial Portfolios AI MCP Server.

Prompts are the ready-made starters a client lists for the user (Claude shows them
with an input dialog). Each argument therefore carries a description, because the
client renders that as the field's help text - without one the user sees a bare
parameter name and an empty box.

Portfolio-code arguments are optional. Left blank, the prompt resolves the user's
own subscribed portfolios through `list_portfolios` instead of assuming one: a fixed
default would silently review a model the user may not even hold.

Every prompt stays inside what the tools can actually do, and none asks the model to
recommend a security, a trade or a portfolio choice.
"""

import logging
import re
from typing import Annotated, Any

from mcp.types import Completion, CompletionArgument, PromptReference, ResourceTemplateReference
from pydantic import Field

from financial_portfolios_ai_mcp import portal
from financial_portfolios_ai_mcp.auth import get_async_client
from financial_portfolios_ai_mcp.config import get_settings
from financial_portfolios_ai_mcp.disclosure import DISCLAIMER_TEXT

logger = logging.getLogger(__name__)

# Arguments whose values are portfolio codes, for live autocompletion.
# Input names double as the labels Claude shows ("portfolio" -> "Portfolio"): the SDK does
# not pass an argument title through, so a readable name is the only way to get a readable label.
SINGLE_PORTFOLIO_ARGUMENTS = frozenset({"portfolio"})
MULTI_PORTFOLIO_ARGUMENTS = frozenset({"portfolios"})
# The variable in `portfolios://{portfolio_code}/allocation`. A resource template is
# completed the same way a single-code prompt argument is.
TEMPLATE_PORTFOLIO_ARGUMENTS = frozenset({"portfolio_code"})
TICKER_ARGUMENTS = frozenset({"ticker"})
DAYS_ARGUMENTS = frozenset({"days"})
TOPIC_ARGUMENTS = frozenset({"topic"})
# Drop-down choices for the free-text inputs. A client shows completion values as a picker, so a
# short list of sensible values turns a blank box into a choice; typing anything else still works.
DAY_CHOICES = ("7", "30", "90", "180", "365")
TOPIC_CHOICES = ("Inflation", "Interest rates", "Energy", "AI and technology", "Earnings", "Market regime")

PortfolioCode = Annotated[
    str,
    Field(
        description=(
            "Model portfolio, e.g. Defensive, Balanced, Aggressive or Quality (the code, such as "
            "AQA_DEFENSIVE, works too). Leave blank to use the portfolios you subscribe to."
        )
    ),
]

# Shared instructions. Kept as constants so every prompt handles the delayed book and
# the advice boundary identically.
_RESOLVE_PORTFOLIOS = """\
Call `list_portfolios` first. Use the entries marked `access: "subscribed"` - those are
the user's own portfolios. If none are subscribed, the user is on free access, which is
normal rather than a problem: continue with the public delayed book of every listed portfolio."""

_DELAYED_BOOK = """\
Access levels: a `subscribed` portfolio returns the latest book. Anything else returns
the public book delayed by about 45 days, with expected return, expected volatility,
equity exposure, cash allocation and effective N set to null. Whenever a response has
`delayed: true`, state its `as_of` date and say the holdings are delayed - never present
a delayed book as the current allocation, and never fill in the null metrics."""

_PANELS = """\
Offer the matching interactive panel where one fits, rather than only printing a long table:
`open_portfolio_explorer` to browse one portfolio, `open_breadth_board` for anything spanning
portfolios, `open_rebalance_studio` for alignment, `open_research_reader` for research, and
`open_access_centre` for access questions. Offer it; do not insist. A client that cannot render
panels still receives the same data as JSON, so answer from that rather than telling the user
their client is unsupported."""

_PERFORMANCE = """\
Performance comes from `get_portfolio_performance` (curve and risk statistics) and
`get_portfolio_metrics` (best and worst performers, most-held names, win rates). Both are
hypothetical and simulated. Whenever you show any of those figures, include the `disclaimer`
field from that same response, in full and unaltered. Check `available` first: while price
history is backfilling it is false with a `reason`, which you should report rather than treat as
an error or as zero. Never compute a return, gain, drawdown or benchmark comparison yourself, or
from prices obtained elsewhere."""

_BOUNDARY = """\
Stay informational. Describe what the model portfolios contain and how they differ; do
not recommend buying, selling or holding any security, and do not tell the user which
portfolio suits them - no suitability assessment has been performed. If asked, say so
and point them to a licensed adviser."""


def _to_code(value: str) -> str:
    """Map what a user types or picks to a portfolio code: "Defensive" -> "AQA_DEFENSIVE".

    Product names are the code without its "AQA_" prefix (Balanced, Aggressive, Defensive,
    Quality), so the mapping needs no portal call - prompts render synchronously and must not
    fail on a network error. Anything already starting with AQA_ is passed through.
    """
    raw = (value or "").strip()
    if not raw:
        return ""
    code = re.sub(r"[^A-Z0-9]+", "_", raw.upper()).strip("_")
    return code if code.startswith("AQA_") else f"AQA_{code}"


def _code_or_subscribed(portfolio: str) -> str:
    raw = (portfolio or "").strip()
    if raw:
        code = _to_code(raw)
        return (
            f"Portfolio: '{code}' (the user chose '{raw}'). Use this code directly; if "
            "`get_portfolio_allocation` does not recognise it, call `list_portfolios` and match "
            "the user's words against each entry's `product_name`."
        )
    return _RESOLVE_PORTFOLIOS


def _days(value: Any, default: int) -> int:
    """Parse a `days` argument. MCP prompt arguments arrive as strings, and a client sends an
    untouched optional field as "" - which an `int` parameter rejected, so the whole prompt
    failed to render ("Error rendering prompt portfolio_report", 2026-10-25). Blank or invalid
    means the default; anything else is clamped to 1-365."""
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return max(1, min(365, n))


def _days_field(default: int, what: str) -> Any:
    return Annotated[
        str,
        Field(description=f"{what}, from 1 to 365. Leave blank for {default}."),
    ]



async def _complete_ticker(value: str) -> Completion:
    """Suggest tickers the user's portfolios actually hold.

    `find_holding` asks which portfolios hold a stock, and the useful answers are the
    tickers that are in a book at all - typing one that is held nowhere returns an empty
    search. Reads go through the shared cache, so the suggestions cost nothing when the
    portfolios have already been looked at.

    Best-effort like the rest of completion: any failure yields no suggestions rather than
    breaking the dialog, and a portfolio that cannot be read is skipped instead of losing
    the ones that could.
    """
    typed = value.strip().upper()
    settings = get_settings()
    try:
        async def fetch_list() -> dict[str, Any]:
            async with get_async_client() as client:
                return (await client.list_portfolios()).model_dump()

        listing = await portal.read("list_portfolios", settings.cache_ttl_portfolios, fetch_list)
    except Exception:  # noqa: BLE001 - completion is best-effort by design
        return Completion(values=[], total=0, has_more=False)

    tickers: set[str] = set()
    for entry in listing.get("portfolios") or []:
        code = entry.get("code")
        if not code:
            continue
        try:
            async def fetch_allocation(code: str = code) -> dict[str, Any]:
                async with get_async_client() as client:
                    return (await client.get_portfolio(portfolio_code=code)).model_dump()

            allocation = await portal.read(
                "get_portfolio_allocation",
                settings.cache_ttl_allocation,
                fetch_allocation,
                portfolio_code=str(code).upper(),
                as_of=None,
            )
        except Exception as exc:  # noqa: BLE001 - one unreadable book must not lose the others
            logger.debug("ticker completion skipped %s: %s", code, exc)
            continue
        for position in allocation.get("positions") or []:
            ticker = str(position.get("ticker") or "").upper()
            if ticker:
                tickers.add(ticker)

    values = sorted(t for t in tickers if t.startswith(typed))
    return Completion(values=values[:100], total=len(values), has_more=len(values) > 100)


def _complete_fixed(choices: tuple[str, ...], value: str) -> Completion:
    """Offer a fixed list as a drop-down, narrowed by what has been typed."""
    typed = value.strip().lower()
    values = [c for c in choices if typed in c.lower()]
    return Completion(values=values, total=len(values), has_more=False)


async def complete_portfolio_code(ref: Any, argument: CompletionArgument, context: Any) -> Completion | None:
    """Suggest the user's live portfolio codes for portfolio inputs.

    `portfolio` takes one code. `portfolios` takes a comma-separated list, so the
    suggestion completes the fragment after the last comma and keeps what was already
    entered, leaving out codes already chosen - a client replaces the whole value with
    the suggestion, so each suggestion must be the full value.

    Subscribed portfolios come first. Any failure - no credential yet, portal
    unreachable - yields no suggestions rather than an error, since completion is a
    typing aid and must never break the prompt dialog.
    """
    name = argument.name
    if isinstance(ref, ResourceTemplateReference):
        # `portfolios://{portfolio_code}/allocation`. Hosts that offer a resource picker
        # could not complete this at all before: only PromptReference was answered.
        if name not in TEMPLATE_PORTFOLIO_ARGUMENTS:
            return None
        single = True
    elif isinstance(ref, PromptReference):
        if name in TICKER_ARGUMENTS:
            return await _complete_ticker(argument.value or "")
        if name in DAYS_ARGUMENTS:
            return _complete_fixed(DAY_CHOICES, argument.value or "")
        if name in TOPIC_ARGUMENTS:
            return _complete_fixed(TOPIC_CHOICES, argument.value or "")
        if name not in SINGLE_PORTFOLIO_ARGUMENTS and name not in MULTI_PORTFOLIO_ARGUMENTS:
            return None
        single = name in SINGLE_PORTFOLIO_ARGUMENTS
    else:
        return None

    value = argument.value or ""
    if single:
        chosen, fragment = [], value
    else:
        *chosen, fragment = value.split(",")
        chosen = [c.strip() for c in chosen if c.strip()]
    typed = fragment.strip().upper()

    try:
        async with get_async_client() as client:
            result = await client.list_portfolios()
    except Exception:  # noqa: BLE001 - completion is best-effort by design
        return Completion(values=[], total=0, has_more=False)

    # Prompts take the readable product name ("Defensive") and map it to the code themselves, so
    # that is what the drop-down offers. A resource template needs the literal code. Matching is
    # on any part of the name or code, so "def", "Defensive" and "AQA_DEF" all find it.
    taken = {_to_code(c) for c in chosen}
    ranked = sorted(result.portfolios, key=lambda p: p.access != "subscribed")

    def label(p: Any) -> str:
        if isinstance(ref, ResourceTemplateReference):
            return p.code
        return (getattr(p, "product_name", None) or p.code.removeprefix("AQA_").title()).strip()

    labels = [
        label(p)
        for p in ranked
        if p.code.upper() not in taken
        and (typed in p.code.upper() or typed in (getattr(p, "product_name", "") or "").upper())
    ]
    prefix = ", ".join(chosen)
    values = [f"{prefix}, {lab}" if prefix else lab for lab in labels]
    return Completion(values=values[:100], total=len(values), has_more=len(values) > 100)

def register_prompts(server: Any) -> None:
    """Register MCP prompt templates and argument completion with the server."""

    # ------------------------------------------------------------------ #
    # Orientation
    # ------------------------------------------------------------------ #
    @server.prompt(
        name="start_here",
        title="Start here: what can I do?",
        description=(
            "A menu of the things you can do with your model portfolios, what each one needs "
            "connected, and how to run them on a schedule."
        ),
    )
    def start_here() -> str:
        return f"""You are an onboarding guide for Financial Portfolios AI. The user wants to know what they can do.

{DISCLAIMER_TEXT}

1. Call `list_portfolios` so the menu can use their real portfolio names, and note which are subscribed and which are delayed.
2. Check which other tools this conversation has: a market-data or news connector (company news, filings, prices) and a brokerage or aggregator connector (positions). Do not call them; just look at what is available.
3. Present this menu, one line each, marking any journey whose extra connector is missing as "needs a ... connector":

| Journey | Ask | Uses |
|---|---|---|
| What my subscription shows me | "What can my account see?" | `open_access_centre` |
| Show me a portfolio | "Show me <portfolio>" | `open_portfolio_explorer` |
| How has it done | "How has <portfolio> performed?" | `get_portfolio_performance` |
| News on what it holds | "What's the news on <portfolio>'s top holdings?" | holdings + news connector |
| What the portfolios agree on | "What do my portfolios have in common?" | `open_breadth_board` |
| How far my account has drifted | "How far has my account drifted from <portfolio>?" | brokerage connector + `open_rebalance_studio` |
| Align my account | "Align my account to <portfolio>" | `open_rebalance_studio`; orders are proposed, you confirm and place them |
| Keep me posted | "Every Monday, summarise what changed" | your assistant's scheduler, read-only |

4. If a connector is missing, say in one sentence what kind to add and what it unlocks. Do not name it as a requirement for the other journeys.
5. For "keep me posted", say that scheduled runs report only: they never prepare or place orders.
6. End by asking which one they'd like, and offer to start the first.

{_DELAYED_BOOK}

{_BOUNDARY}"""

    @server.prompt(
        name="my_portfolios",
        title="My portfolios at a glance",
        description=(
            "See which model portfolios you subscribe to and what each one holds right now, "
            "plus the other portfolios available on a delayed basis."
        ),
    )
    def my_portfolios() -> str:
        return f"""You are an educational assistant for Financial Portfolios AI, giving the user an overview of their account's portfolios.

{DISCLAIMER_TEXT}

1. Call `list_portfolios`.
2. For each portfolio with `access: "subscribed"`, call `get_portfolio_allocation` and summarise it in one short section: number of positions, the five largest holdings with weights, the largest sectors, and equity exposure vs cash.
3. List the remaining portfolios in a compact table - name, code, risk level, theme - and note that they are available as the public delayed book.
4. If the user subscribes to nothing, they are on free access, which is normal: give the table of all portfolios with their delayed dates, and mention once that a subscription adds the live book.
5. Close by offering, in one line, where to go next: `open_portfolio_explorer` to browse a portfolio, `open_breadth_board` to see what the portfolios have in common, or `open_access_centre` to see exactly what this account can view.

{_PANELS}

{_DELAYED_BOOK}

{_BOUNDARY}

End with the disclaimer."""

    @server.prompt(
        name="access_help",
        title="My access and subscription",
        description=(
            "Explains what your account can see: live vs 45-day-delayed holdings, which "
            "portfolios you subscribe to, and what needs a subscription."
        ),
    )
    def access_help() -> str:
        portal = get_settings().portal_base_url.rstrip("/")
        return f"""You are a support assistant for Financial Portfolios AI. The user wants to understand what their account can access.

{DISCLAIMER_TEXT}

1. Open `open_access_centre`. It shows this in one view: every portfolio with a live or delayed badge, exactly which figures the delayed book withholds, and how the connection is signed in. Prefer it over describing all of this in prose.
2. Use its result - or `list_portfolios` if you would rather answer in text - and explain, in plain language and with the user's actual portfolio names:
   - Subscribed portfolios show the latest holdings, including expected return and risk metrics.
   - Other portfolios show the public book, with holdings delayed by about 45 days and without those premium metrics.
   - Model alignment calculations (`rebalance_portfolio`) are available only for subscribed portfolios.
3. If the user is not subscribed to a portfolio they asked about, tell them live holdings for it come with a subscription, available from the Pricing section of the portal at {portal}/#pricing. Do not quote share prices; you do not have them.
4. If `list_portfolios` fails with an authentication error, the connection has lost its sign-in: tell the user to reconnect the connector and sign in again.

Do not call `get_token_info` for this - it describes API tokens, not subscriptions.

{_BOUNDARY} That includes which portfolio to subscribe to: describe the options, but do not choose one for the user.

End with the disclaimer."""

    # ------------------------------------------------------------------ #
    # Holdings
    # ------------------------------------------------------------------ #
    @server.prompt(
        name="portfolio_review",
        title="Review a model portfolio",
        description=(
            "In-depth look at one model portfolio: holdings and weights, sector mix, "
            "concentration, and equity vs cash."
        ),
    )
    def portfolio_review(portfolio: PortfolioCode = "") -> str:
        return f"""You are an educational quantitative portfolio analyst for Financial Portfolios AI.

{DISCLAIMER_TEXT}

{_code_or_subscribed(portfolio)}

For each portfolio:
1. Call `get_portfolio_allocation`.
2. Show the holdings in a table sorted by weight: ticker, sector, weight, and - when present - expected return and expected volatility.
3. Call `get_portfolio_concentration` for the sector mix and the concentration figures. Do not work them out by hand: it derives effective N, the dominant sector and the unclassified share from the weights, so they are available on a delayed book too, where the portal returns effective N as null.
4. Report equity exposure against cash allocation when present.
5. Offer the next step rather than fetching it unprompted: what changed recently, how it has performed, or the Explorer panel to browse it interactively.

{_PANELS}

{_DELAYED_BOOK}

{_BOUNDARY}

End with the disclaimer."""

    @server.prompt(
        name="portfolio_changes",
        title="What changed in a portfolio",
        description=(
            "Shows how a model portfolio's holdings changed over a period: positions added, "
            "removed, and the biggest weight shifts."
        ),
    )
    def portfolio_changes(
        portfolio: PortfolioCode = "",
        days: _days_field(30, "How many days back to look") = "",
    ) -> str:
        days = _days(days, 30)
        return f"""You are an educational assistant for Financial Portfolios AI, explaining how a model portfolio has changed.

{DISCLAIMER_TEXT}

{_code_or_subscribed(portfolio)}

For each portfolio:
1. Call `get_portfolio_changes` with days={days}. It compares the oldest and newest snapshot in the window and returns what was added, removed, raised and cut, with one-way turnover. Use it rather than diffing `get_portfolio_history` yourself.
2. Report:
   - Positions added (ticker, sector, new weight) and removed (ticker, sector, previous weight).
   - The largest increases and decreases, with old weight, new weight and the change in percentage points.
   - Turnover, as how much of the book moved over the period.
3. If `comparable` is false, say why using the `message` it returns - a short window, or a delayed book whose history ends about 45 days ago - and suggest a longer period. Do not report zeros, which would read as "the model changed nothing".
4. These are the model's own decisions, not returns. If the user wants to know what did well, that is `get_portfolio_metrics`, not this.

For a delayed portfolio the history ends about 45 days ago, so it cannot show recent changes - say this explicitly rather than implying the model has been static.

{_DELAYED_BOOK}

{_BOUNDARY} Describe changes as what the model did, not as actions the user should copy.

End with the disclaimer."""

    @server.prompt(
        name="compare_portfolios",
        title="Compare model portfolios",
        description=(
            "Side-by-side comparison of the model portfolios: risk level, holdings, "
            "sector mix, concentration, and overlap."
        ),
    )
    def compare_portfolios(
        portfolios: Annotated[
            str,
            Field(
                description=(
                    "Comma-separated portfolios to compare, e.g. Defensive, Balanced (codes such as "
                    "AQA_DEFENSIVE work too). Leave blank to compare every portfolio."
                )
            ),
        ] = "",
    ) -> str:
        codes = [_to_code(c) for c in (portfolios or "").split(",") if c.strip()]
        which = (
            "Compare these portfolios: " + ", ".join(f"'{c}'" for c in codes) + "."
            if codes
            else "Call `list_portfolios` and compare every portfolio it returns."
        )
        return f"""You are an educational assistant for Financial Portfolios AI, comparing model portfolios.

{DISCLAIMER_TEXT}

{which}

1. If the comparison covers every portfolio the user has, `open_breadth_board` answers it in one call: most widely held names, pairwise overlap by name and by weight, and each book's dominant sector and concentration. Prefer it, and fall back to the steps below for a specific subset.
2. Otherwise call `get_portfolio_allocation` and `get_portfolio_concentration` for each portfolio.
3. Build one comparison table with a column per portfolio: risk level, theme, number of positions, top-five combined weight, effective N, largest sector, and equity exposure / cash when present.
4. Show the sector mix side by side, as weights per sector.
5. Report overlap: tickers held by more than one portfolio, with each portfolio's weight. Two books can share most of their names and little of their weight, so say which you mean.
6. Summarise the main differences in two or three neutral sentences.

The books may be on different dates - some subscribed and latest, some delayed. Show each column's `as_of` date and warn that a latest book and a delayed book are not a like-for-like comparison.

{_DELAYED_BOOK}

{_BOUNDARY} In particular, do not say which portfolio is better or which one the user should choose.

End with the disclaimer."""

    @server.prompt(
        name="find_holding",
        title="Which portfolios hold a stock",
        description="Look up a stock across the model portfolios: which ones hold it, at what weight, and in which sector.",
    )
    def find_holding(
        ticker: Annotated[str, Field(description="Stock ticker to look up, e.g. NVDA or MSFT.")],
    ) -> str:
        symbol = (ticker or "").strip().upper()
        return f"""You are an educational assistant for Financial Portfolios AI. The user wants to know where '{symbol}' appears in the model portfolios.

{DISCLAIMER_TEXT}

1. Call `list_portfolios`, then `get_portfolio_allocation` for every portfolio. For "which stocks appear across my portfolios" rather than one named stock, use `open_breadth_board` instead - it answers that directly.
2. Report a table of the portfolios holding '{symbol}': portfolio, weight, sector, its rank by weight within that portfolio, and the book's date.
3. List the portfolios that do not hold it.
4. If no portfolio holds it, say so. Mention that a delayed book is about 45 days old, so a recently added position would not show there yet.

Match tickers exactly, case-insensitively. Do not guess at similar symbols or share classes; if a close variant appears, mention it separately and let the user decide.

{_DELAYED_BOOK}

{_BOUNDARY} A stock's presence in a model is not a recommendation to own it.

End with the disclaimer."""

    @server.prompt(
        name="portfolio_report",
        title="Interactive portfolio report",
        description=(
            "Builds an interactive report for a model portfolio: sortable holdings, sector and "
            "concentration charts, and recent changes, as a shareable page."
        ),
    )
    def portfolio_report(
        portfolio: PortfolioCode = "",
        days: _days_field(90, "Days of history to show changes for") = "",
    ) -> str:
        days = _days(days, 90)
        return f"""You are building an interactive, educational report on a Financial Portfolios AI model portfolio.

{DISCLAIMER_TEXT}

{_code_or_subscribed(portfolio)}

Gather the data first:
1. Call `get_portfolio_allocation` for the portfolio.
2. Call `get_portfolio_changes` with days={days}.
3. Call `get_portfolio_concentration` for the concentration and sector figures.
4. Call `get_portfolio_performance` and `get_portfolio_metrics`. If either reports `available: false`, omit that section and say why rather than leaving a gap.

Then build the report as a single self-contained interactive page (an artifact where the client supports one), with these sections:
- Header: portfolio name and code, the book's `as_of` date, and - if `delayed` is true - a prominent "Holdings delayed ~45 days" badge.
- Key figures: number of positions, top-five and top-ten combined weight, and effective N, equity exposure and cash allocation when present. Omit a figure that is null rather than showing zero.
- Holdings: a sortable, filterable table of ticker, sector and weight, plus expected return and expected volatility when present.
- Sector mix: a chart of total weight per sector.
- Concentration: a chart of cumulative weight by holding rank.
- Performance: the curve against its benchmark and the headline statistics, with the `disclaimer` from that response reproduced on the page, in full, next to the figures. Omit the whole section rather than showing figures without it.
- Best and worst performers, and the most-held names, from `get_portfolio_metrics` - again with its disclosure beside them.
- Changes over the period: positions added and removed, and the largest weight shifts, with turnover. Skip this section if there is nothing to compare, and say why.
- Footer: the full disclaimer text above, verbatim, visible on the page itself - the report may be shared without this conversation.

Use only numbers returned by the tools. Performance figures come from `get_portfolio_performance` and `get_portfolio_metrics` and are hypothetical and simulated; if you include any of them, show the `disclaimer` from that response with them, in full and unaltered. Never compute, estimate or chart a return, gain, drawdown or benchmark comparison yourself, and never from prices obtained elsewhere - a figure derived that way is not the publisher's and will not match the website.

{_DELAYED_BOOK}

{_BOUNDARY}"""

    # ------------------------------------------------------------------ #
    # Calculations and research
    # ------------------------------------------------------------------ #
    @server.prompt(
        name="rebalance_advisor",
        title="Align my holdings to a model",
        description=(
            "Walks you through comparing your own holdings with a model portfolio and "
            "calculates the share differences. Requires a subscription to that portfolio."
        ),
    )
    def rebalance_advisor(portfolio: PortfolioCode = "") -> str:
        return f"""You are an educational assistant for Financial Portfolios AI. Guide the user through model alignment arithmetic: the share-quantity differences between their holdings and a target model.

{DISCLAIMER_TEXT}
These calculations are target-model alignment arithmetic only - not trade execution and not individualized advice.

{_code_or_subscribed(portfolio)}

1. Confirm access before asking for any holdings: call `list_portfolios` and check the target has `access: "subscribed"`. Alignment calculations require a subscription. If the target is not subscribed, explain that and stop - do not collect the user's holdings.
2. Get the holdings without making the user retype them. If a brokerage, custodian or portfolio-tracking connector is available, read the positions from there. Never ask anyone for brokerage credentials or account numbers.
3. Open `open_rebalance_studio`, passing `holdings` when you have them. It shows the positions in an editable table so the user can correct them before anything is calculated - positions read from another service can be stale, partial, or from a different account than they mean. With no connector to read from, the panel is also where they paste or type them; `get_rebalance_template` gives the format. Limits: 200 rows, 512 KB.
4. If the client cannot render the panel, collect the holdings in the conversation and call `rebalance_portfolio` directly.
5. Present the results:
   - Positions with a calculated reduction (negative delta) to match the target weight.
   - Positions with a calculated addition (positive delta).
   - The net cash implied by the alignment.
6. Remind the user that any trading decision is theirs alone, and that the model's weights are not tailored to their circumstances.

{_BOUNDARY}

End with the disclaimer."""

    @server.prompt(
        name="market_research_digest",
        title="Research digest",
        description="Summarises the latest research articles and market commentary, optionally on one topic.",
    )
    def market_research_digest(
        topic: Annotated[
            str,
            Field(description="Optional topic to focus on, e.g. inflation, energy or AI. Leave blank for the latest research."),
        ] = "",
    ) -> str:
        subject = (topic or "").strip()
        search = (
            f"Call `list_blog_posts` with search='{subject}' and page_size=20."
            if subject
            else "Call `list_blog_posts` with page=1 and page_size=20."
        )
        focus = f" on '{subject}'" if subject else ""
        return f"""You are a quantitative research analyst for Financial Portfolios AI. Synthesise the portal's research{focus}.

{DISCLAIMER_TEXT}

1. {search}
2. Call `get_blog_post` on the most relevant articles to read them in full.
2b. If the user wants to browse or read rather than receive a synthesis, offer `open_research_reader` - it lists and opens posts in place, and marks the ones mentioning a ticker their portfolios hold.
3. Summarise the key quantitative insights, regime shifts, macro context and factor trends, citing each article by title and date.
4. If a search returns nothing, say so and offer the latest research instead.

Do not pad with market commentary that isn't in the articles.

{_BOUNDARY}

End with educational takeaways and the disclaimer."""

    @server.prompt(
        name="portfolio_performance",
        title="How a portfolio has performed",
        description=(
            "How a model portfolio has done against its benchmark, its risk statistics, and "
            "which holdings helped and hurt most. Figures are hypothetical and simulated."
        ),
    )
    def portfolio_performance(portfolio: PortfolioCode = "") -> str:
        return f"""You are an educational assistant for Financial Portfolios AI, presenting published performance figures.

{DISCLAIMER_TEXT}

{_code_or_subscribed(portfolio)}

For each portfolio:
1. Call `get_portfolio_performance`. If `available` is false, report the `reason` plainly - the history is still being built - and stop there for that portfolio.
2. Give the headline figures: total and annualized return, volatility, Sharpe, Sortino and maximum drawdown, each against the benchmark's, and the period they cover.
3. Give the relative figures - beta, alpha, information ratio, tracking error, correlation - and say in one sentence what each describes, for a reader who may not know.
4. Call `get_portfolio_metrics` and show the best and worst performers with their returns, and the win rate by name and by invested capital.
5. Say whether these are the live or the delayed figures, using `access` and `delayed`, and give the date range.

{_PERFORMANCE}

{_PANELS}

{_BOUNDARY} Past figures, hypothetical or not, say nothing about what comes next, and nothing here suggests the user should buy, sell or hold anything.

End with the disclaimer."""

    @server.prompt(
        name="most_held_stocks",
        title="What my portfolios hold in common",
        description=(
            "The stocks held across several of your model portfolios, how much any two "
            "overlap, and which sector dominates each."
        ),
    )
    def most_held_stocks() -> str:
        return f"""You are an educational assistant for Financial Portfolios AI, describing what the user's model portfolios have in common.

{DISCLAIMER_TEXT}

1. Call `open_breadth_board`. It reads every portfolio and returns the cross-portfolio view in one call: names held in more than one book, pairwise overlap, and each book's concentration and dominant sector.
2. Report the most widely held names: how many portfolios hold each, the average weight where held, and the largest single weight.
3. Report the overlap between each pair, distinguishing shared names from shared weight - two books can hold most of the same names and put very different money behind them.
4. Note any portfolio listed in `unavailable`: the counts cover the rest only, so say so rather than presenting a smaller number as the whole picture.
5. Flag any book that is delayed or on a different date, since overlap partly reflects timing.

Breadth is not conviction and not a recommendation: a name held everywhere at a token weight is not the same as one held twice at a large weight, and neither is advice to own it.

{_DELAYED_BOOK}

{_BOUNDARY}

End with the disclaimer."""

    @server.prompt(
        name="portfolio_digest",
        title="Recurring portfolio digest",
        description=(
            "A short, repeatable summary of what changed across your portfolios - written to "
            "be run on a schedule, as a Claude Cowork task, a routine, or a ChatGPT task."
        ),
    )
    def portfolio_digest(
        days: _days_field(7, "How many days the digest should cover") = "",
    ) -> str:
        days = _days(days, 7)
        return f"""You are producing a recurring digest of the user's Financial Portfolios AI model portfolios, covering the last {days} days.

{DISCLAIMER_TEXT}

This runs unattended on a schedule, so it must be short, self-contained and safe to read out of context. Do not ask the user questions; if something is unavailable, say so and continue.

1. Call `list_portfolios`.
2. For each subscribed portfolio, call `get_portfolio_changes` with days={days}.
3. Write at most one short section per portfolio:
   - One line saying whether anything changed at all.
   - What was added and removed, by ticker.
   - The two or three largest weight moves, in percentage points.
   - Turnover, as how much of the book moved.
4. Skip a portfolio whose `comparable` is false, with a one-line reason - typically too short a window, or a delayed book whose history ends about 45 days ago.
5. If nothing changed anywhere, say exactly that in one sentence. A quiet period is a result, not a failure, and is worth stating plainly.
6. End with a single line naming the portfolios covered and the period.

Keep the whole digest under roughly 200 words per portfolio. Report only what the tools returned: no speculation about why the model changed, and no suggestion about what the user should do.

{_DELAYED_BOOK}

{_BOUNDARY}

End with the disclaimer."""

    @server.prompt(
        name="drift_check",
        title="How far my account has drifted",
        description=(
            "Compares your real holdings against a model portfolio and reports how far they "
            "have drifted. Reports only - it proposes no trades and places none."
        ),
    )
    def drift_check(portfolio: PortfolioCode = "") -> str:
        return f"""You are reporting how far the user's own holdings have drifted from a Financial Portfolios AI model portfolio.

{DISCLAIMER_TEXT}

{_code_or_subscribed(portfolio)}

This is a report, not a trade plan. It is safe to run on a schedule, so do not ask the user questions and do not propose, prepare or place any order. If they want to act on it, that is a separate, explicit request.

1. Read the user's current positions from a brokerage, custodian or portfolio-tracking connector if one is available. Never ask for brokerage credentials or account numbers. If no such connector is there, say the check needs one and stop - do not ask the user to type their holdings into a scheduled run.
2. Confirm the target has `access: "subscribed"` via `list_portfolios`. Alignment needs a subscription; if it is not subscribed, say so and stop.
3. Call `rebalance_portfolio` with the target and those holdings.
4. Report, in under 200 words:
   - A one-line answer: roughly how far the account is from the model, and whether that has moved much.
   - The largest gaps, by ticker: held weight versus target weight, in percentage points.
   - Anything held that the model does not hold, and anything in the model not held at all.
   - Any ticker that could not be matched between the broker and the model - say it was skipped rather than guessing a substitute.
5. If the account already matches closely, say exactly that in one sentence. Being aligned is a result worth reporting.

Do not translate the gaps into share quantities, order tickets or a suggestion to trade, and do not tell the user whether to act. Drift is arithmetic against a published model, not advice, and no suitability assessment has been performed.

{_BOUNDARY}

End with the disclaimer."""

    server.completion()(complete_portfolio_code)
