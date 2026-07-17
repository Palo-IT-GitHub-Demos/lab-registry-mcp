"""Minimal MCP + Ollama client used exclusively for natural-language dispatch tests.

This module is NOT part of the server runtime.  It belongs to the test layer only.

Responsibilities
----------------
1. Spawn the MCP server subprocess and run the JSON-RPC handshake.
2. Retrieve the tool list (``tools/list``) from the server so we can embed live
   descriptions in the LLM system prompt.
3. Send a natural-English user prompt to a local Ollama model and parse its
   tool-call response.
4. Execute the chosen tool against the MCP server and return **both** the server
   result and the full captured traffic (requests + responses).

The captured traffic is the key artifact for test assertions: it lets tests verify
*which* tool name and *which* arguments the client sent, independently of the final
server result.

Usage (from tests)
------------------
::

    from tests.helpers.mcp_nl_client import MCPNLClient

    async with MCPNLClient() as client:
        dispatch = await client.dispatch("Find all Android-related skills")
        # dispatch.tool_name     → "search_entries" (chosen by the LLM)
        # dispatch.tool_args     → {"query": "android", "type": "skill"}
        # dispatch.request_msg   → raw JSON-RPC tools/call dict sent to server
        # dispatch.response_msg  → raw JSON-RPC response dict from server
        # dispatch.result        → parsed result (list / dict)

Environment variables
---------------------
- ``REGISTRY_PATH``: passed through to the server subprocess.
- ``NL_OLLAMA_URL``: base URL for the Ollama API (default ``http://localhost:11434``).
- ``NL_OLLAMA_MODEL``: model name (default ``llama3``).
- ``NL_OLLAMA_TIMEOUT``: per-request timeout in seconds (default ``60``).
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_OLLAMA_URL = os.environ.get("NL_OLLAMA_URL", "http://localhost:11434")
_OLLAMA_MODEL = os.environ.get("NL_OLLAMA_MODEL", "llama3")
_OLLAMA_TIMEOUT = int(os.environ.get("NL_OLLAMA_TIMEOUT", "120"))

_REGISTRY_PATH = os.environ.get("REGISTRY_PATH", "")
_SERVER_SCRIPT = str(
    Path(__file__).parent.parent.parent / "src" / "lab_registry" / "server.py"
)
_MCP_BIN = str(
    Path(__file__).parent.parent.parent / ".venv" / "bin" / "mcp"
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class CapturedTraffic:
    """All JSON-RPC messages exchanged during a single session."""

    outgoing: list[dict] = field(default_factory=list)
    incoming: list[dict] = field(default_factory=list)


@dataclass
class DispatchResult:
    """Result of a natural-language prompt dispatched to the MCP server."""

    prompt: str
    tool_name: str
    tool_args: dict[str, Any]
    request_msg: dict        # The tools/call JSON-RPC message sent to server
    response_msg: dict       # The raw JSON-RPC response from server
    result: Any              # Parsed tool result (list | dict), None if execution_error is set
    traffic: CapturedTraffic
    raw_model_output: str    # Verbatim LLM output for diagnostics
    execution_error: str | None = None  # Pydantic/server error if args were invalid


# ---------------------------------------------------------------------------
# Ollama HTTP helper
# ---------------------------------------------------------------------------


def _ollama_generate(system: str, user: str) -> str:
    """Call Ollama /api/generate and return the concatenated response text.

    Uses urllib (stdlib) to avoid adding a dependency on ``requests`` or ``httpx``.
    Low temperature + json format maximise determinism for test reliability.
    """
    payload = {
        "model": _OLLAMA_MODEL,
        "prompt": user,
        "system": system,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.0,
            "seed": 42,
        },
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{_OLLAMA_URL}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_OLLAMA_TIMEOUT) as resp:
            body = json.loads(resp.read())
            return body.get("response", "")
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Cannot reach Ollama at {_OLLAMA_URL}. "
            "Is the daemon running? (ollama serve)"
        ) from exc


# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------


def _build_system_prompt(tools: list[dict]) -> str:
    """Build a strict system prompt embedding live tool descriptions.

    Discovery tools (suggest_*, search_*) are listed first to counteract
    the model's recency/primacy bias toward fetch/validation tools.
    Only the first sentence of each description is included to keep the
    prompt compact and within llama3's reliable response window.
    """
    # Sort: discovery tools first, then fetch, then compliance/other
    _PRIORITY = {
        "suggest_plugins": 0, "suggest_entries": 1,
        "search_entries": 2, "list_entries": 3, "list_plugins": 4,
        "get_plugin": 5, "get_entry": 6, "get_entry_by_id": 7,
        "get_plugin_install_package": 8, "get_changelog": 9,
        "check_compliance_plugin": 10, "check_compliance": 11,
        "get_marketplace_stats": 12, "validate_entry": 13, "reload_registry": 14,
    }
    sorted_tools = sorted(tools, key=lambda t: _PRIORITY.get(t.get("name", ""), 99))

    tool_docs = []
    for t in sorted_tools:
        name = t.get("name", "")
        description = t.get("description", "").strip()
        # Use only the first sentence to keep the prompt compact
        first_sentence = description.split("\n")[0].split(".")[0].strip()
        params = t.get("inputSchema", {}).get("properties", {})
        required = t.get("inputSchema", {}).get("required", [])
        param_names = ", ".join(
            f"{k}{'*' if k in required else ''}"
            for k in params
        )
        tool_docs.append(f"- {name}: {first_sentence}. params=[{param_names or 'none'}]")

    tools_block = "\n".join(tool_docs)

    return f"""You are a tool router for a gen-e2 skill/plugin registry. Pick ONE tool and return JSON only.

