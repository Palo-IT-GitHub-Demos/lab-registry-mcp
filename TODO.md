# TODO — Lab Registry Server

Last reviewed: 2026-10-13. This file tracks current baseline and genuinely open work.

## Current baseline

- Package version: `0.3.0` (`pyproject.toml`); matching release tag: `v0.3.0`.
- MCP tools: 15, including `suggest_plugins` and `get_plugin_install_package`.
- Default collection: 193 tests (`pytest --collect-only -q`); the NL module is excluded unless explicitly enabled and Ollama is healthy.
- Without `REGISTRY_PATH`: 158 passed, 36 skipped (15 integration, 20 E2E, and the NL module).
- With the local marketplace snapshot: 193 passed, 1 skipped (the NL module).
- Measurements above used Python 3.14.6; GitHub Actions covers Python 3.12 and 3.13.

## Recently completed

- Full-content responses and install targets, including `get_plugin_install_package`.
- Plugin discovery via `suggest_plugins`; search-vs-suggestion guidance is documented.
- Hook JSON validation and safe rejection of non-mapping YAML frontmatter.
- Portable MCP executable resolution and subprocess cleanup in E2E tests.
- NL dispatch tests gated by `RUN_NL_TESTS=1` and a 500 ms Ollama health check.
- CI matrix for Python 3.12/3.13 and release tests before packaging.

## Future improvements

- [ ] Add optional per-artifact versioning; versions are currently tracked per plugin.
- [ ] Detect deprecated artifacts when the marketplace format exposes that metadata.
- [ ] Add incremental cache invalidation for large or frequently updated registries.
- [ ] Consider `get_entry_batch`, a structured plugin-version diff, and a snapshot export tool.
- [ ] Replace token examples with client secret-input/keychain guidance and document private-repository approval paths.
