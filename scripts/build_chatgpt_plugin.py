#!/usr/bin/env python3
"""Build the ChatGPT app-directory plugin package (OpenAI plugin format).

    python scripts/build_chatgpt_plugin.py            # -> dist/chatgpt-plugin-<version>.zip
    python scripts/build_chatgpt_plugin.py --demo-url=https://...   # include the walkthrough video

Layout per developers.openai.com/plugins/build/plugins: plugin.json + mcp.json at the root,
assets/ for the logo. Authentication is OAuth with Dynamic Client Registration against the
portal (our /oauth/register allows the chatgpt.com redirect host). No secrets and no reviewer
credentials go in the package - the portal collects those separately and rejects them here.
Listing text comes from disclosure.SERVICE_DESCRIPTION so the financial disclosure travels with
it, and the version from pyproject.toml.
"""
import json
import shutil
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from financial_portfolios_ai_mcp.disclosure import SERVICE_DESCRIPTION  # noqa: E402

ORIGIN = "https://financial-portfolios.ai"

# Review metadata (developers.openai.com/plugins/deploy/submission#testing): exactly 5 positive and
# 3 negative cases, read-only in the portal - change them here and re-upload the ZIP. Prompts use
# product names, which every tool resolves; the reviewer account holds a subscription, so the live
# book is served. Negative cases are near-misses the model might wrongly route here.
POSITIVE_CASES = [
    {
        "description": "List the model portfolios and what the account can see",
        "prompt": "Which model portfolios does Financial Portfolios AI publish, and which can I see?",
        "tools_triggered": "list_portfolios",
        "expected_behavior": "Lists Aggressive, Balanced, Defensive and Quality with each one's risk "
        "level and access (subscribed = live book; otherwise the public book delayed about 45 days), "
        "with the informational-only disclaimer.",
    },
    {
        "description": "Show a portfolio's current holdings",
        "prompt": "Show me the current holdings of the Balanced model portfolio.",
        "tools_triggered": "get_portfolio_allocation",
        "expected_behavior": "Returns the Balanced book: tickers, sectors and target weights with its "
        "as-of date; states the date and the ~45-day delay if the book is delayed; no buy/sell advice.",
    },
    {
        "description": "Explain what changed over a period",
        "prompt": "What changed in the Quality portfolio over the last 90 days?",
        "tools_triggered": "get_portfolio_changes",
        "expected_behavior": "Reports positions added and removed, the largest weight increases and "
        "decreases, and one-way turnover for the window, described as model decisions, not returns.",
    },
    {
        "description": "Compare concentration and sector mix",
        "prompt": "Compare the sector mix and concentration of the Defensive and Aggressive portfolios.",
        "tools_triggered": "get_portfolio_concentration",
        "expected_behavior": "Shows each portfolio's top-5/top-10 weight, effective number of holdings "
        "and weight by sector side by side, noting if the books are from different dates; does not say "
        "which portfolio is better or suits the user.",
    },
    {
        "description": "Report published hypothetical performance with its disclosure",
        "prompt": "How has the Balanced portfolio performed against its benchmark?",
        "tools_triggered": "get_portfolio_performance",
        "expected_behavior": "Gives the published hypothetical return and risk statistics versus the "
        "benchmark, reproducing the response's disclaimer in full, and computes no figures itself.",
    },
]
NEGATIVE_CASES = [
    {
        "description": "Placing a trade. Should not act: the plugin publishes model portfolios and "
        "places no orders. Expected: explain it cannot trade and that the user places any order at "
        "their own broker.",
        "prompt": "Buy 10 shares of NVDA in my brokerage account.",
    },
    {
        "description": "A live stock quote. Should not act: the plugin has no real-time market "
        "prices, only published model portfolios. Expected: say it does not provide quotes.",
        "prompt": "What is Apple's stock price right now?",
    },
    {
        "description": "The user's own brokerage balance. Should not act: the plugin has no access "
        "to brokerage accounts. Expected: say it cannot see account balances or positions.",
        "prompt": "How much cash is in my Fidelity account?",
    },
]
RELEASE_NOTES = (
    "Browse the Financial Portfolios AI model portfolios (Aggressive, Balanced, Defensive, Quality): "
    "current holdings, what changed, concentration and sector mix, and published hypothetical "
    "performance, plus interactive explorer panels. Read-only; informational and educational only, "
    "not investment advice. Available to US residents."
)


