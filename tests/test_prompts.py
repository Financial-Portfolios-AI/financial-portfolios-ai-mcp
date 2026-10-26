"""Prompt catalogue: what clients render, and what each prompt tells the model."""

from unittest.mock import AsyncMock, patch

import pytest
from financial_portfolios_ai.models import (
    PortfolioListResponse,
    PortfolioSnapshot,
    PortfolioSummary,
    Position,
)
from mcp.types import CompletionArgument, PromptReference, ResourceTemplateReference

from financial_portfolios_ai_mcp.config import get_settings
from financial_portfolios_ai_mcp.disclosure import DISCLAIMER
from financial_portfolios_ai_mcp.prompts import complete_portfolio_code
from financial_portfolios_ai_mcp.server import mcp_server

EXPECTED_PROMPTS = {
    "start_here",
    "my_portfolios",
    "access_help",
    "portfolio_review",
    "portfolio_changes",
    "compare_portfolios",
    "find_holding",
    "rebalance_advisor",
    "market_research_digest",
    "portfolio_performance",
    "most_held_stocks",
    "portfolio_digest",
    "drift_check",
    "portfolio_report",
}

# Minimal valid arguments for rendering every prompt.
RENDER_ARGS = {name: {} for name in EXPECTED_PROMPTS} | {"find_holding": {"ticker": "nvda"}}


async def _render(name: str, args: dict | None = None) -> str:
    result = await mcp_server.get_prompt(name, args if args is not None else RENDER_ARGS[name])
    return result.messages[0].content.text


# --------------------------------------------------------------------------- #
# What the client's prompt dialog shows
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_catalogue_is_complete():
    names = {p.name for p in await mcp_server.list_prompts()}
    assert names == EXPECTED_PROMPTS


@pytest.mark.asyncio
async def test_every_prompt_has_a_title_and_every_argument_has_help_text():
    """Without these Claude shows raw names and a bare, unexplained input box."""
    for prompt in await mcp_server.list_prompts():
        assert prompt.title, f"{prompt.name} has no title"
        assert prompt.description, f"{prompt.name} has no description"
        for arg in prompt.arguments or []:
            assert arg.description, f"{prompt.name}.{arg.name} has no description"


@pytest.mark.asyncio
async def test_only_the_ticker_is_required():
    """Portfolio codes are optional (blank means 'my portfolios'); a lookup needs a ticker."""
    required = {
        (p.name, a.name)
        for p in await mcp_server.list_prompts()
        for a in (p.arguments or [])
        if a.required
    }
    assert required == {("find_holding", "ticker")}


# --------------------------------------------------------------------------- #
# Guardrails every prompt must carry
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
@pytest.mark.parametrize("name", sorted(EXPECTED_PROMPTS))
async def test_every_prompt_carries_the_disclosure_and_advice_boundary(name):
    text = await _render(name)
    assert DISCLAIMER in text
    assert "do\nnot recommend" in text or "do not recommend" in text
    assert "no suitability assessment" in text.lower()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name",
    ["my_portfolios", "portfolio_review", "portfolio_changes", "compare_portfolios", "find_holding", "portfolio_report"],
)
async def test_holdings_prompts_explain_the_delayed_book(name):
    """A delayed book must never be presented as the current allocation."""
    text = await _render(name)
    assert "`delayed: true`" in text
    assert "`as_of`" in text


# --------------------------------------------------------------------------- #
# Blank portfolio code resolves the user's own portfolios
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["portfolio_review", "portfolio_changes", "rebalance_advisor", "portfolio_report"])
async def test_blank_code_uses_subscribed_portfolios_not_a_fixed_default(name):
    text = await _render(name, {})
    assert "`list_portfolios`" in text
    assert 'access: "subscribed"' in text
    # The old default silently reviewed Aggressive regardless of the subscription.
    assert "AQA_AGGRESSIVE'" not in text


@pytest.mark.asyncio
async def test_explicit_code_is_used_directly():
    text = await _render("portfolio_review", {"portfolio": "AQA_DEFENSIVE"})
    assert "Portfolio: 'AQA_DEFENSIVE'" in text and "Use this code directly" in text


