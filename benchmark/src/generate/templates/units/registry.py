"""Prompt variant registry for units generation.

Currently supports only "default" variant. Additional variants (e.g., functional/mvcgen
specific) can be added later if needed.
"""

import tomllib
from pathlib import Path

from pydantic import BaseModel, Field


class VariantConfig(BaseModel):
    """A loaded prompt variant with all templates and metadata.

    Attributes:
        name: Unique identifier for this variant
        description: Human-readable description of the variant's purpose
        system_prompt: The full system prompt text
        initial_template: The initial user prompt template (may contain Jinja2)
        metadata: Additional configuration and notes from metadata.toml
    """

    name: str
    description: str
    system_prompt: str
    initial_template: str
    metadata: dict = Field(default_factory=dict)


class VariantRegistry:
    """Manages units prompt variant loading and validation.

    The registry loads variant configurations from templates/units/registry.toml
    and provides methods to list and retrieve prompt variants.
    """

    def __init__(self, templates_dir: Path | None = None):
        """Initialize the registry.

        Args:
            templates_dir: Path to templates directory. If None, uses package default.
        """
        if templates_dir is None:
            # Default to the templates directory in the package
            templates_dir = Path(__file__).parent
        self.templates_dir = templates_dir
        self.registry_path = templates_dir / "registry.toml"

        if not self.registry_path.exists():
            raise FileNotFoundError(
                f"Registry file not found at {self.registry_path}. "
                "Please ensure registry.toml exists in the templates directory."
            )

        self._registry = self._load_registry()

    def _load_registry(self) -> dict:
        """Load the registry configuration from registry.toml."""
        with open(self.registry_path, "rb") as f:
            return tomllib.load(f)

    def list_variants(self) -> list[str]:
        """Return all available variant names."""
        return list(self._registry["variants"].keys())

    def default_variant(self) -> str:
        """Return the default variant name."""
        return "default"

    def get_variant_info(self, name: str) -> dict:
        """Get registry metadata for a variant without loading templates.

        Args:
            name: Variant name

        Returns:
            Registry metadata dict (description, paths, etc.)

        Raises:
            ValueError: If variant name is not found in registry
        """
        if name not in self._registry["variants"]:
            raise ValueError(
                f"Unknown variant: {name}. Available: {self.list_variants()}"
            )
        return self._registry["variants"][name]

    def get_variant(self, name: str) -> VariantConfig:
        """Load a specific variant's configuration and templates.

        Args:
            name: Variant name (e.g., "default")

        Returns:
            VariantConfig with loaded templates and metadata

        Raises:
            ValueError: If variant name is not found in registry
            FileNotFoundError: If variant files are missing
        """
        variant_meta = self.get_variant_info(name)

        # Load system prompt
        system_prompt_path = self.templates_dir / variant_meta["system_prompt"]
        if not system_prompt_path.exists():
            raise FileNotFoundError(f"System prompt not found: {system_prompt_path}")
        system_prompt = system_prompt_path.read_text()

        # Load initial prompt template
        initial_prompt_path = self.templates_dir / variant_meta["initial_prompt"]
        if not initial_prompt_path.exists():
            raise FileNotFoundError(f"Initial prompt not found: {initial_prompt_path}")
        initial_template = initial_prompt_path.read_text()

        # Load metadata if exists
        variant_dir = system_prompt_path.parent
        metadata_path = variant_dir / "metadata.toml"
        metadata = {}
        if metadata_path.exists():
            with open(metadata_path, "rb") as f:
                metadata = tomllib.load(f)

        return VariantConfig(
            name=name,
            description=variant_meta["description"],
            system_prompt=system_prompt,
            initial_template=initial_template,
            metadata=metadata,
        )
