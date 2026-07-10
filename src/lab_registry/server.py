from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from lab_registry.tools.compliance import check_compliance_handler, check_compliance_plugin_handler
from lab_registry.tools.fetch import (
    get_changelog_handler,
    get_entry_by_id_handler,
    get_entry_handler,
    get_plugin_handler,
    get_plugin_install_package_handler,
    list_plugins_handler,
)
from lab_registry.tools.search import list_entries_handler, search_entries_handler, suggest_entries_handler
from lab_registry.tools.stats import get_marketplace_stats_handler
from lab_registry.tools.validate import validate_entry_handler

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
    """Search registry entries by exact keyword or partial name match.

    Searches name, description, and plugin name.
    Name matches are ranked before description matches.
    Optionally restrict results to a specific type.

    Use this when you have a specific keyword or partial name (e.g. "tdd", "android",
    "architecture"). For natural language task descriptions, use suggest_entries instead.
    """
    return search_entries_handler(query=query, type=type)


@mcp.tool()
def get_entry(
    plugin: str,
    type: str,
    name: str,
) -> dict[str, Any]:
    """Get a specific registry entry with its full content.

    Use this to read a single artefact's documentation or to get its install files.
    To get all artefacts of a plugin at once, use get_plugin_install_package instead.

    Returns:
    - entry: structured RegistryEntry fields
    - metadata: parsed YAML frontmatter from the source file
    - content_raw: markdown body below the frontmatter (the actual instructions)
    - content_full: verbatim file content (frontmatter + body), write-ready
    - install_targets: exact destination paths per client (claude_local, copilot,
      plugin_tracking)
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
    """Check whether locally installed gen-e2 plugin artefacts are up to date with the registry.

    Use this whenever the user asks to verify, check, or audit their installed gen-e2 plugins.
    Workflow: discover local plugin.json files (e.g. .claude/plugins/*/plugin.json), read the
    version field from each, then call this tool — do NOT compare versions manually.

    Each item in entries must have:
    - name: artifact name (e.g. "research", "commit-push-pr")
    - type: "skill", "agent", "command", or "hook"
    - plugin: plugin name (e.g. "research-suite", "delivery")
    - local_version: version read from the local plugin.json (e.g. "0.8.0")

    Returns:
    - outdated: entries where local_version != current registry version (includes registry_version)
    - unknown: entries not found in the registry
    - up_to_date_count: number of entries that match the registry
    """
    return check_compliance_handler(entries=entries)


@mcp.tool()
def check_compliance_plugin(plugin: str, local_version: str) -> dict[str, Any]:
    """Check all artefacts of a gen-e2 plugin against a single local version.

    Use this when you have a plugin.json with one version field and want to verify
    the whole plugin in one call, instead of listing artefacts manually and calling
    check_compliance with each one.

    Typical workflow:
      1. Read .claude/plugins/<name>/plugin.json → get local version
      2. Call check_compliance_plugin(plugin=<name>, local_version=<version>)

    Returns the same shape as check_compliance:
    - outdated: artefacts where local_version != registry version (includes registry_version)
    - unknown: artefacts not found in the registry
    - up_to_date_count: number of matching artefacts
    """
    return check_compliance_plugin_handler(plugin=plugin, local_version=local_version)


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


@mcp.tool()
def list_plugins() -> list[dict[str, Any]]:
    """List all plugins with version, description, and entry counts per type.

    Returns one entry per plugin sorted alphabetically, with:
    - name, version, description, tags, author
    - entry_counts: {skill, agent, command, hook, total}
    """
    return list_plugins_handler()


@mcp.tool()
def get_entry_by_id(id: str) -> dict[str, Any]:
    """Get a registry entry by its full ID (plugin/type/name).

    Shortcut for get_entry when you already have the entry ID from list_entries.
    Returns same shape as get_entry: {entry, metadata, content_raw}.

    Example: id="android/skill/android-architecture"
    """
    return get_entry_by_id_handler(id=id)


@mcp.tool()
def get_changelog(plugin: str) -> dict[str, Any]:
    """Get the full CHANGELOG.md content for a plugin.

    Useful after check_compliance signals an outdated entry — shows what
    changed between versions without leaving the MCP context.

    Returns:
    - plugin: plugin name
    - version: current version
    - changelog_raw: full CHANGELOG.md text (null if absent)
    """
    return get_changelog_handler(plugin=plugin)


@mcp.tool()
def get_marketplace_stats() -> dict[str, Any]:
    """Get a dashboard overview of the entire registry.

    Returns:
    - total_entries, total_plugins
    - by_type: entry counts per artifact type
    - by_plugin: per-plugin breakdown with version and counts
    - last_updated: most recent CHANGELOG date across all plugins
    - plugins_without_changelog: plugins missing a CHANGELOG.md
    """
    return get_marketplace_stats_handler()


@mcp.tool()
def suggest_entries(
    task: str,
    type: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Suggest registry entries relevant to a natural language task description.

    Splits the task into individual terms and scores entries by how many terms
    appear in their name, description, plugin name, and tags. Returns entries
    ranked by relevance score with matched_terms listed.

    Use this for natural language queries (e.g. "I need to review architecture and
    create ADRs", "write tests for a Go service"). For exact keyword or partial name
    matching, use search_entries instead.

    - task: natural language description of what you need
    - type: optional type filter ("skill", "agent", "command", "hook")
    - limit: max results to return (default 5)
    """
    return suggest_entries_handler(task=task, type=type, limit=limit)


@mcp.tool()
def validate_entry(content: str, type: str) -> dict[str, Any]:
    """Validate a skill/agent/command markdown file against the marketplace schema.

    Checks required fields, recommended fields, body content, and naming conventions.

    - content: full file content including YAML frontmatter
    - type: "skill", "agent", "command", or "hook"

    Returns:
    - valid: bool
    - errors: blocking schema violations
    - warnings: non-blocking recommendations
    - parsed: the parsed YAML frontmatter
    """
    return validate_entry_handler(content=content, type=type)


@mcp.tool()
def get_plugin_install_package(plugin: str) -> dict[str, Any]:
    """Get full documentation AND install-ready files for an entire plugin in one call.

    Use this whenever the user wants to:
    - install a plugin into their project
    - get the documentation and install files for a plugin
    - know where to place a plugin's artefacts in their project

    Returns all artefacts with:
    - content_full: verbatim file content (frontmatter + body), write-ready — use
      this to write the file directly without any reconstruction
    - install_targets: exact destination paths per client:
        claude_local  → .claude/skills|agents|commands/{name}/...
        copilot       → .github/skills|agents|prompts/{name}/...
        plugin_tracking → .claude/plugins/{plugin}/plugin.json
    - plugin_tracking: the plugin.json content to write for compliance tracking

    Prefer this over multiple get_entry calls when working with a full plugin.
    """
    return get_plugin_install_package_handler(plugin=plugin)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
