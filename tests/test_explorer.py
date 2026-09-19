"""Portfolio Explorer MCP App: tool binding, UI resource, and tool behaviour."""

import json
import re
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from financial_portfolios_ai.exceptions import AuthenticationError
from financial_portfolios_ai.models import (
    PortfolioListResponse,
    PortfolioSnapshot,
    PortfolioSummary,
    Position,
)

from financial_portfolios_ai_mcp.app import create_app
from financial_portfolios_ai_mcp.explorer import EXPLORER_URI, _pick_initial
from financial_portfolios_ai_mcp.server import mcp_server

APP_MIME = "text/html;profile=mcp-app"


def _text(result) -> str:
    if hasattr(result, "content") and result.content:
        return result.content[0].text
    if isinstance(result, list) and result:
        return getattr(result[0], "text", str(result[0]))
    return str(result)


async def _html() -> tuple[str, str]:
    contents = await mcp_server.read_resource(EXPLORER_URI)
    item = contents[0]
    body = item.content if hasattr(item, "content") else item.text
    return body, item.mime_type


# --------------------------------------------------------------------------- #
# Binding: what a host needs to find and render the App
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_tool_is_bound_to_the_ui_resource():
    tool = {t.name: t for t in await mcp_server.list_tools()}["open_portfolio_explorer"]
    assert tool.meta == {"ui": {"resourceUri": EXPLORER_URI}}
    assert tool.title == "Portfolio Explorer"
    assert tool.annotations.read_only_hint is True


@pytest.mark.asyncio
async def test_ui_resource_is_served_as_an_mcp_app():
    html, mime = await _html()
    assert mime == APP_MIME
    for method in ("ui/initialize", "ui/notifications/initialized", "ui/notifications/tool-result", "tools/call"):
        assert method in html, f"App never uses {method}"


@pytest.mark.asyncio
async def test_ui_is_self_contained():
    """A host's default CSP for an App blocks all network and external scripts."""
    html, _ = await _html()
    assert not re.search(r"<script[^>]+src=", html), "external script"
    assert not re.search(r"<link[^>]+href=", html), "external stylesheet"
    assert "fetch(" not in html and "XMLHttpRequest" not in html, "network call"
    assert not re.search(r"https?://", html), "remote URL"


@pytest.mark.asyncio
async def test_ui_only_calls_read_only_tools():
    html, _ = await _html()
    called = set(re.findall(r'callTool\("([a-z_]+)"', html))
    assert called == {"list_portfolios", "get_portfolio_allocation", "get_portfolio_history"}


@pytest.mark.asyncio
async def test_ui_carries_the_disclosure_and_delayed_book_notice():
    html, _ = await _html()
    assert "Informational and educational purposes only" in html
    assert "delayed about 45 days" in html


def test_ui_resource_is_not_downloadable_over_http():
    """The public asset route serves icons only; the App reaches hosts over MCP."""
    client = TestClient(create_app())
    assert client.get("/mcp/assets/portfolio_explorer.html").status_code == 404
    assert client.get("/mcp/assets/icon-48.png").status_code == 200


# --------------------------------------------------------------------------- #
# Initial selection
# --------------------------------------------------------------------------- #
PORTFOLIOS = [
    {"code": "AQA_BALANCED", "access": "public_delayed"},
    {"code": "AQA_DEFENSIVE", "access": "subscribed"},
    {"code": "AQA_AGGRESSIVE", "access": "public_delayed"},
]


@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        ("", "AQA_DEFENSIVE"),  # first subscribed, not first listed
        ("aqa_aggressive", "AQA_AGGRESSIVE"),  # case-insensitive, canonical code returned
        ("AQA_UNKNOWN", "AQA_DEFENSIVE"),  # unknown code falls back
    ],
)
def test_initial_selection(requested, expected):
    assert _pick_initial(PORTFOLIOS, requested) == expected


