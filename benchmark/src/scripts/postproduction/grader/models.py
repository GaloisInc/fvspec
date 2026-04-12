"""Pydantic models for grading results and metadata."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DifficultyGrade(BaseModel):
    """Difficulty estimation of a formalization task (v1: 0-10 scale)."""

    model_config = ConfigDict(extra="forbid")

    score: float = Field(ge=0, le=10, description="Overall difficulty score (0-10)")
    haiku_takes: str = Field(
        description="Prose justification for the difficulty score, explaining the main factors that make this task easy or challenging"
    )


class DifficultyGradeV2(BaseModel):
    """Binary difficulty classification (v2: easy/hard).

    Predicts whether an AI theorem-proving agent will successfully
    prove all theorems, based on empirically-calibrated signals.
    """

    model_config = ConfigDict(extra="forbid")

    classification: Literal["easy", "hard"] = Field(
        description="Binary classification: easy = AI likely proves all theorems, hard = AI unlikely to prove all"
    )
    confidence: float = Field(
        ge=0,
        le=1,
        description="Confidence in the classification (0-1)",
    )
    reasoning: str = Field(
        description="Brief reasoning for the classification, focusing on: number of proof obligations, spec size, and any qualitative factors"
    )


class GraderMetadata(BaseModel):
    """Metadata about the grading process."""

    model_config = ConfigDict(extra="forbid")

    model: str = Field(default="claude-haiku-4-5-20251001", description="Model used")
    timestamp: str = Field(description="ISO timestamp of grading")
    tokens_used: int = Field(description="Total tokens used (input + output)")
    grading_time_seconds: float = Field(description="Time taken to grade in seconds")
    version: str = Field(default="1.0.0", description="Grader version")
