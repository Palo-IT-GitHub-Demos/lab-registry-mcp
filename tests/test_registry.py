from __future__ import annotations

from lab_registry.registry import find_entry, get_all_entries, get_all_plugins


def test_entries_loaded():
    entries = get_all_entries()
    # 1 skill + 1 agent + 1 command + 1 hook
    assert len(entries) == 4


def test_skill_fields():
    entry = find_entry("test-plugin", "skill", "test-skill")
    assert entry is not None
    assert entry.type == "skill"
    assert entry.plugin == "test-plugin"
    assert entry.plugin_version == "1.0.0"
    assert entry.updated_at == "2026-01-15"
    assert entry.model == "sonnet"
    assert "Read" in entry.allowed_tools
    assert "testing" in entry.tags


def test_agent_fields():
    entry = find_entry("test-plugin", "agent", "test-agent")
    assert entry is not None
    assert entry.type == "agent"
    assert entry.model == "sonnet"
    assert "test-skill" in entry.agent_skills
    assert "Read" in entry.allowed_tools


def test_command_fields():
    entry = find_entry("test-plugin", "command", "test-command")
    assert entry is not None
    assert entry.type == "command"
    assert entry.argument_hint == "target-name"
    assert "Bash" in entry.allowed_tools


def test_hook_fields():
    entry = find_entry("test-plugin", "hook", "hooks")
    assert entry is not None
    assert entry.type == "hook"
    assert "PostToolUse" in entry.hook_events


def test_plugin_manifest():
    plugins = get_all_plugins()
    assert "test-plugin" in plugins
    p = plugins["test-plugin"]
    assert p.version == "1.0.0"
    assert "testing" in p.tags
    assert p.author == "Test Author"
    assert p.plugin_license == "MIT"


def test_unknown_entry_returns_none():
    assert find_entry("nope", "skill", "missing") is None


def test_case_insensitive_type_lookup():
    entry = find_entry("test-plugin", "Skill", "test-skill")
    assert entry is not None
