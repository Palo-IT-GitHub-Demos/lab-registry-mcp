from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture(scope="session")
def test_registry_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("registry")

    # Marketplace manifest
    (root / ".claude-plugin").mkdir()
    (root / ".claude-plugin/marketplace.json").write_text(json.dumps({
        "name": "test-marketplace",
        "plugins": [
            {
                "name": "test-plugin",
                "description": "A plugin for testing",
                "version": "1.0.0",
                "source": "./plugins/test-plugin",
            }
        ],
    }))

    plugin_dir = root / "plugins" / "test-plugin"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / ".claude-plugin").mkdir()
    (plugin_dir / ".claude-plugin/plugin.json").write_text(json.dumps({
        "name": "test-plugin",
        "version": "1.0.0",
        "description": "A plugin for testing",
        "keywords": ["testing", "mcp"],
        "license": "MIT",
        "author": {"name": "Test Author"},
    }))
    (plugin_dir / "CHANGELOG.md").write_text(
        "## [1.0.0] — 2026-01-15\n### Added\n- Initial release\n"
    )

    # Skill
    skill_dir = plugin_dir / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: test-skill\n"
        "description: A skill for testing MCP tools and registry queries\n"
        "model: sonnet\n"
        "allowed-tools:\n"
        "  - Read\n"
        "  - Grep\n"
        "---\n"
        "# Test Skill\n\n"
        "This is the skill body content.\n"
    )

    # Agent
    (plugin_dir / "agents").mkdir()
    (plugin_dir / "agents/test-agent.agent.md").write_text(
        "---\n"
        "name: test-agent\n"
        "description: A test agent for unit testing workflows\n"
        "tools:\n"
        "  - Read\n"
        "  - Write\n"
        "skills:\n"
        "  - test-skill\n"
        "model: sonnet\n"
        "---\n"
        "You are a test agent.\n"
    )

    # Command
    (plugin_dir / "commands").mkdir()
    (plugin_dir / "commands/test-command.md").write_text(
        "---\n"
        "description: A test slash command for running things\n"
        "argument-hint: target-name\n"
        "allowed-tools:\n"
        "  - Bash\n"
        "---\n"
        "# Test Command\n\n"
        "Run this command.\n"
    )

    # Hooks
    (plugin_dir / "hooks.json").write_text(json.dumps({
        "hooks": {
            "PostToolUse": [
                {"matcher": "Edit|Write", "hooks": [{"type": "command", "command": "echo done"}]}
            ]
        }
    }))

    return root


@pytest.fixture(scope="session", autouse=True)
def set_registry_env(test_registry_path: Path) -> Generator[None, None, None]:
    old = os.environ.get("REGISTRY_PATH")
    os.environ["REGISTRY_PATH"] = str(test_registry_path)
    from lab_registry import registry
    registry.load_registry.cache_clear()
    yield
    if old is not None:
        os.environ["REGISTRY_PATH"] = old
    else:
        os.environ.pop("REGISTRY_PATH", None)
    registry.load_registry.cache_clear()
