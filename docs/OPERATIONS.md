# Operations

## Logs

The server writes **one JSON object per line** to stdout, with the `severity` field Cloud
Logging understands, configured in `create_app()` (see
`financial_portfolios_ai_mcp/logging_setup.py`). Structured fields ride on the record, so
they are filterable: before this, a long record reached Cloud Logging through the MCP
SDK's console formatter, wrapped at console width and split across a dozen entries.

Useful filters (project `financial-portfolios-dev`, service `financial-portfolios-ai-mcp`):

```
# Errors
resource.labels.service_name="financial-portfolios-ai-mcp" AND severity>=ERROR

# Which MCP Apps features a host supports, reported when the Explorer opens
jsonPayload.message="explorer_host_report"

# Portal reads that had to be retried
jsonPayload.message="portal_retry"
```

`explorer_host_report` records carry `host`, `capabilities`, `context` and
`style_variables`; `portal_retry` carries `operation`, `attempt`, `of` and `wait_s`.

## Monitoring (dev)

Created in `financial-portfolios-dev`, notifying the existing **AQA ops email** channel.
The alert policies are checked into [`ops/monitoring`](../ops/monitoring) so they can be
recreated or moved to another project.

| What | Resource | Fires when |
| :--- | :--- | :--- |
| Uptime check | `mcp-dev-protected-resource-metadata-E0Mi60K_e7U`, `GET https://dev.financial-portfolios.ai/.well-known/oauth-protected-resource` every 5 min | — |
| `MCP dev - endpoint down` | that uptime check | the check fails |
| `MCP dev - error logs` | log metric `mcp_error_logs` | any `severity>=ERROR` in 5 min |
| `MCP dev - 5xx responses` | `run.googleapis.com/request_count`, `response_code_class="5xx"` | any 5xx in 5 min |

The uptime check deliberately targets the protected-resource metadata rather than `/mcp`:
that path is public and returns `200`, while a tokenless `/mcp` correctly returns `401`.

Recreate them with:

Run these from PowerShell, not Git Bash: Git Bash rewrites a `/`-prefixed `--path`
into a Windows path, which silently pointed the first attempt at
`/C:/Program Files/Git/.well-known/...`.

```bash
gcloud monitoring uptime create "MCP dev - protected resource metadata" \
  --project financial-portfolios-dev --resource-type=uptime-url \
  --resource-labels=host=dev.financial-portfolios.ai,project_id=financial-portfolios-dev \
  --path="/.well-known/oauth-protected-resource" --protocol=https --port=443 \
  --period=5 --timeout=10 --request-method=get --status-classes=2xx

gcloud logging metrics create mcp_error_logs --project financial-portfolios-dev \
  --description="ERROR-or-worse log records from the MCP service" \
  --log-filter='resource.type="cloud_run_revision" AND resource.labels.service_name="financial-portfolios-ai-mcp" AND severity>=ERROR'

for f in ops/monitoring/*.json; do
  gcloud alpha monitoring policies create --project financial-portfolios-dev --policy-from-file="$f"
done
```

The policy files reference a notification channel and an uptime check by id; update those
ids when recreating them in another project.

## Portal reads: retries and caching

`financial_portfolios_ai_mcp/portal.py` wraps every portal read.

- **Retries**: `500`, `502`, `503`, `504` and connection or timeout errors, twice by
  default, with exponential backoff and jitter. A `4xx` is never retried - a `401`, `403`,
  `404`, `422` or `429` is an answer.
- **Caching**: short-lived, per credential, in process. The cache key hashes the caller's
  credential, because the portal answers differently per subscriber, and concurrent reads
  of the same key share one fetch (the Explorer's stock search reads every portfolio at
  once).

| Read | Default TTL | Environment variable |
| :--- | :--- | :--- |
| Portfolio list | 30 s | `MCP_CACHE_TTL_PORTFOLIOS` |
| Allocation snapshot | 60 s | `MCP_CACHE_TTL_ALLOCATION` |
| Allocation history | 120 s | `MCP_CACHE_TTL_HISTORY` |
| Research listings and articles | 120 s | `MCP_CACHE_TTL_RESEARCH` |
| Retries / first delay | 2 / 0.25 s | `MCP_PORTAL_RETRIES`, `MCP_PORTAL_RETRY_BASE_DELAY` |

Set a TTL to `0` to disable that cache. Nothing user-specific is cached beyond these
windows, and `rebalance_portfolio` (which receives the user's own holdings) and
`get_token_info` are never cached.

## Deploying

See [RELEASING.md](RELEASING.md). Use `gcloud run services update --image`, which keeps
the service's environment variables.
