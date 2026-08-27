# Financial Portfolios AI MCP — Fix List (Round 2)

Follow-up review after the Round-1 fixes in [`FIXES.md`](FIXES.md) were applied.

---

## 🔴 P0 — Deployment blockers (remote build/deploy is broken until these land)

- [x] **R2-1 — The remote-auth test does not cover the path where tools run (silent-401 risk)**
  - **Status:** Resolved & Tested (`test_e2e_mounted_mcp_app_auth_propagation`).
  - **Files:** [`src/financial_portfolios_ai_mcp/app.py`](src/financial_portfolios_ai_mcp/app.py), [`tests/test_server.py`](tests/test_server.py)
  - Switched `InboundAuthHeaderMiddleware` to **pure ASGI middleware** (`InboundAuthHeaderASGIMiddleware`), setting the `ContextVar` before delegating to mounted Starlette sub-apps (`/mcp`, `/sse`).
  - Added end-to-end test verifying multi-tenant header token propagation into tool execution in the mounted app.

- [x] **R2-2 — Dockerfile COPY paths are inconsistent with the Cloud Build context → image won't build**
  - **Status:** Resolved.
  - **Files:** [`Dockerfile`](Dockerfile), [`cloudbuild.yaml`](cloudbuild.yaml)
  - Aligned all `COPY` paths in `Dockerfile` to source from the workspace root context (`financial-portfolios-ai-sdk`, `financial-portfolios-ai-mcp/...`). Updated `cloudbuild.yaml` to specify `-f financial-portfolios-ai-mcp/Dockerfile .`.

- [x] **R2-3 — `openapi.yaml` is never shipped → advertised `/openapi.yaml` 404s in production**
  - **Status:** Resolved & Tested (`test_app_health_endpoints`).
  - **Files:** [`src/financial_portfolios_ai_mcp/app.py`](src/financial_portfolios_ai_mcp/app.py), [`pyproject.toml`](pyproject.toml), [`Dockerfile`](Dockerfile)
  - Packaged `openapi.yaml` in `[tool.hatch.build.targets.wheel.force-include]` and copied into `src/financial_portfolios_ai_mcp/`.
  - Updated `get_openapi_yaml` in `app.py` to resolve via `importlib.resources.files("financial_portfolios_ai_mcp") / "openapi.yaml"`.

---

## 🟠 P1 — Security / correctness

- [x] **R2-4 — Remove the query-param token fallback (`?api_key=` / `?token=`) — it logs secrets in URLs**
  - **Status:** Resolved & Tested (`test_query_param_token_is_rejected_for_security`).
  - **File:** [`src/financial_portfolios_ai_mcp/app.py`](src/financial_portfolios_ai_mcp/app.py)
  - Removed query string fallback completely. Tokens are only extracted from `X-API-Key` and `Authorization: Bearer` headers.

- [x] **R2-5 — CORS wildcard mixed with an explicit allowlist makes the allowlist dead**
  - **Status:** Resolved.
  - **File:** [`src/financial_portfolios_ai_mcp/app.py`](src/financial_portfolios_ai_mcp/app.py)
  - Cleaned CORS configuration to standard open headers-based API policy: `allow_origins=["*"]`, `allow_credentials=False`, explicit methods and headers.

---

## ⚪ P2 — Minor

- [x] **R2-6 — `get_token_info` output has no `disclaimer` (consistency)**
  - **Status:** Resolved & Tested.
  - **Files:** [`src/financial_portfolios_ai_mcp/tools.py`](src/financial_portfolios_ai_mcp/tools.py), [`src/financial_portfolios_ai_mcp/resources.py`](src/financial_portfolios_ai_mcp/resources.py)
  - Injected `"disclaimer": DISCLAIMER` across all tools and resources for consistency.

---

## Verification Evidence

```bash
uv run pytest tests/ -v
uv run ruff check .
```
```
======================= 24 passed, 2 warnings in 1.10s =======================
All checks passed!
```
