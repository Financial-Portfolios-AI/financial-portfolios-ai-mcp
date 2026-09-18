# Continuous integration

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs on pushes to `main`, on
`v*` tags, on pull requests, and on demand.

| Job | What it does |
| :--- | :--- |
| **Lint and test** | `ruff check`, then the full `pytest` suite (143 tests) on Python 3.12, the version the image uses |
| **Build image and smoke-test it** | builds the Docker image, runs the container, and drives a real MCP client against it with [`scripts/ci_smoke.py`](../scripts/ci_smoke.py) |

## One-time setup: `SDK_READ_TOKEN`

**CI cannot pass until this secret exists.** The server depends on the SDK through a local
sibling path (`[tool.uv.sources]`), so both repositories are checked out side by side, the
layout the Dockerfile also builds from. GitHub's automatic `GITHUB_TOKEN` is scoped to this
repository alone and cannot read the SDK.

1. Create a **fine-grained personal access token** with `Contents: read` on
   `Financial-Portfolios-AI/financial-portfolios-ai-sdk`.
2. Add it as a secret named `SDK_READ_TOKEN`, on this repository or the organisation.

Without it the "Check out the SDK" step fails, which is the first thing to check on a red
first run.

## What the smoke test covers

It exercises the protocol surface against a running container, no portal required, and
each check corresponds to something a release actually broke:

- the `initialize` handshake answers (a Host allow-list once turned this into `421`),
- `POST /mcp` without a trailing slash works (a `307` here broke connectors silently),
- the reported version matches this checkout's `pyproject.toml`,
- every tool has a `title` and a `readOnlyHint`, as the Claude directory requires,
- the Portfolio Explorer is listed with its `_meta.ui.resourceUri`, and that resource is
  served as `text/html;profile=mcp-app` and is a real page,
- prompts are listed and titled,
- a tokenless request is challenged with `401` and `WWW-Authenticate: … resource_metadata`,
- icons are served, and the Explorer's HTML is **not** downloadable over plain HTTP.

Run it against any deployment:

```bash
python scripts/ci_smoke.py https://dev.financial-portfolios.ai
```

Against a real deployment the version check compares with your local checkout, so expect
that one line to differ unless you are on the deployed commit.

## Not enforced

`ruff format --check` is deliberately absent: the repository predates it, and 21 files
would be reformatted. Worth doing as its own reviewable change rather than as a gate added
after the fact.

## Dependabot

[`.github/dependabot.yml`](../.github/dependabot.yml) opens weekly grouped updates for
Python packages and GitHub Actions. The SDK is a path dependency, so its changes arrive
through its own repository and a version bump here.