def test_initial_selection_without_subscriptions_or_portfolios():
    delayed_only = [{"code": "AQA_BALANCED", "access": "public_delayed"}]
    assert _pick_initial(delayed_only, "") == "AQA_BALANCED"
    assert _pick_initial([], "") is None


# --------------------------------------------------------------------------- #
# Tool behaviour
# --------------------------------------------------------------------------- #
def _client(listing=None, snapshot=None, error=None):
    client = AsyncMock()
    if error:
        client.list_portfolios.side_effect = error
    else:
        client.list_portfolios.return_value = listing
        client.get_portfolio.return_value = snapshot
    client.__aenter__.return_value = client
    return client


@pytest.mark.asyncio
async def test_explorer_returns_list_selection_and_allocation():
    listing = PortfolioListResponse(
        total=2,
        portfolios=[
            PortfolioSummary(code="AQA_BALANCED", access="public_delayed", delayed=True),
            PortfolioSummary(code="AQA_DEFENSIVE", access="subscribed", delayed=False),
        ],
    )
    snapshot = PortfolioSnapshot(
        portfolio_code="AQA_DEFENSIVE",
        date="2026-09-10T00:00:00",
        total_positions=1,
        positions=[Position(ticker="MSFT", weight=1.0, sector="Technology")],
    )
    client = _client(listing, snapshot)
    with patch("financial_portfolios_ai_mcp.explorer.get_async_client", return_value=client):
        data = json.loads(_text(await mcp_server.call_tool("open_portfolio_explorer", {})))

    assert [p["code"] for p in data["portfolios"]] == ["AQA_BALANCED", "AQA_DEFENSIVE"]
    assert data["selected"] == "AQA_DEFENSIVE"
    assert data["allocation"]["portfolio_code"] == "AQA_DEFENSIVE"
    assert "disclaimer" in data
    client.get_portfolio.assert_awaited_once_with(portfolio_code="AQA_DEFENSIVE")


@pytest.mark.asyncio
async def test_explorer_with_no_portfolios_skips_the_allocation_call():
    client = _client(PortfolioListResponse(total=0, portfolios=[]))
    with patch("financial_portfolios_ai_mcp.explorer.get_async_client", return_value=client):
        data = json.loads(_text(await mcp_server.call_tool("open_portfolio_explorer", {})))
    assert data["selected"] is None and data["allocation"] is None
    client.get_portfolio.assert_not_awaited()


@pytest.mark.asyncio
async def test_explorer_reports_portal_errors_as_json():
    client = _client(error=AuthenticationError("session expired"))
    with patch("financial_portfolios_ai_mcp.explorer.get_async_client", return_value=client):
        data = json.loads(_text(await mcp_server.call_tool("open_portfolio_explorer", {})))
    assert data["error"] == "Unable to open the Portfolio Explorer"
    assert "session expired" in data["message"]


@pytest.mark.asyncio
async def test_connector_manifest_lists_exactly_the_served_tools():
    from pathlib import Path

    manifest = json.loads((Path(__file__).resolve().parent.parent / "claude_connector.json").read_text(encoding="utf-8"))
    listed = {t["name"] for t in manifest["capabilities"]["tools"]}
    # The manifest describes what a user or model can use; page-only tools are internal.
    served = {
        t.name for t in await mcp_server.list_tools()
        if (t.meta or {}).get("ui", {}).get("visibility") != ["app"]
    }
    assert listed == served



# --------------------------------------------------------------------------- #
# Regression: the page must read the result the SDK actually sends
# --------------------------------------------------------------------------- #
def _wire_result(tool: str, arguments: dict, client) -> dict:
    """Call a tool over real HTTP and return the exact CallToolResult a host receives."""
    headers = {
        "X-API-Key": "aqat_v1_test",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": "2025-11-25",
    }
    with (
        patch("financial_portfolios_ai_mcp.explorer.get_async_client", return_value=client),
        TestClient(create_app(), base_url="http://localhost") as http,
    ):
        http.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}})
        r = http.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                                    "params": {"name": tool, "arguments": arguments}})
    match = re.search(r"^data: (.*)$", r.text, re.MULTILINE)
    return json.loads(match.group(1) if match else r.text)["result"]