@pytest.mark.asyncio
@pytest.mark.parametrize("typed", ["Defensive", "defensive", " Defensive "])
async def test_a_product_name_resolves_to_its_code(typed):
    """Users pick "Defensive" from the drop-down, not AQA_DEFENSIVE."""
    text = await _render("portfolio_review", {"portfolio": typed})
    assert "Portfolio: 'AQA_DEFENSIVE'" in text
    assert "product_name" in text  # fallback when a name does not map


# --------------------------------------------------------------------------- #
# Prompt-specific behaviour
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_portfolio_changes_passes_the_window_and_flags_delayed_history():
    text = await _render("portfolio_changes", {"days": "90"})
    assert "days=90" in text
    assert "history ends about 45 days ago" in text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "days,expected", [("", 30), ("soon", 30), ("0", 1), ("366", 365), (" 90 ", 90)]
)
async def test_portfolio_changes_tolerates_blank_and_clamps_the_window(days, expected):
    """Clients send an untouched optional field as "" - that used to fail the whole prompt."""
    text = await _render("portfolio_changes", {"days": days})
    assert f"days={expected}" in text


@pytest.mark.asyncio
@pytest.mark.parametrize("name,default", [("portfolio_report", 90), ("portfolio_digest", 7)])
async def test_blank_days_renders_with_the_default(name, default):
    """2026-10-25 prod: "Error rendering prompt portfolio_report" from days=""."""
    args = {"days": ""} if name == "portfolio_digest" else {"portfolio": "", "days": ""}
    text = await _render(name, args)
    assert f"days={default}" in text or f"{default} days" in text


@pytest.mark.asyncio
async def test_compare_portfolios_parses_the_code_list():
    text = await _render("compare_portfolios", {"portfolios": " AQA_DEFENSIVE, AQA_BALANCED ,"})
    assert "Compare these portfolios: 'AQA_DEFENSIVE', 'AQA_BALANCED'." in text
    assert "not a like-for-like comparison" in text

    everything = await _render("compare_portfolios", {})
    assert "compare every portfolio it returns" in everything


@pytest.mark.asyncio
async def test_find_holding_normalises_the_ticker_and_requires_it():
    text = await _render("find_holding", {"ticker": "  nvda "})
    assert "'NVDA'" in text
    with pytest.raises(ValueError):
        await mcp_server.get_prompt("find_holding", {})


@pytest.mark.asyncio
async def test_rebalance_checks_entitlement_before_collecting_holdings():
    """A non-subscriber must not be asked to hand over holdings that will be refused."""
    text = await _render("rebalance_advisor", {"portfolio": "AQA_BALANCED"})
    check = text.index("Confirm access before asking for any holdings")
    collect = text.index("Use the holdings the user has given in the conversation")
    assert check < collect
    assert "do not collect the user's holdings" in text


@pytest.mark.asyncio
async def test_rebalance_uses_holdings_the_user_provides_and_names_no_other_connector():
    """OpenAI review (2026-10-25) flags text that steers the model to another plugin or connector;
    holdings come from the user, and asking for credentials is never acceptable."""
    text = await _render("rebalance_advisor")
    assert "holdings the user has given in the conversation" in text
    assert "connector is available" not in text and "portfolio-tracking connector" not in text
    assert "Never ask anyone for brokerage credentials" in text
    # The Studio shows what arrived so the user can correct it before anything is calculated.
    assert "open_rebalance_studio" in text
    assert "editable table" in text
    # And a client that cannot render it still has a path.
    assert "cannot render the panel" in text


@pytest.mark.asyncio
async def test_performance_prompt_carries_the_disclosure_rule():
    text = await _render("portfolio_performance", {"portfolio": "AQA_BALANCED"})
    assert "hypothetical and simulated" in text
    assert "in full and unaltered" in text
    # `available: false` is an answer, not an error, and must not be reported as zero.
    assert "available" in text and "reason" in text


@pytest.mark.asyncio
async def test_digest_is_written_to_run_unattended():
    """It is the body of a scheduled task, so it must not ask questions or stall.

    A quiet period is a result worth stating, not a failure to report.
    """
    text = await _render("portfolio_digest", {"days": "7"})
    assert "days=7" in text
    assert "Do not ask the user questions" in text
    assert "A quiet period is a result" in text
    assert "get_portfolio_changes" in text


