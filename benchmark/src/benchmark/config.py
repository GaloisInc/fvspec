import tomllib
from pathlib import Path
import os
from dotenv import load_dotenv

# import logfire
from pydantic import BaseModel


#   def setup_logfire() -> None:
#       """Configure logfire with token from .env"""
#       load_dotenv()
#
#       logfire_token = os.getenv("LOGFIRE_WRITE_TOKEN")
#       if not logfire_token:
#           raise ValueError("LOGFIRE__WRITE_TOKEN not found in .env file")
#
#       logfire.configure(token=logfire_token)


class AgentConfig(BaseModel):
    model: str
    max_attempts: int
    max_tokens: int


class MetaConfig(BaseModel):
    logging: bool
    debug: bool = False


class Config(BaseModel):
    agent: AgentConfig
    meta: MetaConfig

    @classmethod
    def load(cls, config_path: Path) -> "Config":
        """Load configuration from the TOML file"""
        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        # Convert tool paths to Path objects
        return cls(
            agent=AgentConfig(**data["agent"]),
            meta=MetaConfig(**data["meta"]),
        )


def find_config_file(start_dir: Path | None = None) -> Path:
    """
    Find the config.toml in the scaffold directory.
    """
    if start_dir is None:
        start_dir = Path(".")
    current = start_dir.absolute()
    config_path = current / "src" / "benchmark" / "config.toml"
    if config_path.exists():
        return config_path
    raise FileNotFoundError(
        f"Configuration file not found at {config_path}. "
        "Please ensure config.toml exists in the `generate` directory."
    )


def load_config(config_path: Path | None = None) -> Config:
    """
    Load the configuration from the specified path or find it in parent directories.
    """
    if config_path is None:
        config_path = find_config_file()
    config = Config.load(config_path)
    return config
