# Lab Registry Server — Copilot Instructions

## What this project is
MCP server (Python, FastMCP) exposing the Gen-e2 Lab Registry — skills, agents, commands, and hooks
from the `gen-e2-marketplace` repo — via the Model Context Protocol.
Designed to work identically from Claude Code and GitHub Copilot agent mode (stdio transport).

## Architecture
```
src/lab_registry/
├── server.py      # FastMCP entry; all @mcp.tool() decorators live here
├── registry.py    # Indexer: reads REGISTRY_PATH at first call, lru_cache'd
├── models.py      # Pydantic: RegistryEntry, Plugin
└── tools/
    ├── search.py      # list_entries_handler, search_entries_handler
    ├── fetch.py       # get_entry_handler, get_plugin_handler
    └── compliance.py  # check_compliance_handler
```

## Conventions
- Python 3.12+, `from __future__ import annotations`, type hints everywhere
- Handler functions are pure — no side effects beyond reading the filesystem
- Registry is **read-only**; never write to `REGISTRY_PATH`
- On error: return `{"error": "message"}`, never raise inside a tool handler
- Tool return types: `dict[str, Any]` or `list[dict[str, Any]]` (JSON-serializable)
- `REGISTRY_PATH` env var → `gen-e2-marketplace` repo root

## Run locally
```bash
# Install
pip install -e ".[dev]"

# Dev mode with MCP Inspector (browser UI at http://localhost:5173)
mcp dev src/lab_registry/server.py

# Stdio run (for client config)
REGISTRY_PATH=/path/to/gen-e2-marketplace mcp run src/lab_registry/server.py

# Tests
pytest tests/ -v
```

## Adding a new tool
1. Add handler to `src/lab_registry/tools/<category>.py`
2. Register in `server.py` with `@mcp.tool()` + clear docstring
3. Write tests in `tests/test_tools_<category>.py`
4. Update the Tools table below

## Client config

### Claude Code — `.claude/settings.json`
```json
{
  "mcpServers": {
    "lab-registry": {
      "command": "mcp",
      "args": ["run", "/abs/path/to/lab-registry-server/src/lab_registry/server.py"],
      "env": { "REGISTRY_PATH": "/abs/path/to/gen-e2-marketplace" }
    }
  }
}
```

### GitHub Copilot agent mode — `.vscode/mcp.json`
```json
{
  "servers": {
    "lab-registry": {
      "type": "stdio",
      "command": "mcp",
      "args": ["run", "${workspaceFolder}/../lab-registry-server/src/lab_registry/server.py"],
      "env": { "REGISTRY_PATH": "${workspaceFolder}" }
    }
  }
}
```

## Tools
| Tool | Description |
|------|-------------|
| `list_entries` | List entries — filter by type / plugin / tags |
| `search_entries` | Keyword search (name + description); name matches rank higher |
| `get_entry` | Full content: `entry` + `metadata` (frontmatter) + `content_raw` (body) |
| `get_plugin` | All entries for one plugin + its manifest |
| `check_compliance` | Diff `local_version` vs registry; returns `outdated` + `unknown` |

## Known gaps (documented, not bugs)
- No per-artifact deprecation flag (absent from gen-e2 format; `check_compliance` detects version drift only)
- `updated_at` is best-effort (parsed from CHANGELOG.md; `null` if absent)
- Hooks are indexed one entry per plugin (not per event type)
