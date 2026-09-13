"""The server's version, defined once.

`pyproject.toml` is the single source of truth. Everything that reports a version -
`serverInfo.version` in the MCP handshake, the HTTP root document, the FastAPI app,
the Portfolio Explorer's `appInfo` - reads it from here, and tests check that the
static manifests (`server.json`, `claude_connector.json`) and `CHANGELOG.md` agree.

Resolution order:

1. `pyproject.toml` beside the source tree, when running from a checkout. This comes
   first because an editable or previously installed copy can carry stale package
   metadata - a checkout bumped to 1.1.0 would otherwise keep reporting 1.0.0.
2. Installed package metadata, for a wheel or the Docker image, where no
   `pyproject.toml` ships next to the code.
"""

import re
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

DISTRIBUTION = "financial-portfolios-ai-mcp"

_PROJECT_VERSION = re.compile(r'^\[project\][^\[]*?^version\s*=\s*"([^"]+)"', re.MULTILINE | re.DOTALL)


def _from_pyproject() -> str | None:
    pyproject = Path(__file__).resolve().parent.parent.parent / "pyproject.toml"
    if not pyproject.is_file():
        return None
    match = _PROJECT_VERSION.search(pyproject.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def _resolve() -> str:
    source = _from_pyproject()
    if source:
        return source
    try:
        return version(DISTRIBUTION)
    except PackageNotFoundError:
        return "0.0.0+unknown"


__version__ = _resolve()
