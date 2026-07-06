# Testing Guide — Lab Registry Server

This document describes how to run the test suite and how to manually verify
end-to-end interoperability with both supported MCP clients.

---

## Prerequisites

| Requirement | Version | Check |
|---|---|---|
| Python | ≥ 3.12 | `python3 --version` |
| uv (package manager) | any | `uv --version` |
| GitHub token | classic PAT, `repo` scope | needed for GitHub source mode |
| gen-e2-marketplace clone | optional | only for local source mode |

### Setup

```bash
cd lab-registry-server
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

---

## Running the Test Suite

### Unit + Integration + E2E (all at once)

```bash
# Against the real marketplace (recommended)
REGISTRY_PATH=../gen-e2-marketplace pytest tests/ -v

# Without a local clone (GitHub mock only)
pytest tests/ -v
```

Expected output: **137 passed**

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
Expected: table of ~36 skills grouped by plugin

```
Using lab-registry, get the full content of the android-architecture skill
```
Expected: `content_raw` field with the MVVM + Clean Architecture instructions

```
Check if these entries are up to date using lab-registry:
- plugin: android, type: skill, name: android-architecture, version: 0.0.1
```
Expected: `outdated` list with `current_version: 0.1.0`

**Validation date**: 2026-07-06 ✅ — `list_entries type=skill` → 36 skills returned

---

### Claude Code CLI

**Prerequisites**
- `claude mcp add --scope user` registered (see README for command)
- GitHub token with access to the marketplace repo

**Steps**
1. Open any terminal directory
2. Run `claude` to start an interactive session
3. Type `/mcp` → verify `lab-registry · ✔ connected · 5 tools`
4. Ask:

```
List all skills available in the lab registry
```
Expected: same list as Copilot

```
Use the lab-registry tool to get the full content of the research skill
```
Expected: structured response with `content_raw`

**Validation date**: 2026-07-06 ✅ — `lab-registry · connected · 5 tools`

---

## Cross-Client Consistency Check

Both clients must return identical data for the same query. Run this check after
any change to the server or registry.

| Query | Expected result | Copilot | Claude Code |
|---|---|---|---|
| `list_entries type=skill` | ≥ 36 entries | ✅ | ✅ |
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
