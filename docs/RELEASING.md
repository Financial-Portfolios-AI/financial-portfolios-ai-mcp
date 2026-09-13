# Releasing

## Versioning

[Semantic Versioning](https://semver.org/):

- **Major**: a change that breaks a caller, such as removing or renaming a tool or a
  tool argument, or changing a tool's result shape incompatibly.
- **Minor**: new tools, prompts, Apps or fields, and compatible behaviour changes.
- **Patch**: fixes with no interface change.

Prompt input renames count as **minor**. Prompts are filled in by hand through a client
dialog rather than called by code, so a rename changes a label, not a contract. Tool
arguments are called by models and clients, so renaming one is **major**.

The version is defined once, in `pyproject.toml`. The server reads it through
`financial_portfolios_ai_mcp._version`, and tests fail if `server.json`,
`claude_connector.json` or `CHANGELOG.md` disagree.

## Release steps

1. **SDK first**, if the release depends on SDK changes. Release
   `financial-portfolios-ai` using the same steps, then raise the floor in this
   project's `pyproject.toml` dependencies.
2. **Bump** `version` in `pyproject.toml`, `server.json` (both fields) and
   `claude_connector.json`.
3. **Changelog**: move the `[Unreleased]` entries under a new version heading with
   today's date, and update the comparison links at the bottom.
4. **Release notes**: add a plain-language section to `RELEASE_NOTES.md`. Keep internal
   details out, and make no claims about prices, returns or performance.
5. **Test**: run `ruff check src tests scripts` and `pytest`.
6. **Commit** (`release: vX.Y.Z`), **tag** annotated (`git tag -a vX.Y.Z`), and **push**
   both the branch and the tag.
7. **Build** the image tagged with both the version and the commit:
   `gcr.io/<project>/financial-portfolios-ai-mcp:X.Y.Z` and `:<short-sha>`.
8. **Deploy** with `gcloud run services update --image`, which keeps the service's
   environment variables. Don't use `gcloud run deploy --set-env-vars` with
   `cloudbuild.yaml`'s defaults against a non-production service.
9. **Verify**: `serverInfo.version` in the `initialize` response matches, the tokenless
   `POST /mcp` returns `401`, and `/mcp/assets/icon-512.png` returns `200`.
