from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class ArtifactType(str, Enum):
    skill = "skill"
    agent = "agent"
    command = "command"
    hook = "hook"


class RegistryEntry(BaseModel):
    id: str                          # "{plugin}/{type}/{name}"
    name: str
    type: ArtifactType
    plugin: str
    plugin_version: str
    description: str
    path: str                        # relative to REGISTRY_PATH
    updated_at: str | None = None    # YYYY-MM-DD, parsed from CHANGELOG.md
    tags: list[str] = []

    # Type-specific fields (None/empty when not applicable)
    disable_model_invocation: bool = False   # skills
    model: str | None = None                 # skills + agents
    allowed_tools: list[str] = []            # skills + commands
    context: str | None = None              # "fork" for subagent skills
    agent_skills: list[str] = []             # agents
    argument_hint: str | None = None         # commands
    hook_events: list[str] = []              # hooks

    def summary_dump(self) -> dict:
        """Lean serialization for list/search responses.

        Strips null and empty type-specific fields so AI clients receive only
        meaningful data. Core identity fields are always included.
        """
        d: dict = {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "plugin": self.plugin,
            "plugin_version": self.plugin_version,
            "description": self.description,
            "tags": self.tags,
        }
        if self.updated_at is not None:
            d["updated_at"] = self.updated_at
        if self.disable_model_invocation:
            d["disable_model_invocation"] = True
        if self.model is not None:
            d["model"] = self.model
        if self.allowed_tools:
            d["allowed_tools"] = self.allowed_tools
        if self.context is not None:
            d["context"] = self.context
        if self.agent_skills:
            d["agent_skills"] = self.agent_skills
        if self.argument_hint is not None:
            d["argument_hint"] = self.argument_hint
        if self.hook_events:
            d["hook_events"] = self.hook_events
        return d


class Plugin(BaseModel):
    name: str
    version: str
    description: str
    tags: list[str] = []
    author: str | None = None
    plugin_license: str | None = None
    source_path: str = ""   # relative path to plugin dir from registry root (e.g. "plugins/android")
    updated_at: str | None = None  # most recent CHANGELOG.md date across entries