@pytest.mark.asyncio
async def test_start_here_offers_every_journey_and_keeps_schedules_read_only():
    text = await _render("start_here")
    for tool in ("open_access_centre", "open_portfolio_explorer", "get_portfolio_performance",
                 "open_breadth_board", "open_rebalance_studio"):
        assert tool in text
    assert "never prepare or place orders" in text
    # No journey depends on, or names, another connector (OpenAI review, 2026-10-25).
    assert "connector" not in text.split("Journey")[1].split("Keep me posted")[0]


@pytest.mark.asyncio
async def test_drift_check_reports_without_proposing_trades():
    """It is schedulable, so it must not drift into preparing orders unattended.

    Turning gaps into share quantities is the step that needs a person looking at it, and a
    scheduled run has nobody looking.
    """
    text = await _render("drift_check", {"portfolio": "AQA_BALANCED"})
    assert "do not propose, prepare or place any order" in text
    assert "Do not translate the gaps into share quantities" in text
    assert "do not ask for them in a scheduled run" in text
    assert "portfolio-tracking connector" not in text
    # An aligned account is a result, not an empty report.
    assert "Being aligned is a result worth reporting" in text


@pytest.mark.asyncio
async def test_breadth_prompt_refuses_to_read_breadth_as_conviction():
    text = await _render("most_held_stocks")
    assert "open_breadth_board" in text
    assert "Breadth is not conviction" in text
    # A partial read must not be presented as the whole picture.
    assert "unavailable" in text


@pytest.mark.asyncio
async def test_research_digest_searches_a_topic_when_given():
    assert "search='energy'" in await _render("market_research_digest", {"topic": "energy"})
    assert "search=" not in await _render("market_research_digest", {})


@pytest.mark.asyncio
async def test_access_help_points_at_this_deployments_pricing_and_not_token_info():
    text = await _render("access_help")
    assert f"{get_settings().portal_base_url.rstrip('/')}/#pricing" in text
    assert "Do not call `get_token_info`" in text
    assert "Do not quote share prices" in text


# --------------------------------------------------------------------------- #
# Autocomplete for portfolio codes
# --------------------------------------------------------------------------- #
def _catalog():
    return PortfolioListResponse(
        total=3,
        portfolios=[
            PortfolioSummary(code="AQA_BALANCED", access="public_delayed", delayed=True),
            PortfolioSummary(code="AQA_DEFENSIVE", access="subscribed", delayed=False),
            PortfolioSummary(code="AQA_AGGRESSIVE", access="public_delayed", delayed=True),
        ],
    )


def _client_returning(catalog=None, error=None):
    client = AsyncMock()
    if error:
        client.list_portfolios.side_effect = error
    else:
        client.list_portfolios.return_value = catalog
    client.__aenter__.return_value = client
    return client


@pytest.mark.asyncio
async def test_completion_suggests_live_codes_subscribed_first():
    ref = PromptReference(type="ref/prompt", name="portfolio_review")
    with patch("financial_portfolios_ai_mcp.prompts.get_async_client", return_value=_client_returning(_catalog())):
        result = await complete_portfolio_code(ref, CompletionArgument(name="portfolio", value=""), None)
    assert result.values[0] == "Defensive"
    assert set(result.values) == {"Defensive", "Balanced", "Aggressive"}


@pytest.mark.asyncio
async def test_completion_filters_by_what_was_typed_case_insensitively():
    ref = PromptReference(type="ref/prompt", name="portfolio_changes")
    with patch("financial_portfolios_ai_mcp.prompts.get_async_client", return_value=_client_returning(_catalog())):
        by_code = await complete_portfolio_code(ref, CompletionArgument(name="portfolio", value="aqa_ag"), None)
        by_name = await complete_portfolio_code(ref, CompletionArgument(name="portfolio", value="aggr"), None)
        mid_word = await complete_portfolio_code(ref, CompletionArgument(name="portfolio", value="fens"), None)
    assert by_code.values == ["Aggressive"]
    assert by_name.values == ["Aggressive"]
    assert mid_word.values == ["Defensive"]


