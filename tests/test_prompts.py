"""Prompt catalogue: what clients render, and what each prompt tells the model."""

from unittest.mock import AsyncMock, patch

import pytest
from financial_portfolios_ai.models import PortfolioListResponse, PortfolioSummary
from mcp.types import CompletionArgument, PromptReference, ResourceTemplateReference

from financial_portfolios_ai_mcp.config import get_settings
from financial_portfolios_ai_mcp.disclosure import DISCLAIMER
from financial_portfolios_ai_mcp.prompts import complete_portfolio_code
from financial_portfolios_ai_mcp.server import mcp_server

EXPECTED_PROMPTS = {
    "my_portfolios",
    "access_help",
    "portfolio_review",
    "portfolio_changes",
    "compare_portfolios",
    "find_holding",
    "rebalance_advisor",
    "market_research_digest",
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
    assert "Portfolio: 'AQA_DEFENSIVE'. Use this code directly." in text


# --------------------------------------------------------------------------- #
# Prompt-specific behaviour
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_portfolio_changes_passes_the_window_and_flags_delayed_history():
    text = await _render("portfolio_changes", {"days": "90"})
    assert "days=90" in text
    assert "history ends about 45 days ago" in text


@pytest.mark.asyncio
@pytest.mark.parametrize("days", ["0", "366", "soon"])
async def test_portfolio_changes_rejects_an_invalid_window(days):
    with pytest.raises(ValueError):
        await mcp_server.get_prompt("portfolio_changes", {"days": days})


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
    ask = text.index("Ask for the user's current holdings")
    assert check < ask
    assert "do not collect the user's holdings" in text


@pytest.mark.asyncio
async def test_research_digest_searches_a_topic_when_given():
    assert "search='energy'" in await _render("market_research_digest", {"topic": "energy"})
    assert "search=" not in await _render("market_research_digest", {})


@pytest.mark.asyncio
async def test_access_help_points_at_this_deployments_pricing_and_not_token_info():
    text = await _render("access_help")
    assert f"{get_settings().portal_base_url.rstrip('/')}/#pricing" in text
    assert "Do not call `get_token_info`" in text
    assert "Do not quote prices" in text


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
    assert result.values[0] == "AQA_DEFENSIVE"
    assert set(result.values) == {"AQA_DEFENSIVE", "AQA_BALANCED", "AQA_AGGRESSIVE"}


@pytest.mark.asyncio
async def test_completion_filters_by_what_was_typed_case_insensitively():
    ref = PromptReference(type="ref/prompt", name="portfolio_changes")
    with patch("financial_portfolios_ai_mcp.prompts.get_async_client", return_value=_client_returning(_catalog())):
        result = await complete_portfolio_code(ref, CompletionArgument(name="portfolio", value="aqa_ag"), None)
    assert result.values == ["AQA_AGGRESSIVE"]


@pytest.mark.asyncio
async def test_completion_ignores_other_arguments_and_resource_templates():
    prompt_ref = PromptReference(type="ref/prompt", name="find_holding")
    assert await complete_portfolio_code(prompt_ref, CompletionArgument(name="ticker", value="N"), None) is None

    template_ref = ResourceTemplateReference(type="ref/resource", uri="portfolios://{portfolio_code}/allocation")
    assert await complete_portfolio_code(template_ref, CompletionArgument(name="portfolio_code", value=""), None) is None


@pytest.mark.asyncio
async def test_completion_failure_returns_no_suggestions_instead_of_an_error():
    """Autocomplete is a typing aid; a portal outage must not break the dialog."""
    ref = PromptReference(type="ref/prompt", name="portfolio_review")
    failing = _client_returning(error=RuntimeError("portal unreachable"))
    with patch("financial_portfolios_ai_mcp.prompts.get_async_client", return_value=failing):
        result = await complete_portfolio_code(ref, CompletionArgument(name="portfolio", value=""), None)
    assert result.values == []


@pytest.mark.asyncio
async def test_report_never_fabricates_performance():
    """No price or return data exists behind this connector; a report must not invent any."""
    text = await _render("portfolio_report", {"portfolio": "AQA_DEFENSIVE", "days": "30"})
    assert "days=30" in text
    assert "do not compute, estimate or chart returns, performance" in text
    assert "not from other sources" in text


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

    assert first.values[0] == "AQA_DEFENSIVE"
    assert second.values == ["AQA_DEFENSIVE, AQA_BALANCED"]
    # Already-chosen codes are not offered again.
    assert rest.values == ["AQA_DEFENSIVE, AQA_BALANCED", "AQA_DEFENSIVE, AQA_AGGRESSIVE"]
