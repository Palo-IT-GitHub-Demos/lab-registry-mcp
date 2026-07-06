"""Tests for the reload_registry tool."""
from __future__ import annotations

import pytest

from lab_registry.registry import load_registry


def test_reload_registry_response_shape():
    """reload_registry must return the documented four-key shape."""
    from lab_registry.server import reload_registry
    result = reload_registry()
    assert set(result.keys()) == {"added", "removed", "modified", "total"}
    assert isinstance(result["added"], list)
    assert isinstance(result["removed"], list)
    assert isinstance(result["modified"], list)
    assert isinstance(result["total"], int)


def test_reload_registry_no_changes_when_source_unchanged():
    """Reloading without any marketplace change must produce empty diffs."""
    from lab_registry.server import reload_registry
    result = reload_registry()
    # Same source → nothing added, removed, or modified
    assert result["added"] == []
    assert result["removed"] == []
    assert result["modified"] == []
    assert result["total"] > 0


def test_reload_registry_total_matches_get_all_entries():
    """total field must equal the number of entries load_registry returns."""
    from lab_registry.server import reload_registry
    result = reload_registry()
    entries, _ = load_registry()
    assert result["total"] == len(entries)


def test_reload_registry_clears_cache():
    """After reload, load_registry() must return a fresh object (not same as before)."""
    entries_before, _ = load_registry()
    from lab_registry.server import reload_registry
    reload_registry()
    entries_after, _ = load_registry()
    # Different tuple instances (cache was cleared and rebuilt)
    assert entries_before is not entries_after
    # But same content
    ids_before = {e.id for e in entries_before}
    ids_after = {e.id for e in entries_after}
    assert ids_before == ids_after
