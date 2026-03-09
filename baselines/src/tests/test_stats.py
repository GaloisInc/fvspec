"""Tests for baselines.stats."""

import tomllib
from pathlib import Path

from baselines.models import BucketStats, RunStats
from baselines.stats import _extract_model_name, write_results_toml


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


class TestWriteResultsToml:
    def test_writes_valid_toml(self, tmp_path: Path):
        stats = {
            "claude-sonnet-4": RunStats(
                model="claude-sonnet-4",
                easy=BucketStats(proved=10, n=100, rate=0.1),
                medium=BucketStats(proved=5, n=100, rate=0.05),
                hard=BucketStats(proved=1, n=100, rate=0.01),
                total=BucketStats(proved=16, n=300, rate=0.0533),
            ),
        }
        out = write_results_toml(
            stats,
            output_path=str(tmp_path / "results.toml"),
            ranseed=42,
        )
        assert out.exists()

        with out.open("rb") as f:
            doc = tomllib.load(f)

        assert doc["meta"]["ranseed"] == 42
        assert "claude_sonnet_4" in doc["results"]
        r = doc["results"]["claude_sonnet_4"]
        assert r["easy_proved"] == 10
        assert r["total_rate"] == 0.0533

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
            output_path=str(tmp_path / "results.toml"),
            ranseed=0,
        )
        with out.open("rb") as f:
            doc = tomllib.load(f)

        assert len(doc["results"]) == 2
