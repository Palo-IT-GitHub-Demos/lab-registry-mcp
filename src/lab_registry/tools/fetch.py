from __future__ import annotations

import json as _json
from typing import Any

from lab_registry.registry import (
    find_entry,
    get_all_entries,
    get_all_plugins,
    get_entry_content,
)
from lab_registry.models import RegistryEntry


def _install_targets(entry: RegistryEntry) -> dict[str, str]:
    """Return the canonical install paths for each supported AI client."""
    t = entry.type.value  # "skill", "agent", "command", "hook"
    n = entry.name
    p = entry.plugin
    targets: dict[str, str] = {"plugin_tracking": f".claude/plugins/{p}/plugin.json"}
    if t == "skill":
        targets["claude_local"] = f".claude/skills/{n}/SKILL.md"
        targets["copilot"]      = f".github/skills/{n}/SKILL.md"
    elif t == "agent":
        targets["claude_local"] = f".claude/agents/{n}.md"
        targets["copilot"]      = f".github/agents/{n}.agent.md"
    elif t == "command":
        targets["claude_local"] = f".claude/commands/{n}.md"
        targets["copilot"]      = f".github/prompts/{n}.prompt.md"
    else:  # hook
        targets["claude_local"] = f".claude/hooks/{n}.json"
        targets["copilot"]      = f".github/hooks/{n}.json"
    return targets


def get_entry_handler(plugin: str, type: str, name: str) -> dict[str, Any]:
    entry = find_entry(plugin, type, name)
    if entry is None:
        return {"error": f"Entry '{plugin}/{type}/{name}' not found in registry"}

    metadata, content_raw, content_full = get_entry_content(entry)
    return {
        "entry": entry.model_dump(),
        "metadata": metadata,
        "content_raw": content_raw,
        "content_full": content_full,
        "install_targets": _install_targets(entry),
    }


def get_entry_by_id_handler(id: str) -> dict[str, Any]:
    parts = id.strip().split("/")
    if len(parts) != 3:
        return {"error": f"Invalid entry ID '{id}'. Expected format: 'plugin/type/name'"}
    plugin, type_, name = parts
    return get_entry_handler(plugin=plugin, type=type_, name=name)


def get_plugin_handler(plugin: str) -> dict[str, Any]:
    plugins = get_all_plugins()
    manifest = plugins.get(plugin)
    if manifest is None:
        return {"error": f"Plugin '{plugin}' not found in registry"}

    entries = [e for e in get_all_entries() if e.plugin == plugin]
    return {
        "manifest": manifest.model_dump(),
        "entries": [e.summary_dump() for e in entries],
    }


def list_plugins_handler() -> list[dict[str, Any]]:
    plugins = get_all_plugins()
    all_entries = get_all_entries()

    result = []
    for name, plugin in sorted(plugins.items()):
        plugin_entries = [e for e in all_entries if e.plugin == name]
        counts: dict[str, int] = {"skill": 0, "agent": 0, "command": 0, "hook": 0}
        for e in plugin_entries:
            counts[e.type] = counts.get(e.type, 0) + 1

        row = plugin.model_dump(exclude_none=True)
        if not row.get("tags"):
            row.pop("tags", None)
        row["entry_counts"] = {**counts, "total": len(plugin_entries)}
        result.append(row)

    return result


def get_plugin_install_package_handler(plugin: str) -> dict[str, Any]:
    """Return a complete install package: all artefacts with content_full + install_targets."""
    plugins = get_all_plugins()
    manifest = plugins.get(plugin)
    if manifest is None:
        return {"error": f"Plugin '{plugin}' not found in registry"}

    entries = [e for e in get_all_entries() if e.plugin == plugin]
    files = []
    for entry in entries:
        metadata, content_raw, content_full = get_entry_content(entry)
        files.append({
            "id": entry.id,
            "type": entry.type,
            "name": entry.name,
            "content_full": content_full,
            "install_targets": _install_targets(entry),
        })

    plugin_json_content = _json.dumps({
        "name": plugin,
        "version": manifest.version,
        "description": manifest.description,
    }, indent=2)

    return {
        "plugin": manifest.model_dump(),
        "files": files,
        "plugin_tracking": {
            "path": f".claude/plugins/{plugin}/plugin.json",
            "content": plugin_json_content,
        },
    }


def get_changelog_handler(plugin: str) -> dict[str, Any]:
    from lab_registry.registry import get_plugin_changelog  # noqa: PLC0415
    plugins = get_all_plugins()
    if plugin not in plugins:
        return {"error": f"Plugin '{plugin}' not found in registry"}

    changelog = get_plugin_changelog(plugin)
    if changelog is None:
        return {
            "plugin": plugin,
            "version": plugins[plugin].version,
            "changelog_raw": None,
            "warning": "No CHANGELOG.md found for this plugin",
        }
    return {
        "plugin": plugin,
        "version": plugins[plugin].version,
        "changelog_raw": changelog,
    }
