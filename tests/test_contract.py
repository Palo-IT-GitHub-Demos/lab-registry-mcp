"""Contract tests: validate the exact shape and types of every tool response.

Uses the mock registry from conftest.py — no REGISTRY_PATH needed.
Guarantees that both Claude Code and Copilot see a stable, documented API surface,
and that any handler refactor that breaks the contract is caught immediately.
"""
from __future__ import annotations

import pytest

from lab_registry.tools.compliance import check_compliance_handler
from lab_registry.tools.fetch import get_entry_handler, get_plugin_handler
from lab_registry.tools.search import list_entries_handler, search_entries_handler

# ---------------------------------------------------------------------------
# Expected schemas (mirrors RegistryEntry and Plugin model_dump() shapes)
# ---------------------------------------------------------------------------

# Core keys always present in summary_dump() (list/search operations)
ENTRY_SUMMARY_KEYS = {
    "id", "name", "type", "plugin", "plugin_version", "description", "tags",
}

# All keys present in model_dump() (get_entry "entry" field — full serialization)
ENTRY_FULL_KEYS = {
    "id", "name", "type", "plugin", "plugin_version",
    "description", "path", "updated_at", "tags",
    "disable_model_invocation", "model", "allowed_tools",
    "context", "agent_skills", "argument_hint", "hook_events",
}

# Backward-compatible alias used by tests that pre-date the lean serialization
ENTRY_REQUIRED_KEYS = ENTRY_SUMMARY_KEYS

PLUGIN_MANIFEST_KEYS = {"name", "version", "description", "tags", "author", "plugin_license"}

VALID_TYPES = {"skill", "agent", "command", "hook"}


# ===========================================================================
# list_entries contracts
# ===========================================================================

def test_list_entries_returns_list():
    result = list_entries_handler()
    assert isinstance(result, list)


def test_list_entries_all_entry_keys_present():
    result = list_entries_handler()
    assert len(result) > 0
    for entry in result:
        missing = ENTRY_REQUIRED_KEYS - set(entry.keys())
        assert missing == set(), f"Entry '{entry.get('id')}' missing keys: {missing}"


def test_list_entries_type_is_valid_enum_value():
    result = list_entries_handler()
    for entry in result:
        assert entry["type"] in VALID_TYPES, f"Invalid type value: {entry['type']}"


def test_list_entries_id_format():
    """id must follow the '{plugin}/{type}/{name}' convention exactly."""
    result = list_entries_handler()
    for entry in result:
        parts = entry["id"].split("/")
        assert len(parts) == 3, f"Bad ID format: {entry['id']}"
        plugin, type_, name = parts
        assert plugin == entry["plugin"], f"ID plugin mismatch: {entry['id']}"
        assert type_ == entry["type"], f"ID type mismatch: {entry['id']}"
        assert name == entry["name"], f"ID name mismatch: {entry['id']}"


def test_list_entries_list_fields_are_always_lists():
    """tags must always be a list; type-specific list fields only when present."""
    result = list_entries_handler()
    for entry in result:
        assert isinstance(entry["tags"], list), f"tags is not list: {entry['id']}"
        for key in ("allowed_tools", "agent_skills", "hook_events"):
            if key in entry:
                assert isinstance(entry[key], list), f"{key} is not list: {entry['id']}"


def test_list_entries_filter_type_returns_only_that_type():
    for type_ in VALID_TYPES:
        result = list_entries_handler(type=type_)
        for entry in result:
            assert entry["type"] == type_, f"Type filter leaked: got {entry['type']} when filtering for {type_}"


def test_list_entries_filter_unknown_plugin_returns_empty_list():
    assert list_entries_handler(plugin="no-such-plugin-xyz") == []


def test_list_entries_filter_unknown_tag_returns_empty_list():
    assert list_entries_handler(tags=["no-such-tag-abc"]) == []


def test_list_entries_combined_plugin_and_type_filter():
    result = list_entries_handler(plugin="test-plugin", type="skill")
    assert len(result) == 1
    assert result[0]["plugin"] == "test-plugin"
    assert result[0]["type"] == "skill"


def test_list_entries_tags_or_match():
    """Tags use OR semantics — any matching tag includes the entry."""
    result_mcp = list_entries_handler(tags=["mcp"])
    result_testing = list_entries_handler(tags=["testing"])
    result_both = list_entries_handler(tags=["mcp", "testing"])
    # OR-match: combined result must be at least as large as each individual
    assert len(result_both) >= len(result_mcp)
    assert len(result_both) >= len(result_testing)