def manifests(version: str, demo_url: str = "") -> tuple[dict, dict]:
    plugin = {
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        "name": "financial-portfolios-ai",
        "version": version,
        "description": SERVICE_DESCRIPTION,
        "extensions": {
            "com.openai": {
                "interface": {
                    "displayName": "Financial Portfolios AI",  # <=30
                    "shortDescription": "Model portfolios and research",  # <=30
                    "longDescription": SERVICE_DESCRIPTION,  # <=4000
                    "developerName": "Autonomous Intelligent Agents LLC",
                    "category": "Finance",
                    "capabilities": ["Read"],
                    "websiteURL": ORIGIN,
                    "supportURL": f"{ORIGIN}/contact",
                    "privacyPolicyURL": f"{ORIGIN}/legal/privacy",
                    "termsOfServiceURL": f"{ORIGIN}/legal/terms",
                    "defaultPrompt": [
                        "Show me the holdings of the Balanced model portfolio.",
                        "Compare the Defensive and Aggressive model portfolios.",
                        "What changed in the Quality portfolio over the last 90 days?",
                    ],
                    "brandColor": "#0B1020",
                    "logo": "./assets/logo.png",
                    "composerIcon": "./assets/icon.png",
                },
                "review": {
                    "test_cases": {"positive": POSITIVE_CASES, "negative": NEGATIVE_CASES},
                    **({"demo_recording_url": demo_url} if demo_url else {}),
                    "commerce": False,
                    "commerce_description": "No purchases happen in ChatGPT. Subscriptions are bought "
                    "on financial-portfolios.ai; the plugin only reads published model portfolios.",
                },
                "publication": {"release_notes": RELEASE_NOTES, "countries": ["US"]},
            }
        },
    }
    mcp = {
        "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
        "mcpServers": {
            "financial-portfolios-ai": {
                "type": "streamable-http",
                "url": f"{ORIGIN}/mcp",
                "extensions": {
                    "com.openai": {
                        "auth": {
                            "type": "oauth",
                            "client": {"mode": "dcr"},
                            "registrationUrl": f"{ORIGIN}/oauth/register",
                        }
                    }
                },
            }
        },
    }
    return plugin, mcp


def main() -> int:
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    demo_url = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--demo-url=")), "")
    plugin, mcp = manifests(version, demo_url)
    assert len(POSITIVE_CASES) == 5 and len(NEGATIVE_CASES) == 3, "OpenAI requires exactly 5 and 3"
    for key in ("displayName", "shortDescription"):
        value = plugin["extensions"]["com.openai"]["interface"][key]
        assert len(value) <= 30, f"{key} is {len(value)} chars (max 30): {value!r}"
    out = ROOT / "dist" / "chatgpt-plugin"
    shutil.rmtree(out, ignore_errors=True)
    (out / "assets").mkdir(parents=True)
    (out / "plugin.json").write_text(json.dumps(plugin, indent=2) + "\n", encoding="utf-8")
    (out / "mcp.json").write_text(json.dumps(mcp, indent=2) + "\n", encoding="utf-8")
    assets = ROOT / "src" / "financial_portfolios_ai_mcp" / "assets"
    shutil.copy(assets / "icon-512.png", out / "assets" / "logo.png")
    shutil.copy(assets / "icon-192.png", out / "assets" / "icon.png")
    archive = ROOT / "dist" / f"chatgpt-plugin-{version}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(out.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(out).as_posix())
    print(archive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
