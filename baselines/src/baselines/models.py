"""Pydantic models for fvspec baselines evaluation."""

from pydantic import BaseModel, Field, computed_field


class FvspecSample(BaseModel):
    """A single sample from the galoisinc/fvspec-fv HuggingFace dataset."""

    sample_id: str
    spec: str
    impl: str
    pbt_code: str
    pbt_summary: str | None = None
    num_theorems: int
    difficulty_binary: str | None = None

    @computed_field
    @property
    def difficulty_bucket(self) -> str:
        """Binary difficulty bucket (easy/hard)."""
        return self.difficulty_binary or "unknown"


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
    partial_credit_avg: float = 0.0
    k: int = 1
    pass_at_1: float = 0.0
    pass_at_k: float = 0.0


class RunStats(BaseModel):
    """Per-model aggregates for TOML output."""

    model: str
    easy: BucketStats = Field(default_factory=BucketStats)
    hard: BucketStats = Field(default_factory=BucketStats)
    total: BucketStats = Field(default_factory=BucketStats)
