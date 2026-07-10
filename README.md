# Lab Registry Server

MCP server exposing the Gen-e2 Lab Registry — skills, agents, commands, and hooks — to any MCP-compatible client (Claude Code, GitHub Copilot agent mode). Designed for the Innovation Lab at Palo IT Singapore.

Canonical repository: `https://github.com/Palo-IT-GitHub-Demos/lab-registry-mcp`

This repository contains only the MCP server.
It does not embed the `gen-e2-marketplace` project, which remains the registry source of truth.
In normal usage, the server reads that source directly from GitHub.

---

## What it does

This MCP server connects to the gen-e2 plugins repository and gives agents direct access to the library from VS Code.

### Who it's for

It is mainly intended for Labs developers, especially those who are new to gen-e2.

### Why it exists

It makes the gen-e2 library easier to discover, reuse, and integrate across projects.

### Main use cases

- Explore the gen-e2 artefact library in more depth
- Find a specific plugin or artefact by name and integrate it easily into the current project
- Get suggestions for which gen-e2 artefacts are most relevant to the current project
- Stay informed about new gen-e2 plugins and updates to existing ones

---

## How it works

```text
gen-e2-marketplace/          ← source of truth (read-only, never written)
  .claude-plugin/
    marketplace.json         ← list of all 13 plugins with semver versions
  plugins/
    android/
      .claude-plugin/plugin.json
      CHANGELOG.md
      skills/android-architecture/SKILL.md   ← YAML frontmatter + markdown body
      agents/android-architect.agent.md
      commands/add-screen.md
      hooks.json
    research-suite/ ...
    delivery/ ...
    ...

lab-registry-mcp/            ← this repo
  src/lab_registry/
    registry.py              ← reads marketplace on first call, caches result
    models.py                ← RegistryEntry, Plugin (Pydantic)
    server.py                ← FastMCP, 15 tools registered via @mcp.tool()
    tools/
      search.py              ← list_entries, search_entries, suggest_entries, suggest_plugins
      fetch.py               ← get_entry, get_plugin, get_entry_by_id, list_plugins, get_changelog
      compliance.py          ← check_compliance, check_compliance_plugin
      stats.py               ← get_marketplace_stats
      validate.py            ← validate_entry
```

**Startup sequence:**

1. MCP client (Claude Code or Copilot) spawns the server process via stdio
2. Server responds to `initialize` — no files read yet
3. On first tool call, `load_registry()` reads from either `REGISTRY_GITHUB_REPO` or `REGISTRY_PATH`, parses marketplace metadata, indexes plugin entries, and extracts `updated_at` from `CHANGELOG.md` when available
4. Result is cached in memory (`lru_cache`) for the life of the process
5. All subsequent tool calls use the in-memory index — no disk access except `get_entry` (reads file content on demand)

**Versioning model:** version lives at the **plugin level** (from `plugin.json`), not per individual artifact. All 33 android artefacts share `plugin_version: "0.1.0"`. If the android plugin bumps to `0.2.0`, all its artefacts are considered outdated.

---

## Install

```bash
# Install directly from GitHub
pip install "git+https://github.com/Palo-IT-GitHub-Demos/lab-registry-mcp"

# Or pin an explicit tag
pip install "git+https://github.com/Palo-IT-GitHub-Demos/lab-registry-mcp@v0.2.0"
```

For local development:

