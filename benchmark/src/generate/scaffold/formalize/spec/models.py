"""Data models for spec generation agent."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SpecPayload(BaseModel):
    """Input payload for spec generation agent.

    Contains all information needed to generate a Lean specification
    from a property-based test, including implementation signatures.
    """

    model_config = ConfigDict(frozen=True)

    pbt_code: str = Field(..., description="Property-based test source code")
    pbt_name: str = Field(..., description="Test function name")
    impl_signatures: dict[str, str] = Field(
        default_factory=dict,
        description="Function signatures extracted from Impl.lean",
    )
    function_name: str = Field(
        ..., description="Primary function name (inferred from test name)"
    )
    variant: str = Field(..., description="Spec variant (functional/mvcgen)")


class SpecValidation(BaseModel):
    """Result of validating spec agent output.

    Note: For specs, has_sorry=True is GOOD! We want theorem statements
    with sorry proofs, not full implementations.
    """

    model_config = ConfigDict(frozen=True)

    compiles: bool = Field(..., description="Code has no type errors")
    has_statements: bool = Field(..., description="Has theorem/def/lemma statements")
    has_sorry: bool = Field(
        ..., description="Has sorry (this is EXPECTED and GOOD for specs!)"
    )
    valid: bool = Field(
        ..., description="Overall validity: compiles AND has_statements"
    )
    errors: list[str] = Field(
        default_factory=list, description="List of validation errors"
    )


class SpecResult(BaseModel):
    """Output result from spec generation agent.

    Tracks success, generated code, validation status, and metrics.
    """

    model_config = ConfigDict(frozen=True)

    success: bool = Field(..., description="Whether spec generation succeeded")
    lean_code: str | None = Field(
        default=None, description="Generated Lean specification code"
    )
    compiles: bool = Field(
        default=False, description="Whether the spec compiles (no type errors)"
    )
    has_sorry: bool = Field(
        default=False,
        description="Whether spec has sorry (EXPECTED for theorem statements)",
    )
    has_statements: bool = Field(
        default=False, description="Whether spec has theorem/def statements"
    )
    attempts: int = Field(default=0, description="Number of generation attempts")
    tool_calls: int = Field(default=0, description="Total LSP tool calls made")
    error: str | None = Field(default=None, description="Error message if failed")

    def prompt_dict(self) -> dict[str, object]:
        """Convert to dict for template rendering."""
        return {
            "success": self.success,
            "lean_code": self.lean_code,
            "compiles": self.compiles,
            "has_sorry": self.has_sorry,
            "has_statements": self.has_statements,
            "attempts": self.attempts,
            "tool_calls": self.tool_calls,
            "error": self.error,
        }