def _explorer_client():
    listing = PortfolioListResponse(
        total=1, portfolios=[PortfolioSummary(code="AQA_DEFENSIVE", product_name="Defensive", access="subscribed")]
    )
    snapshot = PortfolioSnapshot(
        portfolio_code="AQA_DEFENSIVE", date="2026-09-10T00:00:00", total_positions=1,
        positions=[Position(ticker="MSFT", weight=1.0, sector="Technology")],
    )
    return _client(listing, snapshot)


def test_structured_content_is_the_payload_itself():
    """Tools return objects, so structuredContent is the data - not the
    {"result": "<json string>"} envelope a string return produced, which is what left the
    Explorer empty on Claude mobile. Clients such as ChatGPT widgets read this field."""
    result = _wire_result("open_portfolio_explorer", {}, _explorer_client())
    structured = result["structuredContent"]
    assert "result" not in structured
    assert structured["selected"] == "AQA_DEFENSIVE"
    assert structured["portfolios"][0]["code"] == "AQA_DEFENSIVE"
    # The text block still carries the same JSON, for clients that read only content.
    assert json.loads(result["content"][0]["text"]) == structured


@pytest.mark.skipif(__import__("shutil").which("node") is None, reason="node not installed")
def test_page_parser_reads_the_real_wire_result(tmp_path):
    """Run the page's own parseResult against real server output, in both shapes a host may send."""
    import subprocess

    html = (Path(__file__).resolve().parent.parent / "src/financial_portfolios_ai_mcp/assets/portfolio_explorer.html").read_text(encoding="utf-8")
    parser = re.search(r"(function parseResult\(result\) \{.*?\n  \})", html, re.DOTALL).group(1)
    wire = _wire_result("open_portfolio_explorer", {}, _explorer_client())
    structured_only = {"structuredContent": wire["structuredContent"]}

    cases = json.dumps([wire, structured_only])
    script = tmp_path / "parse.js"
    script.write_text(
        f"{parser}\n"
        f"const out = {cases}.map((r) => parseResult(r).selected);\n"
        "process.stdout.write(JSON.stringify(out));\n",
        encoding="utf-8",
    )
    out = subprocess.run(["node", str(script)], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == ["AQA_DEFENSIVE", "AQA_DEFENSIVE"]


@pytest.mark.skipif(__import__("shutil").which("node") is None, reason="node not installed")
def test_page_metrics_are_scale_free_and_normalised(tmp_path):
    """Run the page's own metricsOf over books the portal really produces.

    The concentration figures are the reason these metrics exist at all: the portal sends
    `effective_n` as null on the public delayed book, so the page derives it. Two things
    are easy to get wrong and are pinned here - the HHI must be computed on weights
    normalised to sum 1 (a book can sum to less than 1 when cash sits outside `positions`),
    while the headline percentages must stay on the raw scale so they match the table the
    user is reading.
    """
    import subprocess

    html = (Path(__file__).resolve().parent.parent / "src/financial_portfolios_ai_mcp/assets/portfolio_explorer.html").read_text(encoding="utf-8")
    fn = re.search(r"(function metricsOf\(a\) \{.*?\n  \})", html, re.DOTALL).group(1)

    equal = {"positions": [{"ticker": t, "weight": 0.25, "sector": "Tech"} for t in "ABCD"]}
    with_cash = {"positions": [{"ticker": "A", "weight": 0.45, "sector": "Tech"}, {"ticker": "B", "weight": 0.45, "sector": "Energy"}]}
    unclassified = {"positions": [{"ticker": "A", "weight": 0.5, "sector": "Tech"}, {"ticker": "B", "weight": 0.5, "sector": None}]}

    script = tmp_path / "metrics.js"
    script.write_text(
        'const isNum = (v) => typeof v === "number" && Number.isFinite(v);\n'
        f"{fn}\n"
        f"const books = {json.dumps([equal, with_cash, unclassified])};\n"
        "const out = books.map((b) => { const m = metricsOf(b); return {\n"
        "  effectiveN: Number(m.effectiveN.toFixed(4)), top5: Number(m.top5.toFixed(4)),\n"
        "  largest: m.largest, dominant: m.dominant[0], dominantWeight: Number(m.dominant[1].toFixed(4)),\n"
        "  effectiveSectors: Number(m.effectiveSectors.toFixed(4)), unclassified: m.unclassified }; });\n"
        "process.stdout.write(JSON.stringify(out));\n",
        encoding="utf-8",
    )
    equal_book, cash_book, unclassified_book = json.loads(
        subprocess.run(["node", str(script)], capture_output=True, text=True, check=True).stdout
    )

    # Four equal weights are four effective holdings, and one sector.
    assert equal_book["effectiveN"] == 4
    assert equal_book["top5"] == 1
    assert equal_book["effectiveSectors"] == 1

    # Cash outside `positions` leaves the book summing to 0.9. Effective N must still be 2 -
    # not 2.47, which is what an un-normalised HHI would give - while top 5 stays 90%,
    # matching the page's own "Top 5 weight" card.
    assert cash_book["effectiveN"] == 2
    assert cash_book["top5"] == 0.9
    assert cash_book["effectiveSectors"] == 2

    # A null sector is reported as its own bucket rather than silently dropped: `sector` is
    # frequently null, and a dominant-sector claim that ignored it would overstate.
    assert unclassified_book["dominant"] in {"Tech", "Unclassified"}
    assert unclassified_book["unclassified"] == 0.5


@pytest.mark.asyncio
async def test_ui_offers_compare_and_find_with_their_guardrails():
    html, _ = await _html()
    for tab in ('data-tab="compare"', 'data-tab="find"'):
        assert tab in html
    # Compare must warn when books differ in date or access, and must not rank portfolios.
    assert "not a like-for-like comparison" in html
    assert "not a recommendation of any portfolio" in html
    # Find must not read presence in a model as advice, and must explain delayed gaps.
    assert "not a recommendation to own it" in html
    assert "a recently added position would not show there yet" in html


@pytest.mark.asyncio
async def test_ui_reports_content_height_not_document_height():
    """A document is at least as tall as its iframe, so reporting documentElement.scrollHeight
    lets the host's frame grow but never shrink - it left empty space under short tabs."""
    html, _ = await _html()
    size_code = html[html.index("Keep the host's iframe sized"):]
    assert "wrap.getBoundingClientRect()" in size_code
    # Check code only: the comment explaining the bug names the old approach.
    code = "\n".join(line for line in html.splitlines() if not line.strip().startswith("//"))
    assert "documentElement.scrollHeight" not in code
    # Re-sent after the handshake in case the host ignored an earlier report.
    assert "reportSize(true)" in html

@pytest.mark.asyncio
async def test_a_bad_tool_result_does_not_disable_the_fallback():
    """An unparseable payload must leave the page able to load itself.

    `gotToolResult` used to be set before parsing, so a result the page could not read both
    showed an error and suppressed the bootstrap fetch - a dead page with no second chance.
    It is now set only after a successful parse.
    """
    html, _ = await _html()
    begin = html.index("function onToolResult(result) {")
    handler = html[begin:html.index("showError(err.message)", begin)]
    before_try = handler.split("try {")[0]

    assert "gotToolResult = true" not in before_try, "flag set before the parse can fail"
    assert "gotToolResult = true" in handler, "flag must still be set on success"
    # A wrapped result is tolerated too: a host sending one would otherwise blank the page.
    assert "result.result" in handler
