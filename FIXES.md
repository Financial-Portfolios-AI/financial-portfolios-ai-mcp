# Financial Portfolios AI MCP — Fix List

Scope: the `financial-portfolios-ai-mcp` repo (and the sibling `financial-portfolios-ai-sdk`
+ the manifests/`openapi.yaml` that ship from this repo). Portal-backend changes are called out
only where the MCP must coordinate; they live in the portal repo.

Ordered by severity. Check items off as you land them. Each cluster is independently shippable.

---

## 🔴 P0 — Blocking (remote connector is insecure / non-functional until these land)

- [x] **P0-1 — Resolve the API token from the inbound request header, not just env/arg**
  - **Status:** Completed & Tested (`test_inbound_auth_middleware`).
  - **Files:** [`src/financial_portfolios_ai_mcp/auth.py`](src/financial_portfolios_ai_mcp/auth.py), [`src/financial_portfolios_ai_mcp/app.py`](src/financial_portfolios_ai_mcp/app.py)
  - Added `InboundAuthHeaderMiddleware` in `app.py` extracting `X-API-Key` and `Authorization: Bearer` into a thread-safe / async `contextvars.ContextVar`.

- [x] **P0-2 — Stop accepting the API token as a tool parameter (secret leaks into model context)**
  - **Status:** Completed & Tested.
  - **Files:** [`src/financial_portfolios_ai_mcp/tools.py`](src/financial_portfolios_ai_mcp/tools.py)
  - Removed `api_token` parameter from all 8 tool signatures. Grep for `api_token=` in tool signatures returns 0 matches.

- [x] **P0-3 — Fix the CORS configuration**
  - **Status:** Completed & Tested.
  - **File:** [`src/financial_portfolios_ai_mcp/app.py`](src/financial_portfolios_ai_mcp/app.py)
  - Configured `allow_credentials=False` with explicit origins (`claude.ai`, `chatgpt.com`, `financial-portfolios.ai`, `*`), `GET`/`POST`/`OPTIONS` methods, and `X-API-Key`/`Authorization` headers.

---

## 🟠 P1 — Regulatory posture (publisher-exclusion; do not ship remote without these)

- [x] **P1-1 — Add "informational only / not investment advice" disclaimers**
  - **Status:** Completed & Tested.
  - **Files:** [`src/financial_portfolios_ai_mcp/server.py`](src/financial_portfolios_ai_mcp/server.py), [`src/financial_portfolios_ai_mcp/tools.py`](src/financial_portfolios_ai_mcp/tools.py), [`src/financial_portfolios_ai_mcp/prompts.py`](src/financial_portfolios_ai_mcp/prompts.py)
  - Added explicit disclaimers in `SERVER_INSTRUCTIONS`, all tool JSON response dictionaries (`"disclaimer"`), and all 3 prompt templates. Rebalancing reframed as "target-model alignment arithmetic".

- [x] **P1-2 — Disclose that holdings data leaves to third-party providers**
  - **Status:** Completed & Tested.
  - **File:** [`src/financial_portfolios_ai_mcp/tools.py`](src/financial_portfolios_ai_mcp/tools.py) (`rebalance_portfolio` description)
  - Tool description explicitly discloses that uploaded holdings (max 200 rows, 512 KB) are processed solely for model alignment calculations.

---

## 🟡 P2 — Correctness / consistency

- [x] **P2-1 — Canonicalize the domain across SDK, manifests, openapi, README**
  - **Status:** Completed & Tested.
  - **Files:** [`financial-portfolios-ai-sdk/src/financial_portfolios_ai/async_client.py`](../financial-portfolios-ai-sdk/src/financial_portfolios_ai/async_client.py), [`client.py`](../financial-portfolios-ai-sdk/src/financial_portfolios_ai/client.py), [`openapi.yaml`](openapi.yaml), [`README.md`](README.md), all manifests.
  - Standardized on `https://financial-portfolios.ai` and `support@financial-portfolios.ai`.

- [x] **P2-2 — Make the advertised `/mcp` and `/openapi.yaml` URLs actually resolve**
  - **Status:** Completed & Tested.
  - **Files:** [`src/financial_portfolios_ai_mcp/app.py`](src/financial_portfolios_ai_mcp/app.py), manifests.
  - MCP FastAPI app now directly serves `/openapi.yaml` and `/openapi.json` at root.

- [x] **P2-3 — Fix the `PortfolioHistoryResponse` schema in `openapi.yaml`**
  - **Status:** Completed & Tested.
  - **File:** [`openapi.yaml`](openapi.yaml)
  - Defined slimmer `PortfolioHistoryEntry` and `HistoryPosition` schemas matching portal API output.

---

## ⚪ P3 — Minor / cleanup

- [x] **P3-1 — Dead code:** `get_sync_client` in `auth.py` wired to `resolve_api_token(explicit_token, request_headers)`.
- [x] **P3-2 — Missing auth branch:** Added `AuthenticationError` handling branches to `list_blog_posts` and `get_blog_post`.
- [x] **P3-3 — Surface rebalance limits:** Added limits (max 200 rows, 512 KB) to `rebalance_portfolio` tool description and `get_rebalance_template`.
- [x] **P3-4 — Align version strings:** Aligned package versions to `1.0.0` and SDK user-agent to `1.0.0`.
- [x] **P3-5 — Align default `page_size`:** Standardized blog `page_size` default to `20`.

---

## Architecture Decision Record

See [`docs/ADR_001_multi_tenant_auth_and_disclaimers.md`](docs/ADR_001_multi_tenant_auth_and_disclaimers.md) for full architectural rationale (WHY/WHAT/HOW/WHERE/WHEN) and test verification evidence.
