"""Derived-analysis tools: the arithmetic the apps show, reachable as plain tool calls."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from financial_portfolios_ai.exceptions import AuthenticationError, NotFoundError
from financial_portfolios_ai.models import (
    PortfolioHistoryEntry,
    PortfolioHistoryResponse,
    PortfolioSnapshot,
    Position,
)

from financial_portfolios_ai_mcp.server import mcp_server


def _text(result) -> str:
    if hasattr(result, "content") and result.content:
        return result.content[0].text
    return str(result)


def _snapshot(positions, delayed=False):
    return PortfolioSnapshot(
        portfolio_code="AQA_BALANCED", date="2026-09-10T00:00:00", total_positions=len(positions),
        positions=[Position(ticker=t, weight=w, sector=s) for t, w, s in positions],
        access="public_delayed" if delayed else "subscribed", delayed=delayed,
        as_of="2026-09-10", effective_n=None if delayed else 4.0,
    )


def _history(entries, delayed=False):
    return PortfolioHistoryResponse(
        portfolio_code="AQA_BALANCED", days=30, total_snapshots=len(entries),
        access="public_delayed" if delayed else "subscribed", delayed=delayed,
        snapshots=[
            PortfolioHistoryEntry(
                date=date, total_positions=len(positions),
                positions=[Position(ticker=t, weight=w, sector=None) for t, w in positions],
            )
            for date, positions in entries
        ],
    )


async def _call(tool, args, **mocks) -> dict:
    client = AsyncMock()
    for name, value in mocks.items():
        if isinstance(value, Exception):
            getattr(client, name).side_effect = value
        else:
            getattr(client, name).return_value = value
    client.__aenter__.return_value = client
    with patch("financial_portfolios_ai_mcp.analysis.get_async_client", return_value=client):
        return json.loads(_text(await mcp_server.call_tool(tool, args)))


# --------------------------------------------------------------------------- #
# They must be tools, not only prompts
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_the_analyses_are_tools_because_prompts_are_not_a_delivery_surface():
    """ChatGPT's docs never mention prompts/list, and claude.ai's prompt support is disputed.

    A prompt-only analysis is invisible to those users, so each one ships as a tool that
    every host surfaces.
    """
    tools = {t.name: t for t in await mcp_server.list_tools()}
    for name in ("get_portfolio_concentration", "get_portfolio_changes"):
        assert name in tools
        assert tools[name].title
        assert tools[name].annotations.read_only_hint is True


# --------------------------------------------------------------------------- #
# Concentration and sector mix
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_metrics_are_derived_so_they_work_on_the_delayed_book():
    """The portal sends effective_n as null on the public book, where a user has least else.

    Deriving it from the weights is the whole point: a delayed reader gets the same
    concentration picture a subscriber does.
    """
    book = _snapshot([("A", 0.25, "Tech"), ("B", 0.25, "Tech"), ("C", 0.25, "Energy"), ("D", 0.25, "Energy")], delayed=True)
    data = await _call("get_portfolio_concentration", {"portfolio_code": "AQA_BALANCED"}, get_portfolio=book)

    assert data["delayed"] is True
    assert book.effective_n is None, "the portal withheld it"
    assert data["concentration"]["effective_n"] == 4.0, "and we derived it anyway"
    assert data["sectors"]["dominant"]["sector"] in {"Tech", "Energy"}
    assert data["sectors"]["effective_sectors"] == 2.0
    assert "disclaimer" in data


@pytest.mark.asyncio
async def test_metrics_report_the_scale_weights_arrived_on():
    """Sums are published weights, not renormalised, so they match get_portfolio_allocation."""
    data = await _call(
        "get_portfolio_concentration", {"portfolio_code": "AQA_BALANCED"},
        get_portfolio=_snapshot([("A", 0.45, "Tech"), ("B", 0.45, "Energy")]),
    )
    assert data["concentration"]["top_5"] == pytest.approx(0.9)
    assert "same scale as `get_portfolio_allocation`" in data["note"]


# --------------------------------------------------------------------------- #
# Changes - the model's decisions, never returns
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_changes_report_what_the_model_did():
    history = _history([
        ("2026-08-10T00:00:00", [("KEEP", 0.3), ("CUT", 0.4), ("GONE", 0.3)]),
        ("2026-09-10T00:00:00", [("KEEP", 0.3), ("CUT", 0.1), ("NEW", 0.6)]),
    ])
    data = await _call("get_portfolio_changes", {"portfolio_code": "AQA_BALANCED"}, get_portfolio_history=history)

    assert data["comparable"] is True
    assert data["from"] == "2026-08-10" and data["to"] == "2026-09-10"
    assert [row["ticker"] for row in data["added"]] == ["NEW"]
    assert [row["ticker"] for row in data["removed"]] == ["GONE"]
    assert [row["ticker"] for row in data["decreased"]] == ["CUT"]
    assert data["turnover"] == pytest.approx(0.6)
    # No price ever enters this: the payload must carry no return-shaped field.
    assert not {"return", "performance", "gain", "pnl"} & set(data)


@pytest.mark.asyncio
async def test_too_few_snapshots_says_so_rather_than_reporting_no_change():
    """Zeros would read as "the model changed nothing", which is a different claim.

    On a delayed book the reason is usually the 45-day lag, so the message says which.
    """
    data = await _call(
        "get_portfolio_changes", {"portfolio_code": "AQA_BALANCED", "days": 7},
        get_portfolio_history=_history([("2026-09-10T00:00:00", [("A", 1.0)])], delayed=True),
    )
    assert data["comparable"] is False
    assert "nothing to compare" in data["message"]
    assert "delayed" in data["message"]
    assert "added" not in data and "turnover" not in data


@pytest.mark.asyncio
async def test_snapshots_are_ordered_before_they_are_compared():
    """The portal's ordering is not guaranteed; comparing the wrong way round inverts
    every direction, turning every cut into a raise."""
    history = _history([
        ("2026-09-10T00:00:00", [("A", 0.8)]),
        ("2026-08-10T00:00:00", [("A", 0.2)]),
    ])
    data = await _call("get_portfolio_changes", {"portfolio_code": "AQA_BALANCED"}, get_portfolio_history=history)
    assert data["from"] == "2026-08-10" and data["to"] == "2026-09-10"
    assert [row["ticker"] for row in data["increased"]] == ["A"]


# --------------------------------------------------------------------------- #
# Errors use the same vocabulary as the rest of the server
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool", "args", "mock", "error", "label"),
    [
        ("get_portfolio_concentration", {"portfolio_code": "NOPE"}, "get_portfolio",
         NotFoundError("no such portfolio"), "Portfolio Not Found"),
        ("get_portfolio_changes", {"portfolio_code": "AQA_BALANCED"}, "get_portfolio_history",
         AuthenticationError("session expired"), "Authentication or subscription required"),
    ],
)
async def test_portal_errors_keep_the_servers_error_vocabulary(tool, args, mock, error, label):
    data = await _call(tool, args, **{mock: error})
    assert data["error"] == label
    assert "disclaimer" in data
