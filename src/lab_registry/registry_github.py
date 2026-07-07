"""GitHub-backed registry loader.

Fetches the gen-e2 marketplace directly from GitHub without requiring a local clone.
Uses a single Git Trees API call to discover all file paths, then fetches file content
via raw.githubusercontent.com (not rate-limited).

Environment variables:
    REGISTRY_GITHUB_REPO    Required. e.g. "GLOBAL-PALO-IT/gen-e2-marketplace"
    REGISTRY_GITHUB_BRANCH  Optional. Default: "main"
    REGISTRY_GITHUB_TOKEN   Optional. GitHub PAT for private repos or higher API rate limits.
                            Unauthenticated: 60 API req/h (1 req at startup is sufficient).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from lab_registry.models import ArtifactType, Plugin, RegistryEntry
from lab_registry.registry import _parse_frontmatter, _parse_updated_at


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _fetch_text(url: str, token: str | None = None) -> str | None:
    """GET url → decoded text. Returns None on 404, raises on other HTTP errors."""
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "lab-registry-mcp/0.1")
    req.add_header("Accept", "application/vnd.github+json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def _raw_url(owner: str, repo: str, branch: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"


def _get_repo_tree(owner: str, repo: str, branch: str, token: str | None) -> set[str]:
    """Fetch the full repo file tree in a single API call.

    Returns a set of all blob (file) paths. This is the only rate-limited API
    call made per registry load — raw file fetches are via CDN and not limited.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    text = _fetch_text(url, token)
    if text is None:
        raise FileNotFoundError(
            f"Repository '{owner}/{repo}@{branch}' not found or not accessible. "
            "Set REGISTRY_GITHUB_TOKEN if the repo is private."
        )
    data = json.loads(text)
    return {item["path"] for item in data.get("tree", []) if item["type"] == "blob"}


# ---------------------------------------------------------------------------
# Per-artifact loaders (GitHub variants)
# ---------------------------------------------------------------------------

def _load_github_skill(
    plugin: str, version: str, updated_at: str | None, tags: list[str],
    skill_path: str, skill_name: str,
    owner: str, repo: str, branch: str, token: str | None,
) -> RegistryEntry | None:
    text = _fetch_text(_raw_url(owner, repo, branch, f"{skill_path}/SKILL.md"), token)
    if not text:
        return None
    meta, _ = _parse_frontmatter(text)
    name = str(meta.get("name") or skill_name)
    return RegistryEntry(
        id=f"{plugin}/skill/{name}",
        name=name,
        type=ArtifactType.skill,
        plugin=plugin,
        plugin_version=version,
        description=str(meta.get("description", "")),
        path=f"{skill_path}/SKILL.md",
        updated_at=updated_at,
        tags=tags,
        disable_model_invocation=bool(meta.get("disable-model-invocation", False)),
        model=meta.get("model"),
        allowed_tools=list(meta.get("allowed-tools") or []),
        context=meta.get("context"),
        agent_skills=list(meta.get("skills") or []),
    )


def _load_github_agent(
    plugin: str, version: str, updated_at: str | None, tags: list[str],
    agent_path: str,
    owner: str, repo: str, branch: str, token: str | None,
) -> RegistryEntry | None:
    text = _fetch_text(_raw_url(owner, repo, branch, agent_path), token)
    if not text:
        return None
    meta, _ = _parse_frontmatter(text)
    file_name = agent_path.rsplit("/", 1)[-1]
    stem = file_name[:-3]  # strip .md
    name = str(meta.get("name") or (stem[:-6] if stem.endswith(".agent") else stem))
    return RegistryEntry(
        id=f"{plugin}/agent/{name}",
        name=name,
        type=ArtifactType.agent,
        plugin=plugin,
        plugin_version=version,
        description=str(meta.get("description", "")),
        path=agent_path,
        updated_at=updated_at,
        tags=tags,
        model=meta.get("model"),
        allowed_tools=list(meta.get("tools") or []),
        agent_skills=list(meta.get("skills") or []),
    )


