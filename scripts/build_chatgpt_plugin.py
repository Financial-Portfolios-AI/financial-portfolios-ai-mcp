#!/usr/bin/env python3
"""Build the ChatGPT app-directory plugin package (OpenAI plugin format).

    python scripts/build_chatgpt_plugin.py            # -> dist/chatgpt-plugin-<version>.zip

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


def manifests(version: str) -> tuple[dict, dict]:
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
                }
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
    plugin, mcp = manifests(version)
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
