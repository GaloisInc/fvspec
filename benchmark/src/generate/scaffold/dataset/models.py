"""Pydantic models for realpbt2.jsonl schema.

These models map directly to the JSONL records and provide
type-safe access with Pydantic validation.
"""

from pydantic import BaseModel


class Repo(BaseModel, frozen=True):
    """Repository metadata."""

    name: str | None = None
    url: str | None = None
    license: str | None = None
    stars: int | None = None
    forks: int | None = None


class Metrics(BaseModel, frozen=True):
    """Code complexity metrics (embedded from radon analysis)."""

    loc: int | None = None
    sloc: int | None = None
    lloc: int | None = None
    comments: int | None = None
    avg_complexity: float | None = None
    max_complexity: int | None = None
    maintainability_index: float | None = None
    halstead_difficulty: float | None = None
    halstead_effort: float | None = None


class Dependency(BaseModel, frozen=True):
    """A resolved dependency of a PBT."""

    name: str
    qualified_name: str | None = None
    code: str | None = None
    language: str | None = None
    source_file: str | None = None
    depth: int | None = None
    kind: str | None = None
    resolution: str | None = None


class Datapoint(BaseModel):
    """Property-based test datapoint (primary model for benchmark generation).

    Each record corresponds to one PBT from realpbt2.jsonl.
    """

    id: int
    name: str
    code: str
    language: str | None = None
    source_file: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    summary: str | None = None
    repo: Repo | None = None
    metrics: Metrics | None = None
    dependencies: list[Dependency] = []

    def get_deps(self) -> list[str]:
        """Return dependency code snippets (compatibility method)."""
        return [d.code for d in self.dependencies if d.code is not None]

    def get_dep_names(self) -> list[str]:
        """Return dependency names (compatibility method)."""
        return [d.name for d in self.dependencies]
