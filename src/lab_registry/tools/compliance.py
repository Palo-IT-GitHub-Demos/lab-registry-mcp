from __future__ import annotations

from typing import Any

from lab_registry.registry import find_entry


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
                "current_version": registry_entry.plugin_version,
            })

    return {
        "outdated": outdated,
        "unknown": unknown,
        "up_to_date_count": len(entries) - len(outdated) - len(unknown),
    }
