"""Brand icon assets advertised to MCP clients.

LLM providers (Claude Connectors, ChatGPT Apps, Gemini extensions, IDE clients)
render a server's logo from the `icons` field of the `Implementation` object
returned by `initialize` (MCP spec) and from the `logo_url`/`icon_url` keys of
their own manifests. This module is the single source of truth for both.

Two source forms are advertised deliberately:

* a small **`data:` URI** — self-contained, so the icon renders for local stdio
  clients and for any client that will not fetch a remote image; and
* **absolute HTTPS URLs** served by this server at `/assets/...` — higher
  resolution, and what directory/marketplace listings prefer.
"""

import base64
import importlib.resources
import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

# Square PNG renditions shipped in `assets/`, plus the multi-size .ico for browsers.
PNG_SIZES = (16, 32, 48, 64, 128, 192, 256, 512)

# Size embedded directly in the initialize response as a data: URI. Small enough
# (~3 KB base64) to keep the handshake light, large enough for a sidebar avatar.
INLINE_SIZE = 48

# Sizes advertised as remote HTTPS URLs (directory listings and web UIs use these).
REMOTE_SIZES = (192, 512)

_MEDIA_TYPES = {".png": "image/png", ".ico": "image/x-icon"}


def asset_path(filename: str) -> Path | None:
    """Resolve a packaged asset, falling back to the repo layout for source checkouts."""
    try:
        traversable = importlib.resources.files("financial_portfolios_ai_mcp") / "assets" / filename
        if traversable.is_file():
            return Path(str(traversable))
    except (FileNotFoundError, ModuleNotFoundError, TypeError, ValueError, OSError) as exc:
        logger.debug("Packaged asset %s not resolvable: %s", filename, exc)

    candidate = Path(__file__).resolve().parent / "assets" / filename
    return candidate if candidate.exists() else None


def media_type(filename: str) -> str:
    """Return the media type for an asset filename."""
    return _MEDIA_TYPES.get(Path(filename).suffix.lower(), "application/octet-stream")


def read_asset(filename: str) -> bytes | None:
    """Read the raw bytes of a packaged asset, or None when it is missing."""
    path = asset_path(filename)
    return path.read_bytes() if path else None


@lru_cache
def data_uri(size: int = INLINE_SIZE) -> str | None:
    """Return the `icon-<size>.png` asset encoded as a `data:` URI."""
    raw = read_asset(f"icon-{size}.png")
    if raw is None:
        return None
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


# Public path prefix for the asset routes. `/mcp` is the prefix the portal's load
# balancer routes to this service; top-level `/assets` belongs to the portal backend
# (its own assets router), so an icon URL there would never reach us.
ASSET_PATH = "/mcp/assets"


def asset_url(base_url: str, filename: str) -> str:
    """Absolute public URL for an asset served from this server's asset route."""
    return f"{base_url.rstrip('/')}{ASSET_PATH}/{filename}"


def icon_specs(base_url: str | None = None) -> list[dict[str, object]]:
    """Icon descriptors for the MCP `Implementation.icons` field.

    The inline `data:` URI comes first so clients that take the first usable entry
    always have something to render without a network fetch.
    """
    icons: list[dict[str, object]] = []

    inline = data_uri(INLINE_SIZE)
    if inline:
        icons.append({
            "src": inline,
            "mimeType": "image/png",
            "sizes": [f"{INLINE_SIZE}x{INLINE_SIZE}"],
        })

    if base_url:
        for size in REMOTE_SIZES:
            if asset_path(f"icon-{size}.png"):
                icons.append({
                    "src": asset_url(base_url, f"icon-{size}.png"),
                    "mimeType": "image/png",
                    "sizes": [f"{size}x{size}"],
                })

    return icons
