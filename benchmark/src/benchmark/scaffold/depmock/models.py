"""Pydantic models used by the dependency autoformalization agent."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, computed_field


def _sanitize_module_name(name: str) -> str:
    """Convert an arbitrary dependency name into a Lean-safe module identifier."""
    # Extract alphanumeric chunks and title-case them
    parts = re.findall(r"[A-Za-z0-9]+", name)
    if not parts:
        return "Dependency"
    candidate = "".join(part.capitalize() for part in parts)
    # Lean module identifiers must start with an uppercase letter
    if not candidate[0].isalpha():
        candidate = f"M{candidate}"
    return candidate


class DependencyPayload(BaseModel):
    """Input payload describing a Python dependency snippet to autoformalize."""

    dep_name: str = Field(..., description="Human-readable dependency name")
    python_source: str = Field(..., description="Original Python helper code")
    source_hash: str | None = Field(
        default=None, description="Stable hash for cache lookups"
    )
    tags: list[str] = Field(default_factory=list, description="Contextual tags")
    usage_example: str | None = Field(
        default=None, description="Representative usage pulled from the dataset"
    )
    lean_module: str | None = Field(
        default=None,
        description="Optional Lean module name override (defaults to sanitized dep name)",
    )

    @computed_field  # type: ignore[misc]
    @property
    def lean_module_name(self) -> str:
        """Lean module name to generate for this dependency."""
        return self.lean_module or _sanitize_module_name(self.dep_name)

    def prompt_context(self) -> dict[str, object]:
        """Prepare a dictionary for Jinja template rendering."""
        return {
            "dep_name": self.dep_name,
            "python_source": self.python_source,
            "source_hash": self.source_hash or "unknown",
            "tags": self.tags,
            "usage_example": self.usage_example,
            "dep_module": self.lean_module_name,
        }


class DependencyResult(BaseModel):
    """Result metadata emitted by the autoformalization agent."""

    lean_module: str = Field(..., description="Lean module identifier")
    lean_code: str = Field(..., description="Generated Lean source code")
    variant: str | None = Field(default=None, description="Prompt variant used")
    status: Literal["ok", "failed", "stub"] = Field(
        default="ok", description="Outcome of the generation attempt"
    )
    diagnostics: str | None = Field(
        default=None, description="Diagnostics returned by Lean, if any"
    )
