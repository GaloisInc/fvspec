"""Pydantic models for grading results and metadata."""

from pydantic import BaseModel, Field


class QualityGrade(BaseModel):
    """Quality assessment of a formalization.

    Evaluates how well the Lean formalization captures the Python PBT
    in terms of correctness, type safety, edge case handling, and idiomatic Lean.
    """

    score: float = Field(ge=0, le=10, description="Overall quality score (0-10)")
    correctness: float = Field(
        ge=0, le=10, description="Formalization correctness and faithfulness (0-10)"
    )
    type_safety: float = Field(
        ge=0, le=10, description="Type safety and alignment with Python types (0-10)"
    )
    edge_cases: float = Field(
        ge=0, le=10, description="Edge case handling and completeness (0-10)"
    )
    lean_idioms: float = Field(
        ge=0, le=10, description="Idiomatic Lean usage and style (0-10)"
    )
    explanation: str = Field(description="Detailed explanation of the assessment")
    confidence: float = Field(ge=0, le=1, description="Confidence in assessment (0-1)")


class DifficultyGrade(BaseModel):
    """Difficulty estimation of a formalization task.

    Estimates the difficulty of creating the formalization based on
    mathematical complexity, type challenges, proof requirements, domain knowledge,
    and Lean expertise needed.
    """

    score: float = Field(ge=0, le=10, description="Overall difficulty score (0-10)")
    math_complexity: float = Field(
        ge=0, le=10, description="Mathematical complexity (0-10)"
    )
    type_challenges: float = Field(
        ge=0, le=10, description="Type system challenges (0-10)"
    )
    proof_difficulty: float = Field(
        ge=0, le=10, description="Proof difficulty and length (0-10)"
    )
    domain_knowledge: float = Field(
        ge=0, le=10, description="Domain-specific knowledge required (0-10)"
    )
    lean_expertise: float = Field(
        ge=0, le=10, description="Lean expertise level required (0-10)"
    )
    explanation: str = Field(description="Detailed explanation of the difficulty")
    confidence: float = Field(ge=0, le=1, description="Confidence in estimation (0-1)")


class GraderMetadata(BaseModel):
    """Metadata about the grading process."""

    model: str = Field(default="claude-haiku-4-5-20251001", description="Model used")
    timestamp: str = Field(description="ISO timestamp of grading")
    tokens_used: int = Field(description="Total tokens used (input + output)")
    quality_tokens: int = Field(description="Tokens used for quality assessment")
    difficulty_tokens: int = Field(description="Tokens used for difficulty assessment")
    grading_time_seconds: float = Field(description="Time taken to grade in seconds")
    version: str = Field(default="1.0.0", description="Grader version")
