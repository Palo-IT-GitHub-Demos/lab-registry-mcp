"""End-to-end test: spawns the real MCP server via stdio and calls all 5 tools.

Run:
    REGISTRY_PATH=/path/to/gen-e2-marketplace pytest tests/test_e2e.py -v
    # or directly:
    REGISTRY_PATH=../gen-e2-marketplace python tests/test_e2e.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

REGISTRY_PATH = os.environ.get("REGISTRY_PATH", "")
SERVER_SCRIPT = str(Path(__file__).parent.parent / "src" / "lab_registry" / "server.py")
MCP_BIN = str(Path(__file__).parent.parent / ".venv" / "bin" / "mcp")

SKIP = pytest.mark.skipif(
    not (REGISTRY_PATH and (Path(REGISTRY_PATH) / ".claude-plugin" / "marketplace.json").exists()),
    reason="REGISTRY_PATH not set or marketplace.json not found",
)


async def _call_server(tool: str, args: dict, registry_path: str = REGISTRY_PATH) -> dict | list:
    """Spawn the MCP server and call one tool via stdio JSON-RPC."""
    proc = await asyncio.create_subprocess_exec(
        MCP_BIN, "run", SERVER_SCRIPT,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env={**os.environ, "REGISTRY_PATH": registry_path},
        limit=8 * 1024 * 1024,  # 8 MB — large list_entries responses can exceed default 64 KB
    )

    async def send(msg: dict) -> None:
        line = json.dumps(msg) + "\n"
        proc.stdin.write(line.encode())
        await proc.stdin.drain()

    async def recv() -> dict:
        line = await asyncio.wait_for(proc.stdout.readline(), timeout=10.0)
        return json.loads(line)

    # MCP handshake
    await send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2024-11-05",
                           "capabilities": {},
                           "clientInfo": {"name": "e2e-test", "version": "0.1"}}})
    await recv()
    await send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    # Call the tool
    await send({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": tool, "arguments": args}})
    raw = await recv()

    proc.stdin.close()
    proc.kill()
    await proc.wait()

    if "error" in raw:
        raise RuntimeError(f"JSON-RPC error: {raw['error']}")

    result_body = raw["result"]

    # FastMCP 1.28 sets isError=true and puts the message in content[0]["text"]
    if result_body.get("isError"):
        msg = (result_body.get("content") or [{}])[0].get("text", "unknown tool error")
        raise RuntimeError(msg)

    # FastMCP 1.28 also returns structuredContent — use it when present (more reliable)
    if "structuredContent" in result_body:
        return result_body["structuredContent"].get("result", result_body["structuredContent"])

    # Fallback: parse content items
    # - empty list   → content: []
    # - list[dict]   → N separate content items, one per element
    # - scalar/dict  → 1 content item with JSON text
    content = result_body.get("content", [])
    if len(content) == 0:
        return []
    if len(content) > 1:
        return [json.loads(item["text"]) for item in content]
    return json.loads(content[0]["text"])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@SKIP
@pytest.mark.asyncio
async def test_e2e_list_entries_all():
    result = await _call_server("list_entries", {})
    assert isinstance(result, list)
    assert len(result) >= 50, f"Expected ≥50 entries, got {len(result)}"


@SKIP
@pytest.mark.asyncio
async def test_e2e_list_entries_filter_skill():
    result = await _call_server("list_entries", {"type": "skill"})
    assert all(r["type"] == "skill" for r in result)
    assert len(result) >= 30


@SKIP
@pytest.mark.asyncio
async def test_e2e_list_entries_filter_plugin():
    result = await _call_server("list_entries", {"plugin": "android"})
    assert all(r["plugin"] == "android" for r in result)
    assert len(result) >= 14


@SKIP
@pytest.mark.asyncio
async def test_e2e_list_entries_empty_result():
    """FastMCP returns content:[] for empty list — must not crash."""
    result = await _call_server("list_entries", {"tags": ["no-such-tag-xyz"]})
    assert result == []


@SKIP
@pytest.mark.asyncio
async def test_e2e_search_entries():
    result = await _call_server("search_entries", {"query": "architecture"})
    assert isinstance(result, list)
    assert len(result) >= 1
    names = [r["name"] for r in result]
    assert any("architecture" in n for n in names)


@SKIP
@pytest.mark.asyncio
async def test_e2e_get_entry():
    result = await _call_server("get_entry", {
        "plugin": "android", "type": "skill", "name": "android-architecture"
    })
    assert "error" not in result
    assert result["entry"]["plugin_version"] == "0.1.0"
    assert len(result["content_raw"]) > 100
    # android-architecture frontmatter only has name + description (no model field)
    assert result["metadata"]["name"] == "android-architecture"


@SKIP
@pytest.mark.asyncio
async def test_e2e_get_plugin():
    result = await _call_server("get_plugin", {"plugin": "research-suite"})
    assert "error" not in result
    assert result["manifest"]["version"] == "1.0.1"
    assert len(result["entries"]) >= 2


@SKIP
@pytest.mark.asyncio
async def test_e2e_check_compliance_up_to_date():
    result = await _call_server("check_compliance", {"entries": [
        {"name": "android-architecture", "type": "skill",
         "plugin": "android", "local_version": "0.1.0"},
    ]})
    assert result["up_to_date_count"] == 1
    assert result["outdated"] == []
    assert result["unknown"] == []


@SKIP
@pytest.mark.asyncio
async def test_e2e_check_compliance_outdated():
    result = await _call_server("check_compliance", {"entries": [
        {"name": "android-architecture", "type": "skill",
         "plugin": "android", "local_version": "0.0.1"},
    ]})
    assert len(result["outdated"]) == 1
    assert result["outdated"][0]["current_version"] == "0.1.0"


@SKIP
@pytest.mark.asyncio
async def test_e2e_missing_registry_raises():
    """REGISTRY_PATH misconfigured → server returns isError:true → RuntimeError."""
    with pytest.raises(RuntimeError, match="REGISTRY_PATH"):
        await _call_server("list_entries", {}, registry_path="")


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

async def _main() -> None:
    tests = [
        ("list_entries – all",       "list_entries", {}),
        ("list_entries – skill",     "list_entries", {"type": "skill"}),
        ("list_entries – android",   "list_entries", {"plugin": "android"}),
        ("search_entries",           "search_entries", {"query": "architecture"}),
        ("get_entry",                "get_entry", {"plugin": "android", "type": "skill", "name": "android-architecture"}),
        ("get_plugin",               "get_plugin", {"plugin": "research-suite"}),
        ("check_compliance – ok",    "check_compliance", {"entries": [{"name": "android-architecture", "type": "skill", "plugin": "android", "local_version": "0.1.0"}]}),
        ("check_compliance – old",   "check_compliance", {"entries": [{"name": "android-architecture", "type": "skill", "plugin": "android", "local_version": "0.0.1"}]}),
    ]

    passed = failed = 0
    for label, tool, args in tests:
        try:
            result = await _call_server(tool, args)
            summary = (
                f"{len(result)} entries" if isinstance(result, list)
                else str({k: v for k, v in result.items() if k != "content_raw"})[:120]
            )
            print(f"  ✓  {label:<35} → {summary}")
            passed += 1
        except Exception as exc:
            print(f"  ✗  {label:<35} → {exc}")
            failed += 1

    print(f"\n{passed + failed} tests — {passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    if not REGISTRY_PATH:
        print("Usage: REGISTRY_PATH=../gen-e2-marketplace python tests/test_e2e.py")
        sys.exit(1)
    asyncio.run(_main())