def _client_with_books(books, failures=()):
    """A client whose allocations differ per portfolio, so ticker completion has to read each."""
    client = AsyncMock()
    client.list_portfolios.return_value = _catalog()

    async def get_portfolio(portfolio_code):
        if portfolio_code in failures:
            raise RuntimeError(f"{portfolio_code} unavailable")
        return PortfolioSnapshot(
            portfolio_code=portfolio_code, date="2026-09-10T00:00:00",
            total_positions=len(books.get(portfolio_code, [])),
            positions=[Position(ticker=t, weight=0.5, sector=None) for t in books.get(portfolio_code, [])],
        )

    client.get_portfolio.side_effect = get_portfolio
    client.__aenter__.return_value = client
    return client


BOOKS = {"AQA_DEFENSIVE": ["MSFT", "NVDA"], "AQA_BALANCED": ["NVDA", "KO"], "AQA_AGGRESSIVE": ["AMD"]}


@pytest.mark.asyncio
async def test_ticker_completion_suggests_only_tickers_actually_held():
    """`find_holding` had no autocomplete, so a user typed a ticker from memory.

    A ticker held in no book returns an empty search, so the useful suggestions are the
    union of what the portfolios hold - de-duplicated, since a name can be in several.
    """
    ref = PromptReference(type="ref/prompt", name="find_holding")
    with patch("financial_portfolios_ai_mcp.prompts.get_async_client", return_value=_client_with_books(BOOKS)):
        result = await complete_portfolio_code(ref, CompletionArgument(name="ticker", value=""), None)
    assert result.values == ["AMD", "KO", "MSFT", "NVDA"], "sorted and de-duplicated"


@pytest.mark.asyncio
async def test_ticker_completion_filters_by_what_was_typed():
    ref = PromptReference(type="ref/prompt", name="find_holding")
    with patch("financial_portfolios_ai_mcp.prompts.get_async_client", return_value=_client_with_books(BOOKS)):
        result = await complete_portfolio_code(ref, CompletionArgument(name="ticker", value="n"), None)
    assert result.values == ["NVDA"], "case-insensitive prefix match"


@pytest.mark.asyncio
async def test_ticker_completion_survives_one_unreadable_portfolio():
    """Completion is a typing aid: one failed read must not empty the whole list."""
    client = _client_with_books(BOOKS, failures=("AQA_BALANCED",))
    ref = PromptReference(type="ref/prompt", name="find_holding")
    with patch("financial_portfolios_ai_mcp.prompts.get_async_client", return_value=client):
        result = await complete_portfolio_code(ref, CompletionArgument(name="ticker", value=""), None)
    assert result.values == ["AMD", "MSFT", "NVDA"], "KO is lost with its book, the rest survive"


@pytest.mark.asyncio
async def test_completion_answers_the_resource_template_too():
    """`portfolios://{portfolio_code}/allocation` could not be completed at all before.

    Only PromptReference was answered, so a host offering a resource picker left the user
    typing a code from memory.
    """
    template_ref = ResourceTemplateReference(type="ref/resource", uri="portfolios://{portfolio_code}/allocation")
    with patch("financial_portfolios_ai_mcp.prompts.get_async_client", return_value=_client_returning(_catalog())):
        result = await complete_portfolio_code(template_ref, CompletionArgument(name="portfolio_code", value=""), None)
    assert result.values[0] == "AQA_DEFENSIVE", "subscribed first, as for a prompt argument"
    assert set(result.values) == {"AQA_DEFENSIVE", "AQA_BALANCED", "AQA_AGGRESSIVE"}


@pytest.mark.asyncio
async def test_completion_ignores_arguments_it_knows_nothing_about():
    prompt_ref = PromptReference(type="ref/prompt", name="portfolio_changes")
    assert await complete_portfolio_code(prompt_ref, CompletionArgument(name="horizon", value="3"), None) is None

    template_ref = ResourceTemplateReference(type="ref/resource", uri="research://posts/latest")
    assert await complete_portfolio_code(template_ref, CompletionArgument(name="slug", value="a"), None) is None


