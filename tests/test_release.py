"""Release hygiene: one version, reported consistently, with a changelog entry."""

import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from financial_portfolios_ai_mcp import __version__
from financial_portfolios_ai_mcp._version import _from_pyproject
from financial_portfolios_ai_mcp.app import create_app
from financial_portfolios_ai_mcp.explorer import VERSION_PLACEHOLDER, _load_html
from financial_portfolios_ai_mcp.server import mcp_server

ROOT = Path(__file__).resolve().parent.parent
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def test_version_is_single_sourced_from_pyproject():
    assert SEMVER.match(__version__), __version__
    assert __version__ == _from_pyproject()


def test_every_runtime_surface_reports_the_same_version():
    assert mcp_server.version == __version__  # serverInfo.version in the handshake
    app = create_app()
    assert app.version == __version__  # FastAPI / OpenAPI
    assert TestClient(app).get("/").json()["version"] == __version__  # HTTP root document
    html = _load_html()  # Explorer appInfo
    assert f'version: "{__version__}"' in html
    assert VERSION_PLACEHOLDER not in html


def test_static_manifests_match_the_version():
    """These are submitted as files, so they stay literal; this keeps them honest."""
    registry = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
    assert registry["version"] == __version__
    assert all(pkg["version"] == __version__ for pkg in registry.get("packages", []))

    connector = json.loads((ROOT / "claude_connector.json").read_text(encoding="utf-8"))
    assert connector["version"] == __version__


def test_changelog_has_an_entry_for_this_version():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert re.search(rf"^## \[{re.escape(__version__)}\] - \d{{4}}-\d{{2}}-\d{{2}}$", changelog, re.MULTILINE), (
        f"CHANGELOG.md has no dated '## [{__version__}]' section"
    )
    assert f"[{__version__}]: " in changelog, "missing comparison link for this version"


def test_release_notes_cover_this_version_without_performance_claims():
    notes = (ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    assert f"Version {__version__}" in notes
    # Customer notes must not promise what the connector cannot provide.
    lowered = notes.lower()
    assert "does not\n  provide prices, returns or performance" in lowered or "does not provide prices, returns or performance" in lowered

def test_every_force_included_file_exists():
    """A renamed packaged file must not be discoverable only by a failed image build.

    `force-include` names files by path, and hatchling fails the wheel build when one is
    missing - which surfaces inside `docker build`, minutes later and far from the rename.
    This has now happened twice: once for chatgpt_manifest.json, once for
    gemini_extension.json when it became gemini-extension.json.
    """
    import re

    root = Path(__file__).resolve().parent.parent
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    block = text.split("[tool.hatch.build.targets.wheel.force-include]")[1].split("[tool.pytest")[0]
    named = re.findall(r'^"([^"]+)"\s*=', block, re.MULTILINE)
    assert named, "expected force-include entries"
    missing = [name for name in named if not (root / name).is_file()]
    assert not missing, f"force-include names files that do not exist: {missing}"
