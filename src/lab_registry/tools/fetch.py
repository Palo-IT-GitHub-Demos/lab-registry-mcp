from __future__ import annotations

from typing import Any

from lab_registry.registry import (
    find_entry,
    get_all_entries,
    get_all_plugins,
    get_entry_content,
)


def get_entry_handler(plugin: str, type: str, name: str) -> dict[str, Any]:
    entry = find_entry(plugin, type, name)
    if entry is None:
        return {"error": f"Entry '{plugin}/{type}/{name}' not found in registry"}

    metadata, content_raw = get_entry_content(entry)
    return {
        "entry": entry.model_dump(),
        "metadata": metadata,
        "content_raw": content_raw,
    }


def get_plugin_handler(plugin: str) -> dict[str, Any]:
    plugins = get_all_plugins()
    manifest = plugins.get(plugin)
    if manifest is None:
        return {"error": f"Plugin '{plugin}' not found in registry"}

    entries = [e for e in get_all_entries() if e.plugin == plugin]
    return {
        "manifest": manifest.model_dump(),
        "entries": [e.model_dump() for e in entries],
    }
