"""SQLModel definitions for pbts_full.db schema.

These models map directly to the SQLite database tables and provide
type-safe access with Pydantic validation.
"""

import json
from typing import Any

from pydantic import ConfigDict, field_validator
from sqlmodel import Field, SQLModel


class Repo(SQLModel, table=True):
    """Repository metadata table."""

    __tablename__ = "repos"

    id: int = Field(primary_key=True)
    source: str | None = None
    name: str | None = None
    url: str | None = None
    license: str | None = None
    license_status: str | None = None
    stars: int | None = None
    forks: int | None = None
    parsed_at: str | None = None
    hash: str | None = None


class Datapoint(SQLModel, table=True):
    """Property-based test datapoint (main table).

    This is the primary model for PBT samples used in benchmark generation.
    Note: dep_names and deps are stored as JSON strings in SQLite.

    Non-DB fields like `unit_tests` are populated dynamically at load time.

    Attributes:
        unit_tests: Non-DB field populated at load time. List of unit test dicts.
                    Accessed via property to maintain type safety.
    """

    model_config = ConfigDict(extra="allow")

    __tablename__ = "pbts"

    id: int = Field(primary_key=True)
    repo_id: int
    name: str  # PBT function name
    code: str  # PBT source code
    source_file: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    original_id: int | None = None
    dep_names: str = Field(
        default="[]"
    )  # JSON array string of dependency names (parsed by validator)
    deps: str = Field(default="[]")  # JSON array string of dependency code
    source: str | None = None
    summary: str | None = None
    hash: str | None = None
    summary_vector: str | None = None  # JSON array string of floats
    mode: str | None = None
    summaryversion: int | None = None
    summaryconfidence: float | None = None

    @property
    def unit_tests(self) -> list[dict[str, Any]]:
        """Non-DB field: unit tests populated by sample_datapoints()."""
        return self.__dict__.get("unit_tests", [])

    @unit_tests.setter
    def unit_tests(self, value: list[dict[str, Any]]) -> None:
        """Set unit tests (stored in __dict__ to avoid DB persistence)."""
        self.__dict__["unit_tests"] = value

    @field_validator("dep_names", mode="before")
    @classmethod
    def parse_dep_names(cls, v: Any) -> str:
        """Ensure dep_names is valid JSON (stored as string in DB)."""
        if isinstance(v, str):
            # Validate it's parseable JSON
            try:
                json.loads(v)
                return v
            except json.JSONDecodeError:
                return "[]"
        if isinstance(v, list):
            return json.dumps(v)
        return "[]"

    @field_validator("deps", mode="before")
    @classmethod
    def parse_deps(cls, v: Any) -> str:
        """Ensure deps is valid JSON (stored as string in DB)."""
        if isinstance(v, str):
            try:
                json.loads(v)
                return v
            except json.JSONDecodeError:
                return "[]"
        if isinstance(v, list):
            return json.dumps(v)
        return "[]"

    def get_dep_names(self) -> list[str]:
        """Parse dep_names JSON string to list."""
        return json.loads(self.dep_names)

    def get_deps(self) -> list[str]:
        """Parse deps JSON string to list."""
        return json.loads(self.deps)


class UnitTest(SQLModel, table=True):
    """Unit test table (for overlap analysis)."""

    __tablename__ = "unit_tests"

    id: int = Field(primary_key=True)
    repo_id: int
    name: str
    code: str
    source_file: str | None = None
    start_line: int | None = None
    end_line: int | None = None


class Function(SQLModel, table=True):
    """Shared function table (for overlap analysis)."""

    __tablename__ = "functions"

    id: int = Field(primary_key=True)
    repo_id: int
    name: str
    code: str
    source_file: str | None = None
    start_line: int | None = None
    end_line: int | None = None


class PBTFunction(SQLModel, table=True):
    """Junction table: PBT -> shared functions."""

    __tablename__ = "pbt_functions"

    pbt_id: int = Field(primary_key=True)
    function_name: str = Field(primary_key=True)


class UnitTestFunction(SQLModel, table=True):
    """Junction table: Unit test -> shared functions."""

    __tablename__ = "unit_test_functions"

    unit_test_id: int = Field(primary_key=True)
    function_name: str = Field(primary_key=True)


class ProcessingStatus(SQLModel, table=True):
    """Processing status tracking table."""

    __tablename__ = "processing_status"

    repo_id: int = Field(primary_key=True)
    status: str | None = None
    last_attempt: str | None = None
    error_message: str | None = None
