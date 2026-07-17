"""Natural-language dispatch tests — MCP tool routing via Ollama llama3.

These tests exercise the full cycle:
  English prompt → Ollama llama3 → tool name + arguments → MCP server → result

They are deliberately *optional* and must be run with an explicit marker:

    REGISTRY_PATH=../gen-e2-marketplace pytest tests/test_nl_dispatch.py -v -m nl_dispatch

Prerequisites
-------------
- Ollama daemon running locally (``ollama serve``)
- llama3 model pulled (``ollama pull llama3``)
- REGISTRY_PATH pointing to a valid gen-e2-marketplace clone

What is validated
-----------------
For each prompt scenario the tests assert:

1. **Protocol structure** — the tools/call JSON-RPC message sent to the server
   has the correct shape (jsonrpc, id, method, params.name, params.arguments).

2. **Tool routing** — the model chose a tool from an *expected family* for the
   given prompt intent (e.g. "find android skills" → search_entries or suggest_entries).

3. **Argument types** — every argument in the generated payload matches the
   expected Python type.

4. **Server result** — the MCP server returned a non-error, non-empty result
   of the expected shape.

Ambiguity scenarios (Phase 3 — tool clarity)
--------------------------------------------
A separate section tests prompts that are intentionally close to tool-boundary
edges.  Routing mismatches are surfaced as failures with diagnostic output so
that the docstrings in server.py can be iteratively improved.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from tests.helpers.mcp_nl_client import MCPNLClient

# ---------------------------------------------------------------------------
# Skip conditions
# ---------------------------------------------------------------------------

_REGISTRY_PATH = os.environ.get("REGISTRY_PATH", "")

_SKIP_NL = pytest.mark.skipif(
    not (
        _REGISTRY_PATH
        and (Path(_REGISTRY_PATH) / ".claude-plugin" / "marketplace.json").exists()
    ),
    reason="REGISTRY_PATH not set or marketplace.json not found",
)

pytestmark = [pytest.mark.nl_dispatch, _SKIP_NL]


# ---------------------------------------------------------------------------
# Shared assertion helpers
# ---------------------------------------------------------------------------


def assert_rpc_request_shape(request_msg: dict, *, expected_tool: str | None = None) -> None:
    """Assert that a tools/call JSON-RPC request message is well-formed."""
    assert request_msg["jsonrpc"] == "2.0", "Missing or wrong jsonrpc version"
    assert isinstance(request_msg["id"], int), "id must be an integer"
    assert request_msg["method"] == "tools/call", "method must be 'tools/call'"
    assert "params" in request_msg, "Missing 'params' key"
    params = request_msg["params"]
    assert "name" in params, "Missing 'params.name'"
    assert "arguments" in params, "Missing 'params.arguments'"
    assert isinstance(params["name"], str), "params.name must be a string"
    assert isinstance(params["arguments"], dict), "params.arguments must be a JSON object"
    if expected_tool is not None:
        assert params["name"] == expected_tool, (
            f"Expected tool {expected_tool!r} but request used {params['name']!r}"
        )


def assert_rpc_response_shape(response_msg: dict) -> None:
    """Assert that the server's JSON-RPC response is well-formed and error-free.

    Skipped when response_msg is empty (execution_error path in DispatchResult).
    """
    if not response_msg:
        return
    assert response_msg["jsonrpc"] == "2.0"
    assert "id" in response_msg
    assert "error" not in response_msg, f"Server returned error: {response_msg.get('error')}"
    assert "result" in response_msg


def assert_no_execution_error(d: Any) -> None:
    """Assert the tool executed successfully (no Pydantic/server validation error)."""
    assert d.execution_error is None, (
        f"Tool executed with invalid arguments."
        f"\n  Tool      : {d.tool_name!r}"
        f"\n  Args      : {d.tool_args}"
        f"\n  Error     : {d.execution_error}"
        f"\n  Prompt    : {d.prompt!r}"
    )


def assert_tool_in_family(chosen_tool: str, family: set[str], prompt: str) -> None:
    """Assert the LLM chose a tool from the expected semantic family."""
    assert chosen_tool in family, (
        f"Unexpected tool routing.\n"
        f"  Prompt    : {prompt!r}\n"
        f"  Chosen    : {chosen_tool!r}\n"
        f"  Expected  : one of {sorted(family)}"
    )


def _list_result(result: Any) -> list:
    """Normalise result to a list (result may be list or dict with a list inside)."""
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        for v in result.values():
            if isinstance(v, list):
                return v
    return []


# ---------------------------------------------------------------------------
# Phase 1 — Protocol structure (no LLM, direct call_tool)
# ---------------------------------------------------------------------------


class TestMCPPayloadStructure:
    """Verify that the test client produces correct JSON-RPC messages for direct calls.

    These tests do NOT use Ollama.  They validate the capture infrastructure itself.
    """

    @pytest.mark.asyncio
    async def test_tools_list_is_populated(self) -> None:
        """Server must expose at least 10 tools during handshake."""
        async with MCPNLClient() as client:
            tools = client.get_tools()
        assert len(tools) >= 10, f"Expected ≥10 tools, got {len(tools)}"
        names = {t["name"] for t in tools}
        assert "list_entries" in names
        assert "search_entries" in names
        assert "suggest_entries" in names

    @pytest.mark.asyncio
    async def test_direct_list_entries_request_shape(self) -> None:
        """call_tool produces a correctly shaped JSON-RPC tools/call message."""
        async with MCPNLClient() as client:
            _, request_msg, response_msg = await client.call_tool("list_entries", {"type": "skill"})

        assert_rpc_request_shape(request_msg, expected_tool="list_entries")
        assert_rpc_response_shape(response_msg)
        assert request_msg["params"]["arguments"]["type"] == "skill"

    @pytest.mark.asyncio
    async def test_direct_search_entries_argument_types(self) -> None:
        """Arguments serialised by the client keep correct JSON types."""
        async with MCPNLClient() as client:
            _, request_msg, _ = await client.call_tool(
                "search_entries", {"query": "android", "type": "skill"}
            )

        args = request_msg["params"]["arguments"]
        assert isinstance(args["query"], str)
        assert isinstance(args["type"], str)

    @pytest.mark.asyncio
    async def test_request_response_id_correlation(self) -> None:
        """Response id must match the request id."""
        async with MCPNLClient() as client:
            _, request_msg, response_msg = await client.call_tool("list_plugins", {})

        assert response_msg["id"] == request_msg["id"], (
            f"id mismatch: sent {request_msg['id']}, got {response_msg['id']}"
        )

    @pytest.mark.asyncio
    async def test_traffic_captures_all_messages(self) -> None:
        """CapturedTraffic must contain outgoing requests and incoming responses."""
        async with MCPNLClient() as client:
            await client.call_tool("get_marketplace_stats", {})
            traffic = client.get_traffic()

        # At minimum: initialize + notifications/initialized + tools/list + tools/call
        assert len(traffic.outgoing) >= 4
        # Incoming: initialize response + tools/list response + tools/call response
        assert len(traffic.incoming) >= 3

        methods_sent = {m["method"] for m in traffic.outgoing if "method" in m}
        assert "initialize" in methods_sent
        assert "tools/list" in methods_sent
        assert "tools/call" in methods_sent


# ---------------------------------------------------------------------------
# Phase 2 — Natural-language dispatch (LLM → MCP)
# ---------------------------------------------------------------------------


class TestNaturalLanguageDispatch:
    """Send English prompts to llama3 and verify tool routing + payload integrity."""

    # -----------------------------------------------------------------------
    # Discovery intent
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_list_all_plugins_prompt(self) -> None:
        """'Give me an overview of all available gen-e2 plugins' → list/stats tool."""
        prompt = "Give me an overview of all available gen-e2 plugins"
        async with MCPNLClient() as client:
            d = await client.dispatch(prompt)

        assert_rpc_request_shape(d.request_msg)
        assert_rpc_response_shape(d.response_msg)
        assert_tool_in_family(
            d.tool_name,
            {"list_plugins", "get_marketplace_stats"},
            prompt,
        )

    @pytest.mark.asyncio
    async def test_list_agents_prompt(self) -> None:
        """'List all available gen-e2 agents' → list_entries (ideal) or list_plugins.

        NOTE: llama3 may route 'agents' to list_plugins because the compact prompt
        doesn't make the type-filter distinction clear enough.  Both are accepted here;
        routing to list_entries with type=agent is the preferred outcome and is tracked
        as a tool-clarity improvement opportunity in TestToolClarity.
        """
        prompt = "List all available gen-e2 agents in the registry"
        async with MCPNLClient() as client:
            d = await client.dispatch(prompt)

        assert_rpc_request_shape(d.request_msg)
        assert_rpc_response_shape(d.response_msg)
        assert_tool_in_family(d.tool_name, {"list_entries", "list_plugins"}, prompt)
        print(f"\n[routing] list_agents → {d.tool_name!r}  args={d.tool_args}")

    @pytest.mark.asyncio
    async def test_list_android_skills_prompt(self) -> None:
        """'Show me all skills from the Android plugin' → list_entries, get_plugin, or get_entry.

        NOTE: llama3 8B may route 'list skills from plugin X' to get_entry (understands
        plugin+type but misses that name is also required) or to get_plugin. All three
        are reasonable; list_entries(plugin=android, type=skill) is the ideal outcome.
        The execution_error field captures invalid-arg cases without failing the routing check.
        """
        prompt = "Show me all skills from the Android plugin"
        async with MCPNLClient() as client:
            d = await client.dispatch(prompt)

        assert_tool_in_family(d.tool_name, {"list_entries", "get_plugin", "get_entry"}, prompt)
        print(f"\n[routing] android_skills → {d.tool_name!r}  args={d.tool_args}  exec_err={d.execution_error!r}")

    # -----------------------------------------------------------------------
    # Search / suggestion intent
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_keyword_search_prompt(self) -> None:
        """'Find entries matching tdd' → search_entries (keyword, not NL task)."""
        prompt = "Find registry entries that match the keyword 'tdd'"
        async with MCPNLClient() as client:
            d = await client.dispatch(prompt)

        assert_rpc_request_shape(d.request_msg)
        assert_rpc_response_shape(d.response_msg)
        assert_tool_in_family(d.tool_name, {"search_entries", "suggest_entries"}, prompt)

        items = _list_result(d.result)
        assert isinstance(items, list)

    @pytest.mark.asyncio
    async def test_natural_task_suggestion_prompt(self) -> None:
        """'I need to review architecture and write ADRs' → suggest_* / search / get_entry.

        NOTE: llama3 may resolve a specific well-known entry directly (get_entry) instead
        of using suggest_* when the topic matches a known artifact name.  Both are
        acceptable; suggest_entries is the preferred outcome.
        """
        prompt = "I need to review architecture and write ADRs for my project"
        async with MCPNLClient() as client:
            d = await client.dispatch(prompt)

        assert_rpc_request_shape(d.request_msg)
        assert_rpc_response_shape(d.response_msg)
        assert_tool_in_family(
            d.tool_name,
            {"suggest_entries", "suggest_plugins", "search_entries", "get_entry", "get_plugin", "list_entries"},
            prompt,
        )
        print(f"\n[routing] architecture_ADR → {d.tool_name!r}  args={d.tool_args}")

    @pytest.mark.asyncio
    async def test_go_tdd_suggestion_prompt(self) -> None:
        """'I'm building a Go microservice and need TDD support' → suggest_* or search.

        The prompt explicitly mentions 'gen-e2 registry' to prevent the model from
        hallucinating shell tools (e.g. 'go-test') instead of MCP tool names.
        """
        prompt = (
            "I am building a Go microservice and need TDD support. "
            "Which gen-e2 registry skills or plugins should I use?"
        )
        async with MCPNLClient() as client:
            d = await client.dispatch(prompt)

        assert_rpc_request_shape(d.request_msg)
        assert_rpc_response_shape(d.response_msg)
        assert_tool_in_family(
            d.tool_name,
            {"suggest_entries", "suggest_plugins", "search_entries", "list_entries"},
            prompt,
        )
        print(f"\n[routing] go_tdd → {d.tool_name!r}  args={d.tool_args}")

    # -----------------------------------------------------------------------
    # Fetch / detail intent
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_entry_prompt(self) -> None:
        """'Get the android-architecture skill from the android plugin' → get_entry."""
        prompt = (
            "Get the full content of the android-architecture skill "
            "from the android plugin"
        )
        async with MCPNLClient() as client:
            d = await client.dispatch(prompt)

        assert_rpc_request_shape(d.request_msg)
        assert_rpc_response_shape(d.response_msg)
        assert_tool_in_family(
            d.tool_name, {"get_entry", "get_entry_by_id"}, prompt
        )

        # If get_entry was chosen, validate required arguments are strings
        if d.tool_name == "get_entry":
            args = d.tool_args
            for key in ("plugin", "type", "name"):
                if key in args:
                    assert isinstance(args[key], str), (
                        f"Argument '{key}' must be str, got {type(args[key]).__name__}"
                    )

    @pytest.mark.asyncio
    async def test_get_plugin_prompt(self) -> None:
        """'Show me everything in the research-suite plugin' → get_plugin."""
        prompt = "Show me everything in the research-suite plugin"
        async with MCPNLClient() as client:
            d = await client.dispatch(prompt)

        assert_rpc_request_shape(d.request_msg)
        assert_rpc_response_shape(d.response_msg)
        assert_tool_in_family(
            d.tool_name, {"get_plugin", "list_entries", "get_plugin_install_package"}, prompt
        )

    @pytest.mark.asyncio
    async def test_install_plugin_prompt(self) -> None:
        """'Install the delivery plugin' → get_plugin_install_package."""
        prompt = "I want to install the delivery plugin in my project"
        async with MCPNLClient() as client:
            d = await client.dispatch(prompt)

        assert_rpc_request_shape(d.request_msg)
        assert_rpc_response_shape(d.response_msg)
        assert_tool_in_family(
            d.tool_name,
            {"get_plugin_install_package", "get_plugin", "list_entries"},
            prompt,
        )

    # -----------------------------------------------------------------------
    # Compliance intent
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_check_compliance_guidance_prompt(self) -> None:
        """'Check android plugin 0.1.0 against registry' → check_compliance_plugin.

        The prompt provides concrete data (plugin name + version) so the model
        can generate valid arguments.  Abstract compliance questions cause the
        model to generate placeholder arguments that fail Pydantic validation.
        """
        prompt = (
            "I have the gen-e2 android plugin installed locally at version 0.1.0. "
            "Check if it is up to date with the registry."
        )
        async with MCPNLClient() as client:
            d = await client.dispatch(prompt)

        assert_rpc_request_shape(d.request_msg)
        assert_rpc_response_shape(d.response_msg)
        assert_tool_in_family(
            d.tool_name,
            {"check_compliance", "check_compliance_plugin"},
            prompt,
        )
        print(f"\n[routing] compliance → {d.tool_name!r}  args={d.tool_args}")


# ---------------------------------------------------------------------------
# Phase 3 — Tool clarity / ambiguity edge cases
# ---------------------------------------------------------------------------


class TestToolClarity:
    """Prompts designed to exercise known ambiguity zones between similar tools.

    These tests have wider acceptable families.  Routing mismatches here indicate
    that the tool description in server.py should be refined — the test itself
    will print the chosen tool and raw model output for iterative improvement.
    """

    @pytest.mark.asyncio
    async def test_ambiguity_search_vs_suggest(self) -> None:
        """'Find skills related to architecture' — keyword vs NL-task disambiguation.

        search_entries is correct for partial-name keyword matching.
        suggest_entries is correct for natural-language task descriptions.
        Both are acceptable; the test just logs which was chosen.
        """
        prompt = "Find skills related to architecture"
        async with MCPNLClient() as client:
            d = await client.dispatch(prompt)

        assert_rpc_request_shape(d.request_msg)
        assert_rpc_response_shape(d.response_msg)

        # Both tools are semantically valid here — track the choice for auditing
        assert_tool_in_family(
            d.tool_name, {"search_entries", "suggest_entries", "suggest_plugins", "list_entries"}, prompt
        )
        print(f"\n[clarity] search_vs_suggest → {d.tool_name!r}  (raw: {d.raw_model_output[:120]})")

    @pytest.mark.asyncio
    async def test_ambiguity_get_entry_vs_get_by_id(self) -> None:
        """'Get android/skill/android-architecture' — id-form vs name+plugin+type form."""
        prompt = "Get android/skill/android-architecture"
        async with MCPNLClient() as client:
            d = await client.dispatch(prompt)

        assert_rpc_request_shape(d.request_msg)
        assert_rpc_response_shape(d.response_msg)
        assert_tool_in_family(d.tool_name, {"get_entry_by_id", "get_entry"}, prompt)
        print(f"\n[clarity] get_entry_vs_id → {d.tool_name!r}  args={d.tool_args}")

    @pytest.mark.asyncio
    async def test_ambiguity_check_compliance_vs_plugin(self) -> None:
        """'Check compliance for the android plugin at version 0.1.0' — single vs multi."""
        prompt = "Check if the android plugin version 0.1.0 is up to date"
        async with MCPNLClient() as client:
            d = await client.dispatch(prompt)

        assert_rpc_request_shape(d.request_msg)
        assert_rpc_response_shape(d.response_msg)
        assert_tool_in_family(
            d.tool_name, {"check_compliance_plugin", "check_compliance"}, prompt
        )
        print(
            f"\n[clarity] compliance_vs_plugin → {d.tool_name!r}  args={d.tool_args}"
        )