```bash
git clone https://github.com/Palo-IT-GitHub-Demos/lab-registry-mcp
cd lab-registry-mcp

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## Configuration

There are 3 practical ways to configure the source registry.

### 1) GitHub source from `GLOBAL-PALO-IT/gen-e2-marketplace` (recommended when you have access)

Use this when you can obtain a GitHub token with access to the official marketplace repository.

```bash
export REGISTRY_GITHUB_REPO=GLOBAL-PALO-IT/gen-e2-marketplace
# optional but usually needed for private repo access
export REGISTRY_GITHUB_TOKEN=ghp_...
```

### 2) GitHub source from your own fork (temporary workaround)

Use this when access to the official repo token is difficult, but you can fork the marketplace into a personal or easier-to-access repository.

```bash
export REGISTRY_GITHUB_REPO=<your-user-or-org>/gen-e2-marketplace
export REGISTRY_GITHUB_TOKEN=ghp_...
```

### 3) Local source from a clone of `gen-e2-marketplace`

Use this for offline development, local debugging, or local integration/E2E tests.

```bash
export REGISTRY_PATH=/abs/path/to/gen-e2-marketplace
# or copy .env.example → .env and set it there
```

### Client setup

Both Claude Code and Copilot use the same stdio server; only the client registration format changes.

#### Claude Code CLI — user-level

```bash
claude mcp add lab-registry --scope user \
  -e REGISTRY_GITHUB_REPO=GLOBAL-PALO-IT/gen-e2-marketplace \
  -e REGISTRY_GITHUB_TOKEN=ghp_... \
  -- /abs/path/to/.venv/bin/mcp run /abs/path/to/src/lab_registry/server.py
```

If you use a fork or a local clone, replace the env vars accordingly.

#### GitHub Copilot agent mode — `~/Library/Application Support/Code/User/mcp.json`

```json
{
  "servers": {
    "lab-registry": {
      "type": "stdio",
      "command": "/abs/path/to/.venv/bin/mcp",
      "args": ["run", "/abs/path/to/src/lab_registry/server.py"],
      "env": {
        "REGISTRY_GITHUB_REPO": "GLOBAL-PALO-IT/gen-e2-marketplace",
        "REGISTRY_GITHUB_TOKEN": "ghp_..."
      }
    }
  }
}
```

For local mode, replace the `env` block with:

```json
{
  "REGISTRY_PATH": "/abs/path/to/gen-e2-marketplace"
}
```

---

## Run

```bash
# Visual debug UI (MCP Inspector at http://localhost:6274)
mcp dev src/lab_registry/server.py

# Stdio (for client config)
REGISTRY_GITHUB_REPO=owner/repo REGISTRY_GITHUB_TOKEN=ghp_... mcp run src/lab_registry/server.py

