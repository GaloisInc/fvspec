"""Tests for baselines.config."""

import pytest

from baselines.config import Config, ModelConfig, load_config


class TestModelConfig:
    def test_inspect_model(self):
        m = ModelConfig(
            human_name="test",
            provider="anthropic",
            model_pin="claude-sonnet-4-6",
            dollars_per_output_millitoken=15,
        )
        assert m.inspect_model == "anthropic/claude-sonnet-4-6"


class TestConfig:
    @pytest.fixture
    def cfg(self) -> Config:
        return Config(
            ranseed=42,
            parallelism=5,
            model=[
                ModelConfig(
                    human_name="snt",
                    provider="anthropic",
                    model_pin="claude-sonnet-4-6",
                    dollars_per_output_millitoken=15,
                ),
                ModelConfig(
                    human_name="gpt",
                    provider="openai",
                    model_pin="gpt-4o",
                    dollars_per_output_millitoken=10,
                ),
            ],
        )

    def test_get_model_by_human_name(self, cfg: Config):
        assert cfg.get_model("snt").provider == "anthropic"

    def test_get_model_by_model_pin(self, cfg: Config):
        assert cfg.get_model("gpt-4o").human_name == "gpt"

    def test_get_model_by_inspect_model(self, cfg: Config):
        assert cfg.get_model("openai/gpt-4o").human_name == "gpt"

    def test_get_model_unknown_raises(self, cfg: Config):
        with pytest.raises(KeyError, match="Unknown model"):
            cfg.get_model("nonexistent")


class TestLoadConfig:
    def test_loads_real_config(self):
        cfg = load_config()
        assert cfg.ranseed >= 0
        assert len(cfg.model) > 0
        for m in cfg.model:
            assert "/" in m.inspect_model
