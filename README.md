# Lab Registry Server

MCP server exposing the Gen-e2 Lab Registry — skills, agents, commands, and hooks — to any MCP-compatible client (Claude Code, GitHub Copilot agent mode). Designed for the Innovation Lab at Palo IT Singapore.

---

## What it does

Two primary use cases:

**1. Discovery** — a client that doesn't know what tools exist can list, filter, and search the registry, then fetch the full content of any skill or agent to materialise it in its own repo.

**2. Compliance** — a client that already has tools locally sends its current inventory, and the server returns what is outdated (version drift) or unknown (not in the registry).

---

## How it works

```
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

lab-registry-server/         ← this repo
  src/lab_registry/
    registry.py              ← reads marketplace on first call, caches result
    models.py                ← RegistryEntry, Plugin (Pydantic)
    server.py                ← FastMCP, 12 tools registered via @mcp.tool()
    tools/
      search.py              ← list_entries, search_entries, suggest_entries
      fetch.py               ← get_entry, get_plugin, get_entry_by_id, list_plugins, get_changelog
      compliance.py          ← check_compliance
      stats.py               ← get_marketplace_stats
      validate.py            ← validate_entry
```

**Startup sequence:**
1. MCP client (Claude Code or Copilot) spawns the server process via stdio
2. Server responds to `initialize` — no files read yet
3. On first tool call, `load_registry()` indexes `REGISTRY_PATH`: reads `marketplace.json`, walks each plugin directory, parses YAML frontmatter from every `.md` file, extracts `updated_at` from `CHANGELOG.md`
4. Result is cached in memory (`lru_cache`) for the life of the process
5. All subsequent tool calls use the in-memory index — no disk access except `get_entry` (reads file content on demand)

**Versioning model:** version lives at the **plugin level** (from `plugin.json`), not per individual artifact. All 33 android artefacts share `plugin_version: "0.1.0"`. If the android plugin bumps to `0.2.0`, all its artefacts are considered outdated.

---

## Install

```bash
# Install directly from GitHub
pip install "git+https://github.com/Palo-IT-GitHub-Demos/lab-registry-mcp"

# Or pin an explicit tag
pip install "git+https://github.com/Palo-IT-GitHub-Demos/lab-registry-mcp@v0.1.0"
```

For local development:

```bash
git clone https://github.com/Palo-IT-GitHub-Demos/lab-registry-mcp lab-registry-server
cd lab-registry-server

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## Configure

`REGISTRY_PATH` must point to the `gen-e2-marketplace` repo root:

```bash
export REGISTRY_PATH=/abs/path/to/gen-e2-marketplace
# or copy .env.example → .env and set it there
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

## The 12 tools

### `list_entries`
List all registry entries. Returns a flat list of `RegistryEntry` objects.

| Parameter | Type | Description |
|-----------|------|-------------|
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
|-----------|------|-------------|
| `query` | `string` | Search term |
| `type` | `string?` | Optional type filter |

```json
{ "query": "architecture", "type": "skill" }
```

---

### `get_entry`
Fetch the full content of a specific entry. Returns structured metadata **and** the raw markdown body.

| Parameter | Type | Description |
|-----------|------|-------------|
| `plugin` | `string` | Plugin name |
| `type` | `string` | Artifact type |
| `name` | `string` | Artifact name |

```json
{ "plugin": "android", "type": "skill", "name": "android-architecture" }
```

Response shape:
```json
{
  "entry": { "id": "android/skill/android-architecture", "plugin_version": "0.1.0", ... },
  "metadata": { "name": "android-architecture", "description": "..." },
  "content_raw": "# Android architecture (project delta)\n\n..."
}
```

---

### `get_plugin`
All entries for one plugin, plus its manifest.

```json
{ "plugin": "research-suite" }
```

Response: `{ "manifest": { "version": "1.0.1", ... }, "entries": [...] }`

---

### `check_compliance`
Diff a client's local inventory against the registry. Each item must have `name`, `type`, `plugin`, and `local_version`.

```json
{
  "entries": [
    { "name": "android-architecture", "type": "skill", "plugin": "android", "local_version": "0.1.0" },
    { "name": "my-custom-skill",      "type": "skill", "plugin": "android", "local_version": "0.1.0" }
  ]
}
```

Response:
```json
{
  "outdated": [],
  "unknown":  [{ "name": "my-custom-skill", "type": "skill", "plugin": "android" }],
  "up_to_date_count": 1
}
```

`outdated` = version mismatch. `unknown` = not found in registry. No deprecated detection (field absent from source format).

---

### `reload_registry`
Force reload the in-memory cache from its source (GitHub or local). Use after a marketplace update to get fresh data without restarting the server.

Response: `{ "added": [...], "removed": [...], "modified": [...], "total": N }`

---

## Client configuration

> Both clients use **stdio transport** — no port, no HTTP.

### GitHub source mode (recommended — no local clone required)

Set `REGISTRY_GITHUB_REPO` to point directly at the marketplace repo.
Optionally set `REGISTRY_GITHUB_TOKEN` for private repos (classic PAT, `repo` scope).

**Claude Code CLI — user-level (applies to all projects)**

