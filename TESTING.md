# Testing Guide — Lab Registry Server

This document describes how to run the test suite and how to manually verify
end-to-end interoperability with both supported MCP clients.

The downloadable GitHub repository contains only the MCP server.
The `gen-e2-marketplace` clone is optional and only needed for local-source development or tests that explicitly exercise `REGISTRY_PATH`.

---

## Prerequisites

| Requirement | Version | Check |
|---|---|---|
| Python | ≥ 3.12 | `python3 --version` |
| uv (package manager) | any | `uv --version` |
| GitHub token | classic PAT, `repo` scope | needed for GitHub source mode |
| gen-e2-marketplace clone | optional | only for local source mode and local integration/E2E tests |

### Setup

```bash
git clone https://github.com/Palo-IT-GitHub-Demos/lab-registry-mcp
cd lab-registry-mcp
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

### Remote install smoke test

```bash
python3 -m venv /tmp/lab-registry-git
source /tmp/lab-registry-git/bin/activate
pip install "git+https://github.com/Palo-IT-GitHub-Demos/lab-registry-mcp"
lab-registry --help
```

Expected result: package installs successfully from GitHub and the `lab-registry` CLI is available.

Validated on 2026-07-06:
- Installation succeeded in a local virtual environment after macOS blocked system-wide install (PEP 668).
- Installed distribution name: `lab-registry-server 0.1.0`
- Import check: `python -c "import lab_registry; print('ok')"`

---

## Running the Test Suite

### Unit + Integration + E2E (all at once)

```bash
# Against the real marketplace (recommended)
REGISTRY_PATH=../gen-e2-marketplace pytest tests/ -v

# Without a local clone (GitHub mock only)
pytest tests/ -v
```

Expected output: **177 passed**

### By category

```bash
# Unit tests only (mock registry, no network)
pytest tests/test_contract.py tests/test_registry.py \
       tests/test_tools_*.py -v

# GitHub source mode (mocked HTTP, no network)
pytest tests/test_registry_github.py -v

# Integration tests (requires REGISTRY_PATH)
REGISTRY_PATH=../gen-e2-marketplace pytest tests/test_integration.py -v

# E2E tests — spawns real MCP server subprocess (requires REGISTRY_PATH)
REGISTRY_PATH=../gen-e2-marketplace pytest tests/test_e2e.py -v
```

### Coverage table

| File | Scope | Network | Marketplace needed |
|---|---|---|---|
| `test_contract.py` | Handler response shapes | ✗ | ✗ |
| `test_registry.py` | Parser + indexer + cache | ✗ | ✗ |
| `test_tools_*.py` | Tool handlers | ✗ | ✗ |
| `test_registry_github.py` | GitHub fetcher (mocked) | ✗ | ✗ |
| `test_integration.py` | Real marketplace data | ✗ | ✓ local clone |
| `test_e2e.py` | Full MCP subprocess | ✗ | ✓ local clone |

---

## Manual Client Tests

### GitHub Copilot Agent Mode (VS Code)

**Prerequisites**
- `~/Library/Application Support/Code/User/mcp.json` contains `lab-registry` server
- `REGISTRY_GITHUB_REPO` and `REGISTRY_GITHUB_TOKEN` set in the `env` block
- VS Code reloaded after any config change (`Cmd+Shift+P` → Developer: Reload Window)

**Steps**
1. Open any project in VS Code
2. Open Copilot Chat (`Cmd+Shift+I`)
3. Select **Agent** mode
4. Verify `lab-registry` tools appear under `{}` (tools icon)
5. Send the following messages and check results:

```
Using the lab-registry tools, list all available skills
```
Expected: table of 43 skills grouped by plugin

```
Using lab-registry, get the full content of the android-architecture skill
```
Expected: `content_raw` field with the MVVM + Clean Architecture instructions

```
Check if these entries are up to date using lab-registry:
- plugin: android, type: skill, name: android-architecture, version: 0.0.1
```
Expected: `outdated` list with `current_version: 0.1.0`

**Validation date**: 2026-07-06 ✅ — `list_entries type=skill` → 43 skills returned

---

### Claude Code CLI

**Prerequisites**
- `claude mcp add --scope user` registered (see README for command)
- GitHub token with access to the marketplace repo

**Steps**
1. Open any terminal directory
2. Run `claude` to start an interactive session
3. Type `/mcp` → verify `lab-registry · ✔ connected · 12 tools`
4. Ask:

```
List all skills available in the lab registry
```
Expected: same list as Copilot

```
Use the lab-registry tool to get the full content of the research skill
```
Expected: structured response with `content_raw`

**Validation date**: 2026-07-06 ✅ — `lab-registry · connected · 12 tools`

---

## Demo Script (Copy/Paste)

Use these prompts as a quick acceptance demo in either Copilot Agent mode or Claude Code.

```text
Give me a summary of all available gen-e2 plugins
```
Expected: plugin list with versions and entry counts (`list_plugins` / `get_marketplace_stats`).

```text
List all gen-e2 agents available in the registry
```
Expected: all indexed agents (`list_entries` with `type=agent`).

```text
I need to write tests for a Go service. Which gen-e2 skills are relevant?
```
Expected: ranked suggestions with matched terms (`suggest_entries`).

```text
Get the full content of android/skill/android-architecture
```
Expected: parsed metadata + full markdown body (`get_entry_by_id`).

```text
Show me everything in the gen-e2 delivery plugin
```
Expected: plugin manifest + entry list (`get_plugin`).

```text
Check if these local entries are up to date and show me what changed in the plugin changelog
```
Expected: outdated/unknown entries (`check_compliance`) + full changelog (`get_changelog`).

```text
Validate this new skill markdown file against the gen-e2 schema
```
Expected: `valid`, `errors`, `warnings`, parsed frontmatter (`validate_entry`).

```text
Reload the gen-e2 registry and tell me what changed
```
Expected: diff with `added`, `removed`, `modified`, `total` (`reload_registry`).

---

## Cross-Client Consistency Check

Both clients must return identical data for the same query. Run this check after
any change to the server or registry.

| Query | Expected result | Copilot | Claude Code |
|---|---|---|---|
| `list_entries type=skill` | 43 entries | ✅ | ✅ |
| `get_entry android/skill/android-architecture` | `plugin_version: 0.1.0` | — | — |
| `check_compliance` outdated entry | `current_version` present | — | — |

---

## Troubleshooting

### "No MCP servers configured" in Claude Code
```bash
# Re-register at user scope
claude mcp add lab-registry --scope user \
  -e REGISTRY_GITHUB_REPO=<owner/repo> \
  -e REGISTRY_GITHUB_TOKEN=<token> \
  -- /path/to/.venv/bin/mcp run /path/to/server.py
```

### "REGISTRY_GITHUB_TOKEN missing" error from Copilot
- Check `~/Library/Application Support/Code/User/mcp.json` has `REGISTRY_GITHUB_TOKEN`
- Run `Cmd+Shift+P` → Developer: Reload Window to restart the server

### "Repository not found" error
- Token may not have access to the repo (check `repo` scope for classic PAT)
- Fine-grained PATs on org repos require admin approval — use classic PAT instead

### Server returns stale data after marketplace update
```
# In Copilot agent mode or Claude Code:
Use the lab-registry reload_registry tool to refresh the cache
```
