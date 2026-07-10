from __future__ import annotations

from lab_registry.tools.compliance import check_compliance_handler, check_compliance_plugin_handler


def test_up_to_date():
    result = check_compliance_handler(entries=[
        {"name": "test-skill", "type": "skill", "plugin": "test-plugin", "local_version": "1.0.0"},
    ])
    assert result["outdated"] == []
    assert result["unknown"] == []
    assert result["up_to_date_count"] == 1


def test_outdated_version():
    result = check_compliance_handler(entries=[
        {"name": "test-skill", "type": "skill", "plugin": "test-plugin", "local_version": "0.9.0"},
    ])
    assert len(result["outdated"]) == 1
    assert result["outdated"][0]["local_version"] == "0.9.0"
    assert result["outdated"][0]["registry_version"] == "1.0.0"
    assert result["up_to_date_count"] == 0


def test_unknown_entry():
    result = check_compliance_handler(entries=[
        {"name": "ghost-skill", "type": "skill", "plugin": "test-plugin", "local_version": "1.0.0"},
    ])
    assert len(result["unknown"]) == 1
    assert result["unknown"][0]["name"] == "ghost-skill"
    assert result["up_to_date_count"] == 0


def test_mixed_scenarios():
    result = check_compliance_handler(entries=[
        # up to date
        {"name": "test-skill", "type": "skill", "plugin": "test-plugin", "local_version": "1.0.0"},
        # outdated
        {"name": "test-agent", "type": "agent", "plugin": "test-plugin", "local_version": "0.5.0"},
        # unknown
        {"name": "ghost-hook", "type": "hook", "plugin": "test-plugin", "local_version": "1.0.0"},
    ])
    assert result["up_to_date_count"] == 1
    assert len(result["outdated"]) == 1
    assert len(result["unknown"]) == 1


def test_empty_input():
    result = check_compliance_handler(entries=[])
    assert result == {"outdated": [], "unknown": [], "up_to_date_count": 0}


def test_case_insensitive_type():
    result = check_compliance_handler(entries=[
        {"name": "test-skill", "type": "Skill", "plugin": "test-plugin", "local_version": "1.0.0"},
    ])
    assert result["up_to_date_count"] == 1
    assert result["unknown"] == []


# ===========================================================================
# check_compliance_plugin tests
# ===========================================================================

def test_compliance_plugin_all_up_to_date():
    result = check_compliance_plugin_handler(plugin="test-plugin", local_version="1.0.0")
    assert result["outdated"] == []
    assert result["unknown"] == []
    assert result["up_to_date_count"] > 0


def test_compliance_plugin_all_outdated():
    result = check_compliance_plugin_handler(plugin="test-plugin", local_version="0.5.0")
    assert len(result["outdated"]) > 0
    assert result["up_to_date_count"] == 0
    for item in result["outdated"]:
        assert item["local_version"] == "0.5.0"
        assert item["registry_version"] == "1.0.0"


def test_compliance_plugin_unknown_plugin():
    result = check_compliance_plugin_handler(plugin="nonexistent-plugin", local_version="1.0.0")
    assert "error" in result
