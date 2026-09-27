"""Provider manifests, rendered for the deployment that serves them.

The three connector manifests (`claude_connector.json`, `chatgpt_manifest.json`,
`gemini-extension.json`) are stored as templates: every absolute URL they contain
is written as `${PUBLIC_ORIGIN}/...` rather than a baked-in hostname. Rendering
happens either here, against the origin a request arrived on, or offline via
`scripts/render_manifests.py` for the static artifacts submitted to the provider
directories.

That keeps one document per provider for every environment - a dev deployment
advertises dev URLs without a second hand-maintained copy drifting out of sync.
"""

import importlib.resources
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PLACEHOLDER = "${PUBLIC_ORIGIN}"

from financial_portfolios_ai_mcp.environments import ENVIRONMENTS  # noqa: F401 - re-exported

# Public path prefix for the manifest routes; see icons.ASSET_PATH for why /mcp.
MANIFEST_PATH = "/mcp/manifests"

MANIFESTS = (
    "claude_connector.json",
    "chatgpt_manifest.json",
    "gemini-extension.json",
    "mcp_clients.json",
)

# Per-environment copies of the client snippets, committed so a user can copy the right one
# without running anything. `scripts/render_manifests.py --clients` writes them and a test
# fails if they drift from the template.
CLIENTS_DIR = "clients"


def clients_filename(env: str) -> str:
    return f"mcp_clients.{env}.json"


def _repo_root_candidates(filename: str) -> list[Path]:
    here = Path(__file__).resolve().parent
    return [
        here / "manifests" / filename,
        here.parent.parent / filename,
        Path(filename),
    ]


def template_path(filename: str) -> Path | None:
    """Locate a manifest template, packaged or in a source checkout."""
    try:
        traversable = importlib.resources.files("financial_portfolios_ai_mcp") / "manifests" / filename
        if traversable.is_file():
            return Path(str(traversable))
    except (FileNotFoundError, ModuleNotFoundError, TypeError, ValueError, OSError) as exc:
        logger.debug("Packaged manifest %s not resolvable: %s", filename, exc)

    for candidate in _repo_root_candidates(filename):
        if candidate.exists():
            return candidate
    return None


def render(filename: str, origin: str) -> dict[str, Any] | None:
    """Return the manifest with `${PUBLIC_ORIGIN}` replaced by `origin`.

    The `$comment` line explaining the templating is dropped from the rendered
    document - it is guidance for the repository, not for the provider.
    """
    if filename not in MANIFESTS:
        return None

    path = template_path(filename)
    if path is None:
        return None

    text = path.read_text(encoding="utf-8").replace(PLACEHOLDER, origin.rstrip("/"))
    document = json.loads(text)
    document.pop("$comment", None)
    return document
