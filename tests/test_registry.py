from __future__ import annotations

import pytest

from lab_registry.registry import (
    _extract_updated_at,
    _load_command,
    _parse_frontmatter,
    find_entry,
    get_all_entries,
    get_all_plugins,
    load_registry,
)


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


# ===========================================================================
# _parse_frontmatter edge cases
# ===========================================================================

def test_parse_frontmatter_valid():
    meta, body = _parse_frontmatter("---\nname: hello\n---\n# Body\n")
    assert meta == {"name": "hello"}
    assert "Body" in body


def test_parse_frontmatter_no_frontmatter():
    content = "# Just a heading\n\nSome body text"
    meta, body = _parse_frontmatter(content)
    assert meta == {}
    assert "Just a heading" in body


def test_parse_frontmatter_empty_body():
    meta, body = _parse_frontmatter("---\nname: test\n---\n")
    assert meta["name"] == "test"
    assert body == ""


def test_parse_frontmatter_multiline_frontmatter():
    content = "---\nname: foo\ndescription: bar baz\ntools:\n  - Read\n  - Write\n---\nBody here\n"
    meta, body = _parse_frontmatter(content)
    assert meta["name"] == "foo"
    assert meta["tools"] == ["Read", "Write"]
    assert "Body here" in body


def test_parse_frontmatter_invalid_yaml_returns_empty_meta():
    content = "---\n: broken: yaml: {here\n---\nBody\n"
    meta, body = _parse_frontmatter(content)
    assert meta == {}


# ===========================================================================
# _extract_updated_at edge cases
# ===========================================================================

def test_extract_updated_at_em_dash(tmp_path):
    (tmp_path / "CHANGELOG.md").write_text("## [1.0.0] — 2025-03-10\n### Added\n- thing\n")
    assert _extract_updated_at(tmp_path) == "2025-03-10"


def test_extract_updated_at_en_dash(tmp_path):
    (tmp_path / "CHANGELOG.md").write_text("## [1.0.0] – 2025-03-10\n### Added\n- thing\n")
    assert _extract_updated_at(tmp_path) == "2025-03-10"


def test_extract_updated_at_hyphen(tmp_path):
    (tmp_path / "CHANGELOG.md").write_text("## [1.0.0] - 2025-03-10\n### Added\n- thing\n")
    assert _extract_updated_at(tmp_path) == "2025-03-10"


def test_extract_updated_at_picks_first_entry(tmp_path):
    """When multiple versions are listed, the first (most recent) date is returned."""
    content = (
        "## [2.0.0] — 2026-06-01\n### Added\n- new stuff\n\n"
        "## [1.0.0] — 2025-01-15\n### Added\n- initial\n"
    )
    (tmp_path / "CHANGELOG.md").write_text(content)
    assert _extract_updated_at(tmp_path) == "2026-06-01"


def test_extract_updated_at_no_changelog_returns_none(tmp_path):
    assert _extract_updated_at(tmp_path) is None


def test_extract_updated_at_changelog_without_date_returns_none(tmp_path):
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\nNo version headers here.\n")
    assert _extract_updated_at(tmp_path) is None


# ===========================================================================
# _load_command: argument-hint normalization
# ===========================================================================

def test_argument_hint_string_kept_as_is(tmp_path):
    cmd = tmp_path / "my-cmd.md"
    cmd.write_text("---\ndescription: A command\nargument-hint: foo-bar\n---\nBody\n")
    entry = _load_command("test-plugin", "1.0.0", None, [], cmd, tmp_path)
    assert entry is not None
    assert entry.argument_hint == "foo-bar"


def test_argument_hint_list_joined_to_string(tmp_path):
    """YAML list argument-hint must be joined into a single space-separated string."""
    cmd = tmp_path / "my-cmd.md"
    cmd.write_text(
        "---\ndescription: A command\nargument-hint:\n  - foo\n  - bar\n---\nBody\n"
    )
    entry = _load_command("test-plugin", "1.0.0", None, [], cmd, tmp_path)
    assert entry is not None
    assert entry.argument_hint == "foo bar"


def test_argument_hint_absent_is_none(tmp_path):
    cmd = tmp_path / "my-cmd.md"
    cmd.write_text("---\ndescription: A command\n---\nBody\n")
    entry = _load_command("test-plugin", "1.0.0", None, [], cmd, tmp_path)
    assert entry is not None
    assert entry.argument_hint is None


# ===========================================================================
# load_registry cache behaviour
# ===========================================================================

def test_load_registry_is_cached():
    """Calling load_registry() twice must return the same object (lru_cache)."""
    result1 = load_registry()
    result2 = load_registry()
    assert result1 is result2


def test_load_registry_cache_clear_forces_reload():
    """After cache_clear(), load_registry() constructs a new object."""
    result1 = load_registry()
    load_registry.cache_clear()
    result2 = load_registry()
    # Different objects — not the same tuple instance
    assert result1 is not result2
    # But the content is equivalent
    assert len(result1[0]) == len(result2[0])
