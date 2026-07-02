---
name: python-mcp-patterns
description: FastMCP patterns for lab-registry-server. Use when writing or reviewing MCP tool handlers, registering tools in server.py, writing pytest tests for MCP tools, or configuring the server in Claude Code / Copilot mcp.json. Triggers on "mcp.tool", "FastMCP", "@mcp.tool()", "tool handler pattern", "mcp dev", "tool registration".
model: sonnet
allowed-tools:
  - Read
  - Grep
---
# Python MCP Patterns — lab-registry-server

## Tool registration in server.py

```python
from mcp.server.fastmcp import FastMCP
from lab_registry.tools.search import list_entries_handler

mcp = FastMCP("lab-registry", description="...")

@mcp.tool()
def list_entries(type: str | None = None) -> list[dict]:
    """Docstring becomes the tool description the LLM and client see.
    Keep it clear: what it does, what parameters mean, what it returns."""
    return list_entries_handler(type=type)

def main() -> None:
    mcp.run()
```

## Handler function pattern (tools/*.py)

```python
# tools/search.py — pure function, JSON-serializable return
from lab_registry.registry import get_all_entries

def list_entries_handler(type: str | None = None) -> list[dict]:
    entries = get_all_entries()
    if type:
        entries = [e for e in entries if e.type == type.lower()]
    return [e.model_dump() for e in entries]
```

Rules:
- Never raise inside a handler — return `{"error": "message"}` instead
- Return `list[dict]` or `dict`, never Pydantic model instances
- Normalize user-supplied `type` strings with `.lower()`
- Access registry only through `registry.py` public functions

## pytest pattern

```python
# tests/test_tools_search.py
from lab_registry.tools.search import list_entries_handler

def test_filter_by_type():
    result = list_entries_handler(type="skill")
    assert all(r["type"] == "skill" for r in result)

def test_unknown_plugin_empty():
    assert list_entries_handler(plugin="nonexistent") == []
```

The session fixture in `conftest.py` sets `REGISTRY_PATH` and clears `load_registry.cache_clear()` once for all tests — nothing extra needed per test.

## Running locally

```bash
# Install dev deps
pip install -e ".[dev]"

# Dev mode (MCP Inspector at http://localhost:5173)
mcp dev src/lab_registry/server.py

# Stdio run
REGISTRY_PATH=/path/to/gen-e2-marketplace mcp run src/lab_registry/server.py

# Tests
pytest tests/ -v
```

## Client configs

### Claude Code — add to `.claude/settings.json`
```json
{
  "mcpServers": {
    "lab-registry": {
      "command": "mcp",
      "args": ["run", "/abs/path/to/src/lab_registry/server.py"],
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
