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

---

## Future improvements (identified during demo)

### Priority 1 — Content integrity ✅ done

- [x] Add `content_full` to `get_entry` response — verbatim file (frontmatter + body), write-ready. Fixes AI dropping YAML frontmatter when installing skills.
- [x] `get_entry` and `get_entry_by_id` now return `content_full` alongside the existing `metadata` and `content_raw` fields.

### Priority 2 — Response minimalism ✅ done

- [x] `RegistryEntry.summary_dump()` — lean serialization used by `list_entries`, `search_entries`, `suggest_entries`. Strips null/empty type-specific fields. Core keys always present: `id`, `name`, `type`, `plugin`, `plugin_version`, `description`, `tags`.
- [x] `get_entry` keeps full `model_dump()` for the `entry` field — two modes: lean for discovery, full for fetch.

### Priority 3 — Installation ergonomics ✅ done

- [x] `install_targets` added to `get_entry` response — computed paths for `claude_local`, `copilot`, and `plugin_tracking` per artefact type.
- [x] New tool `get_plugin_install_package(plugin)` — returns all artefacts with `content_full` + `install_targets` in one call.

### Priority 4 — Registry freshness ✅ done

- [x] `updated_at` added to `Plugin` model — populated at load time from `CHANGELOG.md`, exposed in `list_plugins`.
- [x] `last_updated_plugin` added to `get_marketplace_stats` — identifies the most recently updated plugin by name alongside the existing `last_updated` date.
