"""Load common strings for dependency autoformalization."""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel


class BoundToolStrings(BaseModel, frozen=True):
    """Strings for bound dependency tools."""

    description: str
    trigger_message: str
    success_message: str


class ErrorStrings(BaseModel, frozen=True):
    """Error message templates."""

    missing_code_tags: str
    missing_code_tags_with_preview: str
    no_task_state: str


class DepsLeanStrings(BaseModel, frozen=True):
    """Strings for Deps.lean file generation."""

    empty: str


class DependencyStrings(BaseModel, frozen=True):
    """All dependency autoformalization strings."""

    agent_description: str
    legacy_tool_description: str
    supervisor_prompt: str
    bound_tool: BoundToolStrings
    errors: ErrorStrings
    deps_lean: DepsLeanStrings


_strings_cache: DependencyStrings | None = None


def get_dependency_strings() -> DependencyStrings:
    """Load dependency autoformalization strings from templates/deps/common/strings.toml."""
    global _strings_cache
    if _strings_cache is not None:
        return _strings_cache

    strings_path = Path(__file__).parent / "common" / "strings.toml"
    if not strings_path.exists():
        raise FileNotFoundError(f"Dependency strings file not found at {strings_path}")

    with open(strings_path, "rb") as f:
        data = tomllib.load(f)

    _strings_cache = DependencyStrings(
        agent_description=data["agent"]["description"],
        legacy_tool_description=data["legacy_tool"]["description"],
        supervisor_prompt=data["supervisor"]["prompt"],
        bound_tool=BoundToolStrings(
            description=data["bound_tool"]["description"],
            trigger_message=data["bound_tool"]["trigger_message"],
            success_message=data["bound_tool"]["success_message"],
        ),
        errors=ErrorStrings(
            missing_code_tags=data["errors"]["missing_code_tags"],
            missing_code_tags_with_preview=data["errors"][
                "missing_code_tags_with_preview"
            ],
            no_task_state=data["errors"]["no_task_state"],
        ),
        deps_lean=DepsLeanStrings(
            empty=data["deps_lean"]["empty"],
        ),
    )

    return _strings_cache
