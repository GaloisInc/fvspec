"""Pydantic models for fvspec baselines evaluation."""

from pydantic import BaseModel, Field, computed_field


class FvspecSample(BaseModel):
    """A single sample from the quinn-dougherty/fvspec HuggingFace dataset."""

    sample_id: str
    spec: str
    impl: str
    realpbt_code: str
    realpbt_summary: str | None = None
    num_theorems: int
    difficulty_subjective_haiku: float | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def difficulty_bucket(self) -> str:
        """Bucket based on haiku difficulty score: easy ≤ 3, medium ≤ 6, hard > 6."""
        if self.difficulty_subjective_haiku is None:
            return "unknown"
        if self.difficulty_subjective_haiku <= 3:
            return "easy"
        if self.difficulty_subjective_haiku <= 6:
            return "medium"
        return "hard"


class SampleResult(BaseModel):
    """Per-sample outcome from a baselines run."""

    sample_id: str
    model: str
    sorries_removed: int = 0
    sorries_total: int = 0
    compiles: bool = False
    proved: bool = False
    error: str | None = None
    wall_time_s: float = 0.0


class BucketStats(BaseModel):
    """Aggregated stats for one difficulty bucket."""

    proved: int = 0
    n: int = 0
    rate: float = 0.0


class RunStats(BaseModel):
    """Per-model aggregates for TOML output."""

    model: str
    easy: BucketStats = Field(default_factory=BucketStats)
    medium: BucketStats = Field(default_factory=BucketStats)
    hard: BucketStats = Field(default_factory=BucketStats)
    total: BucketStats = Field(default_factory=BucketStats)
