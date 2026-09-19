"""Portfolio metrics derived from weights alone.

Everything here is computed from `positions` - ticker, weight, sector - and nothing else.
That is deliberate: the portal sends `effective_n`, `equity_exposure`, `cash_allocation`,
`expected_return` and `expected_volatility` as null on the public delayed book, so a
delayed user sees the fewest figures precisely when they have the least else to go on.
Deriving them gives that user the same concentration and sector picture a subscriber gets,
without inventing anything - the weights are all the arithmetic needs.

None of this is performance. There are no prices behind any tool here, and these functions
never estimate a return; they describe the shape of a book and how it changed.

Two conventions run through the module:

* **Sums stay on the scale they arrived on.** A top-5 weight is the sum of five weights as
  published, so it matches what the tables display.
* **Concentration normalises first.** HHI is only meaningful on weights summing to 1, and a
  book can sum to less when cash sits outside `positions`.
"""

from collections import defaultdict
from typing import Any

UNCLASSIFIED = "Unclassified"


def _weights(positions: list[dict[str, Any]]) -> list[float]:
    return [p["weight"] for p in positions if isinstance(p.get("weight"), (int, float))]


def concentration(positions: list[dict[str, Any]]) -> dict[str, Any]:
    """How concentrated a book is, by weight.

    `effective_n` is the reciprocal of the Herfindahl-Hirschman index: the number of equally
    sized holdings that would be this concentrated. Ten equal weights give 10; ten weights
    where one is most of the book give something close to 1.
    """
    weights = sorted(_weights(positions), reverse=True)
    total = sum(weights)
    if not weights or total <= 0:
        return {"positions": len(positions), "top_5": None, "top_10": None, "largest": None, "effective_n": None}
    hhi = sum((w / total) ** 2 for w in weights)
    return {
        "positions": len(positions),
        "top_5": sum(weights[:5]),
        "top_10": sum(weights[:10]),
        "largest": weights[0],
        "effective_n": round(1 / hhi, 2) if hhi else None,
    }


def sector_mix(positions: list[dict[str, Any]]) -> dict[str, Any]:
    """Weight by sector, the dominant sector, and how spread across sectors the book is.

    `sector` is frequently null, so the unclassified share is reported rather than hidden:
    a dominant-sector claim made over a book that is half unclassified is not worth much.
    """
    by_sector: dict[str, float] = defaultdict(float)
    for position in positions:
        weight = position.get("weight")
        if isinstance(weight, (int, float)):
            by_sector[position.get("sector") or UNCLASSIFIED] += weight
    if not by_sector:
        return {"sectors": [], "dominant": None, "effective_sectors": None, "unclassified": 0.0}

    ranked = sorted(by_sector.items(), key=lambda item: item[1], reverse=True)
    total = sum(by_sector.values())
    hhi = sum((w / total) ** 2 for _, w in ranked) if total > 0 else 0
    return {
        "sectors": [{"sector": name, "weight": weight} for name, weight in ranked],
        "dominant": {"sector": ranked[0][0], "weight": ranked[0][1]},
        "effective_sectors": round(1 / hhi, 2) if hhi else None,
        "unclassified": by_sector.get(UNCLASSIFIED, 0.0),
    }


def breadth(books: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Which tickers appear across several portfolios, most-held first.

    Ranked by how many books hold a ticker, then by its average weight: breadth alone would
    put a token position held everywhere above a conviction position held twice.
    """
    holders: dict[str, dict[str, Any]] = {}
    for code, positions in books.items():
        for position in positions:
            ticker = str(position.get("ticker") or "").upper()
            weight = position.get("weight")
            if not ticker or not isinstance(weight, (int, float)):
                continue
            entry = holders.setdefault(ticker, {"ticker": ticker, "sector": position.get("sector"), "holdings": {}})
            entry["holdings"][code] = weight
            if not entry["sector"]:
                entry["sector"] = position.get("sector")

    rows = []
    for entry in holders.values():
        weights = list(entry["holdings"].values())
        rows.append({
            "ticker": entry["ticker"],
            "sector": entry["sector"],
            "held_by": sorted(entry["holdings"]),
            "count": len(weights),
            "mean_weight": sum(weights) / len(weights),
            "max_weight": max(weights),
        })
    rows.sort(key=lambda row: (-row["count"], -row["mean_weight"], row["ticker"]))
    return rows


def overlap(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> dict[str, Any]:
    """How much two books are the same.

    Two numbers, because they answer different questions: `weight_overlap` is how much of
    the money sits in the same names (the sum of the smaller weight for each shared ticker),
    while `jaccard` ignores size and asks how much of the combined name list is shared. Two
    books can share most of their names and little of their weight.
    """
    def by_ticker(positions: list[dict[str, Any]]) -> dict[str, float]:
        return {
            str(p["ticker"]).upper(): p["weight"]
            for p in positions
            if p.get("ticker") and isinstance(p.get("weight"), (int, float))
        }

    a, b = by_ticker(left), by_ticker(right)
    shared = sorted(set(a) & set(b))
    union = set(a) | set(b)
    return {
        "shared": shared,
        "weight_overlap": sum(min(a[t], b[t]) for t in shared),
        "jaccard": round(len(shared) / len(union), 4) if union else 0.0,
    }


def changes(earlier: list[dict[str, Any]], later: list[dict[str, Any]], limit: int = 10) -> dict[str, Any]:
    """What the model did between two snapshots.

    This is the honest answer to "which holdings did best": we have no prices, so we cannot
    say what a holding earned - but we can say what the model itself decided, which is the
    weight it raised, cut, opened or closed.

    `turnover` is one-way: half the summed absolute weight change, so a purchase and the
    sale that funded it count once between them rather than twice.
    """
    def by_ticker(positions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return {str(p["ticker"]).upper(): p for p in positions if p.get("ticker")}

    def weight_of(row: dict[str, Any]) -> float:
        weight = row.get("weight")
        return float(weight) if isinstance(weight, (int, float)) else 0.0

    before, after = by_ticker(earlier), by_ticker(later)

    added = [
        {"ticker": t, "sector": after[t].get("sector"), "weight": weight_of(after[t])}
        for t in after if t not in before
    ]
    removed = [
        {"ticker": t, "sector": before[t].get("sector"), "weight": weight_of(before[t])}
        for t in before if t not in after
    ]
    moves = [
        {
            "ticker": t,
            "sector": after[t].get("sector"),
            "from": weight_of(before[t]),
            "to": weight_of(after[t]),
            "change": weight_of(after[t]) - weight_of(before[t]),
        }
        for t in after if t in before
    ]
    moves = [m for m in moves if abs(m["change"]) > 1e-12]

    drift = sum(abs(weight_of(after.get(t, {})) - weight_of(before.get(t, {}))) for t in set(before) | set(after))
    added.sort(key=lambda row: -row["weight"])
    removed.sort(key=lambda row: -row["weight"])
    moves.sort(key=lambda row: -abs(row["change"]))
    return {
        "added": added[:limit],
        "removed": removed[:limit],
        "increased": [m for m in moves if m["change"] > 0][:limit],
        "decreased": [m for m in moves if m["change"] < 0][:limit],
        "added_count": len(added),
        "removed_count": len(removed),
        "turnover": drift / 2,
    }
