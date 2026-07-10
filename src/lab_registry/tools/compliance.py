from __future__ import annotations

from typing import Any

from lab_registry.registry import find_entry, get_all_entries


def check_compliance_handler(entries: list[dict[str, Any]]) -> dict[str, Any]:
    outdated: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []

    for item in entries:
        name = str(item.get("name", ""))
        type_ = str(item.get("type", ""))
        plugin = str(item.get("plugin", ""))
        local_version = str(item.get("local_version", ""))

        registry_entry = find_entry(plugin, type_, name)
        if registry_entry is None:
            unknown.append({"name": name, "type": type_, "plugin": plugin})
        elif registry_entry.plugin_version != local_version:
            outdated.append({
                "name": name,
                "type": type_,
                "plugin": plugin,
                "local_version": local_version,
                "registry_version": registry_entry.plugin_version,
            })

    return {
        "outdated": outdated,
        "unknown": unknown,
        "up_to_date_count": len(entries) - len(outdated) - len(unknown),
    }


def check_compliance_plugin_handler(plugin: str, local_version: str) -> dict[str, Any]:
    """Shortcut: check all artefacts of a plugin against a single local version.

    Equivalent to calling get_plugin to list artefacts, then check_compliance
    with each one at local_version. Returns the same shape as check_compliance.
    """
    entries_in_plugin = [
        {"name": e.name, "type": e.type.value, "plugin": e.plugin, "local_version": local_version}
        for e in get_all_entries()
        if e.plugin == plugin
    ]
    if not entries_in_plugin:
        return {"error": f"Plugin '{plugin}' not found in registry"}
    return check_compliance_handler(entries_in_plugin)
