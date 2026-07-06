# TODO — Lab Registry Server

This file tracks only current, actionable items.

---

## Current status (2026-07-06)

- MCP server published on GitHub: `Palo-IT-GitHub-Demos/lab-registry-mcp`
- Distribution model: GitHub install (`pip install git+https://...`)
- Tooling status: 12 tools implemented and documented
- Automated tests:
  - `177 passed` with `REGISTRY_PATH` set (integration + E2E enabled)
  - `142 passed, 35 skipped` without local marketplace clone
- Git tag published: `v0.1.0`

---

## Remaining priorities

### 1) Clean and modernize docs structure

- [ ] Normalize markdown style in `README.md` (headings/tables/fenced-block spacing)
- [ ] Keep one source of truth per topic (`README.md` product view, `TESTING.md` validation view, `GITHUB_RELEASE.md` release view)

### 2) Operational hardening

- [ ] Move token usage guidance away from plaintext examples when possible (VS Code MCP `inputs` / keychain)
- [ ] Add a short troubleshooting note for private repo access approval paths (classic PAT vs fine-grained PAT)

### 3) Next release

- [ ] Decide whether to keep `v0.1.0` as baseline and publish `v0.1.1` for documentation-only updates
- [ ] If `v0.1.1` is created: update examples to prefer `@v0.1.1` in install snippets

---

## Stretch ideas (optional)

- [ ] `get_entry_batch`: fetch multiple entries in one call
- [ ] `diff_plugin`: structured changelog diff between two plugin versions
- [ ] `export_snapshot`: full registry JSON export (without `content_raw`)
