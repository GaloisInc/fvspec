"""Prompt variant registry for unified formalization agent A/B testing."""

import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class FormalizationVariantConfig(BaseModel):
    """A loaded prompt variant with all templates and metadata."""

    name: str
    style: Literal["functional", "mvcgen"]
    description: str
    system_prompt: str
    initial_template: str
    metadata: dict = Field(default_factory=dict)


class FormalizationVariantRegistry:
    """Manages prompt variant loading and validation for the unified formalization agent."""

    def __init__(self, templates_dir: Path | None = None):
        """Initialize the registry.

        Args:
            templates_dir: Path to templates directory. If None, uses package default.
        """
        if templates_dir is None:
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

    def get_variant_info(self, name: str) -> dict:
        """Get registry metadata for a variant without loading templates."""
        if name not in self._registry["variants"]:
            raise ValueError(
                f"Unknown variant: {name}. Available: {self.list_variants()}"
            )
        return self._registry["variants"][name]

    def get_variant(self, name: str) -> FormalizationVariantConfig:
        """Load a specific variant's configuration and templates."""
        variant_meta = self.get_variant_info(name)
        variant_path = self.templates_dir / variant_meta["path"]

        # Load metadata
        metadata_path = variant_path / "metadata.toml"
        if not metadata_path.exists():
            raise FileNotFoundError(
                f"Metadata file not found at {metadata_path} for variant '{name}'"
            )

        with open(metadata_path, "rb") as f:
            metadata = tomllib.load(f)

        # Load system prompt
        system_prompt_path_template = variant_path / "system.prompt.template"
        system_prompt_path = variant_path / "system.prompt"

        if system_prompt_path_template.exists():
            system_prompt = system_prompt_path_template.read_text()
        elif system_prompt_path.exists():
            system_prompt = system_prompt_path.read_text()
        else:
            raise FileNotFoundError(f"System prompt not found for variant '{name}'")

        # Load initial user prompt — variant-specific, then common fallback
        initial_prompt_path_template = variant_path / "initial.prompt.template"
        initial_prompt_path = variant_path / "initial.prompt"

        if initial_prompt_path_template.exists():
            initial_template = initial_prompt_path_template.read_text()
        elif initial_prompt_path.exists():
            initial_template = initial_prompt_path.read_text()
        else:
            # Try common initial prompt
            common_initial_template = (
                self.templates_dir / "common" / "initial.prompt.template"
            )
            common_initial = self.templates_dir / "common" / "initial.prompt"

            if common_initial_template.exists():
                initial_template = common_initial_template.read_text()
            elif common_initial.exists():
                initial_template = common_initial.read_text()
            else:
                raise FileNotFoundError(f"No initial prompt found for variant '{name}'")

        return FormalizationVariantConfig(
            name=name,
            style=variant_meta["style"],
            description=variant_meta["description"],
            system_prompt=system_prompt,
            initial_template=initial_template,
            metadata=metadata,
        )

    def default_variant(self) -> str:
        """Get the default variant name from registry metadata."""
        return self._registry["meta"]["default_variant"]

    def list_variants_by_tag(self, tag: str) -> list[str]:
        """List all variants that have a specific tag."""
        return [
            name
            for name, info in self._registry["variants"].items()
            if tag in info.get("tags", [])
        ]

    def list_variants_by_style(self, style: str) -> list[str]:
        """List all variants that use a specific verification style."""
        return [
            name
            for name, info in self._registry["variants"].items()
            if info.get("style") == style
        ]