Key rules:
- Use suggest_plugins or suggest_entries when the user asks "which tools/skills/plugins should I use for X" or describes a task/project.
- Use search_entries for exact keyword searches.
- Use list_entries to enumerate entries by type (skill/agent/command/hook) or plugin.
- Use get_entry only when you know the exact plugin, type AND name.
- Use validate_entry only to validate markdown file content, never for discovery.

Tools (* = required param):
{tools_block}

Respond ONLY with this JSON, no extra text:
{{"tool": "<name>", "arguments": {{"param": "value"}}}}
"""


# ---------------------------------------------------------------------------
# LLM output parser
# ---------------------------------------------------------------------------

_KNOWN_TOOLS = {
    "list_entries", "search_entries", "get_entry", "get_plugin",
    "check_compliance", "check_compliance_plugin", "reload_registry",
    "list_plugins", "get_entry_by_id", "get_changelog", "get_marketplace_stats",
    "suggest_entries", "suggest_plugins", "validate_entry",
    "get_plugin_install_package",
}

# Common singular/plural or typo hallucinations the model produces.
# Maps hallucinated name → nearest real tool.
_TOOL_CORRECTIONS: dict[str, str] = {
    "get_plugins": "get_plugin",
    "list_plugin": "list_plugins",
    "search_entry": "search_entries",
    "list_entry": "list_entries",
    "suggest_entry": "suggest_entries",
    "suggest_plugin": "suggest_plugins",
    "get_entries": "list_entries",
    "get_plugins_list": "list_plugins",
    "check_compliance_plugins": "check_compliance_plugin",
}


def _parse_model_output(raw: str, prompt: str) -> tuple[str, dict]:
    """Extract tool name and arguments from raw model output.

    Raises ``ValueError`` with a diagnostic message if the output is malformed,
    the tool name is unknown, or the arguments are not a JSON object.
    """
    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()

    # Find first JSON object in the output
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        raise ValueError(
            f"Model produced no JSON object.\n"
            f"  Prompt: {prompt!r}\n"
            f"  Raw output: {raw!r}"
        )

    try:
        parsed = json.loads(match.group())
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Model output is not valid JSON.\n"
            f"  Prompt: {prompt!r}\n"
            f"  Raw output: {raw!r}\n"
            f"  Parse error: {exc}"
        ) from exc

    tool_name = parsed.get("tool")
    if not tool_name:
        raise ValueError(
            f"Model output missing 'tool' key.\n"
            f"  Prompt: {prompt!r}\n"
            f"  Parsed: {parsed}"
        )

    # Attempt to correct common near-miss hallucinations before rejecting
    if tool_name not in _KNOWN_TOOLS:
        corrected = _TOOL_CORRECTIONS.get(tool_name)
        if corrected:
            tool_name = corrected
        else:
            raise ValueError(
                f"Model chose unknown tool {tool_name!r}.\n"
                f"  Prompt: {prompt!r}\n"
                f"  Parsed: {parsed}\n"
                f"  Known tools: {sorted(_KNOWN_TOOLS)}"
            )

    arguments = parsed.get("arguments", {}) or {}
    if not isinstance(arguments, dict):
        raise ValueError(
            f"Model 'arguments' must be a JSON object, got {type(arguments).__name__}.\n"
            f"  Prompt: {prompt!r}\n"
            f"  Parsed: {parsed}"
        )

    # Strip null values — MCP servers expect absent keys, not null
    arguments = {k: v for k, v in arguments.items() if v is not None}

    return tool_name, arguments


# ---------------------------------------------------------------------------
# MCP session
# ---------------------------------------------------------------------------


class MCPNLClient:
    """Async context manager that owns a single MCP server subprocess session.

    Provides:
    - ``get_tools()`` — fetch the tool list from the server
    - ``dispatch(prompt)`` — full NL → LLM → MCP → result cycle
    - ``call_tool(tool, args)`` — direct tool call (no LLM) with traffic capture
    """

    def __init__(self, registry_path: str = _REGISTRY_PATH) -> None:
        self._registry_path = registry_path
        self._proc: asyncio.subprocess.Process | None = None
        self._traffic = CapturedTraffic()
        self._rpc_id = 0
        self._tools: list[dict] = []

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "MCPNLClient":
        await self._start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._stop()

    # ------------------------------------------------------------------
    # Subprocess lifecycle
    # ------------------------------------------------------------------

    async def _start(self) -> None:
        self._proc = await asyncio.create_subprocess_exec(
            _MCP_BIN, "run", _SERVER_SCRIPT,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env={**os.environ, "REGISTRY_PATH": self._registry_path},
            limit=8 * 1024 * 1024,
        )
        # Run MCP handshake
        self._rpc_id = 1
        await self._send({
            "jsonrpc": "2.0", "id": self._rpc_id, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "nl-test-client", "version": "0.1"},
            },
        })
        init_resp = await self._recv()
        self._traffic.incoming.append(init_resp)

        self._rpc_id += 1
        await self._send({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        })

        # Fetch tool list so we can embed descriptions in the LLM prompt
        self._tools = await self._fetch_tools()

    async def _stop(self) -> None:
        if self._proc:
            try:
                self._proc.stdin.close()
                self._proc.kill()
                await self._proc.wait()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # JSON-RPC primitives
    # ------------------------------------------------------------------

    async def _send(self, msg: dict) -> None:
        self._traffic.outgoing.append(msg)
        line = json.dumps(msg) + "\n"
        assert self._proc and self._proc.stdin
        self._proc.stdin.write(line.encode())
        await self._proc.stdin.drain()

    async def _recv(self) -> dict:
        assert self._proc and self._proc.stdout
        line = await asyncio.wait_for(
            self._proc.stdout.readline(), timeout=15.0
        )
        msg = json.loads(line)
        return msg

    def _next_id(self) -> int:
        self._rpc_id += 1
        return self._rpc_id

    # ------------------------------------------------------------------
    # Tools list
    # ------------------------------------------------------------------

    async def _fetch_tools(self) -> list[dict]:
        rpc_id = self._next_id()
        await self._send({"jsonrpc": "2.0", "id": rpc_id, "method": "tools/list", "params": {}})
        resp = await self._recv()
        self._traffic.incoming.append(resp)
        return resp.get("result", {}).get("tools", [])

    def get_tools(self) -> list[dict]:
        """Return the tool list fetched during handshake."""
        return self._tools

    # ------------------------------------------------------------------
    # Direct tool call (no LLM)
    # ------------------------------------------------------------------

    async def call_tool(
        self, tool: str, args: dict
    ) -> tuple[Any, dict, dict]:
        """Call a tool directly and return (result, request_msg, response_msg)."""
        rpc_id = self._next_id()
        request_msg = {
            "jsonrpc": "2.0", "id": rpc_id, "method": "tools/call",
            "params": {"name": tool, "arguments": args},
        }
        await self._send(request_msg)
        response_msg = await self._recv()
        self._traffic.incoming.append(response_msg)

        if "error" in response_msg:
            raise RuntimeError(f"JSON-RPC error: {response_msg['error']}")

        result_body = response_msg.get("result", {})
        if result_body.get("isError"):
            text = (result_body.get("content") or [{}])[0].get("text", "tool error")
            raise RuntimeError(text)

        if "structuredContent" in result_body:
            result = result_body["structuredContent"].get(
                "result", result_body["structuredContent"]
            )
        else:
            content = result_body.get("content", [])
            if len(content) == 0:
                result = []
            elif len(content) > 1:
                result = [json.loads(item["text"]) for item in content]
            else:
                result = json.loads(content[0]["text"])

        return result, request_msg, response_msg

    # ------------------------------------------------------------------
    # Natural-language dispatch (LLM → MCP)
    # ------------------------------------------------------------------

    async def dispatch(self, prompt: str) -> DispatchResult:
        """Send a natural-English prompt to Ollama, parse its tool selection,
        then execute the tool against the MCP server.

        Returns a ``DispatchResult`` with all intermediate artifacts captured.
        """
        system = _build_system_prompt(self._tools)
        raw_output = _ollama_generate(system=system, user=prompt)
        tool_name, tool_args = _parse_model_output(raw_output, prompt)

        execution_error: str | None = None
        result: Any = None
        request_msg: dict = {}
        response_msg: dict = {}

        try:
            result, request_msg, response_msg = await self.call_tool(tool_name, tool_args)
        except RuntimeError as exc:
            # Server-side validation error (e.g. missing required field).
            # We still return a DispatchResult so tests can assert on routing
            # independently of argument quality.
            execution_error = str(exc)
            rpc_id = self._rpc_id
            request_msg = {
                "jsonrpc": "2.0", "id": rpc_id, "method": "tools/call",
                "params": {"name": tool_name, "arguments": tool_args},
            }

        return DispatchResult(
            prompt=prompt,
            tool_name=tool_name,
            tool_args=tool_args,
            request_msg=request_msg,
            response_msg=response_msg,
            result=result,
            traffic=self._traffic,
            raw_model_output=raw_output,
            execution_error=execution_error,
        )

    # ------------------------------------------------------------------
    # Traffic snapshot
    # ------------------------------------------------------------------

    def get_traffic(self) -> CapturedTraffic:
        """Return a snapshot of all captured JSON-RPC messages so far."""
        return self._traffic
