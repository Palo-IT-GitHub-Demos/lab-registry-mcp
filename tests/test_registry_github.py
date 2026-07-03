"""Tests for the GitHub-backed registry loader.

All HTTP calls are mocked — no network access required.
Tests that REGISTRY_GITHUB_REPO=owner/repo activates the GitHub path and
produces the same RegistryEntry shapes as the local loader.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MOCK_REPO = "test-owner/test-repo"
MOCK_BRANCH = "main"
BASE_RAW = f"https://raw.githubusercontent.com/{MOCK_REPO}/{MOCK_BRANCH}"
TREE_URL = f"https://api.github.com/repos/{MOCK_REPO}/git/trees/{MOCK_BRANCH}?recursive=1"

_MARKETPLACE = json.dumps({
    "name": "test-marketplace",
    "plugins": [{"name": "gh-plugin", "source": "./plugins/gh-plugin"}],
})

_PLUGIN_JSON = json.dumps({
    "name": "gh-plugin",
    "version": "2.0.0",
    "description": "A GitHub-backed test plugin",
    "keywords": ["github", "testing"],
    "license": "MIT",
    "author": {"name": "GitHub Author"},
})

_CHANGELOG = "## [2.0.0] — 2026-06-15\n### Added\n- New stuff\n"

_SKILL = (
    "---\nname: gh-skill\ndescription: A GitHub-fetched skill\nmodel: sonnet\n"
    "allowed-tools:\n  - Read\n---\n# GitHub Skill\n\nSkill body.\n"
)

_AGENT = (
    "---\nname: gh-agent\ndescription: A GitHub-fetched agent\n"
    "tools:\n  - Read\nskills:\n  - gh-skill\n---\nAgent instructions.\n"
)

_COMMAND = (
    "---\ndescription: A GitHub command\nargument-hint: target-file\n"
    "allowed-tools:\n  - Bash\n---\nCommand body.\n"
)

_COMMAND_LIST_HINT = (
    "---\ndescription: Command with list hint\nargument-hint:\n  - foo\n  - bar\n"
    "---\nBody.\n"
)

_HOOKS = json.dumps({
    "hooks": {
        "PostToolUse": [{"matcher": "Edit", "hooks": [{"type": "command", "command": "echo ok"}]}]
    }
})

MOCK_TREE_PATHS = {
    ".claude-plugin/marketplace.json",
    "plugins/gh-plugin/.claude-plugin/plugin.json",
    "plugins/gh-plugin/CHANGELOG.md",
    "plugins/gh-plugin/skills/gh-skill/SKILL.md",
    "plugins/gh-plugin/agents/gh-agent.agent.md",
    "plugins/gh-plugin/commands/gh-command.md",
    "plugins/gh-plugin/commands/gh-list-cmd.md",
    "plugins/gh-plugin/hooks.json",
}

_URL_MAP: dict[str, str] = {
    TREE_URL: json.dumps({
        "tree": [{"path": p, "type": "blob"} for p in MOCK_TREE_PATHS],
        "truncated": False,
    }),
    f"{BASE_RAW}/.claude-plugin/marketplace.json": _MARKETPLACE,
    f"{BASE_RAW}/plugins/gh-plugin/.claude-plugin/plugin.json": _PLUGIN_JSON,
    f"{BASE_RAW}/plugins/gh-plugin/CHANGELOG.md": _CHANGELOG,
    f"{BASE_RAW}/plugins/gh-plugin/skills/gh-skill/SKILL.md": _SKILL,
    f"{BASE_RAW}/plugins/gh-plugin/agents/gh-agent.agent.md": _AGENT,
    f"{BASE_RAW}/plugins/gh-plugin/commands/gh-command.md": _COMMAND,
    f"{BASE_RAW}/plugins/gh-plugin/commands/gh-list-cmd.md": _COMMAND_LIST_HINT,
    f"{BASE_RAW}/plugins/gh-plugin/hooks.json": _HOOKS,
}


def _mock_fetch(url: str, token: str | None = None) -> str | None:
    return _URL_MAP.get(url)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def github_env(monkeypatch):
    """Set REGISTRY_GITHUB_REPO and clear REGISTRY_PATH for every test in this module."""
    monkeypatch.setenv("REGISTRY_GITHUB_REPO", MOCK_REPO)
    monkeypatch.setenv("REGISTRY_GITHUB_BRANCH", MOCK_BRANCH)
    monkeypatch.delenv("REGISTRY_PATH", raising=False)
    monkeypatch.delenv("REGISTRY_GITHUB_TOKEN", raising=False)
    from lab_registry import registry
    registry.load_registry.cache_clear()
    yield
    registry.load_registry.cache_clear()


@pytest.fixture(autouse=True)
def mock_http(github_env):
    """Patch _fetch_text so no real HTTP calls are made."""
    with patch("lab_registry.registry_github._fetch_text", side_effect=_mock_fetch):
        yield


# ---------------------------------------------------------------------------
# load_registry_from_github
# ---------------------------------------------------------------------------

def test_github_loads_all_entry_types():
    from lab_registry.registry import get_all_entries
    entries = get_all_entries()
    types = {e.type for e in entries}
    assert "skill" in types
    assert "agent" in types
    assert "command" in types
    assert "hook" in types


def test_github_correct_entry_count():
    from lab_registry.registry import get_all_entries
    entries = get_all_entries()
    # 1 skill + 1 agent + 2 commands + 1 hook = 5
    assert len(entries) == 5


def test_github_skill_fields():
    from lab_registry.registry import find_entry
    entry = find_entry("gh-plugin", "skill", "gh-skill")
    assert entry is not None
    assert entry.plugin == "gh-plugin"
    assert entry.plugin_version == "2.0.0"
    assert entry.updated_at == "2026-06-15"
    assert entry.model == "sonnet"
    assert "Read" in entry.allowed_tools
    assert "github" in entry.tags


def test_github_agent_fields():
    from lab_registry.registry import find_entry
    entry = find_entry("gh-plugin", "agent", "gh-agent")
    assert entry is not None
    assert entry.type == "agent"
    assert "gh-skill" in entry.agent_skills
    assert "Read" in entry.allowed_tools


def test_github_command_argument_hint_string():
    from lab_registry.registry import find_entry
    entry = find_entry("gh-plugin", "command", "gh-command")
    assert entry is not None
    assert entry.argument_hint == "target-file"


def test_github_command_argument_hint_list_joined():
    """A YAML-list argument-hint must be joined to a single string."""
    from lab_registry.registry import find_entry
    entry = find_entry("gh-plugin", "command", "gh-list-cmd")
    assert entry is not None
    assert entry.argument_hint == "foo bar"


def test_github_hook_fields():
    from lab_registry.registry import find_entry
    entry = find_entry("gh-plugin", "hook", "hooks")
    assert entry is not None
    assert "PostToolUse" in entry.hook_events


def test_github_plugin_manifest():
    from lab_registry.registry import get_all_plugins
    plugins = get_all_plugins()
    assert "gh-plugin" in plugins
    p = plugins["gh-plugin"]
    assert p.version == "2.0.0"
    assert p.author == "GitHub Author"
    assert p.plugin_license == "MIT"
    assert "github" in p.tags


def test_github_entry_id_format():
    """Every entry ID must follow '{plugin}/{type}/{name}'."""
    from lab_registry.registry import get_all_entries
    for entry in get_all_entries():
        parts = entry.id.split("/")
        assert len(parts) == 3, f"Bad ID: {entry.id}"
        assert parts[0] == entry.plugin
        assert parts[1] == entry.type
        assert parts[2] == entry.name


def test_github_entry_path_is_repo_relative():
    """Entry paths must be relative to the repo root (not local filesystem)."""
    from lab_registry.registry import get_all_entries
    for entry in get_all_entries():
        assert not entry.path.startswith("/"), f"Absolute path in GitHub entry: {entry.path}"
        assert entry.path in MOCK_TREE_PATHS, f"Path not in tree: {entry.path}"


# ---------------------------------------------------------------------------
# fetch_entry_content_github
# ---------------------------------------------------------------------------

def test_github_get_entry_content_skill():
    from lab_registry.registry import find_entry, get_entry_content
    entry = find_entry("gh-plugin", "skill", "gh-skill")
    assert entry is not None
    metadata, body = get_entry_content(entry)
    assert metadata["name"] == "gh-skill"
    assert metadata["model"] == "sonnet"
    assert "Skill body" in body


def test_github_get_entry_content_hook():
    """get_entry_content on a hook returns the raw JSON as content_raw."""
    from lab_registry.registry import find_entry, get_entry_content
    entry = find_entry("gh-plugin", "hook", "hooks")
    assert entry is not None
    _, body = get_entry_content(entry)
    assert "PostToolUse" in body  # JSON content is returned as-is


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

def test_github_missing_repo_env_raises(monkeypatch):
    from lab_registry.registry_github import load_registry_from_github
    monkeypatch.delenv("REGISTRY_GITHUB_REPO", raising=False)
    with pytest.raises(EnvironmentError, match="REGISTRY_GITHUB_REPO"):
        load_registry_from_github()


def test_github_invalid_repo_format_raises(monkeypatch):
    from lab_registry.registry_github import load_registry_from_github
    monkeypatch.setenv("REGISTRY_GITHUB_REPO", "no-slash-here")
    with pytest.raises(EnvironmentError, match="owner/repo"):
        load_registry_from_github()


def test_github_load_registry_dispatcher():
    """load_registry() must use GitHub path when REGISTRY_GITHUB_REPO is set."""
    from lab_registry.registry import load_registry
    entries, plugins = load_registry()
    assert len(entries) == 5
    assert "gh-plugin" in plugins


# ---------------------------------------------------------------------------
# Compatibility: local tests still pass when REGISTRY_PATH is set
# ---------------------------------------------------------------------------

def test_local_path_takes_over_when_github_unset(monkeypatch, tmp_path):
    """When REGISTRY_GITHUB_REPO is unset, registry.py falls back to REGISTRY_PATH."""
    from lab_registry import registry

    # Build a minimal local registry in tmp_path
    (tmp_path / ".claude-plugin").mkdir()
    (tmp_path / ".claude-plugin/marketplace.json").write_text(
        json.dumps({"name": "local", "plugins": []})
    )
    monkeypatch.delenv("REGISTRY_GITHUB_REPO")
    monkeypatch.setenv("REGISTRY_PATH", str(tmp_path))
    registry.load_registry.cache_clear()

    entries, plugins = registry.load_registry()
    assert entries == []  # empty local marketplace
    assert plugins == {}
