import tomllib
from pathlib import Path

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
    """Configuration for the AI agent behavior.

    Attributes:
        model: Model identifier string (e.g., "anthropic/claude-sonnet-4-5")
        max_attempts: Maximum number of generation attempts
        max_tokens: Maximum token limit for generation
    """

    model: str
    max_attempts: int
    max_tokens: int


class MetaConfig(BaseModel):
    """Configuration for logging and debugging.

    Attributes:
        logging: Enable logging functionality
        debug: Enable debug mode for verbose output
    """

    logging: bool
    debug: bool = False


class PromptConfig(BaseModel):
    """Configuration for prompt template selection.

    Attributes:
        variant: Name of the prompt variant to use from registry.toml
                 If None, uses registry default
    """

    variant: str | None = None


class Config(BaseModel):
    """Top-level configuration loaded from config.toml.

    Attributes:
        agent: Agent configuration settings
        meta: Logging and debugging configuration
        prompt: Prompt template configuration
    """

    agent: AgentConfig
    meta: MetaConfig
    prompt: PromptConfig = PromptConfig()

    @classmethod
    def load(cls, config_path: Path) -> "Config":
        """Load configuration from the TOML file"""
        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        # Convert tool paths to Path objects
        return cls(
            agent=AgentConfig(**data["agent"]),  # type: ignore[arg-type]
            meta=MetaConfig(**data["meta"]),  # type: ignore[arg-type]
            prompt=PromptConfig(**data.get("prompt", {})),  # type: ignore[arg-type]
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
