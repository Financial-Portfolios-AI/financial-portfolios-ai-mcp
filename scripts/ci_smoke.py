#!/usr/bin/env python3
"""Smoke-test a running MCP server over HTTP, with no dependencies beyond the stdlib.

Checks what every client does first, and what past releases actually broke:

* the `initialize` handshake answers (a Host allow-list once made this a 421),
* `POST /mcp` without a trailing slash works (a 307 here silently broke connectors),
* the version it reports matches the package being tested,
* `tools/list` includes the Portfolio Explorer with its `_meta.ui.resourceUri`,
* that UI resource is served as `text/html;profile=mcp-app` (an empty page shipped once),
* a tokenless request is challenged with `401` + `WWW-Authenticate` (RFC 9728),
* icons are served and the Explorer's HTML is not fetchable over plain HTTP.

The portal is unreachable in CI, so no tool is actually called: this exercises the
protocol surface, not portal data.

Usage: ci_smoke.py [base-url]   (default http://localhost:8080)
"""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080").rstrip("/")
HEADERS = {
    "X-API-Key": "aqat_v1_ci_smoke",
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
    "MCP-Protocol-Version": "2025-11-25",
}
EXPLORER_MIME = "text/html;profile=mcp-app"

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {name}{'' if ok else f'  ({detail})'}")
    if not ok:
        failures.append(name)


def rpc(method: str, params: dict, request_id: int) -> dict:
    body = json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}).encode()
    request = urllib.request.Request(f"{BASE}/mcp", data=body, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read().decode()
    match = re.search(r"^data: (.*)$", raw, re.MULTILINE)  # streamable HTTP may answer as SSE
    payload = json.loads(match.group(1) if match else raw)
    if "error" in payload:
        raise RuntimeError(f"{method} returned {payload['error']}")
    return payload["result"]


def expected_version() -> str | None:
    """The version in this checkout's pyproject.toml - the source of truth for the image
    built from it. Not the version installed wherever this script happens to run: that
    machine's metadata can be stale, which first made this check compare against 1.0.0.
    """
    import pathlib

    pyproject = pathlib.Path(__file__).resolve().parent.parent / "pyproject.toml"
    if not pyproject.is_file():
        return None
    match = re.search(r'^\[project\][^\[]*?^version\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8"), re.MULTILINE | re.DOTALL)
    return match.group(1) if match else None


def main() -> int:
    try:
        init = rpc("initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "ci-smoke", "version": "1"}}, 1)
    except (urllib.error.URLError, RuntimeError, OSError) as error:
        check("initialize handshake", False, str(error))
        return 1

    info = init.get("serverInfo", {})
    check("initialize handshake", bool(info.get("name")), json.dumps(init)[:200])
    check("POST /mcp without a trailing slash", True)  # any answer above proves it

    wanted = expected_version()
    if wanted:
        check(f"serverInfo.version == {wanted}", info.get("version") == wanted, f"got {info.get('version')}")

    icons = info.get("icons") or []
    check("serverInfo carries icons", bool(icons), json.dumps(icons)[:120])

    tools = {tool["name"]: tool for tool in rpc("tools/list", {}, 2)["tools"]}
    check("tools/list is not empty", bool(tools))
    for name in ("list_portfolios", "get_portfolio_allocation", "open_portfolio_explorer"):
        check(f"tool {name} is listed", name in tools)

    explorer = tools.get("open_portfolio_explorer", {})
    resource_uri = (explorer.get("_meta", {}).get("ui", {}) or {}).get("resourceUri")
    check("Explorer tool links its UI resource", bool(resource_uri), json.dumps(explorer.get("_meta"))[:120])

    for name, tool in tools.items():
        annotations = tool.get("annotations") or {}
        check(f"tool {name} has a title and readOnlyHint", bool(tool.get("title")) and "readOnlyHint" in annotations)

    if resource_uri:
        contents = rpc("resources/read", {"uri": resource_uri}, 3)["contents"][0]
        check("UI resource served as an MCP App", contents.get("mimeType") == EXPLORER_MIME, str(contents.get("mimeType")))
        html = contents.get("text") or ""
        check("UI resource is a real page", "ui/initialize" in html and len(html) > 2000, f"{len(html)} chars")

    prompts = rpc("prompts/list", {}, 4)["prompts"]
    check("prompts/list is not empty", bool(prompts))
    check("prompts have titles", all(prompt.get("title") for prompt in prompts))

    # A tokenless request must be challenged, which is what starts OAuth sign-in.
    request = urllib.request.Request(
        f"{BASE}/mcp",
        data=b"{}",
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            check("tokenless /mcp is challenged", False, f"got {response.status}")
    except urllib.error.HTTPError as error:
        check("tokenless /mcp is challenged with 401", error.code == 401, f"got {error.code}")
        check(
            "challenge carries WWW-Authenticate resource_metadata",
            "resource_metadata" in (error.headers.get("WWW-Authenticate") or ""),
            error.headers.get("WWW-Authenticate") or "missing",
        )

    def status(path: str) -> int:
        try:
            with urllib.request.urlopen(f"{BASE}{path}", timeout=30) as response:
                return response.status
        except urllib.error.HTTPError as error:
            return error.code

    check("icon is served", status("/mcp/assets/icon-512.png") == 200)
    check("well-known metadata is served", status("/.well-known/oauth-protected-resource") == 200)
    check("Explorer HTML is not downloadable over HTTP", status("/mcp/assets/portfolio_explorer.html") == 404)

    print()
    if failures:
        print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