def _load_github_command(
    plugin: str, version: str, updated_at: str | None, tags: list[str],
    cmd_path: str,
    owner: str, repo: str, branch: str, token: str | None,
) -> RegistryEntry | None:
    text = _fetch_text(_raw_url(owner, repo, branch, cmd_path), token)
    if not text:
        return None
    meta, _ = _parse_frontmatter(text)
    name = cmd_path.rsplit("/", 1)[-1][:-3]  # strip .md
    hint_raw = meta.get("argument-hint")
    argument_hint = " ".join(hint_raw) if isinstance(hint_raw, list) else hint_raw
    return RegistryEntry(
        id=f"{plugin}/command/{name}",
        name=name,
        type=ArtifactType.command,
        plugin=plugin,
        plugin_version=version,
        description=str(meta.get("description", "")),
        path=cmd_path,
        updated_at=updated_at,
        tags=tags,
        allowed_tools=list(meta.get("allowed-tools") or []),
        argument_hint=argument_hint,
    )


def _load_github_plugin_entries(
    plugin_name: str, plugin_path: str, version: str, tags: list[str],
    updated_at: str | None,
    owner: str, repo: str, branch: str, token: str | None, tree: set[str],
) -> list[RegistryEntry]:
    entries: list[RegistryEntry] = []

    # Skills: every path matching "{plugin_path}/skills/{name}/SKILL.md"
    skills_prefix = f"{plugin_path}/skills/"
    skill_dirs = sorted({
        p[len(skills_prefix):].split("/")[0]
        for p in tree
        if p.startswith(skills_prefix) and p.endswith("/SKILL.md")
    })
    for skill_name in skill_dirs:
        entry = _load_github_skill(
            plugin_name, version, updated_at, tags,
            f"{plugin_path}/skills/{skill_name}", skill_name,
            owner, repo, branch, token,
        )
        if entry:
            entries.append(entry)

    # Agents: every direct .md child of "{plugin_path}/agents/"
    agents_prefix = f"{plugin_path}/agents/"
    agent_paths = sorted(
        p for p in tree
        if p.startswith(agents_prefix)
        and p.endswith(".md")
        and "/" not in p[len(agents_prefix):]
    )
    for agent_path in agent_paths:
        entry = _load_github_agent(
            plugin_name, version, updated_at, tags,
            agent_path, owner, repo, branch, token,
        )
        if entry:
            entries.append(entry)

    # Commands: every direct .md child of "{plugin_path}/commands/"
    commands_prefix = f"{plugin_path}/commands/"
    cmd_paths = sorted(
        p for p in tree
        if p.startswith(commands_prefix)
        and p.endswith(".md")
        and "/" not in p[len(commands_prefix):]
    )
    for cmd_path in cmd_paths:
        entry = _load_github_command(
            plugin_name, version, updated_at, tags,
            cmd_path, owner, repo, branch, token,
        )
        if entry:
            entries.append(entry)

    # Hooks
    hooks_path = f"{plugin_path}/hooks.json"
    if hooks_path in tree:
        hooks_text = _fetch_text(_raw_url(owner, repo, branch, hooks_path), token)
        if hooks_text:
            hooks_data = json.loads(hooks_text)
            events = list(hooks_data.get("hooks", {}).keys())
            entries.append(RegistryEntry(
                id=f"{plugin_name}/hook/hooks",
                name="hooks",
                type=ArtifactType.hook,
                plugin=plugin_name,
                plugin_version=version,
                description=f"Hooks for {plugin_name}: {', '.join(events)}",
                path=hooks_path,
                updated_at=updated_at,
                tags=tags,
                hook_events=events,
            ))

    return entries


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_registry_from_github() -> tuple[list[RegistryEntry], dict[str, Plugin]]:
    """Load registry from GitHub. Reads env vars at call time."""
    repo_spec = os.environ.get("REGISTRY_GITHUB_REPO", "")
    if not repo_spec or "/" not in repo_spec:
        raise EnvironmentError(
            "REGISTRY_GITHUB_REPO must be set to 'owner/repo' "
            "(e.g. GLOBAL-PALO-IT/gen-e2-marketplace)"
        )
    owner, repo = repo_spec.split("/", 1)
    branch = os.environ.get("REGISTRY_GITHUB_BRANCH", "main")
    token = os.environ.get("REGISTRY_GITHUB_TOKEN")

    # One rate-limited API call to discover all file paths
    tree = _get_repo_tree(owner, repo, branch, token)

    # Fetch marketplace.json
    marketplace_path = ".claude-plugin/marketplace.json"
    if marketplace_path not in tree:
        raise FileNotFoundError(
            f"marketplace.json not found in '{owner}/{repo}'. "
            "Is this a gen-e2-compatible repository?"
        )
    marketplace_text = _fetch_text(_raw_url(owner, repo, branch, marketplace_path), token)
    if not marketplace_text:
        raise FileNotFoundError(f"Could not fetch marketplace.json from '{owner}/{repo}'")
    marketplace = json.loads(marketplace_text)

    all_entries: list[RegistryEntry] = []
    plugins: dict[str, Plugin] = {}

    for spec in marketplace.get("plugins", []):
        plugin_name = spec["name"]
        source = spec.get("source", "")
        if not isinstance(source, str):
            continue
        # source is "./plugins/android" → strip leading "./" → "plugins/android"
        plugin_path = source.lstrip("./").lstrip("/")

        # Plugin metadata
        plugin_meta: dict = {}
        plugin_json_path = f"{plugin_path}/.claude-plugin/plugin.json"
        if plugin_json_path in tree:
            pj_text = _fetch_text(_raw_url(owner, repo, branch, plugin_json_path), token)
            if pj_text:
                plugin_meta = json.loads(pj_text)

        version = spec.get("version") or plugin_meta.get("version", "0.0.0")
        tags: list[str] = plugin_meta.get("keywords", [])
        description = spec.get("description") or plugin_meta.get("description", "")
        author_raw = plugin_meta.get("author")
        author = (
            author_raw if isinstance(author_raw, str)
            else (author_raw.get("name") if isinstance(author_raw, dict) else None)
        )

        # updated_at from CHANGELOG.md
        updated_at: str | None = None
        changelog_path = f"{plugin_path}/CHANGELOG.md"
        if changelog_path in tree:
            cl_text = _fetch_text(_raw_url(owner, repo, branch, changelog_path), token)
            if cl_text:
                updated_at = _parse_updated_at(cl_text)

        entries = _load_github_plugin_entries(
            plugin_name, plugin_path, version, tags, updated_at,
            owner, repo, branch, token, tree,
        )
        all_entries.extend(entries)

        plugins[plugin_name] = Plugin(
            name=plugin_name,
            version=version,
            description=description,
            tags=tags,
            author=author,
            plugin_license=plugin_meta.get("license"),
            source_path=plugin_path,
            updated_at=updated_at,
        )

    return all_entries, plugins


