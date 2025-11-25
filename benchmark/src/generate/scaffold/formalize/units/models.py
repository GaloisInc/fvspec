"""Data models for units generation agent."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class UnitsPayload(BaseModel):
    """Input payload for units generation agent.

    Contains all information needed to generate LSpec unit tests from a
    property-based test, including optional implementation signatures.
    """

    model_config = ConfigDict(frozen=True)

    pbt_code: str = Field(..., description="Property-based test source code")
    pbt_name: str = Field(..., description="Test function name")
    function_name: str = Field(..., description="Primary function name")
    impl_signatures: dict[str, str] = Field(
        default_factory=dict,
        description="Function signatures from Impl.lean (optional)",
    )


class UnitsValidation(BaseModel):
    """Result of validating units agent output.

    Checks for basic LSpec syntax and test presence without requiring
    compilation (compilation check can be added in future iteration).
    """

    model_config = ConfigDict(frozen=True)

    has_tests: bool = Field(..., description="Has at least one test")
    valid_lspec_syntax: bool = Field(..., description="Valid LSpec syntax")
    compiles: bool = Field(
        default=False, description="Tests compile (not checked in MVP)"
    )
    valid: bool = Field(..., description="Overall validity: has_tests AND valid_syntax")
    errors: list[str] = Field(
        default_factory=list, description="List of validation errors"
    )


class UnitsResult(BaseModel):
    """Output result from units generation agent.

    Tracks success, generated code, validation status, and metrics.
    """

    model_config = ConfigDict(frozen=True)

    success: bool = Field(..., description="Whether test generation succeeded")
    lean_code: str | None = Field(default=None, description="Generated Tests.lean code")
    test_count: int = Field(default=0, description="Number of tests generated")
    has_tests: bool = Field(default=False, description="Has at least one test")
    attempts: int = Field(default=0, description="Number of generation attempts")
    tool_calls: int = Field(default=0, description="Total tool calls made")
    error: str | None = Field(default=None, description="Error message if failed")

    def prompt_dict(self) -> dict[str, object]:
        """Convert to dict for template rendering."""
        return {
            "success": self.success,
            "lean_code": self.lean_code,
            "test_count": self.test_count,
            "has_tests": self.has_tests,
            "attempts": self.attempts,
            "tool_calls": self.tool_calls,
            "error": self.error,
        }