@pytest.mark.asyncio
async def test_completion_failure_returns_no_suggestions_instead_of_an_error():
    """Autocomplete is a typing aid; a portal outage must not break the dialog."""
    ref = PromptReference(type="ref/prompt", name="portfolio_review")
    failing = _client_returning(error=RuntimeError("portal unreachable"))
    with patch("financial_portfolios_ai_mcp.prompts.get_async_client", return_value=failing):
        result = await complete_portfolio_code(ref, CompletionArgument(name="portfolio", value=""), None)
    assert result.values == []


@pytest.mark.asyncio
async def test_report_carries_the_disclosure_and_computes_no_performance_of_its_own():
    """A report may now include published performance - with its disclosure attached.

    The figures come from the portal, labelled hypothetical. What the report must never do
    is derive its own from prices found elsewhere: that figure is nobody's published number
    and would disagree with the website.
    """
    text = await _render("portfolio_report", {"portfolio": "AQA_DEFENSIVE", "days": "30"})
    assert "days=30" in text
    assert "hypothetical and simulated" in text
    assert "in full and unaltered" in text
    assert "Never compute, estimate or chart a return" in text
    assert "from prices obtained" in text and "elsewhere" in text


@pytest.mark.asyncio
async def test_report_embeds_the_disclosure_on_the_page_itself():
    """A shared report travels without the conversation, so the page must carry the notice."""
    text = await _render("portfolio_report")
    assert "visible on the page itself" in text
    assert "Holdings delayed ~45 days" in text


@pytest.mark.asyncio
async def test_connector_manifest_lists_exactly_the_served_prompts():
    """claude_connector.json is regenerated from the server; guard against drift."""
    import json
    from pathlib import Path

    manifest = json.loads((Path(__file__).resolve().parent.parent / "claude_connector.json").read_text(encoding="utf-8"))
    listed = {p["name"]: p.get("title") for p in manifest["capabilities"]["prompts"]}
    served = {p.name: p.title for p in await mcp_server.list_prompts()}
    assert listed == served


@pytest.mark.asyncio
async def test_input_names_read_as_labels():
    """Claude shows the capitalised input name, so names must read as labels."""
    names = {a.name for p in await mcp_server.list_prompts() for a in (p.arguments or [])}
    assert names == {"portfolio", "portfolios", "days", "ticker", "topic"}
    assert not any("_" in n for n in names)


@pytest.mark.asyncio
async def test_multi_portfolio_completion_extends_the_list_without_repeats():
    """Suggestions are full values: what was entered, plus the code being typed."""
    ref = PromptReference(type="ref/prompt", name="compare_portfolios")
    with patch("financial_portfolios_ai_mcp.prompts.get_async_client", return_value=_client_returning(_catalog())):
        first = await complete_portfolio_code(ref, CompletionArgument(name="portfolios", value=""), None)
        second = await complete_portfolio_code(
            ref, CompletionArgument(name="portfolios", value="AQA_DEFENSIVE, aqa_b"), None
        )
        rest = await complete_portfolio_code(
            ref, CompletionArgument(name="portfolios", value="AQA_DEFENSIVE, "), None
        )

    assert first.values[0] == "Defensive"
    assert second.values == ["AQA_DEFENSIVE, Balanced"]
    # Already-chosen portfolios are not offered again, whether entered as a code or a name.
    assert rest.values == ["AQA_DEFENSIVE, Balanced", "AQA_DEFENSIVE, Aggressive"]


@pytest.mark.asyncio
async def test_days_and_topic_offer_a_drop_down():
    ref = PromptReference(type="ref/prompt", name="portfolio_report")
    days = await complete_portfolio_code(ref, CompletionArgument(name="days", value=""), None)
    assert days.values == ["7", "30", "90", "180", "365"]
    narrowed = await complete_portfolio_code(ref, CompletionArgument(name="days", value="3"), None)
    assert narrowed.values == ["30", "365"]
    topic = await complete_portfolio_code(
        PromptReference(type="ref/prompt", name="market_research_digest"), CompletionArgument(name="topic", value="infl"), None
    )
    assert topic.values == ["Inflation"]


@pytest.mark.asyncio
async def test_compare_portfolios_accepts_names():
    text = await _render("compare_portfolios", {"portfolios": "Defensive, balanced"})
    assert "Compare these portfolios: 'AQA_DEFENSIVE', 'AQA_BALANCED'." in text
