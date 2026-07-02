from __future__ import annotations

from typing import Any

from lab_registry.registry import get_all_entries


def list_entries_handler(
    type: str | None = None,
    plugin: str | None = None,
    tags: list[str] | None = None,
) -> list[dict[str, Any]]:
    entries = get_all_entries()

    if type:
        type_lower = type.lower()
        entries = [e for e in entries if e.type == type_lower]
    if plugin:
        entries = [e for e in entries if e.plugin == plugin]
    if tags:
        tag_set = set(tags)
        entries = [e for e in entries if tag_set.intersection(e.tags)]

    return [e.model_dump() for e in entries]


def search_entries_handler(
    query: str,
    type: str | None = None,
) -> list[dict[str, Any]]:
    """Name matches rank above description matches."""
    query_lower = query.lower()
    type_lower = type.lower() if type else None
    entries = get_all_entries()

    name_matches: list = []
    desc_matches: list = []

    for entry in entries:
        if type_lower and entry.type != type_lower:
            continue
        if query_lower in entry.name.lower():
            name_matches.append(entry)
        elif (
            query_lower in entry.description.lower()
            or query_lower in entry.plugin.lower()
        ):
            desc_matches.append(entry)

    return [e.model_dump() for e in name_matches + desc_matches]