def fetch_entry_content_github(entry: RegistryEntry) -> tuple[dict, str, str]:
    """Fetch a single entry's raw file content from GitHub.

    Returns (parsed_frontmatter, markdown_body, verbatim_content).
    Called by registry.get_entry_content() when REGISTRY_GITHUB_REPO is set.
    """
    repo_spec = os.environ.get("REGISTRY_GITHUB_REPO", "")
    owner, repo = repo_spec.split("/", 1)
    branch = os.environ.get("REGISTRY_GITHUB_BRANCH", "main")
    token = os.environ.get("REGISTRY_GITHUB_TOKEN")

    text = _fetch_text(_raw_url(owner, repo, branch, entry.path), token)
    if text is None:
        raise FileNotFoundError(
            f"Entry file not found on GitHub: {entry.path} in {repo_spec}@{branch}"
        )
    metadata, content_raw = _parse_frontmatter(text)
    return metadata, content_raw, text


def fetch_raw_file(path: str) -> str | None:
    """Fetch any file from the configured GitHub repo. Returns None if not found."""
    repo_spec = os.environ.get("REGISTRY_GITHUB_REPO", "")
    if not repo_spec or "/" not in repo_spec:
        return None
    owner, repo = repo_spec.split("/", 1)
    branch = os.environ.get("REGISTRY_GITHUB_BRANCH", "main")
    token = os.environ.get("REGISTRY_GITHUB_TOKEN")
    return _fetch_text(_raw_url(owner, repo, branch, path), token)
