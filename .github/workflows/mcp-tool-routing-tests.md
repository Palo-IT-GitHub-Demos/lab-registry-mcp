---
on:
  pull_request:
    types: [opened, synchronize, reopened]
    paths:
      - 'src/lab_registry/server.py'
      - 'src/lab_registry/tools/**'
      - 'tests/mcp_triggers.json'

permissions:
  contents: read
  pull-requests: read

# Engine: Copilot (Claude Sonnet 4.6).
# Advisory only — COMMENT event, never REQUEST_CHANGES.
# Re-runs supersede prior review via supersede-older-reviews.
engine:
  id: copilot

safe-outputs:
  submit-pull-request-review:
    max: 1
    allowed-events: [COMMENT]
    supersede-older-reviews: true

tools:
  github:
    toolsets: [context, repos, pull_requests]
---

# MCP Tool Routing Test Runner

You are running tool-routing tests for the **Lab Registry MCP server**.
These tests verify that a natural-language prompt would be routed to the
correct MCP tool, given the tool descriptions registered in `server.py`.

The structural/CI workflow has already verified that the code builds and
unit tests pass. Your job is to **simulate the routing decision** an LLM
client (Claude, Copilot Agent, etc.) would make when presented with each
prompt, then report the results as a PR comment.

This workflow is **advisory**. Test failures do not block merge — they
surface routing regressions so reviewers can decide whether a tool
description needs to be improved.

## Output contract — CRITICAL

Your final message MUST contain, in this exact order:

1. **Headline** — one line opening with `MCP routing tests:` and the
   overall tally.

   Examples:
   - `MCP routing tests: 21/23 passing.`
   - `MCP routing tests: all 23 passing.`
   - `MCP routing tests: skipped — no tool descriptions or trigger file changed.`

2. **Results table** — a single `<details>` block (use `<details open>`
   if any test fails). Render this exact markdown:

   ```
   <details open>  <!-- when any test fails — otherwise just <details> -->
   <summary><strong>N/M passing</strong></summary>

   | # | Intent | Prompt | Expected | Got | Result |
   |---|---|---|---|---|---|
   | 1 | discovery — all entries | List all entries... | list_entries | list_entries | ✅ |
   | 8 | natural language suggestion | I need to review... | suggest_entries | list_entries | ❌ |

   For each ❌ row, add one bullet below the table explaining:
   - which tool was chosen and why its description seemed to match
   - why the expected tool was not selected
   - a concrete suggestion to improve the tool description in server.py

   </details>
   ```

3. **Verdict marker** at the very end:
   - `<!-- mcp-routing: pass -->` if every test passed.
   - `<!-- mcp-routing: partial -->` if at least one test failed.
   - `<!-- mcp-routing: error -->` if the trigger file was unreadable or
     server.py tool descriptions could not be extracted.

## Procedure

### Step 1 — Check scope

Read the changed files in this PR. If neither `src/lab_registry/server.py`,
`src/lab_registry/tools/**`, nor `tests/mcp_triggers.json` was modified,
post: `MCP routing tests: skipped — no tool descriptions or trigger file changed.`
and stop.

### Step 2 — Build the routing menu

Read `src/lab_registry/server.py`. Extract every function decorated with
`@mcp.tool()`. For each, capture:
- **Tool name** — the function name (e.g. `list_entries`)
- **Description** — the full docstring (this is what an LLM client sees)

The routing menu is the complete list of `(tool_name, description)` pairs.
There are currently 15 tools. If extraction fails, emit `<!-- mcp-routing: error -->`.

### Step 3 — Read the test corpus

Read `tests/mcp_triggers.json`. Parse the `tests` array. Each item has:
- `id`: integer
- `intent`: short label (for the table)
- `prompt`: natural-language user request
- `expected`: tool name string, or `null` (meaning no tool should fire)

### Step 4 — Route each prompt

For each test case:

**Make your routing decision BEFORE looking at `expected`.**

Present yourself with the routing menu (tool names + descriptions) and the
prompt. Decide which single tool whose description most clearly matches the
prompt's intent. If none clearly match, the result is `null`.

Rules that mirror real LLM client behaviour:
- Read the full docstring, especially `Use this when…` and `Use this ONLY
  when…` clauses — these are explicit routing signals.
- `suggest_entries` / `suggest_plugins` fire for natural-language task
  descriptions where the user does NOT know a specific artifact name.
- `search_entries` fires for exact keyword or partial name searches.
- `list_entries` fires when the user wants to enumerate entries, optionally
  filtered by type, plugin, or tag.
- `get_entry` fires ONLY when the user specifies exact plugin + type + name.
- `get_entry_by_id` fires when the user provides a full id in `plugin/type/name`
  format.
- `check_compliance_plugin` fires when a single plugin name + version is
  given; `check_compliance` fires when a list of individual artefacts is given.
- Anti-triggers (`expected: null`): if the prompt is out of scope for this
  registry server entirely (e.g. deploy, git, weather), return `null`.
- Be willing to return `null`. Forcing a match is exactly the over-firing
  failure mode these anti-trigger tests catch.

After deciding, compare to `expected`. Pass = match (including both `null`).

### Step 5 — Compose the comment

Tally pass/fail across all tests. Build the table. For each failure, write
one actionable bullet pointing to the specific docstring in `server.py`
that should be improved and how.

## Routing reference — tool descriptions are the source of truth

Do not hard-code routing logic. The descriptions in `server.py` ARE the
specification. If a description is ambiguous and causes a mis-route, that
is the finding — report it in the failure bullet with a concrete rewrite
suggestion for the `@mcp.tool()` docstring.
