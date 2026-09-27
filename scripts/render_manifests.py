#!/usr/bin/env python3
"""Render the provider connector manifests for a deployment environment.

The manifests in the repo root are templates: every absolute URL is written as
`${PUBLIC_ORIGIN}/...` so a single document serves every environment. This script
produces the submittable artifacts:

    python scripts/render_manifests.py --env prod
    python scripts/render_manifests.py --env dev
    python scripts/render_manifests.py --origin https://staging.example.com
    python scripts/render_manifests.py --clients   # committed clients/mcp_clients.<env>.json

A running server renders the same documents on demand at `GET /manifests/<name>`,
using the origin the request arrived on - prefer that when you can reach the
deployment, and use this script for offline artifacts.
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from financial_portfolios_ai_mcp.manifests import (
    CLIENTS_DIR,
    ENVIRONMENTS,
    MANIFESTS,
    PLACEHOLDER,
    clients_filename,
    render,
)


def render_clients(env: str) -> str:
    """The committed client-snippet file for one environment, as text."""
    document = render("mcp_clients.json", ENVIRONMENTS[env])
    if document is None:
        raise SystemExit("mcp_clients.json template not found")
    document = {
        "$comment": f"Client configuration for the {env} deployment ({ENVIRONMENTS[env]}). "
        "Generated from mcp_clients.json by scripts/render_manifests.py --clients. Do not edit.",
        **document,
    }
    return json.dumps(document, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument(
        "--clients",
        action="store_true",
        help="Write the committed clients/mcp_clients.<env>.json for every environment.",
    )
    target.add_argument(
        "--env",
        choices=sorted(ENVIRONMENTS),
        help="Named environment to render for.",
    )
    target.add_argument(
        "--origin",
        help="Explicit public origin, e.g. https://staging.financial-portfolios.ai",
    )
    parser.add_argument(
        "--out",
        help="Directory to write to (default: build/manifests/<env or host>).",
    )
    args = parser.parse_args(argv)

    if args.clients:
        out = REPO_ROOT / CLIENTS_DIR
        out.mkdir(exist_ok=True)
        for env in sorted(ENVIRONMENTS):
            path = out / clients_filename(env)
            path.write_text(render_clients(env), encoding="utf-8")
            print(f"{env} -> {path.relative_to(REPO_ROOT)}")
        return 0

    origin = (args.origin or ENVIRONMENTS[args.env]).rstrip("/")
    if not origin.startswith(("http://", "https://")):
        parser.error("--origin must include the scheme, e.g. https://dev.financial-portfolios.ai")

    label = args.env or origin.split("://", 1)[1].replace("/", "_")
    out_dir = Path(args.out) if args.out else REPO_ROOT / "build" / "manifests" / label
    out_dir.mkdir(parents=True, exist_ok=True)

    for name in MANIFESTS:
        document = render(name, origin)
        if document is None:
            print(f"{name}: template not found", file=sys.stderr)
            return 1
        rendered = json.dumps(document, indent=2) + "\n"
        if PLACEHOLDER in rendered:
            print(f"{name}: placeholder survived rendering", file=sys.stderr)
            return 1
        (out_dir / name).write_text(rendered, encoding="utf-8")
        print(f"{name} -> {out_dir / name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
