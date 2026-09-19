"""Metrics derived from weights alone - the figures the delayed book does not carry."""

import pytest

from financial_portfolios_ai_mcp.metrics import breadth, changes, concentration, overlap, sector_mix


def p(ticker, weight, sector=None):
    return {"ticker": ticker, "weight": weight, "sector": sector}


# --------------------------------------------------------------------------- #
# Concentration
# --------------------------------------------------------------------------- #
def test_equal_weights_are_as_many_effective_holdings_as_there_are():
    book = [p(t, 0.25) for t in "ABCD"]
    assert concentration(book)["effective_n"] == 4


def test_effective_n_normalises_when_cash_sits_outside_positions():
    """A book can sum to less than 1, and HHI is only meaningful on weights summing to 1.

    Two 45% positions with 10% cash held elsewhere are still two effective holdings; an
    un-normalised HHI would report 2.47.
    """
    assert concentration([p("A", 0.45), p("B", 0.45)])["effective_n"] == 2.0


def test_sums_stay_on_the_scale_they_arrived_on():
    """Top-N is a plain sum so it matches the tables, which show published weights."""
    book = [p("A", 0.45), p("B", 0.45)]
    assert concentration(book)["top_5"] == pytest.approx(0.9)
    assert concentration(book)["largest"] == 0.45


def test_a_dominant_holding_collapses_effective_n_towards_one():
    book = [p("BIG", 0.9)] + [p(t, 0.02) for t in "ABCDE"]
    assert concentration(book)["effective_n"] < 1.3


def test_an_empty_or_weightless_book_reports_nothing_rather_than_zero():
    assert concentration([])["effective_n"] is None
    assert concentration([{"ticker": "A"}])["effective_n"] is None


# --------------------------------------------------------------------------- #
# Sectors
# --------------------------------------------------------------------------- #
def test_dominant_sector_and_spread():
    book = [p("A", 0.5, "Technology"), p("B", 0.25, "Energy"), p("C", 0.25, "Energy")]
    mix = sector_mix(book)
    assert mix["dominant"] == {"sector": "Technology", "weight": 0.5}
    assert [s["sector"] for s in mix["sectors"]] == ["Technology", "Energy"]
    assert mix["effective_sectors"] == 2.0


def test_a_missing_sector_is_reported_not_hidden():
    """`sector` is frequently null, and a dominant-sector claim over a half-unclassified
    book is not worth much - so the share is surfaced rather than quietly dropped."""
    mix = sector_mix([p("A", 0.5, "Technology"), p("B", 0.5, None)])
    assert mix["unclassified"] == 0.5
    assert {s["sector"] for s in mix["sectors"]} == {"Technology", "Unclassified"}


# --------------------------------------------------------------------------- #
# Breadth across portfolios
# --------------------------------------------------------------------------- #
def test_most_held_ranks_by_how_many_books_hold_it():
    books = {
        "AQA_DEFENSIVE": [p("MSFT", 0.1, "Technology"), p("KO", 0.05, "Staples")],
        "AQA_BALANCED": [p("MSFT", 0.2, "Technology"), p("NVDA", 0.3, "Technology")],
        "AQA_AGGRESSIVE": [p("MSFT", 0.15, "Technology")],
    }
    rows = breadth(books)
    assert rows[0]["ticker"] == "MSFT"
    assert rows[0]["count"] == 3
    assert rows[0]["held_by"] == ["AQA_AGGRESSIVE", "AQA_BALANCED", "AQA_DEFENSIVE"]
    assert rows[0]["mean_weight"] == pytest.approx(0.15)
    assert rows[0]["max_weight"] == 0.2


def test_a_wide_token_position_does_not_outrank_a_narrow_conviction_one_at_equal_breadth():
    """Breadth alone would rank a 0.1% holding held twice above a 30% holding held twice."""
    books = {
        "A": [p("TINY", 0.001), p("BIG", 0.3)],
        "B": [p("TINY", 0.001), p("BIG", 0.3)],
    }
    assert [row["ticker"] for row in breadth(books)] == ["BIG", "TINY"]


def test_breadth_ignores_rows_without_a_usable_weight():
    rows = breadth({"A": [p("MSFT", 0.1), {"ticker": "BAD"}, {"weight": 0.2}]})
    assert [row["ticker"] for row in rows] == ["MSFT"]


# --------------------------------------------------------------------------- #
# Overlap
# --------------------------------------------------------------------------- #
def test_overlap_separates_shared_names_from_shared_money():
    """Two books can share most of their names and little of their weight."""
    left = [p("A", 0.8), p("B", 0.1), p("C", 0.1)]
    right = [p("A", 0.1), p("B", 0.1), p("C", 0.8)]
    result = overlap(left, right)
    assert result["jaccard"] == 1.0, "every name is shared"
    assert result["weight_overlap"] == pytest.approx(0.3), "but only 30% of the money is in the same place"
    assert result["shared"] == ["A", "B", "C"]


def test_books_with_nothing_in_common():
    result = overlap([p("A", 1.0)], [p("B", 1.0)])
    assert result["shared"] == [] and result["weight_overlap"] == 0 and result["jaccard"] == 0.0


# --------------------------------------------------------------------------- #
# Changes: what the model did, since we cannot say what a holding earned
# --------------------------------------------------------------------------- #
def test_changes_report_the_models_own_decisions():
    earlier = [p("KEEP", 0.3), p("CUT", 0.4), p("GONE", 0.3)]
    later = [p("KEEP", 0.3), p("CUT", 0.1), p("NEW", 0.6)]
    result = changes(earlier, later)

    assert [row["ticker"] for row in result["added"]] == ["NEW"]
    assert [row["ticker"] for row in result["removed"]] == ["GONE"]
    assert [row["ticker"] for row in result["decreased"]] == ["CUT"]
    assert result["increased"] == [], "nothing was raised"
    assert result["decreased"][0]["change"] == pytest.approx(-0.3)
    # An unchanged holding is not a change.
    assert all(row["ticker"] != "KEEP" for row in result["increased"] + result["decreased"])


def test_turnover_counts_a_switch_once_not_twice():
    """One-way turnover: a purchase and the sale funding it are one move between them."""
    earlier = [p("OLD", 0.5), p("STAY", 0.5)]
    later = [p("NEW", 0.5), p("STAY", 0.5)]
    assert changes(earlier, later)["turnover"] == pytest.approx(0.5)


def test_an_unchanged_book_has_no_turnover():
    book = [p("A", 0.5), p("B", 0.5)]
    result = changes(book, list(book))
    assert result["turnover"] == 0
    assert result["added"] == [] and result["removed"] == []
