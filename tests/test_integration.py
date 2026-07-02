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
            _, body = get_entry_content(entry)
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
    expected = {"list_entries", "search_entries", "get_entry", "get_plugin", "check_compliance"}
    assert tool_names == expected, f"Registered tools: {tool_names}"
