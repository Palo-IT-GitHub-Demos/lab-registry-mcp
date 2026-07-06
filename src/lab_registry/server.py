from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from lab_registry.tools.compliance import check_compliance_handler
from lab_registry.tools.fetch import get_entry_handler, get_plugin_handler
from lab_registry.tools.search import list_entries_handler, search_entries_handler

mcp = FastMCP(
    "lab-registry",
    instructions="Gen-e2 Lab Registry — canonical skill/agent/hook library for the Innovation Lab",
)


@mcp.tool()
def list_entries(
    type: str | None = None,
    plugin: str | None = None,
    tags: list[str] | None = None,
) -> list[dict[str, Any]]:
    """List all registry entries.

    Filter by:
    - type: "skill", "agent", "command", or "hook"
    - plugin: plugin name (e.g. "android", "delivery", "research-suite")
    - tags: list of keywords (OR match — any tag must match)
    """
    return list_entries_handler(type=type, plugin=plugin, tags=tags)


@mcp.tool()
def search_entries(
    query: str,
    type: str | None = None,
) -> list[dict[str, Any]]:
    """Search registry entries by keyword.

    Searches name, description, and plugin name.
    Name matches are ranked before description matches.
    Optionally restrict results to a specific type.
    """
    return search_entries_handler(query=query, type=type)


@mcp.tool()
def get_entry(
    plugin: str,
    type: str,
    name: str,
) -> dict[str, Any]:
    """Get a specific registry entry with its full content.

    Returns:
    - entry: structured RegistryEntry fields
    - metadata: parsed YAML frontmatter from the source file
    - content_raw: markdown body below the frontmatter (the actual instructions)
    """
    return get_entry_handler(plugin=plugin, type=type, name=name)


@mcp.tool()
def get_plugin(plugin: str) -> dict[str, Any]:
    """Get all registry entries for a plugin, plus its manifest.

    Returns:
    - manifest: Plugin metadata (name, version, description, tags)
    - entries: list of all RegistryEntry objects in the plugin
    """
    return get_plugin_handler(plugin=plugin)


@mcp.tool()
def check_compliance(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Check local entries against the registry.

    Each item in entries must have:
    - name: artifact name (e.g. "android-architecture")
    - type: "skill", "agent", "command", or "hook"
    - plugin: plugin name (e.g. "android")
    - local_version: version currently used locally (e.g. "0.1.0")

    Returns:
    - outdated: entries where local_version != current registry version
    - unknown: entries not found in the registry
    - up_to_date_count: number of entries that match the registry
    """
    return check_compliance_handler(entries=entries)


@mcp.tool()
def reload_registry() -> dict[str, Any]:
    """Force reload the registry from its source (GitHub or local path).

    Clears the in-memory cache and re-fetches all entries.
    Use after a marketplace update (git pull / new commit) to get fresh data
    without restarting the server.

    Returns a diff vs the previous state:
    - added: entry IDs new in this reload
    - removed: entry IDs no longer present
    - modified: entry IDs whose plugin_version changed
    - total: total number of entries after reload
    """
    from lab_registry.registry import load_registry  # noqa: PLC0415

    old = {e.id: e.plugin_version for e in load_registry()[0]}
    load_registry.cache_clear()
    new = {e.id: e.plugin_version for e in load_registry()[0]}

    return {
        "added":    [id for id in new if id not in old],
        "removed":  [id for id in old if id not in new],
        "modified": [id for id in new if id in old and new[id] != old[id]],
        "total":    len(new),
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
