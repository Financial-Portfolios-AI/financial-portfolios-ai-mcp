#!/usr/bin/env python3
"""Render the connector manifests for a given deployment environment.

The committed manifests carry the production origin because that is what the
Claude / ChatGPT / Gemini directories are submitted with. Every other environment
is the same document with a different origin, so render it rather than keeping a
second hand-edited copy in sync:

    python scripts/render_manifests.py --origin https://dev.financial-portfolios.ai --out build/dev

The MCP server itself never reads these files; it derives its own public URLs from
MCP_PUBLIC_BASE_URL / MCP_PUBLIC_URL, and falls back to the origin the request
arrived on. This script only exists for the static manifests submitted to the
provider directories.
"""

import argparse
import json
import sys
from pathlib import Path

MANIFESTS = ("claude_connector.json", "chatgpt_manifest.json", "gemini_extension.json")

# Origins appearing in the committed manifests that belong to the portal and should
# therefore follow the target environment.
SOURCE_ORIGINS = ("https://financial-portfolios.ai",)


def retarget(value: object, origin: str) -> object:
    """Recursively rewrite portal origins inside strings of a JSON document."""
    if isinstance(value, str):
        for source in SOURCE_ORIGINS:
            value = value.replace(source, origin)
        return value
    if isinstance(value, list):
        return [retarget(item, origin) for item in value]
    if isinstance(value, dict):
        return {key: retarget(item, origin) for key, item in value.items()}
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--origin",
        required=True,
        help="Target public origin, e.g. https://dev.financial-portfolios.ai",
    )
    parser.add_argument(
        "--out",
        default="build/manifests",
        help="Directory to write the rendered manifests to (default: build/manifests)",
    )
    args = parser.parse_args(argv)

    origin = args.origin.rstrip("/")
    if not origin.startswith(("http://", "https://")):
        parser.error("--origin must include the scheme, e.g. https://dev.financial-portfolios.ai")

    repo_root = Path(__file__).resolve().parent.parent
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    for name in MANIFESTS:
        source = repo_root / name
        document = json.loads(source.read_text(encoding="utf-8"))
        target = out_dir / name
        target.write_text(json.dumps(retarget(document, origin), indent=2) + "\n", encoding="utf-8")
        print(f"{name} -> {target}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
