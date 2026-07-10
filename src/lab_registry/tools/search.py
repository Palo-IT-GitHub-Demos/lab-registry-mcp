from __future__ import annotations

from typing import Any

from lab_registry.registry import get_all_entries, get_all_plugins


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

    return [e.summary_dump() for e in entries]


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

    return [e.summary_dump() for e in name_matches + desc_matches]


def suggest_entries_handler(
    task: str,
    type: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Multi-term scoring: rank entries by how many task words match name/description/plugin.

    Returns entries with a 'score' and 'matched_terms' field added.
    """
    # Tokenise: keep words longer than 2 chars, lowercase
    terms = [t.lower() for t in task.replace("-", " ").split() if len(t) > 2]
    if not terms:
        return []

    type_lower = type.lower() if type else None
    entries = get_all_entries()
    if type_lower:
        entries = [e for e in entries if e.type == type_lower]

    scored: list[tuple[int, Any, list[str]]] = []
    for entry in entries:
        text = f"{entry.name} {entry.description} {entry.plugin} {' '.join(entry.tags)}".lower()
        matched = [t for t in terms if t in text]
        score = sum(text.count(t) for t in matched)
        if score > 0:
            scored.append((score, entry, matched))

    scored.sort(key=lambda x: x[0], reverse=True)

    result = []
    for score, entry, matched in scored[:limit]:
        row = entry.summary_dump()
        row["score"] = score
        row["matched_terms"] = matched
        result.append(row)
    return result


def suggest_plugins_handler(
    task: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Plugin-level recommendation: rank plugins by how many task words match name/description/tags.

    Returns plugins sorted by relevance score with 'score' and 'matched_terms' added.
    Name matches are weighted 3x higher than description/tag matches.
    """
    terms = [t.lower() for t in task.replace("-", " ").split() if len(t) > 2]
    if not terms:
        return []

    plugins = get_all_plugins()
    scored: list[tuple[int, str, Any, list[str]]] = []

    for name, plugin in plugins.items():
        name_text = name.lower()
        body_text = f"{plugin.description} {' '.join(plugin.tags)}".lower()
        matched = [t for t in terms if t in name_text or t in body_text]
        if not matched:
            continue
        name_score = sum(name_text.count(t) for t in matched) * 3
        body_score = sum(body_text.count(t) for t in matched)
        score = name_score + body_score
        scored.append((score, name, plugin, matched))

    scored.sort(key=lambda x: x[0], reverse=True)

    result = []
    for score, name, plugin, matched in scored[:limit]:
        row = plugin.model_dump(exclude_none=True)
        row["score"] = score
        row["matched_terms"] = matched
        result.append(row)
    return result