# ===========================================================================
# search_entries contracts
# ===========================================================================

def test_search_entries_returns_list():
    result = search_entries_handler(query="test")
    assert isinstance(result, list)


def test_search_entries_entry_has_all_keys():
    result = search_entries_handler(query="test")
    for entry in result:
        missing = ENTRY_REQUIRED_KEYS - set(entry.keys())
        assert missing == set(), f"Entry '{entry.get('id')}' missing keys: {missing}"


def test_search_entries_name_matches_ranked_before_description_matches():
    """Entries whose name contains the query must come before description-only matches."""
    result = search_entries_handler(query="test")
    name_positions = [i for i, r in enumerate(result) if "test" in r["name"]]
    desc_positions = [i for i, r in enumerate(result) if "test" not in r["name"]]
    if name_positions and desc_positions:
        assert max(name_positions) < min(desc_positions), (
            "Description-only matches appeared before name matches"
        )


def test_search_entries_no_match_returns_empty_list():
    assert search_entries_handler(query="zzz-absolutely-no-match-xyz") == []


def test_search_entries_type_filter_respected():
    result = search_entries_handler(query="test", type="skill")
    assert all(r["type"] == "skill" for r in result)


def test_search_entries_type_filter_invalid_type_returns_empty():
    assert search_entries_handler(query="test", type="nonexistent") == []


# ===========================================================================
# get_entry contracts
# ===========================================================================

def test_get_entry_success_has_expected_top_level_keys():
    result = get_entry_handler(plugin="test-plugin", type="skill", name="test-skill")
    assert {"entry", "metadata", "content_raw", "content_full", "install_targets"} <= set(result.keys())


def test_get_entry_entry_has_all_required_keys():
    result = get_entry_handler(plugin="test-plugin", type="skill", name="test-skill")
    missing = ENTRY_FULL_KEYS - set(result["entry"].keys())
    assert missing == set()


def test_get_entry_metadata_is_dict():
    result = get_entry_handler(plugin="test-plugin", type="skill", name="test-skill")
    assert isinstance(result["metadata"], dict)


def test_get_entry_content_raw_is_non_empty_string():
    result = get_entry_handler(plugin="test-plugin", type="skill", name="test-skill")
    assert isinstance(result["content_raw"], str)
    assert len(result["content_raw"]) > 0


def test_get_entry_content_full_is_non_empty_string():
    result = get_entry_handler(plugin="test-plugin", type="skill", name="test-skill")
    assert isinstance(result["content_full"], str)
    assert len(result["content_full"]) > 0


def test_get_entry_install_targets_has_expected_keys():
    result = get_entry_handler(plugin="test-plugin", type="skill", name="test-skill")
    targets = result["install_targets"]
    assert isinstance(targets, dict)
    assert "claude_local" in targets
    assert "copilot" in targets
    assert "plugin_tracking" in targets


def test_get_entry_not_found_returns_only_error_key():
    result = get_entry_handler(plugin="no-plugin", type="skill", name="nothing")
    assert "error" in result
    assert "entry" not in result
    assert "metadata" not in result
    assert "content_raw" not in result


def test_get_entry_agent_has_agent_skills_list():
    result = get_entry_handler(plugin="test-plugin", type="agent", name="test-agent")
    assert "error" not in result
    assert isinstance(result["entry"]["agent_skills"], list)
    assert "test-skill" in result["entry"]["agent_skills"]


def test_get_entry_command_has_argument_hint_string():
    result = get_entry_handler(plugin="test-plugin", type="command", name="test-command")
    assert "error" not in result
    assert result["entry"]["argument_hint"] == "target-name"


def test_get_entry_hook_has_non_empty_hook_events():
    result = get_entry_handler(plugin="test-plugin", type="hook", name="hooks")
    assert "error" not in result
    assert isinstance(result["entry"]["hook_events"], list)
    assert len(result["entry"]["hook_events"]) > 0
    assert "PostToolUse" in result["entry"]["hook_events"]


def test_get_entry_case_insensitive_type():
    result_lower = get_entry_handler(plugin="test-plugin", type="skill", name="test-skill")
    result_upper = get_entry_handler(plugin="test-plugin", type="Skill", name="test-skill")
    assert "error" not in result_lower
    assert "error" not in result_upper
    assert result_lower["entry"]["id"] == result_upper["entry"]["id"]


