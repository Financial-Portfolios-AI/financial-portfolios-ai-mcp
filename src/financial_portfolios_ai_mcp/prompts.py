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

from typing import Annotated, Any

from mcp.types import Completion, CompletionArgument, PromptReference
from pydantic import Field

from financial_portfolios_ai_mcp.auth import get_async_client
from financial_portfolios_ai_mcp.config import get_settings
from financial_portfolios_ai_mcp.disclosure import DISCLAIMER_TEXT

# Arguments whose values are portfolio codes, for live autocompletion.
# Input names double as the labels Claude shows ("portfolio" -> "Portfolio"): the SDK does
# not pass an argument title through, so a readable name is the only way to get a readable label.
SINGLE_PORTFOLIO_ARGUMENTS = frozenset({"portfolio"})
MULTI_PORTFOLIO_ARGUMENTS = frozenset({"portfolios"})

PortfolioCode = Annotated[
    str,
    Field(
        description=(
            "Model portfolio code, e.g. AQA_DEFENSIVE, AQA_BALANCED or AQA_AGGRESSIVE. "
            "Leave blank to use the portfolios you subscribe to."
        )
    ),
]

# Shared instructions. Kept as constants so every prompt handles the delayed book and
# the advice boundary identically.
_RESOLVE_PORTFOLIOS = """\
Call `list_portfolios` first. Use the entries marked `access: "subscribed"` - those are
the user's own portfolios. If none are subscribed, say so plainly, then continue with
the public delayed book of every listed portfolio so the user still gets an answer."""

_DELAYED_BOOK = """\
Access levels: a `subscribed` portfolio returns the latest book. Anything else returns
the public book delayed by about 45 days, with expected return, expected volatility,
equity exposure, cash allocation and effective N set to null. Whenever a response has
`delayed: true`, state its `as_of` date and say the holdings are delayed - never present
a delayed book as the current allocation, and never fill in the null metrics."""

_BOUNDARY = """\
Stay informational. Describe what the model portfolios contain and how they differ; do
not recommend buying, selling or holding any security, and do not tell the user which
portfolio suits them - no suitability assessment has been performed. If asked, say so
and point them to a licensed adviser."""


def _code_or_subscribed(portfolio: str) -> str:
    code = (portfolio or "").strip()
    if code:
        return f"Portfolio: '{code}'. Use this code directly."
    return _RESOLVE_PORTFOLIOS



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
    if not isinstance(ref, PromptReference):
        return None
    name = argument.name
    if name not in SINGLE_PORTFOLIO_ARGUMENTS and name not in MULTI_PORTFOLIO_ARGUMENTS:
        return None

    value = argument.value or ""
    if name in MULTI_PORTFOLIO_ARGUMENTS:
        *chosen, fragment = value.split(",")
        chosen = [c.strip() for c in chosen if c.strip()]
    else:
        chosen, fragment = [], value
    typed = fragment.strip().upper()

    try:
        async with get_async_client() as client:
            result = await client.list_portfolios()
    except Exception:  # noqa: BLE001 - completion is best-effort by design
        return Completion(values=[], total=0, has_more=False)

    taken = {c.upper() for c in chosen}
    ranked = sorted(result.portfolios, key=lambda p: p.access != "subscribed")
    codes = [p.code for p in ranked if p.code.upper().startswith(typed) and p.code.upper() not in taken]
    prefix = ", ".join(chosen)
    values = [f"{prefix}, {code}" if prefix else code for code in codes]
    return Completion(values=values[:100], total=len(values), has_more=len(values) > 100)

def register_prompts(server: Any) -> None:
    """Register MCP prompt templates and argument completion with the server."""

    # ------------------------------------------------------------------ #
    # Orientation
    # ------------------------------------------------------------------ #
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
4. If the user subscribes to nothing, say so, give the table of all portfolios, and mention that live holdings require a subscription.

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

1. Call `list_portfolios` and group the portfolios by `access`.
2. Explain, in plain language and with the user's actual portfolio names:
   - Subscribed portfolios show the latest holdings, including expected return and risk metrics.
   - Other portfolios show the public book, with holdings delayed by about 45 days and without those premium metrics.
   - Model alignment calculations (`rebalance_portfolio`) are available only for subscribed portfolios.
