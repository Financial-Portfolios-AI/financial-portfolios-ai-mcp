# Continuous integration

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs on pushes to `main`, on
`v*` tags, on pull requests, and on demand.

| Job | What it does |
| :--- | :--- |
| **Lint and test** | `ruff check`, then the full `pytest` suite on Python 3.12, the version the image uses |
| **Build image and smoke-test it** | builds the Docker image, runs the container, and drives a real MCP client against it with [`scripts/ci_smoke.py`](../scripts/ci_smoke.py) |

## SDK access: `SDK_DEPLOY_KEY`

The server depends on the SDK through a local sibling path (`[tool.uv.sources]`), so both
repositories are checked out side by side, the layout the Dockerfile also builds from.
GitHub's automatic `GITHUB_TOKEN` is scoped to this repository alone and cannot read the
private SDK, so the checkout uses an SSH **deploy key**: read-only, valid for that one
repository, owned by no person, and with no expiry.

- Public half: deploy key **"MCP CI (read-only)"** on `financial-portfolios-ai-sdk`.
- Private half: secret **`SDK_DEPLOY_KEY`** on this repository, under both **Actions** and
  **Dependabot** (Dependabot PRs read Dependabot's secrets, not Actions').
- Deploy keys must be allowed at organisation level (Settings → Member privileges).

To rotate: generate a new pair with `ssh-keygen -t ed25519 -N ""`, add the public half as a
read-only deploy key on the SDK repo, `gh secret set SDK_DEPLOY_KEY` (and again with
`--app dependabot`) from the private half, delete the old deploy key, then delete the local
key files.

If the "Check out the SDK" step fails with a permission or "repository not found" error, the
key or one of the two secrets is missing.

## What the smoke test covers

It exercises the protocol surface against a running container, no portal required, and
each check corresponds to something a release actually broke:

- the `initialize` handshake answers (a Host allow-list once turned this into `421`),
- `POST /mcp` without a trailing slash works (a `307` here broke connectors silently),
- the reported version matches this checkout's `pyproject.toml`,
- every tool has a `title` and a `readOnlyHint`, as the Claude directory requires,
- every app tool carries `_meta.ui.resourceUri`, and each page behind one is served as
  `text/html;profile=mcp-app` and completes a handshake - checked per app, since a page
  that fails to load looks fine from the tool list,
- prompts are listed and titled,
- a tokenless request is challenged with `401` and `WWW-Authenticate: … resource_metadata`,
- icons are served, and **no** app page is downloadable over plain HTTP.

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