# ===========================================================================
# get_plugin contracts
# ===========================================================================

def test_get_plugin_success_has_two_top_level_keys():
    result = get_plugin_handler(plugin="test-plugin")
    assert set(result.keys()) == {"manifest", "entries"}


def test_get_plugin_manifest_has_all_keys():
    result = get_plugin_handler(plugin="test-plugin")
    missing = PLUGIN_MANIFEST_KEYS - set(result["manifest"].keys())
    assert missing == set()


def test_get_plugin_entries_is_list_of_complete_dicts():
    result = get_plugin_handler(plugin="test-plugin")
    assert isinstance(result["entries"], list)
    assert len(result["entries"]) > 0
    for entry in result["entries"]:
        assert isinstance(entry, dict)
        missing = ENTRY_REQUIRED_KEYS - set(entry.keys())
        assert missing == set(), f"Entry missing keys: {missing}"


def test_get_plugin_entries_all_belong_to_plugin():
    result = get_plugin_handler(plugin="test-plugin")
    for entry in result["entries"]:
        assert entry["plugin"] == "test-plugin"


def test_get_plugin_not_found_returns_only_error_key():
    result = get_plugin_handler(plugin="no-such-plugin")
    assert "error" in result
    assert "manifest" not in result
    assert "entries" not in result


# ===========================================================================
# check_compliance contracts
# ===========================================================================

def test_check_compliance_response_has_three_keys():
    result = check_compliance_handler(entries=[])
    assert set(result.keys()) == {"outdated", "unknown", "up_to_date_count"}


def test_check_compliance_up_to_date_count_is_int():
    result = check_compliance_handler(entries=[])
    assert isinstance(result["up_to_date_count"], int)
    assert result["up_to_date_count"] == 0


def test_check_compliance_outdated_item_has_exact_keys():
    result = check_compliance_handler(entries=[
        {"name": "test-skill", "type": "skill", "plugin": "test-plugin", "local_version": "0.0.1"},
    ])
    assert len(result["outdated"]) == 1
    item = result["outdated"][0]
    assert set(item.keys()) == {"name", "type", "plugin", "local_version", "registry_version"}


def test_check_compliance_unknown_item_has_exact_keys():
    result = check_compliance_handler(entries=[
        {"name": "ghost", "type": "skill", "plugin": "test-plugin", "local_version": "1.0.0"},
    ])
    assert len(result["unknown"]) == 1
    item = result["unknown"][0]
    assert set(item.keys()) == {"name", "type", "plugin"}


def test_check_compliance_count_math_invariant():
    """up_to_date_count + len(outdated) + len(unknown) must always equal len(input)."""
    entries = [
        {"name": "test-skill",  "type": "skill",   "plugin": "test-plugin", "local_version": "1.0.0"},  # up-to-date
        {"name": "test-agent",  "type": "agent",   "plugin": "test-plugin", "local_version": "0.0.1"},  # outdated
        {"name": "ghost-entry", "type": "skill",   "plugin": "test-plugin", "local_version": "1.0.0"},  # unknown
        {"name": "test-command","type": "command",  "plugin": "test-plugin", "local_version": "1.0.0"},  # up-to-date
    ]
    result = check_compliance_handler(entries=entries)
    total = result["up_to_date_count"] + len(result["outdated"]) + len(result["unknown"])
    assert total == len(entries), f"Count math failed: {result}"


def test_check_compliance_outdated_carries_both_versions():
    result = check_compliance_handler(entries=[
        {"name": "test-skill", "type": "skill", "plugin": "test-plugin", "local_version": "0.0.1"},
    ])
    item = result["outdated"][0]
    assert item["local_version"] == "0.0.1"
    assert item["registry_version"] == "1.0.0"


def test_check_compliance_empty_input_returns_zeros():
    result = check_compliance_handler(entries=[])
    assert result == {"outdated": [], "unknown": [], "up_to_date_count": 0}


def test_check_compliance_all_up_to_date():
    result = check_compliance_handler(entries=[
        {"name": "test-skill",   "type": "skill",   "plugin": "test-plugin", "local_version": "1.0.0"},
        {"name": "test-agent",   "type": "agent",   "plugin": "test-plugin", "local_version": "1.0.0"},
        {"name": "test-command", "type": "command", "plugin": "test-plugin", "local_version": "1.0.0"},
    ])
    assert result["outdated"] == []
    assert result["unknown"] == []
    assert result["up_to_date_count"] == 3
