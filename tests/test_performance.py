"""Performance tools: published figures relayed, with their disclosure guaranteed."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from financial_portfolios_ai.exceptions import AuthenticationError, NotFoundError
from financial_portfolios_ai.models import PortfolioMetrics, PortfolioPerformance

from financial_portfolios_ai_mcp.disclosure import DISCLAIMER
from financial_portfolios_ai_mcp.performance import _require_disclosure
from financial_portfolios_ai_mcp.server import mcp_server

# The portal's own wording, which this server relays and never composes.
PORTAL_DISCLOSURE = (
    "Past performance is not indicative of future results. All performance figures shown are "
    "hypothetical and simulated..."
)


def _text(result) -> str:
    if hasattr(result, "content") and result.content:
        return result.content[0].text
    return str(result)


async def _call(tool: str, method: str, value) -> dict:
    client = AsyncMock()
    if isinstance(value, Exception):
        getattr(client, method).side_effect = value
    else:
        getattr(client, method).return_value = value
    client.__aenter__.return_value = client
    with patch("financial_portfolios_ai_mcp.performance.get_async_client", return_value=client):
        return json.loads(_text(await mcp_server.call_tool(tool, {"portfolio_code": "AQA_BALANCED"})))


# --------------------------------------------------------------------------- #
# The disclosure is a guarantee, not an intention
# --------------------------------------------------------------------------- #
def test_figures_without_their_disclosure_are_withheld():
    """The portal attaches one to every performance response.

    If a deployment ever stops, the honest failure is to say the figures are unavailable.
    Publishing them bare is how an unlabelled hypothetical return reaches a customer, and
    composing replacement wording here would be worse - it would not be the publisher's.
    """
    result = _require_disclosure({"available": True, "stats": {"portfolio": {"total_return": 0.2}}}, "t")
    assert result["error"] == "Performance disclosure missing"
    assert "withheld" in result["message"]
    assert "total_return" not in json.dumps(result), "the figures must not survive the refusal"


def test_an_unavailable_payload_needs_no_disclosure():
    """While price history backfills the portal answers available: false with a reason.

    There is nothing to disclose, and refusing that would turn a readable answer into an error.
    """
    payload = {"available": False, "reason": "no_benchmark_prices"}
    assert _require_disclosure(payload, "t") == payload


def test_a_disclosed_payload_passes_through_untouched():
    payload = {"available": True, "disclaimer": PORTAL_DISCLOSURE, "stats": {}}
    assert _require_disclosure(payload, "t") is payload


# --------------------------------------------------------------------------- #
# Relaying
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_performance_relays_the_portals_figures_and_its_disclosure():
    response = PortfolioPerformance(
        portfolio_code="AQA_BALANCED",
        available=True,
        access="subscribed",
        delayed=False,
        benchmark="SPY",
        series=[{"date": "2026-01-02", "portfolio": 100.0, "benchmark": 100.0}],
        stats={"trading_days": 250, "portfolio": {"total_return": 0.18, "sharpe": 1.1}},
        disclaimer=PORTAL_DISCLOSURE,
    )
    data = await _call("get_portfolio_performance", "get_portfolio_performance", response)

    assert data["available"] is True
    assert data["stats"]["portfolio"]["total_return"] == 0.18
    assert data["access"] == "subscribed" and data["delayed"] is False
    # Verbatim: the portal's field, not the ADR-0161 constant, and not reworded here.
    assert data["disclaimer"] == PORTAL_DISCLOSURE
    assert data["disclaimer"] != DISCLAIMER
    assert "unaltered" in data["note"], "the model is told what to do with it"


@pytest.mark.asyncio
async def test_metrics_relays_best_and_worst_performers():
    response = PortfolioMetrics(
        portfolio_code="AQA_BALANCED",
        available=True,
        access="public_delayed",
        delayed=True,
        lag_days=45,
        best_performers=[{"ticker": "NVDA", "name": "NVIDIA Corporation", "return_pct": 41.2}],
        worst_performers=[{"ticker": "CFG", "name": "Citizens Financial Group, Inc.", "return_pct": -8.4}],
        most_held=[{"ticker": "APH", "name": "Amphenol Corporation", "appearances": 6, "avg_weight": 0.0223}],
        win_rate=0.61,
        disclaimer=PORTAL_DISCLOSURE,
    )
    data = await _call("get_portfolio_metrics", "get_portfolio_metrics", response)

    assert data["best_performers"][0]["ticker"] == "NVDA"
    assert data["worst_performers"][0]["return_pct"] == -8.4
    # The company name is here and nowhere else in this connector - it is what makes a
    # cross-connector lookup reliable, since positions carry only a ticker.
    assert data["most_held"][0]["name"] == "Amphenol Corporation"
    assert data["delayed"] is True and data["lag_days"] == 45
    assert data["disclaimer"] == PORTAL_DISCLOSURE


@pytest.mark.asyncio
async def test_backfilling_is_reported_rather_than_failing():
    """A product with no book yet answers available: false - not an error, and not zeros."""
    response = PortfolioMetrics(portfolio_code="AQA_QUALITY", available=False, reason="no_snapshots")
    data = await _call("get_portfolio_metrics", "get_portfolio_metrics", response)
    assert data["available"] is False and data["reason"] == "no_snapshots"
    assert "error" not in data


# --------------------------------------------------------------------------- #
# Tool surface and errors
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_both_tools_are_read_only_and_titled():
    tools = {t.name: t for t in await mcp_server.list_tools()}
    for name in ("get_portfolio_performance", "get_portfolio_metrics"):
        assert tools[name].title
        assert tools[name].annotations.read_only_hint is True
        assert "hypothetical" in tools[name].description.lower()


@pytest.mark.asyncio
async def test_the_derived_tool_kept_a_name_that_is_not_performance():
    """`get_portfolio_metrics` now means what the portal's /metrics route means.

    The weight-derived tool was renamed to `get_portfolio_concentration` so a model cannot
    read concentration figures as returns.
    """
    names = {t.name for t in await mcp_server.list_tools()}
    assert "get_portfolio_concentration" in names


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool", "method", "error", "label"),
    [
        ("get_portfolio_performance", "get_portfolio_performance",
         NotFoundError("no such portfolio"), "Portfolio Not Found"),
        ("get_portfolio_metrics", "get_portfolio_metrics",
         AuthenticationError("session expired"), "Authentication or subscription required"),
    ],
)
async def test_portal_errors_keep_the_servers_error_vocabulary(tool, method, error, label):
    data = await _call(tool, method, error)
    assert data["error"] == label
    assert data["disclaimer"] == DISCLAIMER, "an error carries the standing notice, not a performance one"
