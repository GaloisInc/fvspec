"""Tests for baselines.stats."""

import tomllib
from pathlib import Path

from baselines.models import BucketStats, RunStats
from baselines.stats import (
    _extract_eval_timestamp,
    _extract_model_name,
    _pass_at_k_unbiased,
    write_results_toml,
)


class TestExtractModelName:
    def test_strips_provider_and_date(self):
        data = {"eval": {"model": "anthropic/claude-sonnet-4-20250514"}}
        assert _extract_model_name(data) == "claude-sonnet-4"

    def test_no_date_suffix(self):
        data = {"eval": {"model": "openai/gpt-4o"}}
        assert _extract_model_name(data) == "gpt-4o"

    def test_missing_model(self):
        assert _extract_model_name({}) == "unknown"

    def test_no_provider_prefix(self):
        data = {"eval": {"model": "claude-sonnet-4-6"}}
        assert _extract_model_name(data) == "claude-sonnet-4-6"


class TestExtractEvalTimestamp:
    def test_extracts_and_converts(self):
        data = {"eval": {"created": "2026-03-27T21:43:46+00:00"}}
        assert _extract_eval_timestamp(data) == "2026-03-27T21-43-46+00-00"

    def test_missing_created(self):
        assert _extract_eval_timestamp({"eval": {}}) is None

    def test_missing_eval(self):
        assert _extract_eval_timestamp({}) is None


class TestWriteResultsToml:
    def test_writes_valid_toml(self, tmp_path: Path):
        stats = {
            "claude-sonnet-4": RunStats(
                model="claude-sonnet-4",
                easy=BucketStats(proved=10, n=100, rate=0.1, partial_credit_avg=0.3),
                hard=BucketStats(proved=1, n=100, rate=0.01, partial_credit_avg=0.05),
                total=BucketStats(
                    proved=11, n=200, rate=0.055, partial_credit_avg=0.175
                ),
            ),
        }
        eval_ts = "2026-03-27T21-43-46+00-00"
        out = write_results_toml(
            stats,
            output_dir=str(tmp_path / "results"),
            ranseed=42,
            eval_timestamp=eval_ts,
        )
        assert out.exists()
        assert out.parent.name == eval_ts
        assert out.parent.parent == tmp_path / "results"

        with out.open("rb") as f:
            doc = tomllib.load(f)

        assert doc["meta"]["ranseed"] == 42
        assert "claude_sonnet_4" in doc["results"]
        r = doc["results"]["claude_sonnet_4"]
        assert r["easy_proved"] == 10
        assert r["total_rate"] == 0.055
        assert r["easy_partial_credit_avg"] == 0.3

    def test_multiple_models(self, tmp_path: Path):
        stats = {
            "model-a": RunStats(
                model="model-a",
                total=BucketStats(proved=5, n=10, rate=0.5),
            ),
            "model-b": RunStats(
                model="model-b",
                total=BucketStats(proved=3, n=10, rate=0.3),
            ),
        }
        out = write_results_toml(
            stats,
            output_dir=str(tmp_path / "results"),
            ranseed=0,
        )
        with out.open("rb") as f:
            doc = tomllib.load(f)

        assert len(doc["results"]) == 2


class TestPassAtK:
    def test_all_correct(self):
        # n=5, c=5, k=1: always pass
        assert _pass_at_k_unbiased(5, 5, 1) == 1.0
        assert _pass_at_k_unbiased(5, 5, 5) == 1.0

    def test_none_correct(self):
        assert _pass_at_k_unbiased(5, 0, 1) == 0.0
        assert _pass_at_k_unbiased(5, 0, 5) == 0.0

    def test_k_equals_n_one_correct(self):
        # k=n=5, c=1: pass@5 = 1 (any success among the 5 attempts)
        assert _pass_at_k_unbiased(5, 1, 5) == 1.0

    def test_pass_at_1_equals_fraction(self):
        # pass@1 unbiased = c/n
        assert _pass_at_k_unbiased(4, 1, 1) == 0.25
        assert _pass_at_k_unbiased(4, 3, 1) == 0.75

    def test_k_larger_than_remaining(self):
        # n-c < k: always pass
        assert _pass_at_k_unbiased(5, 3, 5) == 1.0