```bash
claude mcp add lab-registry --scope user \
  -e REGISTRY_GITHUB_REPO=GLOBAL-PALO-IT/gen-e2-marketplace \
  -e REGISTRY_GITHUB_TOKEN=ghp_... \
  -- /abs/path/to/.venv/bin/mcp run /abs/path/to/src/lab_registry/server.py
```

**GitHub Copilot agent mode — `~/Library/Application Support/Code/User/mcp.json` (user-level, all projects)**

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

### Local source mode (development / offline)

Set `REGISTRY_PATH` to the local clone of the marketplace repo instead.

```json
"env": { "REGISTRY_PATH": "/abs/path/to/gen-e2-marketplace" }
```

---

## Usage examples

These are natural-language prompts you can use from Copilot Agent mode or Claude Code.

### 1) Discover what exists

Prompt:
```text
Give me a summary of all available gen-e2 plugins
```

Typical tools used: `list_plugins` or `get_marketplace_stats`

---

### 2) Find entries by role or type

Prompt:
```text
List all gen-e2 agents available in the registry
```

Typical tools used: `list_entries` with `type="agent"`

---

### 3) Get recommendations for a task

Prompt:
```text
I need to write tests for a Go service. Which gen-e2 skills are relevant?
```

Typical tools used: `suggest_entries` (optionally cross-checked with `list_entries`)

---

### 4) Fetch full content by ID

Prompt:
```text
Get the full content of android/skill/android-architecture
```

Typical tools used: `get_entry_by_id`

---

### 5) Inspect everything in one plugin

Prompt:
```text
Show me everything in the gen-e2 delivery plugin
```

Typical tools used: `get_plugin`, then `get_entry_by_id` for complete raw content per entry

---

### 6) Explain version drift

Prompt:
```text
Check if these local entries are up to date and show me what changed in the plugin changelog
```

Typical tools used: `check_compliance` then `get_changelog`

---

### 7) Validate a new contribution

Prompt:
```text
Validate this new skill markdown file against the gen-e2 schema
```

Typical tools used: `validate_entry`

---

### 8) Refresh cache after marketplace updates

Prompt:
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
| delivery | 0.2.3 | 5 | 0 | 0 | 0 |
| dev-workflow | 0.1.0 | 3 | 1 | 4 | 1 |
| figma-design-to-code | 0.1.0 | 1 | 0 | 0 | 0 |
| fortran77-explainer | 0.1.0 | 0 | 1 | 0 | 0 |
| go-tdd-orchestrator | 0.1.0 | 1 | 1 | 0 | 0 |
| html-planner-and-presentation | 0.1.0 | 3 | 0 | 0 | 0 |
| html-presentation | 0.1.0 | 1 | 0 | 0 | 0 |
| implementation-plan | 0.1.0 | 1 | 0 | 0 | 0 |
| kotlin-and-kotlin-multiplatform | 0.1.0 | 4 | 0 | 0 | 0 |
| migration-implementation-plan | 0.1.0 | 1 | 0 | 0 | 0 |
| research-suite | 1.0.1 | 2 | 0 | 0 | 0 |
| swift5-development-test-writer | 0.1.0 | 2 | 0 | 0 | 0 |
| **Total** | | **43** | **13** | **13** | **2** |

**74 artefacts** indexed across 14 plugins. `updated_at` is `null` for 4 plugins without `CHANGELOG.md`.

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
  test_tools_new.py        # unit: 6 new tools — list_plugins, get_entry_by_id,
                           #       get_changelog, get_marketplace_stats,
                           #       suggest_entries, validate_entry (35 tests)
  test_contract.py         # contract: response shapes for all tools (38 tests)
  test_registry_github.py  # GitHub source mode (mocked HTTP, 16 tests)
  test_integration.py      # real marketplace: IDs, content, handlers (15 tests)
  test_e2e.py              # full MCP subprocess — all 12 tools (20 tests)
```

**177 tests total, 0 failures.**
E2E and integration tests are skipped if `REGISTRY_PATH` is not set.
GitHub tests use fully mocked HTTP — no network access required.

---

## Known limitations

- **No per-artifact versioning** — version is at plugin level; a plugin bump marks all its artefacts as outdated even if only one changed
- **No deprecated detection** — no `deprecated` flag in the source format
- **`updated_at` is best-effort** — parsed from `CHANGELOG.md`; `null` if absent
- **Cache on demand** — use `reload_registry` tool to refresh without restarting the server
- **Hooks indexed one entry per plugin** — not per event type
```

## Tools

| Tool | Description |
|------|-------------|
| `list_entries` | List entries — filter by type / plugin / tags |
| `search_entries` | Keyword search over name + description |
| `suggest_entries` | Multi-term scoring — find entries relevant to a task description |
| `get_entry` | Full content: parsed metadata + raw markdown body |
| `get_entry_by_id` | Direct lookup by `plugin/type/name` ID string |
| `get_plugin` | All entries for one plugin + its manifest |
| `list_plugins` | All plugins with version and per-type entry counts |
| `get_changelog` | Full CHANGELOG.md for a plugin |
| `get_marketplace_stats` | Dashboard: totals, by-type, by-plugin, last updated |
| `check_compliance` | Diff local versions against registry |
| `validate_entry` | Schema validation for skill/agent/command markdown files |
| `reload_registry` | Clear cache and re-fetch from source, returns diff |
