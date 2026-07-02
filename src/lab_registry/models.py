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


class Plugin(BaseModel):
    name: str
    version: str
    description: str
    tags: list[str] = []
    author: str | None = None
    plugin_license: str | None = None
