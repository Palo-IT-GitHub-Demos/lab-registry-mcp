"""Tests for the 6 new tools: list_plugins, get_entry_by_id, get_changelog,
get_marketplace_stats, suggest_entries, validate_entry.
"""
from __future__ import annotations

import pytest

from lab_registry.tools.fetch import (
    get_changelog_handler,
    get_entry_by_id_handler,
    list_plugins_handler,
)
from lab_registry.tools.search import suggest_entries_handler
from lab_registry.tools.stats import get_marketplace_stats_handler
from lab_registry.tools.validate import validate_entry_handler

# ---------------------------------------------------------------------------
# list_plugins
# ---------------------------------------------------------------------------

def test_list_plugins_returns_list():
    result = list_plugins_handler()
    assert isinstance(result, list)
    assert len(result) >= 1


def test_list_plugins_entry_has_required_keys():
    result = list_plugins_handler()
    for plugin in result:
        assert "name" in plugin
        assert "version" in plugin
        assert "description" in plugin
        assert "entry_counts" in plugin


def test_list_plugins_entry_counts_shape():
    result = list_plugins_handler()
    for plugin in result:
        counts = plugin["entry_counts"]
        assert "skill" in counts
        assert "agent" in counts
        assert "command" in counts
        assert "hook" in counts
        assert "total" in counts
        assert counts["total"] == counts["skill"] + counts["agent"] + counts["command"] + counts["hook"]


def test_list_plugins_covers_all_plugins():
    from lab_registry.registry import get_all_plugins
    plugin_names = {p["name"] for p in list_plugins_handler()}
    expected = set(get_all_plugins().keys())
    assert plugin_names == expected


def test_list_plugins_total_matches_entries():
    from lab_registry.registry import get_all_entries
    result = list_plugins_handler()
    total_from_list = sum(p["entry_counts"]["total"] for p in result)
    assert total_from_list == len(get_all_entries())


# ---------------------------------------------------------------------------
# get_entry_by_id
# ---------------------------------------------------------------------------

def test_get_entry_by_id_success():
    result = get_entry_by_id_handler("test-plugin/skill/test-skill")
    assert "error" not in result
    assert result["entry"]["id"] == "test-plugin/skill/test-skill"


def test_get_entry_by_id_returns_same_as_get_entry():
    from lab_registry.tools.fetch import get_entry_handler
    by_id = get_entry_by_id_handler("test-plugin/skill/test-skill")
    by_parts = get_entry_handler(plugin="test-plugin", type="skill", name="test-skill")
    assert by_id == by_parts


def test_get_entry_by_id_not_found():
    result = get_entry_by_id_handler("nope/skill/missing")
    assert "error" in result


def test_get_entry_by_id_invalid_format():
    result = get_entry_by_id_handler("no-slash-here")
    assert "error" in result
    assert "format" in result["error"].lower()


def test_get_entry_by_id_agent():
    result = get_entry_by_id_handler("test-plugin/agent/test-agent")
    assert "error" not in result
    assert result["entry"]["type"] == "agent"


# ---------------------------------------------------------------------------
# get_changelog
# ---------------------------------------------------------------------------

def test_get_changelog_success():
    result = get_changelog_handler("test-plugin")
    assert "error" not in result
    assert result["plugin"] == "test-plugin"
    assert result["version"] == "1.0.0"
    assert result["changelog_raw"] is not None
    assert "1.0.0" in result["changelog_raw"]


def test_get_changelog_has_required_keys():
    result = get_changelog_handler("test-plugin")
    assert "plugin" in result
    assert "version" in result
    assert "changelog_raw" in result


def test_get_changelog_not_found_plugin():
    result = get_changelog_handler("no-such-plugin")
    assert "error" in result


# ---------------------------------------------------------------------------
# get_marketplace_stats
# ---------------------------------------------------------------------------

def test_get_marketplace_stats_shape():
    result = get_marketplace_stats_handler()
    assert "total_entries" in result
    assert "total_plugins" in result
    assert "by_type" in result
    assert "by_plugin" in result
    assert "last_updated" in result
    assert "plugins_without_changelog" in result


def test_get_marketplace_stats_totals_consistent():
    from lab_registry.registry import get_all_entries, get_all_plugins
    result = get_marketplace_stats_handler()
    assert result["total_entries"] == len(get_all_entries())
    assert result["total_plugins"] == len(get_all_plugins())


def test_get_marketplace_stats_by_type_sums_to_total():
    result = get_marketplace_stats_handler()
    type_sum = sum(result["by_type"].values())
    assert type_sum == result["total_entries"]


