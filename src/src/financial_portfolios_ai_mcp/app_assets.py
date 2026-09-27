"""Loading the packaged HTML for MCP Apps.

Each app is a single self-contained page under `assets/` - inline script and styles, no
network - because the host's default Content-Security-Policy for an app allows nothing
else. Pages are read from package data when installed and from the source tree otherwise,
so an editable checkout serves the file being edited.
"""

import importlib.resources
import logging
from pathlib import Path

from financial_portfolios_ai_mcp._version import __version__

logger = logging.getLogger(__name__)

# Placeholder in a page, replaced with the server version when the page is loaded.
VERSION_PLACEHOLDER = "__APP_VERSION__"


def read_app_html(filename: str) -> str:
    try:
        traversable = importlib.resources.files("financial_portfolios_ai_mcp") / "assets" / filename
        if traversable.is_file():
            return traversable.read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError, TypeError, ValueError, OSError) as exc:
        logger.debug("Packaged app HTML %s not resolvable: %s", filename, exc)
    return (Path(__file__).resolve().parent / "assets" / filename).read_text(encoding="utf-8")


def load_app_html(filename: str) -> str:
    """The page with its version placeholder filled in."""
    return read_app_html(filename).replace(VERSION_PLACEHOLDER, __version__)
