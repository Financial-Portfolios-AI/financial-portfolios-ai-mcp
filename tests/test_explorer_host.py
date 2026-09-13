"""Explorer host integration: capability report, model context, Ask, fullscreen, theming."""

import json
import logging
import re

import pytest

from financial_portfolios_ai_mcp.explorer import EXPLORER_URI, summarize_host
from financial_portfolios_ai_mcp.server import mcp_server


async def _html() -> str:
    item = (await mcp_server.read_resource(EXPLORER_URI))[0]
    return item.content if hasattr(item, "content") else item.text


def _script(html: str) -> str:
    return re.search(r"<script>(.*?)</script>", html, re.DOTALL).group(1)


# --------------------------------------------------------------------------- #
# Capability report (page-only tool)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_capability_tool_is_hidden_from_the_model():
    tool = {t.name: t for t in await mcp_server.list_tools()}["report_explorer_host"]
    assert tool.meta["ui"]["visibility"] == ["app"]
    assert tool.meta["ui"]["resourceUri"] == EXPLORER_URI
    assert tool.annotations.read_only_hint is True


def test_host_summary_keeps_flags_and_drops_identifying_context():
    summary = summarize_host(
        {"message": {"text": {}}, "openLinks": {}, "logging": {}, "serverTools": {"listChanged": True}},
        {
            "theme": "dark", "displayMode": "inline", "availableDisplayModes": ["inline", "fullscreen"],
            "locale": "en-GB", "timeZone": "Europe/London", "containerDimensions": {"width": 400},
            "styles": {"variables": {"--color-text-primary": "#111", "--font-sans": "Inter"}},
        },
        {"name": "Claude", "version": "1.0"},
    )
    assert summary["capabilities"] == {"message": ["text"], "openLinks": [], "logging": [], "serverTools": ["listChanged"]}
    assert summary["context"] == {"theme": "dark", "displayMode": "inline", "availableDisplayModes": ["inline", "fullscreen"]}
    assert "locale" not in json.dumps(summary) and "Europe/London" not in json.dumps(summary)
    assert summary["style_variables"] == 2
    assert summary["host"] == {"name": "Claude", "version": "1.0"}


def test_host_summary_tolerates_junk():
    assert summarize_host(None, "nope", 42) == {"host": {}, "capabilities": {}, "context": {}, "style_variables": 0}


@pytest.mark.asyncio
async def test_capability_report_is_logged(caplog):
    with caplog.at_level(logging.INFO, logger="financial_portfolios_ai_mcp.explorer"):
        await mcp_server.call_tool("report_explorer_host", {
            "host_capabilities": {"updateModelContext": {"text": {}}},
            "host_context": {"theme": "light", "locale": "fr-FR"},
            "host_info": {"name": "ChatGPT"},
        })
    record = next(r for r in caplog.records if r.getMessage().startswith("explorer_host_report "))
    logged = json.loads(record.getMessage().split(" ", 1)[1])
    assert logged["host"] == {"name": "ChatGPT"}
    assert logged["capabilities"] == {"updateModelContext": ["text"]}
    assert "fr-FR" not in record.getMessage()


# --------------------------------------------------------------------------- #
# Page: every optional host feature is feature-detected
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "gate"),
    [
        ("ui/update-model-context", "hostCaps.updateModelContext"),
        ("ui/message", "hostCaps.message"),
        ("notifications/message", "hostCaps.logging"),
        ("ui/request-display-mode", "availableDisplayModes"),
    ],
)
async def test_optional_host_features_are_gated_on_capabilities(method, gate):
    js = _script(await _html())
    assert method in js, f"page never uses {method}"
    assert gate in js, f"{method} is not gated on {gate}"


@pytest.mark.asyncio
async def test_ask_button_wording_never_asks_for_advice():
    """The Ask button posts text into the conversation on the user's behalf."""
    js = _script(await _html())
    body = js[js.index("function askText()"):js.index("function toast(")]
    templates = re.findall(r"`(Using the Portfolio Explorer[^`]*)`", body)
    assert len(templates) >= 5
    for text in templates:
        lowered = text.lower()
        for word in ("buy", "sell", "should", "recommend", "invest in", "suitable", "better"):
            assert word not in lowered, f"advice-like wording {word!r} in: {text}"


@pytest.mark.asyncio
async def test_capability_report_sends_no_identifying_context():
    js = _script(await _html())
    report = js[js.index("function reportHost(init)"):js.index("$(\"holdings\").innerHTML = `<tbody><tr><td class=\"empty\">Loading portfolios")]
    assert "locale" not in report and "timeZone" not in report and "containerDimensions" not in report
    # Theme variable names are counted, their values are not sent.
    assert 'map((k) => [k, ""])' in report


@pytest.mark.asyncio
async def test_theme_follows_host_variables_with_fallbacks():
    html = await _html()
    for host_var in ("--color-background-primary", "--color-text-primary", "--color-border-primary", "--font-sans"):
        assert f"var({host_var}," in html, host_var
    # Applied host variables are validated before use.
    assert "^--[a-z0-9-]{1,64}$" in html
