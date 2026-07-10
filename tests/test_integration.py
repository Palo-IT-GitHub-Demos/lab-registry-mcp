"""Integration tests against the real gen-e2-marketplace registry.

Run with:
    REGISTRY_PATH=/path/to/gen-e2-marketplace pytest tests/test_integration.py -v

Skipped automatically if REGISTRY_PATH is not set or does not contain
the expected marketplace.json.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

REGISTRY_PATH = os.environ.get("REGISTRY_PATH", "")
MARKETPLACE_EXISTS = bool(
    REGISTRY_PATH
    and (Path(REGISTRY_PATH) / ".claude-plugin" / "marketplace.json").exists()
)

skip_if_no_registry = pytest.mark.skipif(
    not MARKETPLACE_EXISTS,
    reason="REGISTRY_PATH not set or marketplace.json not found",
)


@pytest.fixture(scope="module", autouse=True)
def use_real_registry():
    """Override the session-scoped mock env with the real registry for this module."""
    from lab_registry.registry import load_registry

    old = os.environ.get("REGISTRY_PATH")
    os.environ["REGISTRY_PATH"] = REGISTRY_PATH
    load_registry.cache_clear()
    yield
    if old is not None:
        os.environ["REGISTRY_PATH"] = old
    else:
        os.environ.pop("REGISTRY_PATH", None)
    load_registry.cache_clear()


@pytest.fixture(scope="module")
def real_entries():
    """Return (entries, plugins) from the real marketplace (loaded once per module)."""
    from lab_registry.registry import load_registry

    return load_registry()


@skip_if_no_registry
def test_real_entry_count(real_entries):
    entries, _ = real_entries
    assert len(entries) >= 50, f"Expected ≥50 entries, got {len(entries)}"


@skip_if_no_registry
def test_real_ids_are_unique(real_entries):
    entries, _ = real_entries
    ids = [e.id for e in entries]
    assert len(ids) == len(set(ids)), "Duplicate entry IDs found"


@skip_if_no_registry
def test_real_no_empty_names(real_entries):
    entries, _ = real_entries
    bad = [e.id for e in entries if not e.name.strip()]
    assert bad == [], f"Entries with empty name: {bad}"


@skip_if_no_registry
def test_real_no_empty_descriptions(real_entries):
    entries, _ = real_entries
    bad = [e.id for e in entries if not e.description.strip()]
    assert bad == [], f"Entries with empty description: {bad}"


@skip_if_no_registry
def test_real_get_entry_content_readable(real_entries):
    """Every non-hook entry must have a readable, non-empty markdown body."""
    from lab_registry.registry import get_entry_content

    entries, _ = real_entries
    errors: list[tuple[str, str]] = []
    for entry in entries:
        if entry.type == "hook":
            continue
        try:
            _, body, _full = get_entry_content(entry)
            if not body.strip():
                errors.append((entry.id, "empty body"))
        except Exception as exc:
            errors.append((entry.id, str(exc)))

    assert errors == [], f"get_entry_content failed for: {errors}"


@skip_if_no_registry
def test_real_all_plugins_have_version(real_entries):
    _, plugins = real_entries
    bad = [name for name, p in plugins.items() if not p.version or p.version == "0.0.0"]
    assert bad == [], f"Plugins with missing/fallback version: {bad}"


@skip_if_no_registry
def test_server_tools_registered():
    """server.py must import cleanly and expose exactly 5 tools."""
    spec = importlib.util.spec_from_file_location(
        "lab_registry.server", "src/lab_registry/server.py"
    )
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

    tools = mod.mcp._tool_manager.list_tools()
    tool_names = {t.name for t in tools}
    expected = {
        "list_entries", "search_entries", "get_entry", "get_plugin",
        "check_compliance", "check_compliance_plugin", "reload_registry",
        "list_plugins", "get_entry_by_id", "get_changelog",
        "get_marketplace_stats", "suggest_entries", "validate_entry",
        "get_plugin_install_package",
    }
    assert tool_names == expected, f"Registered tools: {tool_names}"


# ===========================================================================
# Day 3 additions: artifact type coverage, ID format, handler integration
# ===========================================================================

@skip_if_no_registry
def test_real_all_four_artifact_types_present(real_entries):
    """The real marketplace must contain at least one entry of every artifact type."""
    from lab_registry.models import ArtifactType
    entries, _ = real_entries
    found_types = {e.type for e in entries}
    for expected_type in ArtifactType:
        assert expected_type in found_types, f"No entries of type '{expected_type}' found"


@skip_if_no_registry
def test_real_entry_id_format(real_entries):
    """Every entry ID must follow '{plugin}/{type}/{name}' exactly."""
    entries, _ = real_entries
    for e in entries:
        parts = e.id.split("/")
        assert len(parts) == 3, f"Bad ID: {e.id}"
        assert parts[0] == e.plugin, f"ID plugin mismatch: {e.id}"
        assert parts[1] == e.type, f"ID type mismatch: {e.id}"
        assert parts[2] == e.name, f"ID name mismatch: {e.id}"


@skip_if_no_registry
def test_real_command_has_argument_hint(real_entries):
    """At least one command in the real registry must carry an argument_hint."""
    entries, _ = real_entries
    commands = [e for e in entries if e.type == "command"]
    assert len(commands) > 0, "No command entries found"
    hints = [e for e in commands if e.argument_hint]
    assert len(hints) > 0, f"No command has argument_hint (checked {len(commands)} commands)"


@skip_if_no_registry
def test_real_hook_has_non_empty_hook_events(real_entries):
    """Every hook entry must list at least one event type."""
    entries, _ = real_entries
    hooks = [e for e in entries if e.type == "hook"]
    assert len(hooks) > 0, "No hook entries found"
    for h in hooks:
        assert len(h.hook_events) > 0, f"Hook {h.id} has empty hook_events"


@skip_if_no_registry
def test_real_list_entries_combined_plugin_and_type_filter(real_entries):
    """list_entries with both plugin and type filters must return their intersection."""
    from lab_registry.tools.search import list_entries_handler
    result = list_entries_handler(plugin="android", type="skill")
    assert len(result) >= 5, f"Expected ≥5 android skills, got {len(result)}"
    assert all(r["plugin"] == "android" for r in result), "Combined filter leaked non-android"
    assert all(r["type"] == "skill" for r in result), "Combined filter leaked non-skill"


@skip_if_no_registry
def test_real_search_ranking_name_before_description(real_entries):
    """Name matches must appear before description-only matches in search results."""
    from lab_registry.tools.search import search_entries_handler
    results = search_entries_handler(query="android")
    if len(results) < 2:
        pytest.skip("Not enough results to verify ranking")
    name_positions = [i for i, r in enumerate(results) if "android" in r["name"]]
    desc_positions = [i for i, r in enumerate(results) if "android" not in r["name"]]
    if name_positions and desc_positions:
        assert max(name_positions) < min(desc_positions), (
            "Description-only matches appeared before name matches in real data"
        )


@skip_if_no_registry
def test_real_get_plugin_handler_android(real_entries):
    """get_plugin for 'android' must return a valid manifest and ≥14 entries."""
    from lab_registry.tools.fetch import get_plugin_handler
    result = get_plugin_handler(plugin="android")
    assert "error" not in result
    assert result["manifest"]["name"] == "android"
    assert result["manifest"]["version"], "Android plugin must have a version"
    assert len(result["entries"]) >= 14, f"Expected ≥14 android entries, got {len(result['entries'])}"


@skip_if_no_registry
def test_real_compliance_count_math(real_entries):
    """up_to_date_count + outdated + unknown must equal input length for real data."""
    from lab_registry.tools.compliance import check_compliance_handler
    entries, plugins = real_entries
    # Build a compliance payload mixing correct + incorrect versions
    android_version = plugins["android"].version
    test_payload = [
        {"name": "android-architecture", "type": "skill", "plugin": "android",
         "local_version": android_version},           # up-to-date
        {"name": "android-architecture", "type": "skill", "plugin": "android",
         "local_version": "0.0.0-old"},               # outdated
        {"name": "ghost-entry", "type": "skill", "plugin": "android",
         "local_version": "1.0.0"},                   # unknown
    ]
    result = check_compliance_handler(entries=test_payload)
    total = result["up_to_date_count"] + len(result["outdated"]) + len(result["unknown"])
    assert total == len(test_payload)
