"""The marketplace publisher: the environment is a parameter, and a bad target is refused.

Two public artifacts hardcode an endpoint - the Gemini extension and the Claude Code
plugin's `.mcp.json` - and they live in a different repository from the templates. Editing
them by hand is how they ended up pointing at a domain that serves nothing, so the
generation is tested rather than trusted.
"""

import importlib.util
import json
from pathlib import Path

import pytest

from financial_portfolios_ai_mcp.manifests import ENVIRONMENTS, PLACEHOLDER

REPO_ROOT = Path(__file__).resolve().parent.parent


def _publisher():
    spec = importlib.util.spec_from_file_location(
        "publish_marketplace", REPO_ROOT / "scripts" / "publish_marketplace.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


publish = _publisher()
DEV = ENVIRONMENTS["dev"]
PROD = ENVIRONMENTS["prod"]


# --------------------------------------------------------------------------- #
# The templates must stay environment-free, or publishing cannot change anything
# --------------------------------------------------------------------------- #
def test_the_context_template_carries_no_environment_origin():
    text = (REPO_ROOT / "GEMINI.md").read_text(encoding="utf-8")
    assert PLACEHOLDER in text
    assert "https://financial-portfolios.ai" not in text
    assert "https://dev.financial-portfolios.ai" not in text


def test_environments_are_defined_once():
    """The renderer, the publisher and these tests must agree on what `dev` means.

    A second copy of this map is how one artifact ends up on a different host from the rest.
    """
    from financial_portfolios_ai_mcp import manifests

    assert publish.ENVIRONMENTS is manifests.ENVIRONMENTS
    assert set(ENVIRONMENTS) == {"dev", "prod"}


# --------------------------------------------------------------------------- #
# The plugin's URL is an env-var default inside a string, so it is rewritten by pattern
# --------------------------------------------------------------------------- #
def test_plugin_default_is_retargeted_and_the_override_survives():
    before = '{"url": "${FPAI_MCP_URL:-https://financial-portfolios.ai/mcp}"}'
    after = publish.plugin_config(before, DEV)
    assert after == '{"url": "${FPAI_MCP_URL:-https://dev.financial-portfolios.ai/mcp}"}'
    # The override is the point: a self-hosted or staging server must still work.
    assert "${FPAI_MCP_URL:-" in after


def test_a_changed_plugin_shape_fails_loudly_rather_than_silently_publishing():
    """No match means the rewrite did nothing, which would publish the previous endpoint."""
    with pytest.raises(SystemExit, match="found 0"):
        publish.plugin_config('{"url": "https://financial-portfolios.ai/mcp"}', DEV)


# --------------------------------------------------------------------------- #
# Generated artifacts
# --------------------------------------------------------------------------- #
def test_generated_manifest_targets_the_requested_environment():
    manifest = json.loads(publish.gemini_manifest(DEV, "dev"))
    assert manifest["mcpServers"]["financial-portfolios-ai"]["httpUrl"] == f"{DEV}/mcp"
    assert "not the production deployment" in manifest["$comment"]
    # The token placeholder belongs to Gemini, not to the origin renderer.
    assert manifest["mcpServers"]["financial-portfolios-ai"]["headers"]["X-API-Key"] == "${FINANCIAL_PORTFOLIOS_API_TOKEN}"

    production = json.loads(publish.gemini_manifest(PROD, "prod"))
    assert production["mcpServers"]["financial-portfolios-ai"]["httpUrl"] == f"{PROD}/mcp"
    assert "not the production deployment" not in production["$comment"]


def test_generated_context_substitutes_every_placeholder():
    for origin, env in ((DEV, "dev"), (PROD, "prod")):
        text = publish.gemini_context(origin, env)
        assert PLACEHOLDER not in text, "an unsubstituted placeholder would ship as literal text"
        assert f"{origin}/mcp" in text
        assert "<!-- Template:" not in text, "the editing note is meaningless once published"
    assert "**Preview.**" in publish.gemini_context(DEV, "dev")
    assert "**Preview.**" not in publish.gemini_context(PROD, "prod")


# --------------------------------------------------------------------------- #
# The probe is the safeguard that a hand edit did not have
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("status", "headers", "expected"),
    [
        (401, {"WWW-Authenticate": 'Bearer resource_metadata="https://x/.well-known/y"'}, True),
        (401, {}, False),           # a challenge with no metadata pointer is not usable
        (404, {}, False),           # nothing mounted - the production failure we shipped once
        (403, {}, False),
    ],
)
def test_probe_accepts_only_a_real_challenge(monkeypatch, status, headers, expected):
    import urllib.error

    def fake_urlopen(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, status, "", headers, None)

    monkeypatch.setattr(publish.urllib.request, "urlopen", fake_urlopen)
    ok, detail = publish.probe(DEV)
    assert ok is expected, detail


def test_probe_rejects_an_unauthenticated_endpoint(monkeypatch):
    """A 200 means /mcp answers without a credential, which is its own problem."""

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(publish.urllib.request, "urlopen", lambda *a, **k: Response())
    ok, detail = publish.probe(DEV)
    assert ok is False
    assert "200" in detail