3. If the user is not subscribed to a portfolio they asked about, tell them live holdings for it come with a subscription, available from the Pricing section of the portal at {portal}/#pricing. Do not quote prices; you do not have them.
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
3. Summarise the sector breakdown by total weight.
4. Describe concentration: the combined weight of the top five and top ten holdings, and effective N when present.
5. Report equity exposure against cash allocation when present.
6. Offer to show what changed recently (the `portfolio_changes` analysis) rather than fetching history unprompted.

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
        days: Annotated[
            int,
            Field(description="How many days back to look, from 1 to 365. Defaults to 30.", ge=1, le=365),
        ] = 30,
    ) -> str:
        return f"""You are an educational assistant for Financial Portfolios AI, explaining how a model portfolio has changed.

{DISCLAIMER_TEXT}

{_code_or_subscribed(portfolio)}

For each portfolio:
1. Call `get_portfolio_history` with days={days}.
2. Compare the earliest and latest snapshot in the window and report:
   - Positions added (ticker, sector, new weight).
   - Positions removed (ticker, sector, previous weight).
   - The largest weight increases and decreases among positions held throughout - show old weight, new weight, and the change in percentage points.
   - Any net shift in sector weights.
3. If there are several snapshots, give a one-line timeline of when the notable changes happened.
4. If the window holds fewer than two snapshots, say there is nothing to compare, and suggest a longer period.

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
                    "Comma-separated portfolio codes to compare, e.g. AQA_DEFENSIVE, AQA_BALANCED. "
                    "Leave blank to compare every portfolio."
                )
            ),
        ] = "",
    ) -> str:
        codes = [c.strip() for c in (portfolios or "").split(",") if c.strip()]
        which = (
            "Compare these portfolios: " + ", ".join(f"'{c}'" for c in codes) + "."
            if codes
            else "Call `list_portfolios` and compare every portfolio it returns."
        )
        return f"""You are an educational assistant for Financial Portfolios AI, comparing model portfolios.

{DISCLAIMER_TEXT}

{which}

1. Call `get_portfolio_allocation` for each portfolio.
2. Build one comparison table with a column per portfolio: risk level, theme, number of positions, top-five combined weight, largest sector, and equity exposure / cash when present.
3. Show the sector mix side by side, as weights per sector.
4. Report overlap: tickers held by more than one portfolio, with each portfolio's weight.
5. Summarise the main differences in two or three neutral sentences.

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

1. Call `list_portfolios`, then `get_portfolio_allocation` for every portfolio.
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
        days: Annotated[
            int,
            Field(description="Days of history to show changes for, from 1 to 365. Defaults to 90.", ge=1, le=365),
        ] = 90,
    ) -> str:
        return f"""You are building an interactive, educational report on a Financial Portfolios AI model portfolio.

{DISCLAIMER_TEXT}

{_code_or_subscribed(portfolio)}

Gather the data first:
1. Call `get_portfolio_allocation` for the portfolio.
2. Call `get_portfolio_history` with days={days}.

Then build the report as a single self-contained interactive page (an artifact where the client supports one), with these sections:
- Header: portfolio name and code, the book's `as_of` date, and - if `delayed` is true - a prominent "Holdings delayed ~45 days" badge.
- Key figures: number of positions, top-five and top-ten combined weight, and effective N, equity exposure and cash allocation when present. Omit a figure that is null rather than showing zero.
- Holdings: a sortable, filterable table of ticker, sector and weight, plus expected return and expected volatility when present.
- Sector mix: a chart of total weight per sector.
- Concentration: a chart of cumulative weight by holding rank.
- Changes over the period: positions added and removed, and the largest weight shifts between the first and last snapshot. Skip this section if there are fewer than two snapshots, and say why.
- Footer: the full disclaimer text above, verbatim, visible on the page itself - the report may be shared without this conversation.

Use only numbers returned by the tools. This connector provides no prices, returns or performance data, so do not compute, estimate or chart returns, performance, gains, drawdowns or benchmark comparisons - not even approximately, and not from other sources. If the user asks for performance, say it is not available through this connector.

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
2. Ask for the user's current holdings: ticker, share quantity, and cash, or a CSV file. Limits: 200 rows, 512 KB.
3. If they need the format, call `get_rebalance_template` and show it.
4. Call `rebalance_portfolio` with the target code and their holdings.
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
3. Summarise the key quantitative insights, regime shifts, macro context and factor trends, citing each article by title and date.
4. If a search returns nothing, say so and offer the latest research instead.

Do not pad with market commentary that isn't in the articles.

{_BOUNDARY}

End with educational takeaways and the disclaimer."""

    server.completion()(complete_portfolio_code)
