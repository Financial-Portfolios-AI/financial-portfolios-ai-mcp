# ADR 001: Multi-Tenant Inbound Authentication & Publisher-Exclusion Posture

- **Status:** Accepted & Implemented
- **Date:** 2026-08-23
- **Deciders:** Financial Portfolios AI Engineering Team
- **Context:** Fixes P0 (Inbound auth header extraction, tool token leak removal, CORS, mounted sub-app ContextVar propagation, container build consistency) and P1 (Regulatory posture disclaimers and holdings disclosure) clusters.

---

## 1. WHY

1. **Multi-Tenant Security & Isolation (P0-1 / R2-1):** In remote hosting (Google Cloud Run), multiple concurrent users connect via Claude Connectors or ChatGPT with their own individual API keys (`X-API-Key: aqat_v1_...`). The server must extract and isolate credentials per request across mounted ASGI sub-apps without leaking across requests or defaulting to an insecure shared token.
2. **Secret Leakage Prevention (P0-2):** Exposing `api_token: str | None` in tool schemas allowed tokens to be passed into LLM prompt contexts, persisting sensitive user credentials in chat transcripts and provider logs.
3. **URL Query Credential Leak Prevention (R2-4):** Tokens passed via query strings (`?api_key=...`) land in access logs, proxy logs, and referer headers. Auth tokens must strictly be accepted via request headers (`X-API-Key` or `Authorization: Bearer`).
4. **CORS Spec Compliance (P0-3 / R2-5):** Combining `allow_origins=["*"]` with `allow_credentials=True` violates browser CORS specifications. An intentional, open header-based policy (`allow_origins=["*"]`, `allow_credentials=False`) ensures cross-origin compatibility without credential confusion.
5. **Container & Asset Packaging (R2-2 / R2-3):** Build paths in `Dockerfile` must align with the workspace context root to build the container cleanly, and `openapi.yaml` must be packaged via Python package resources to guarantee resolution in deployed environments.
6. **Publisher-Exclusion Posture (P1-1 & P1-2):** Financial Portfolios AI operates under the publisher exclusion. Quantitative rebalancing models output mathematical share quantity differences rather than individualized investment advice or order executions. Disclaimers and limits must be explicitly reinforced across all model touchpoints.

---

## 2. WHAT

1. **Pure ASGI Inbound Auth Middleware:** Implemented `InboundAuthHeaderASGIMiddleware` which intercepts `X-API-Key` and `Authorization: Bearer` headers at the root ASGI scope and binds them to an asynchronous `contextvars.ContextVar[Optional[str]]` before dispatching to mounted Starlette apps (`/mcp`, `/sse`) and REST routes.
2. **Strict Header-Only Token Intake:** Query string parameters (`?api_key=`, `?token=`) are rejected and ignored.
3. **Tool Parameter Cleanup:** Removed `api_token` from all 8 tool function signatures.
4. **Package Resource OpenAPI Loading:** Serves `/openapi.yaml` dynamically via `importlib.resources` from the installed package data.
5. **Publisher Exclusion Disclaimers:** Added explicit disclaimers in `SERVER_INSTRUCTIONS`, all tool JSON responses (`disclaimer`), all resource payloads, and all 3 prompt templates. Rebalancing reframed as "target-model alignment arithmetic" with explicit limits (max 200 rows, 512 KB).

---

## 3. HOW

- **`src/financial_portfolios_ai_mcp/app.py`:**
  ```python
  class InboundAuthHeaderASGIMiddleware:
      def __init__(self, app):
          self.app = app

      async def __call__(self, scope, receive, send):
          if scope["type"] == "http":
              token = None
              for h_name, h_val in scope.get("headers", []):
                  name_str = h_name.decode("latin1").lower()
                  if name_str == "x-api-key":
                      token = h_val.decode("latin1").strip()
                      break
                  elif name_str == "authorization":
                      val_str = h_val.decode("latin1").strip()
                      if val_str.lower().startswith("bearer "):
                          token = val_str[7:].strip()
                          break

              token_ctx = set_request_token(token)
              try:
                  await self.app(scope, receive, send)
              finally:
                  reset_request_token(token_ctx)
              return

          await self.app(scope, receive, send)
  ```
- **`src/financial_portfolios_ai_mcp/auth.py`:**
  - ContextVar holds active token throughout downstream tool calls.
- **`src/financial_portfolios_ai_mcp/tools.py` & `resources.py`:**
  - Removed `api_token` parameter from all 8 tools.
  - Attached `"disclaimer": DISCLAIMER` to all output payloads.

---

## 4. VERIFICATION & TESTS

All 24 automated tests in `tests/` pass with 100% success:
- `test_e2e_mounted_mcp_app_auth_propagation`: Live end-to-end verification proving that `X-API-Key` headers propagate through the ASGI middleware and mounted Starlette sub-applications to isolate multi-tenant credentials across concurrent executions.
- `test_query_param_token_is_rejected_for_security`: Asserts query string tokens are not extracted.
- `test_app_health_endpoints` & `/openapi.yaml`: Asserts OpenAPI specification is served with HTTP 200 and valid schema.
- `test_tool_registration`, `test_resource_registration`, `test_prompt_registration`: Verify all capabilities and disclaimers.
