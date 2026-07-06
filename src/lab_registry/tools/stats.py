from __future__ import annotations

from typing import Any

from lab_registry.registry import get_all_entries, get_all_plugins


def get_marketplace_stats_handler() -> dict[str, Any]:
    entries = get_all_entries()
    plugins = get_all_plugins()

    # Counts by type
    by_type: dict[str, int] = {"skill": 0, "agent": 0, "command": 0, "hook": 0}
    for e in entries:
        by_type[e.type] = by_type.get(e.type, 0) + 1

    # Per-plugin breakdown
    by_plugin = []
    for name, plugin in sorted(plugins.items()):
        plugin_entries = [e for e in entries if e.plugin == name]
        counts: dict[str, int] = {"skill": 0, "agent": 0, "command": 0, "hook": 0}
        for e in plugin_entries:
            counts[e.type] = counts.get(e.type, 0) + 1
        by_plugin.append({
            "name": name,
            "version": plugin.version,
            "total": len(plugin_entries),
            "counts": counts,
        })

    # Last updated: most recent updated_at across all entries
    dates = [e.updated_at for e in entries if e.updated_at]
    last_updated = max(dates) if dates else None

    # Plugins without CHANGELOG.md (updated_at is None for all their entries)
    plugins_without_changelog = sorted({
        e.plugin for e in entries
        if e.updated_at is None
        and all(x.updated_at is None for x in entries if x.plugin == e.plugin)
    })

    return {
        "total_entries": len(entries),
        "total_plugins": len(plugins),
        "by_type": by_type,
        "by_plugin": by_plugin,
        "last_updated": last_updated,
        "plugins_without_changelog": plugins_without_changelog,
    }
