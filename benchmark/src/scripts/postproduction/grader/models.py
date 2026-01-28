"""Pydantic models for grading results and metadata."""

from pydantic import BaseModel, Field


class DifficultyGrade(BaseModel):
    """Difficulty estimation of a formalization task.

    Estimates the difficulty of creating the formalization.
    """

    score: float = Field(ge=0, le=10, description="Overall difficulty score (0-10)")
    haiku_takes: str = Field(
        description="Prose justification for the difficulty score, explaining the main factors that make this task easy or challenging"
    )


class GraderMetadata(BaseModel):
    """Metadata about the grading process."""

    model: str = Field(default="claude-haiku-4-5-20251001", description="Model used")
    timestamp: str = Field(description="ISO timestamp of grading")
    tokens_used: int = Field(description="Total tokens used (input + output)")
    grading_time_seconds: float = Field(description="Time taken to grade in seconds")
    version: str = Field(default="1.0.0", description="Grader version")
