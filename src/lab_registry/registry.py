from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path

import yaml

from lab_registry.models import ArtifactType, Plugin, RegistryEntry


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def get_registry_path() -> Path:
    path = os.environ.get("REGISTRY_PATH")
    if not path:
        raise EnvironmentError("REGISTRY_PATH environment variable is not set")
    return Path(path).resolve()


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """Return (metadata_dict, body_string) from a markdown file with YAML frontmatter."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)", content, re.DOTALL)
    if not match:
        return {}, content
    try:
        metadata = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        metadata = {}
    return metadata, match.group(2).strip()


def _extract_updated_at(plugin_dir: Path) -> str | None:
    """Parse the most recent version date from CHANGELOG.md (best effort)."""
    changelog = plugin_dir / "CHANGELOG.md"
    if not changelog.exists():
        return None
    content = changelog.read_text(encoding="utf-8")
    # Handles em dash (—), en dash (–), or hyphen (-)
    match = re.search(r"##\s+\[[^\]]+\]\s+[—–-]+\s+(\d{4}-\d{2}-\d{2})", content)
    return match.group(1) if match else None


# ---------------------------------------------------------------------------
# Per-artifact loaders
# ---------------------------------------------------------------------------

def _load_skill(
    plugin: str, version: str, updated_at: str | None, tags: list[str],
    skill_dir: Path, root: Path,
) -> RegistryEntry | None:
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.exists():
        return None
    meta, _ = _parse_frontmatter(skill_file.read_text(encoding="utf-8"))
    name = str(meta.get("name") or skill_dir.name)
    return RegistryEntry(
        id=f"{plugin}/skill/{name}",
        name=name,
        type=ArtifactType.skill,
        plugin=plugin,
        plugin_version=version,
        description=str(meta.get("description", "")),
        path=str(skill_file.relative_to(root)),
        updated_at=updated_at,
        tags=tags,
        disable_model_invocation=bool(meta.get("disable-model-invocation", False)),
        model=meta.get("model"),
        allowed_tools=list(meta.get("allowed-tools") or []),
        context=meta.get("context"),
        agent_skills=list(meta.get("skills") or []),
    )


def _load_agent(
    plugin: str, version: str, updated_at: str | None, tags: list[str],
    agent_file: Path, root: Path,
) -> RegistryEntry | None:
    meta, _ = _parse_frontmatter(agent_file.read_text(encoding="utf-8"))
    # Strip ".agent" suffix if present: "android-architect.agent" → "android-architect"
    stem = agent_file.stem
    name = str(meta.get("name") or (stem[: -6] if stem.endswith(".agent") else stem))
    return RegistryEntry(
        id=f"{plugin}/agent/{name}",
        name=name,
        type=ArtifactType.agent,
        plugin=plugin,
        plugin_version=version,
        description=str(meta.get("description", "")),
        path=str(agent_file.relative_to(root)),
        updated_at=updated_at,
        tags=tags,
        model=meta.get("model"),
        allowed_tools=list(meta.get("tools") or []),
        agent_skills=list(meta.get("skills") or []),
    )


def _load_command(
    plugin: str, version: str, updated_at: str | None, tags: list[str],
    cmd_file: Path, root: Path,
) -> RegistryEntry | None:
    meta, _ = _parse_frontmatter(cmd_file.read_text(encoding="utf-8"))
    name = cmd_file.stem
    hint_raw = meta.get("argument-hint")
    argument_hint = " ".join(hint_raw) if isinstance(hint_raw, list) else hint_raw
    return RegistryEntry(
        id=f"{plugin}/command/{name}",
        name=name,
        type=ArtifactType.command,
        plugin=plugin,
        plugin_version=version,
        description=str(meta.get("description", "")),
        path=str(cmd_file.relative_to(root)),
        updated_at=updated_at,
        tags=tags,
        allowed_tools=list(meta.get("allowed-tools") or []),
        argument_hint=argument_hint,
    )


def _load_hooks(
    plugin: str, version: str, updated_at: str | None, tags: list[str],
    hooks_file: Path, root: Path,
) -> RegistryEntry | None:
    with hooks_file.open() as f:
        data = json.load(f)
    events = list(data.get("hooks", {}).keys())
    return RegistryEntry(
        id=f"{plugin}/hook/hooks",
        name="hooks",
        type=ArtifactType.hook,
        plugin=plugin,
        plugin_version=version,
        description=f"Hooks for {plugin}: {', '.join(events)}",
        path=str(hooks_file.relative_to(root)),
        updated_at=updated_at,
        tags=tags,
        hook_events=events,
    )


def _load_plugin_entries(
    plugin_name: str, plugin_dir: Path, version: str, tags: list[str], root: Path,
) -> list[RegistryEntry]:
    entries: list[RegistryEntry] = []
    updated_at = _extract_updated_at(plugin_dir)

    skills_dir = plugin_dir / "skills"
    if skills_dir.exists():
        for skill_dir in sorted(skills_dir.iterdir()):
            if skill_dir.is_dir():
                entry = _load_skill(plugin_name, version, updated_at, tags, skill_dir, root)
                if entry:
                    entries.append(entry)

    agents_dir = plugin_dir / "agents"
    if agents_dir.exists():
        for agent_file in sorted(agents_dir.glob("*.md")):  # catches both *.agent.md and *.md
            entry = _load_agent(plugin_name, version, updated_at, tags, agent_file, root)
            if entry:
                entries.append(entry)

    commands_dir = plugin_dir / "commands"
    if commands_dir.exists():
        for cmd_file in sorted(commands_dir.glob("*.md")):
            entry = _load_command(plugin_name, version, updated_at, tags, cmd_file, root)
            if entry:
                entries.append(entry)

    hooks_file = plugin_dir / "hooks.json"
    if hooks_file.exists():
        entry = _load_hooks(plugin_name, version, updated_at, tags, hooks_file, root)
        if entry:
            entries.append(entry)

    return entries


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def load_registry() -> tuple[list[RegistryEntry], dict[str, Plugin]]:
    """Load and index all entries from REGISTRY_PATH. Cached after first call."""
    root = get_registry_path()
    marketplace_file = root / ".claude-plugin" / "marketplace.json"
    if not marketplace_file.exists():
        raise FileNotFoundError(f"marketplace.json not found at {marketplace_file}")

    with marketplace_file.open() as f:
        marketplace = json.load(f)

    all_entries: list[RegistryEntry] = []
    plugins: dict[str, Plugin] = {}

    for spec in marketplace.get("plugins", []):
        plugin_name = spec["name"]
        source = spec.get("source", "")
        if not isinstance(source, str):
            continue  # skip non-local sources

        plugin_dir = (root / source).resolve()
        if not plugin_dir.exists():
            continue

        plugin_meta: dict = {}
        plugin_json = plugin_dir / ".claude-plugin" / "plugin.json"
        if plugin_json.exists():
            with plugin_json.open() as f:
                plugin_meta = json.load(f)

        version = spec.get("version") or plugin_meta.get("version", "0.0.0")
        tags: list[str] = plugin_meta.get("keywords", [])
        description = spec.get("description") or plugin_meta.get("description", "")
        author_raw = plugin_meta.get("author")
        author = (
            author_raw if isinstance(author_raw, str)
            else (author_raw.get("name") if isinstance(author_raw, dict) else None)
        )

        entries = _load_plugin_entries(plugin_name, plugin_dir, version, tags, root)
        all_entries.extend(entries)
        plugins[plugin_name] = Plugin(
            name=plugin_name,
            version=version,
            description=description,
            tags=tags,
            author=author,
            plugin_license=plugin_meta.get("license"),
        )

    return all_entries, plugins


def get_all_entries() -> list[RegistryEntry]:
    entries, _ = load_registry()
    return entries


def get_all_plugins() -> dict[str, Plugin]:
    _, plugins = load_registry()
    return plugins


def find_entry(plugin: str, type_: str, name: str) -> RegistryEntry | None:
    target_id = f"{plugin}/{type_.lower()}/{name}"
    return next((e for e in get_all_entries() if e.id == target_id), None)


def get_entry_content(entry: RegistryEntry) -> tuple[dict, str]:
    """Read the entry's source file and return (parsed_frontmatter, markdown_body)."""
    file_path = get_registry_path() / entry.path
    return _parse_frontmatter(file_path.read_text(encoding="utf-8"))
