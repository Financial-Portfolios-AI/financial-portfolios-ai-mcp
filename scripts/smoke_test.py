#!/usr/bin/env python3
"""
Local smoke test for the Financial Portfolios AI MCP server.

Drives the Streamable-HTTP transport end to end with the Python standard library
only (no deps): /healthz -> initialize -> notifications/initialized -> tools/list,
then — if an API token is supplied — real tools/call round-trips
(list_portfolios -> get_portfolio_allocation).

It also regression-checks the "holdings"/"positions" phrasing fix (ADR-0214):
tools/list must advertise those words on get_portfolio_allocation, otherwise an
LLM won't invoke it for "show me my portfolio holdings".

Usage:
    python scripts/smoke_test.py
    python scripts/smoke_test.py --url http://localhost:8090/mcp/
    python scripts/smoke_test.py --token aqat_v1_xxxxx        # exercises data tools
    MCP_URL=... MCP_TOKEN=aqat_v1_... python scripts/smoke_test.py

Exit code is 0 only if every executed check passes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

# Force UTF-8 output so ✓/✗/… render on Windows consoles (cp1252) too.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):  # pragma: no cover - older/odd streams
    pass

# ---- tiny ANSI helpers (degrade to plain text when not a TTY) ----------------
_TTY = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _TTY else text


def ok(msg: str) -> None:
    print(f"  {_c('32', 'PASS')}  {msg}")


def fail(msg: str) -> None:
    print(f"  {_c('31', 'FAIL')}  {msg}")


def info(msg: str) -> None:
    print(_c("36", msg))


class SmokeError(Exception):
    """A check failed hard enough to stop the run."""


# ---- transport ---------------------------------------------------------------
def _parse_sse(body: str) -> dict[str, Any]:
    """Extract the first JSON object from an SSE 'data:' line (or plain JSON)."""
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            return json.loads(line[len("data:") :].strip())
    # Some servers reply with plain application/json for notifications/acks.
    body = body.strip()
    return json.loads(body) if body else {}


class MCPClient:
    def __init__(self, url: str, token: str | None):
        if not url.endswith("/"):
            url += "/"  # trailing slash avoids a 307 some clients mishandle
        self.url = url
        self.token = token
        self.session_id: str | None = None

    def _post(self, payload: dict[str, Any], expect_response: bool = True) -> dict[str, Any]:
        data = json.dumps(payload).encode()
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            headers["mcp-session-id"] = self.session_id
        if self.token:
            headers["X-API-Key"] = self.token
        req = urllib.request.Request(self.url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                sid = resp.headers.get("mcp-session-id")
                if sid:
                    self.session_id = sid
                raw = resp.read().decode()
        except urllib.error.HTTPError as e:
            raise SmokeError(f"HTTP {e.code} on {payload.get('method')}: {e.read().decode()[:300]}")
        except (urllib.error.URLError, OSError) as e:
            reason = getattr(e, "reason", e)
            raise SmokeError(f"cannot reach {self.url}: {reason}")
        if not expect_response:
            return {}
        return _parse_sse(raw)

    def initialize(self, retries: int = 5) -> dict[str, Any]:
        # A freshly (re)started server can 404 the initialized notification with
        # "Session not found" if it hasn't registered the session yet — retry the
        # whole handshake a few times before giving up.
        last: Exception | None = None
        for attempt in range(retries):
            self.session_id = None
            try:
                resp = self._post(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2025-06-18",
                            "capabilities": {},
                            "clientInfo": {"name": "fpai-smoke-test", "version": "1.0"},
                        },
                    }
                )
                if "error" in resp:
                    raise SmokeError(f"initialize error: {resp['error']}")
                self._post(
                    {"jsonrpc": "2.0", "method": "notifications/initialized"},
                    expect_response=False,
                )
                return resp["result"]
            except SmokeError as e:
                last = e
                # Retry cold-start races: session not yet registered, or the
                # server still coming up (connection refused / reset).
                transient = "Session not found" in str(e) or "cannot reach" in str(e)
                if transient and attempt < retries - 1:
                    time.sleep(1.5)
                    continue
                raise
        raise last or SmokeError("initialize failed")

    def _post_with_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST, transparently re-initializing once if the session was dropped
        (can happen while a just-started server is still warming up)."""
        try:
            return self._post(payload)
        except SmokeError as e:
            if "Session not found" in str(e):
                self.initialize()
                return self._post(payload)
            raise

    def tools_list(self) -> list[dict[str, Any]]:
        resp = self._post_with_session({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        if "error" in resp:
            raise SmokeError(f"tools/list error: {resp['error']}")
        return resp["result"]["tools"]

    def tools_call(self, name: str, arguments: dict[str, Any]) -> Any:
        resp = self._post_with_session(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        if "error" in resp:
            raise SmokeError(f"tools/call {name} error: {resp['error']}")
        content = resp["result"].get("content", [])
        text = "".join(c.get("text", "") for c in content if c.get("type") == "text")
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return text


# ---- checks ------------------------------------------------------------------
HOLDINGS_WORDS = ("holdings", "positions")


def run(url: str, token: str | None) -> int:
    failures = 0

    # 1. health --------------------------------------------------------------
    info("\n[1] Health")
    health_url = url.rsplit("/mcp", 1)[0].rstrip("/") + "/healthz"
    body: Any = None
    last_err: Exception | None = None
    for attempt in range(5):  # tolerate a server still coming up
        try:
            with urllib.request.urlopen(health_url, timeout=10) as resp:
                body = json.loads(resp.read().decode())
            break
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1.5)
    if isinstance(body, dict) and body.get("status") == "ok":
        ok(f"{health_url} -> {body}")
    elif body is not None:
        fail(f"unexpected health body: {body}")
        failures += 1
    else:
        fail(f"health check failed: {last_err}")
        failures += 1

    client = MCPClient(url, token)

    # 2. handshake -----------------------------------------------------------
    info("\n[2] MCP handshake (Streamable-HTTP)")
    try:
        result = client.initialize()
        server = result.get("serverInfo", {})
        sess = f"session {client.session_id[:8]}…" if client.session_id else "stateless (no session id)"
        ok(f"initialize -> {server.get('name')} v{server.get('version')} "
           f"(protocol {result.get('protocolVersion')}, {sess})")
    except SmokeError as e:
        fail(str(e))
        print(_c("31", "\nHandshake failed — cannot continue. Is the server up on this URL?"))
        return failures + 1

    # 3. tools/list + phrasing regression -----------------------------------
    info("\n[3] tools/list + holdings-phrasing regression (ADR-0214)")
    try:
        tools = client.tools_list()
    except SmokeError as e:
        fail(str(e))
        return failures + 1

    by_name = {t["name"]: t for t in tools}
    expected = {
        "list_portfolios",
        "get_portfolio_allocation",
        "get_portfolio_history",
        "rebalance_portfolio",
        "get_rebalance_template",
        "list_blog_posts",
        "get_blog_post",
        "get_token_info",
    }
    missing = expected - by_name.keys()
    if missing:
        fail(f"tools/list missing expected tools: {sorted(missing)}")
        failures += 1
    else:
        ok(f"all {len(expected)} tools advertised: {', '.join(sorted(by_name))}")

    alloc = by_name.get("get_portfolio_allocation", {})
    desc = (alloc.get("description") or "").lower()
    hit = [w for w in HOLDINGS_WORDS if w in desc]
    if hit:
        ok(f"get_portfolio_allocation description advertises {hit} "
           "→ 'show me my portfolio holdings' will map here")
    else:
        fail("get_portfolio_allocation description mentions neither 'holdings' nor "
             "'positions' — the fix is not deployed; 'show me my holdings' won't invoke it")
        failures += 1

    # 4. data tools (token required) ----------------------------------------
    info("\n[4] Data tools (entitlement)")
    if not token:
        print(_c("33", "  SKIP  no token supplied. Pass --token aqat_v1_… "
                       "(generate one at the portal /api-access) to exercise real data."))
        return failures

    try:
        portfolios = client.tools_call("list_portfolios", {})
        if isinstance(portfolios, dict) and portfolios.get("error"):
            fail(f"list_portfolios returned an error object: {portfolios.get('error')} "
                 f"— {portfolios.get('message', '')}")
            failures += 1
            return failures
        items = _extract_portfolio_codes(portfolios)
        if items:
            ok(f"list_portfolios -> {len(items)} entitled: {', '.join(items)}")
        else:
            fail(f"list_portfolios returned no portfolio codes: {str(portfolios)[:200]}")
            failures += 1
            return failures
    except SmokeError as e:
        fail(str(e))
        return failures + 1

    try:
        code = items[0]
        alloc_data = client.tools_call("get_portfolio_allocation", {"portfolio_code": code})
        if isinstance(alloc_data, dict) and alloc_data.get("error"):
            fail(f"get_portfolio_allocation({code}) error: {alloc_data.get('message')}")
            failures += 1
        else:
            n = _count_holdings(alloc_data)
            ok(f"get_portfolio_allocation({code}) -> snapshot with {n} holdings")
    except SmokeError as e:
        fail(str(e))
        failures += 1

    return failures


def _extract_portfolio_codes(payload: Any) -> list[str]:
    """Best-effort pull of portfolio codes from the list_portfolios response."""
    if isinstance(payload, dict):
        for key in ("portfolios", "items", "data", "results"):
            if isinstance(payload.get(key), list):
                return [
                    p.get("code") or p.get("portfolio_code") or p.get("slug")
                    for p in payload[key]
                    if isinstance(p, dict) and (p.get("code") or p.get("portfolio_code") or p.get("slug"))
                ]
    if isinstance(payload, list):
        return [p.get("code") for p in payload if isinstance(p, dict) and p.get("code")]
    return []


def _count_holdings(payload: Any) -> int:
    if isinstance(payload, dict):
        for key in ("holdings", "allocations", "positions", "weights", "assets"):
            v = payload.get(key)
            if isinstance(v, list):
                return len(v)
            if isinstance(v, dict):
                return len(v)
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="Smoke-test the Financial Portfolios AI MCP server.")
    ap.add_argument("--url", default=os.environ.get("MCP_URL", "http://localhost:8090/mcp/"),
                    help="MCP Streamable-HTTP endpoint (default: %(default)s)")
    ap.add_argument("--token", default=os.environ.get("MCP_TOKEN"),
                    help="aqat_v1_ API token to exercise entitled data tools (optional)")
    args = ap.parse_args()

    info(f"Financial Portfolios AI — MCP smoke test\nTarget: {args.url}"
         f"{'  (with token)' if args.token else '  (no token — data tools skipped)'}")

    try:
        failures = run(args.url, args.token)
    except SmokeError as e:
        print(_c("31", f"\nAborted: {e}"))
        sys.exit(1)

    print()
    if failures:
        print(_c("31", f"✗ {failures} check(s) failed."))
        sys.exit(1)
    print(_c("32", "✓ All checks passed."))
    sys.exit(0)


if __name__ == "__main__":
    main()
