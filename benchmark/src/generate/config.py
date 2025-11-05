"""Configuration helpers for the fvspec CLI."""

import tomllib
from pathlib import Path

from pydantic import BaseModel

# Project structure paths (relative to benchmark/ directory)
# These are defined once here to avoid scattered Path(__file__).parent... all over
# config.py location: benchmark/src/generate/config.py
PROJECT_ROOT = Path(__file__).resolve().parents[2]  # benchmark/
SRC_DIR = PROJECT_ROOT / "src"
DATA_DIR = PROJECT_ROOT / "data"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
LAKE_TEMPLATE_DIR = PROJECT_ROOT / "lake-template"
TEMPLATES_DIR = SRC_DIR / "generate" / "templates"


class AgentConfig(BaseModel):
    """Configuration for the AI agent behavior.

    Attributes:
        model: Model identifier string (e.g., "anthropic/claude-sonnet-4-5")
        max_tokens: Maximum token limit for generation
    """

    model: str
    max_tokens: int


class MetaConfig(BaseModel):
    """Configuration for runtime behavior.

    Attributes:
        display: Display mode for inspect_ai eval TUI (full, conversation, rich, plain, log, none)
        parallelism: Number of samples to evaluate in parallel
    """

    display: str = "plain"
    parallelism: int = 25


class PromptConfig(BaseModel):
    """Configuration for prompt template selection.

    Attributes:
        variant: Name of the prompt variant to use from registry.toml
                 If None, uses registry default
    """

    variant: str | None = None


class DatasetConfig(BaseModel):
    """Configuration for dataset sampling.

    Attributes:
        sample_size: Number of samples to draw from the dataset
        ranseed: Random seed used for dataset sampling (0 yields deterministic default)
    """

    sample_size: int = 100
    ranseed: int = 0


class WandbConfig(BaseModel):
    """Configuration for Weights & Biases logging.

    Attributes:
        enabled: Enable wandb logging
        project: wandb project name
        entity: wandb entity/team name (optional)
        tags: Additional tags for runs
        upload_samples: Upload all sample outputs as artifacts (Spec.lean, qa.json, datapoint.json)
        sync_dep_cache: Download cache at start, upload at end of runs
    """

    enabled: bool = False
    project: str = "fvspec"
    entity: str | None = None
    tags: list[str] = []
    upload_samples: bool = True
    sync_dep_cache: bool = True


class Config(BaseModel):
    """Top-level configuration loaded from config.toml.

    Attributes:
        agent: Agent configuration settings
        meta: Runtime behavior configuration
        prompt: Prompt template configuration
        dataset: Dataset sampling configuration
        wandb: Weights & Biases configuration
    """

    agent: AgentConfig
    meta: MetaConfig
    prompt: PromptConfig = PromptConfig()
    dataset: DatasetConfig = DatasetConfig()
    wandb: WandbConfig = WandbConfig()

    @classmethod
    def load(cls, config_path: Path) -> "Config":
        """Load configuration from the TOML file."""
        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        # Convert tool paths to Path objects
        return cls(
            agent=AgentConfig(**data["agent"]),  # type: ignore[arg-type]
            meta=MetaConfig(**data["meta"]),  # type: ignore[arg-type]
            prompt=PromptConfig(**data.get("prompt", {})),  # type: ignore[arg-type]
            dataset=DatasetConfig(**data.get("dataset", {})),  # type: ignore[arg-type]
            wandb=WandbConfig(**data.get("wandb", {})),  # type: ignore[arg-type]
        )


def find_config_file(start_dir: Path | None = None) -> Path:
    """Locate `config.toml` within the scaffold directory tree."""
    if start_dir is None:
        start_dir = Path(".")
    current = start_dir.absolute()
    config_path = current / "src" / "generate" / "config.toml"
    if config_path.exists():
        return config_path
    raise FileNotFoundError(
        f"Configuration file not found at {config_path}. "
        "Please ensure config.toml exists in the `generate` directory."
    )


def load_config(config_path: Path | None = None) -> Config:
    """Load configuration from `config_path`, falling back to the scaffold default."""
    if config_path is None:
        config_path = find_config_file()
    config = Config.load(config_path)
    return config
