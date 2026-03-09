"""Configuration loading for fvspec baselines."""

import tomllib
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel


CONFIG_PATH = Path(__file__).parent / "config.toml"


class ModelConfig(BaseModel):
    """A model to evaluate."""

    human_name: str
    provider: str
    model_pin: str
    dollars_per_output_millitoken: float

    @property
    def inspect_model(self) -> str:
        """Model string for inspect_ai (e.g. 'anthropic/claude-sonnet-4-20250514')."""
        return f"{self.provider}/{self.model_pin}"


class Config(BaseModel):
    """Top-level baselines configuration."""

    ranseed: int = 42
    parallelism: int = 10
    model: list[ModelConfig]

    def get_model(self, name: str) -> ModelConfig:
        """Look up a model by human_name, model_pin, or provider/model_pin."""
        for m in self.model:
            if name in (m.human_name, m.model_pin, m.inspect_model):
                return m
        names = [m.human_name for m in self.model]
        msg = f"Unknown model {name!r}. Known: {names}"
        raise KeyError(msg)


@lru_cache
def load_config() -> Config:
    """Load and parse config.toml."""
    with CONFIG_PATH.open("rb") as f:
        data = tomllib.load(f)
    return Config(**data)
