from __future__ import annotations

from lab_registry.tools.search import list_entries_handler, search_entries_handler, suggest_plugins_handler


def test_list_all():
    result = list_entries_handler()
    assert len(result) == 4


def test_list_filter_type_skill():
    result = list_entries_handler(type="skill")
    assert len(result) == 1
    assert result[0]["type"] == "skill"


def test_list_filter_type_case_insensitive():
    result = list_entries_handler(type="Skill")
    assert len(result) == 1


def test_list_filter_plugin():
    result = list_entries_handler(plugin="test-plugin")
    assert len(result) == 4


def test_list_filter_unknown_plugin():
    assert list_entries_handler(plugin="does-not-exist") == []


def test_list_filter_by_tags():
    result = list_entries_handler(tags=["mcp"])
    assert len(result) == 4  # all entries share plugin tags


def test_list_filter_no_tag_match():
    assert list_entries_handler(tags=["no-such-tag"]) == []


def test_search_by_name():
    result = search_entries_handler(query="test-skill")
    assert result[0]["name"] == "test-skill"


def test_search_name_ranks_before_description():
    result = search_entries_handler(query="test")
    # entries whose name contains "test" come before description-only matches
    name_match_ids = [r["id"] for r in result if "test" in r["name"]]
    desc_only_ids = [r["id"] for r in result if "test" not in r["name"]]
    if name_match_ids and desc_only_ids:
        first_desc_idx = next(i for i, r in enumerate(result) if r["id"] in desc_only_ids)
        last_name_idx = max(i for i, r in enumerate(result) if r["id"] in name_match_ids)
        assert last_name_idx < first_desc_idx


def test_search_no_results():
    assert search_entries_handler(query="zzz-not-found-xyz") == []


def test_search_with_type_filter():
    result = search_entries_handler(query="test", type="agent")
    assert all(r["type"] == "agent" for r in result)


# ===========================================================================
# suggest_plugins tests
# ===========================================================================

def test_suggest_plugins_returns_list():
    result = suggest_plugins_handler(task="testing mcp")
    assert isinstance(result, list)


def test_suggest_plugins_has_score_and_matched_terms():
    result = suggest_plugins_handler(task="testing")
    assert len(result) > 0
    for row in result:
        assert "score" in row
        assert "matched_terms" in row
        assert isinstance(row["score"], int)
        assert isinstance(row["matched_terms"], list)


def test_suggest_plugins_no_match_returns_empty():
    result = suggest_plugins_handler(task="zzz-absolutely-no-match-xyz")
    assert result == []


def test_suggest_plugins_respects_limit():
    result = suggest_plugins_handler(task="testing mcp", limit=1)
    assert len(result) <= 1


def test_suggest_plugins_name_match_scores_higher():
    """Plugin whose name contains the query should rank first."""
    result = suggest_plugins_handler(task="test-plugin")
    assert len(result) > 0
    assert result[0]["name"] == "test-plugin"
