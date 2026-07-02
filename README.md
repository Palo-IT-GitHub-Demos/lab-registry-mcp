# Lab Registry Server

MCP server exposing the Gen-e2 Lab Registry — skills, agents, commands, and hooks from the Innovation Lab at Palo IT Singapore.

## Install

```bash
pip install -e ".[dev]"
# or: uv pip install -e ".[dev]"
```

## Configure

Copy `.env.example` to `.env` and set `REGISTRY_PATH` to the `gen-e2-marketplace` repo root.

## Run

```bash
# Dev mode with MCP Inspector
mcp dev src/lab_registry/server.py

# Tests
pytest tests/ -v
```

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
| `search_entries` | Keyword search over name + description |
| `get_entry` | Full content: parsed metadata + raw markdown body |
| `get_plugin` | All entries for one plugin + its manifest |
| `check_compliance` | Diff local versions against registry |
