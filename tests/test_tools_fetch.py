from __future__ import annotations

from lab_registry.tools.fetch import get_entry_handler, get_plugin_handler


def test_get_entry_returns_all_keys():
    result = get_entry_handler(plugin="test-plugin", type="skill", name="test-skill")
    assert "error" not in result
    assert "entry" in result
    assert "metadata" in result
    assert "content_raw" in result


def test_get_entry_structured_metadata():
    result = get_entry_handler(plugin="test-plugin", type="skill", name="test-skill")
    assert result["entry"]["name"] == "test-skill"
    assert result["entry"]["plugin_version"] == "1.0.0"


def test_get_entry_frontmatter_parsed():
    result = get_entry_handler(plugin="test-plugin", type="skill", name="test-skill")
    assert result["metadata"]["model"] == "sonnet"
    assert "Read" in result["metadata"]["allowed-tools"]


def test_get_entry_content_raw():
    result = get_entry_handler(plugin="test-plugin", type="skill", name="test-skill")
    assert "Test Skill" in result["content_raw"]
    assert "skill body content" in result["content_raw"]


def test_get_entry_not_found():
    result = get_entry_handler(plugin="nope", type="skill", name="missing")
    assert "error" in result


def test_get_plugin_manifest():
    result = get_plugin_handler(plugin="test-plugin")
    assert "error" not in result
    assert result["manifest"]["version"] == "1.0.0"
    assert result["manifest"]["name"] == "test-plugin"


def test_get_plugin_entries_count():
    result = get_plugin_handler(plugin="test-plugin")
    assert len(result["entries"]) == 4


def test_get_plugin_not_found():
    result = get_plugin_handler(plugin="nonexistent")
    assert "error" in result
