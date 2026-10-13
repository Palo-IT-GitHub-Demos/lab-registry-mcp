from __future__ import annotations

import json
import re
from typing import Any

import yaml

# Required fields that MUST be present and non-empty
_REQUIRED: dict[str, list[str]] = {
    "skill":   ["name", "description"],
    "agent":   ["name", "description"],
    "command": ["description"],
    "hook":    [],
}

# Recommended fields — absent triggers a warning, not an error
_RECOMMENDED: dict[str, list[str]] = {
    "skill":   ["model", "allowed-tools"],
    "agent":   ["tools"],
    "command": ["allowed-tools"],
    "hook":    [],
}

VALID_TYPES = set(_REQUIRED.keys())
_FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)", re.DOTALL)


def validate_entry_handler(content: str, type: str) -> dict[str, Any]:
    """Validate Markdown artifact frontmatter or hook JSON requirements.

    Returns:
    - valid: bool — True if no errors
    - errors: list of blocking schema violations
    - warnings: list of non-blocking recommendations
    - parsed: the parsed YAML frontmatter dict
    """
    type_lower = type.lower()
    if type_lower not in VALID_TYPES:
        return {
            "valid": False,
            "errors": [f"Unknown type '{type}'. Must be one of: {', '.join(sorted(VALID_TYPES))}"],
            "warnings": [],
            "parsed": {},
        }

    if type_lower == "hook":
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            return {
                "valid": False,
                "errors": [f"Invalid hook JSON: {exc.msg}"],
                "warnings": [],
                "parsed": {},
            }

        if not isinstance(parsed, dict):
            return {
                "valid": False,
                "errors": ["Hook content must be a JSON object"],
                "warnings": [],
                "parsed": {},
            }

        return {"valid": True, "errors": [], "warnings": [], "parsed": parsed}

    frontmatter_match = _FRONTMATTER_PATTERN.match(content)
    if frontmatter_match:
        try:
            frontmatter = yaml.safe_load(frontmatter_match.group(1))
        except yaml.YAMLError:
            # Preserve the existing behavior for syntactically invalid YAML.
            frontmatter = {}

        if not isinstance(frontmatter, dict):
            return {
                "valid": False,
                "errors": ["Frontmatter must be a YAML dictionary/mapping"],
                "warnings": [],
            }
        meta = frontmatter
        body = frontmatter_match.group(2).strip()
    else:
        meta = {}
        body = content

    errors: list[str] = []
    warnings: list[str] = []

    # Required fields
    for field in _REQUIRED[type_lower]:
        value = meta.get(field)
        if not value or (isinstance(value, str) and not value.strip()):
            errors.append(f"Required field '{field}' is missing or empty")

    # Recommended fields
    for field in _RECOMMENDED[type_lower]:
        if field not in meta:
            warnings.append(f"Recommended field '{field}' is missing")

    # Body content
    if type_lower != "hook" and not body.strip():
        warnings.append("Content body is empty — add instructions below the frontmatter separator")

    # Name format: kebab-case preferred
    name = meta.get("name", "")
    if name and not all(c.isalnum() or c in "-_" for c in str(name)):
        warnings.append(f"Name '{name}' contains special characters — prefer kebab-case (e.g. my-skill-name)")

    # Skill-specific: if disable-model-invocation is true, model should not be set
    if type_lower == "skill":
        if meta.get("disable-model-invocation") and meta.get("model"):
            warnings.append("'model' is set but 'disable-model-invocation' is true — model will be ignored")

    # Agent-specific: warn if no skills referenced
    if type_lower == "agent" and not meta.get("skills"):
        warnings.append("Agent has no 'skills' list — agents typically load one or more skills")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "parsed": meta,
    }
