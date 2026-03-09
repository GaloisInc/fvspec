"""Tests for baselines.models."""

from baselines.models import FvspecSample, RunStats, SampleResult


def _sample(**kwargs: object) -> FvspecSample:
    return FvspecSample(
        sample_id=str(kwargs.get("sample_id", "1")),
        spec=str(kwargs.get("spec", "theorem t : True := sorry")),
        impl=str(kwargs.get("impl", "def f := 1")),
        realpbt_code=str(kwargs.get("realpbt_code", "def test(): pass")),
        num_theorems=int(kwargs.get("num_theorems", 1)),  # type: ignore[arg-type]
        difficulty_subjective_haiku=kwargs.get("difficulty_subjective_haiku"),  # type: ignore[arg-type]
    )


class TestDifficultyBucket:
    def test_none_is_unknown(self):
        assert _sample(difficulty_subjective_haiku=None).difficulty_bucket == "unknown"

    def test_zero_is_easy(self):
        assert _sample(difficulty_subjective_haiku=0.0).difficulty_bucket == "easy"

    def test_boundary_3_is_easy(self):
        assert _sample(difficulty_subjective_haiku=3.0).difficulty_bucket == "easy"

    def test_just_above_3_is_medium(self):
        assert _sample(difficulty_subjective_haiku=3.01).difficulty_bucket == "medium"

    def test_boundary_6_is_medium(self):
        assert _sample(difficulty_subjective_haiku=6.0).difficulty_bucket == "medium"

    def test_just_above_6_is_hard(self):
        assert _sample(difficulty_subjective_haiku=6.01).difficulty_bucket == "hard"

    def test_10_is_hard(self):
        assert _sample(difficulty_subjective_haiku=10.0).difficulty_bucket == "hard"


class TestSampleResult:
    def test_defaults(self):
        r = SampleResult(sample_id="1", model="test")
        assert r.compiles is False
        assert r.proved is False
        assert r.sorries_removed == 0


class TestRunStats:
    def test_default_buckets(self):
        r = RunStats(model="test")
        assert r.easy.n == 0
        assert r.total.rate == 0.0