# Unit + integration + E2E tests
REGISTRY_PATH=../gen-e2-marketplace pytest tests/ -v
```

---

## The 15 tools

> **Response shapes:** `list_entries`, `search_entries`, and `suggest_entries` use a lean serialization — only populated fields are returned (no `null` or empty-list noise). `get_entry` always returns the full entry shape.

### Tool selection guide

| Goal | Use |
|---|---|
| Discover which plugins fit a project type | `suggest_plugins` |
| Exact keyword or partial name (e.g. `"tdd"`, `"android"`) | `search_entries` |
| Natural language task description (e.g. `"I need to review architecture"`) | `suggest_entries` |
| Browse by type or plugin | `list_entries` with filters |
| Install a full plugin (all artefacts + paths) | `get_plugin_install_package` |
| Read one specific artefact | `get_entry` or `get_entry_by_id` |
| Check installed plugins are up to date (one plugin) | `check_compliance_plugin` |
| Check installed plugins are up to date (multiple) | discover `plugin.json` → `check_compliance` |
| See what changed in a plugin | `get_changelog` |

### `list_entries`

List all registry entries. Returns a flat list of `RegistryEntry` objects.

| Parameter | Type | Description |
| --------- | ---- | ----------- |
| `type` | `string?` | Filter: `"skill"`, `"agent"`, `"command"`, or `"hook"` |
| `plugin` | `string?` | Filter by plugin name (e.g. `"android"`) |
| `tags` | `string[]?` | Filter by keywords — OR match (any tag must match) |

```json
// Example: all skills in the android plugin
{ "type": "skill", "plugin": "android" }
```

---

### `search_entries`

Keyword search over name, description, and plugin name. Name matches are ranked above description matches.

| Parameter | Type | Description |
| --------- | ---- | ----------- |
| `query` | `string` | Search term |
| `type` | `string?` | Optional type filter |

```json
{ "query": "architecture", "type": "skill" }
```

---

### `suggest_entries`

Task-oriented suggestion tool. Splits the task into individual terms and scores entries by how many terms appear in their name, description, plugin name, and tags.

Use for natural language queries at the **artefact level**. For plugin-level discovery ("which plugins fit my project?"), use `suggest_plugins` instead. For exact keyword matching, use `search_entries`.

| Parameter | Type | Description |
| --------- | ---- | ----------- |
| `task` | `string` | Natural language description of what you need |
| `type` | `string?` | Optional type filter |
| `limit` | `integer?` | Maximum number of results (default 5) |

```json
{ "task": "I need to write tests for a Go service", "type": "skill", "limit": 5 }
```

---

### `suggest_plugins`

Plugin-level discovery. Scores plugins by how many task words appear in their name (3× weight), description, and tags.

Use this **before** `suggest_entries` when the user describes their project type and wants to know which plugins are most relevant — rather than listing all 15 plugins flat.

| Parameter | Type | Description |
| --------- | ---- | ----------- |
| `task` | `string` | Natural language description of the project or need |
| `limit` | `integer?` | Maximum number of results (default 5) |

```json
{ "task": "I'm building an Android app", "limit": 3 }
```

Example response: `android`, `delivery`, `architecture-reviewer` — each with `score` and `matched_terms`.

---

### `get_entry`

Fetch the full content of a specific entry. Returns structured metadata **and** the raw markdown body.

| Parameter | Type | Description |
| --------- | ---- | ----------- |
| `plugin` | `string` | Plugin name |
| `type` | `string` | Artifact type |
| `name` | `string` | Artifact name |

```json
{ "plugin": "android", "type": "skill", "name": "android-architecture" }
```

Response shape:

```json
{
  "entry":          { "id": "android/skill/android-architecture", "plugin_version": "0.1.0", ... },
  "metadata":       { "name": "android-architecture", "description": "..." },
  "content_raw":    "# Android architecture (project delta)\n\n...",
  "content_full":   "---\nname: android-architecture\n---\n# Android architecture...\n",
  "install_targets": {
    "claude_local":    ".claude/skills/android-architecture/SKILL.md",
    "copilot":         ".github/skills/android-architecture/SKILL.md",
    "plugin_tracking": ".claude/plugins/android/plugin.json"
  }
}
```

`content_full` is the verbatim source file (frontmatter + body) — write it directly to `install_targets.claude_local` or `install_targets.copilot` without any reconstruction.

---

### `get_entry_by_id`

Fetch one entry directly from its canonical ID. Returns the same shape as `get_entry`: `entry`, `metadata`, `content_raw`, `content_full`, and `install_targets`.

| Parameter | Type | Description |
| --------- | ---- | ----------- |
| `id` | `string` | Entry ID in `plugin/type/name` format |

```json
{ "id": "android/skill/android-architecture" }
```

---

### `get_plugin`

All entries for one plugin, plus its manifest.

| Parameter | Type | Description |
| --------- | ---- | ----------- |
| `plugin` | `string` | Plugin name |

```json
{ "plugin": "research-suite" }
```

Response: `{ "manifest": { "version": "1.0.1", ... }, "entries": [...] }`

---

### `list_plugins`

List all indexed plugins with version and per-type entry counts.

Response includes plugin-level summary fields such as version, `updated_at`, and counts for skills, agents, commands, and hooks.

---

### `get_changelog`

Return the raw `CHANGELOG.md` content for a plugin.

| Parameter | Type | Description |
| --------- | ---- | ----------- |
| `plugin` | `string` | Plugin name |

```json
{ "plugin": "delivery" }
```

---

### `get_marketplace_stats`

Return marketplace-level statistics: totals, counts by type, counts by plugin, and latest update information.

Includes `last_updated` (most recent date across all entries) and `last_updated_plugin` (name of the plugin that was updated most recently).

Useful for dashboards, summaries, and quick health checks.

---

### `check_compliance`

Check whether locally installed gen-e2 plugin artefacts are up to date with the registry.

**For a single plugin**, use `check_compliance_plugin` instead — it requires only the plugin name and local version, without listing artefacts manually.

**Recommended workflow for multiple plugins:** discover local `plugin.json` files, read the `version` field from each, build the `entries` list, then call this tool.

Each item in `entries` must have `name`, `type`, `plugin`, and `local_version`.

```json
{
  "entries": [
    { "name": "research",   "type": "skill", "plugin": "research-suite", "local_version": "0.8.0" },
    { "name": "coi-verify", "type": "skill", "plugin": "research-suite", "local_version": "0.8.0" }
  ]
}
```

Response:

```json
{
  "outdated": [{ "name": "research", "plugin": "research-suite", "local_version": "0.8.0", "registry_version": "1.0.1" }],
  "unknown":  [],
  "up_to_date_count": 0
}
```

`outdated` = version mismatch. `unknown` = not found in registry.

---

### `check_compliance_plugin`

Shortcut: check all artefacts of a plugin against a single local version in one call.

Equivalent to calling `get_plugin` to list artefacts, then `check_compliance` with each one. Use this when you have a `plugin.json` with one version field — it removes the need to enumerate artefacts manually.

| Parameter | Type | Description |
| --------- | ---- | ----------- |
| `plugin` | `string` | Plugin name |
| `local_version` | `string` | Version from the local `plugin.json` |

```json
{ "plugin": "research-suite", "local_version": "0.8.0" }
```

Returns the same shape as `check_compliance`: `outdated`, `unknown`, `up_to_date_count`.

Validate a skill, agent, or command markdown file structure against the expected schema.

Typical output includes:

- `valid`
- `errors`
- `warnings`
- parsed frontmatter when available

Useful before contributing a new artefact to the marketplace.

---

### `get_plugin_install_package`

Return a complete install package for a plugin — **one call, everything needed to install**.

| Parameter | Type | Description |
| --------- | ---- | ----------- |
| `plugin` | `string` | Plugin name |

```json
{ "plugin": "implementation-plan" }
```

Response shape:

```json
{
  "plugin": { "name": "implementation-plan", "version": "0.1.0", ... },
  "files": [
    {
      "id": "implementation-plan/skill/create-implementation-plan",
      "type": "skill",
      "name": "create-implementation-plan",
      "content_full": "---\nname: create-implementation-plan\n---\n...",
      "install_targets": {
        "claude_local":    ".claude/skills/create-implementation-plan/SKILL.md",
        "copilot":         ".github/skills/create-implementation-plan/SKILL.md",
        "plugin_tracking": ".claude/plugins/implementation-plan/plugin.json"
      }
    }
  ],
  "plugin_tracking": {
    "path":    ".claude/plugins/implementation-plan/plugin.json",
    "content": "{\"name\": \"implementation-plan\", \"version\": \"0.1.0\", ...}"
  }
}
```

Prefer this over multiple `get_entry` calls when installing a full plugin. Each file in `files` has `content_full` (write-ready) and `install_targets` (exact paths per client).

---

### `reload_registry`

Force reload the in-memory cache from its source (GitHub or local). Use after a marketplace update to get fresh data without restarting the server.

Response: `{ "added": [...], "removed": [...], "modified": [...], "total": N }`

---

## Usage examples

These are natural-language prompts validated against the live registry.

### 1) Discover what exists

```text
What gen-e2 plugins are available and which was updated most recently?
```

Typical tools used: `get_marketplace_stats` (returns `last_updated_plugin`) + `list_plugins`

---

### 2) Find by type

```text
What gen-e2 agents are available in the registry?
```

Typical tools used: `list_entries` with `type="agent"`

---

### 3) Natural language search

```text
Search the gen-e2 registry for skills related to architecture review.
```

Typical tools used: `suggest_entries` with a task description

---

### 4) Get documentation and install files

```text
Get the full documentation and install files for the gen-e2 delivery plugin.
```

Typical tools used: `get_plugin_install_package` — returns all artefacts with `content_full` + `install_targets` in one call

---

### 5) Install a plugin into the current project

```text
Install the gen-e2 implementation-plan plugin into my project for both Claude Code and GitHub Copilot.
```

Typical tools used: `get_plugin_install_package` → write each `file.content_full` to `file.install_targets.claude_local` and `file.install_targets.copilot`

---

### 6) Check for outdated plugins

```text
Check if my locally installed gen-e2 plugins are up to date with the registry.
```

Typical tools used: discover `.claude/plugins/*/plugin.json` → `check_compliance` → `get_changelog` for outdated entries

---

### 7) Read one entry

```text
Get the full content of android/skill/android-architecture
```

Typical tools used: `get_entry_by_id`

---

### 8) Validate a new contribution

```text
Validate this new skill markdown file against the gen-e2 schema
```

Typical tools used: `validate_entry`

---

### 9) Refresh cache after marketplace updates

```text
Reload the gen-e2 registry and tell me what changed
```

Typical tools used: `reload_registry`

---

## Registry coverage

Current state of `gen-e2-marketplace` as indexed:

| Plugin | Version | Skills | Agents | Commands | Hooks |
|--------|---------|--------|--------|----------|-------|
| android | 0.1.0 | 14 | 9 | 9 | 1 |
| architecture-reviewer | 0.1.0 | 4 | 1 | 0 | 0 |
| delivery | 0.2.3 | 5 | 1 | 0 | 0 |
| figma-design-to-code | 0.1.0 | 1 | 0 | 0 | 0 |
| fortran77-explainer | 0.1.0 | 0 | 1 | 0 | 0 |
| go-tdd-orchestrator | 0.1.0 | 2 | 3 | 0 | 0 |
| html-planner-and-presentation | 0.1.0 | 3 | 0 | 0 | 0 |
| html-presentation | 0.1.0 | 1 | 0 | 0 | 0 |
| implementation-plan | 0.1.0 | 1 | 0 | 0 | 0 |
| kotlin-and-kotlin-multiplatform | 0.1.0 | 4 | 0 | 0 | 0 |
| migration-implementation-plan | 0.1.0 | 1 | 0 | 0 | 0 |
| research-suite | 1.0.1 | 2 | 0 | 0 | 0 |
| swift5-development-test-writer | 0.1.0 | 2 | 0 | 0 | 0 |
| **Total** | | **40** | **15** | **9** | **1** |

**65 artefacts** indexed across 13 plugins when reading from `GLOBAL-PALO-IT/gen-e2-marketplace`.

> `dev-workflow` exists in a local clone of the marketplace but is not published to the shared GitHub repository — it is excluded from the counts above. `updated_at` is `null` for plugins without a `CHANGELOG.md`.

---

## Tests

```
tests/
  conftest.py              # session fixture: mock registry with 1 plugin / 4 artefacts
  test_registry.py         # unit: indexer, parsers, cache (25 tests)
  test_tools_search.py     # unit: list_entries, search_entries (11 tests)
  test_tools_fetch.py      # unit: get_entry, get_plugin (8 tests)
  test_tools_compliance.py # unit: check_compliance (6 tests)
  test_tools_reload.py     # unit: reload_registry (4 tests)
  test_tools_new.py        # unit: 7 new tools — list_plugins, get_entry_by_id,
                           #       get_changelog, get_marketplace_stats,
                           #       suggest_entries, validate_entry,
                           #       get_plugin_install_package (38 tests)
  test_contract.py         # contract: response shapes for all tools (40 tests)
  test_registry_github.py  # GitHub source mode (mocked HTTP, 16 tests)
  test_integration.py      # real marketplace: IDs, content, handlers (15 tests)
  test_e2e.py              # full MCP subprocess — all 15 tools (20 tests)
```

**187 tests total, 0 failures.**
E2E and integration tests are skipped if `REGISTRY_PATH` is not set.
GitHub tests use fully mocked HTTP — no network access required.

---

## Known limitations

- **No per-artifact versioning** — version is at plugin level; a plugin bump marks all its artefacts as outdated even if only one changed
- **No deprecated detection** — no `deprecated` flag in the source format
- **`updated_at` is best-effort** — parsed from `CHANGELOG.md`; `null` if absent
- **Cache on demand** — use `reload_registry` tool to refresh without restarting the server
- **Hooks indexed one entry per plugin** — not per event type