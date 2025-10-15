"""Prompt variant registry for A/B testing different prompting strategies."""

import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class VariantConfig(BaseModel):
    """A loaded prompt variant with all templates and metadata.

    Attributes:
        name: Unique identifier for this variant
        style: Verification style (functional or mvcgen)
        description: Human-readable description of the variant's purpose
        system_prompt: The full system prompt text
        initial_template: The initial user prompt template (may contain Jinja2)
        metadata: Additional configuration and notes from metadata.toml
    """

    name: str
    style: Literal["functional", "mvcgen"]
    description: str
    system_prompt: str
    initial_template: str
    metadata: dict = Field(default_factory=dict)


class VariantRegistry:
    """Manages prompt variant loading and validation.

    The registry loads variant configurations from templates/registry.toml
    and provides methods to list and retrieve prompt variants for A/B testing.
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

    def get_variant_info(self, name: str) -> dict:
        """Get registry metadata for a variant without loading templates.

        Args:
            name: Variant name

        Returns:
            Registry metadata dict (path, style, description, tags, etc.)

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
            name: Variant name (e.g., "baseline-functional", "terse-functional")

        Returns:
            VariantConfig with loaded templates and metadata

        Raises:
            ValueError: If variant name is not found in registry
            FileNotFoundError: If variant files are missing
        """
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

        # Load templates
        system_prompt_path = variant_path / "system.prompt"
        initial_prompt_path = variant_path / "initial.prompt"

        if not system_prompt_path.exists():
            raise FileNotFoundError(
                f"System prompt not found at {system_prompt_path} for variant '{name}'"
            )

        system_prompt = system_prompt_path.read_text()

        # Fall back to shared initial prompt if variant doesn't have its own
        if not initial_prompt_path.exists():
            shared_initial = self.templates_dir / "shared" / "initial.prompt"
            if not shared_initial.exists():
                raise FileNotFoundError(
                    f"Neither variant-specific initial prompt at {initial_prompt_path} "
                    f"nor shared initial prompt at {shared_initial} found for variant '{name}'"
                )
            initial_template = shared_initial.read_text()
        else:
            initial_template = initial_prompt_path.read_text()

        return VariantConfig(
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
        """List all variants that have a specific tag.

        Args:
            tag: Tag to filter by (e.g., "baseline", "experimental", "functional")

        Returns:
            List of variant names with the specified tag
        """
        return [
            name
            for name, info in self._registry["variants"].items()
            if tag in info.get("tags", [])
        ]

    def list_variants_by_style(self, style: str) -> list[str]:
        """List all variants that use a specific verification style.

        Args:
            style: Style to filter by ("functional" or "mvcgen")

        Returns:
            List of variant names with the specified style
        """
        return [
            name
            for name, info in self._registry["variants"].items()
            if info.get("style") == style
        ]