def test_get_marketplace_stats_by_plugin_sums_to_total():
    result = get_marketplace_stats_handler()
    plugin_sum = sum(p["total"] for p in result["by_plugin"])
    assert plugin_sum == result["total_entries"]


def test_get_marketplace_stats_by_type_has_all_types():
    result = get_marketplace_stats_handler()
    assert set(result["by_type"].keys()) >= {"skill", "agent", "command", "hook"}


# ---------------------------------------------------------------------------
# suggest_entries
# ---------------------------------------------------------------------------

def test_suggest_entries_returns_list():
    result = suggest_entries_handler(task="testing workflow skill")
    assert isinstance(result, list)


def test_suggest_entries_has_score_field():
    result = suggest_entries_handler(task="test skill")
    for item in result:
        assert "score" in item
        assert "matched_terms" in item
        assert isinstance(item["score"], int)
        assert isinstance(item["matched_terms"], list)


def test_suggest_entries_sorted_by_score():
    result = suggest_entries_handler(task="test skill")
    scores = [r["score"] for r in result]
    assert scores == sorted(scores, reverse=True)


def test_suggest_entries_limit_respected():
    result = suggest_entries_handler(task="test", limit=2)
    assert len(result) <= 2


def test_suggest_entries_type_filter():
    result = suggest_entries_handler(task="test", type="skill")
    for item in result:
        assert item["type"] == "skill"


def test_suggest_entries_no_match_returns_empty():
    result = suggest_entries_handler(task="zzz-absolutely-no-match-xyz")
    assert result == []


def test_suggest_entries_short_words_ignored():
    """Words ≤2 chars should not match (noise filtering)."""
    result = suggest_entries_handler(task="a b c")
    assert result == []


# ---------------------------------------------------------------------------
# validate_entry
# ---------------------------------------------------------------------------

VALID_SKILL = (
    "---\nname: my-skill\ndescription: A valid test skill\nmodel: sonnet\n"
    "allowed-tools:\n  - Read\n---\n# Instructions\n\nDo the thing.\n"
)

VALID_AGENT = (
    "---\nname: my-agent\ndescription: A valid test agent\n"
    "tools:\n  - Read\nskills:\n  - my-skill\n---\nAgent instructions.\n"
)

VALID_COMMAND = (
    "---\ndescription: A valid command\nallowed-tools:\n  - Bash\n---\nCommand body.\n"
)


def test_validate_skill_valid():
    result = validate_entry_handler(VALID_SKILL, "skill")
    assert result["valid"] is True
    assert result["errors"] == []


def test_validate_agent_valid():
    result = validate_entry_handler(VALID_AGENT, "agent")
    assert result["valid"] is True
    assert result["errors"] == []


def test_validate_command_valid():
    result = validate_entry_handler(VALID_COMMAND, "command")
    assert result["valid"] is True
    assert result["errors"] == []


def test_validate_missing_required_field():
    no_name = "---\ndescription: A skill without name\n---\nBody.\n"
    result = validate_entry_handler(no_name, "skill")
    assert result["valid"] is False
    assert any("name" in e for e in result["errors"])


def test_validate_missing_description():
    no_desc = "---\nname: my-skill\n---\nBody.\n"
    result = validate_entry_handler(no_desc, "skill")
    assert result["valid"] is False
    assert any("description" in e for e in result["errors"])


def test_validate_empty_body_warning():
    no_body = "---\nname: my-skill\ndescription: A skill\n---\n"
    result = validate_entry_handler(no_body, "skill")
    assert result["valid"] is True  # not an error, just a warning
    assert any("body" in w.lower() or "empty" in w.lower() for w in result["warnings"])


def test_validate_unknown_type_error():
    result = validate_entry_handler(VALID_SKILL, "nonexistent-type")
    assert result["valid"] is False
    assert any("Unknown type" in e for e in result["errors"])


def test_validate_response_shape():
    result = validate_entry_handler(VALID_SKILL, "skill")
    assert set(result.keys()) == {"valid", "errors", "warnings", "parsed"}
    assert isinstance(result["valid"], bool)
    assert isinstance(result["errors"], list)
    assert isinstance(result["warnings"], list)
    assert isinstance(result["parsed"], dict)


def test_validate_parsed_contains_frontmatter():
    result = validate_entry_handler(VALID_SKILL, "skill")
    assert result["parsed"]["name"] == "my-skill"
    assert result["parsed"]["model"] == "sonnet"


def test_validate_missing_recommended_field_is_warning_not_error():
    no_model = "---\nname: my-skill\ndescription: A skill\n---\nBody.\n"
    result = validate_entry_handler(no_model, "skill")
    assert result["valid"] is True
    assert any("model" in w for w in result["warnings"])
