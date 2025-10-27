"""Registry for dependency autoformalization prompt variants."""

import tomllib
from pathlib import Path
from pydantic import BaseModel, Field


class DependencyVariantConfig(BaseModel):
    """Configuration for a dependency prompt variant."""

    name: str
    style: str
    description: str
    system_prompt: str
    translate_template: str
    refine_template: str
    metadata: dict = Field(default_factory=dict)


class DependencyVariantRegistry:
    """Load dependency autoformalization prompt variants."""

    def __init__(self, templates_dir: Path | None = None) -> None:
        """Initialise the registry with an optional templates directory override."""
        if templates_dir is None:
            templates_dir = Path(__file__).parent
        self.templates_dir = templates_dir
        self.registry_path = templates_dir / "registry.toml"

        if not self.registry_path.exists():
            raise FileNotFoundError(f"Registry file not found at {self.registry_path}.")

        self._registry = self._load_registry()

    def _load_registry(self) -> dict:
        """Load the registry TOML file from disk."""
        with open(self.registry_path, "rb") as f:
            return tomllib.load(f)

    def list_variants(self) -> list[str]:
        """Return all registered dependency variants."""
        return list(self._registry["variants"].keys())

    def get_variant_info(self, name: str) -> dict:
        """Return the raw configuration dictionary for ``name``."""
        if name not in self._registry["variants"]:
            raise ValueError(f"Unknown dependency prompt variant: {name}.")
        return self._registry["variants"][name]

    def get_variant(self, name: str) -> DependencyVariantConfig:
        """Load the fully parsed prompt bundle for ``name``."""
        meta = self.get_variant_info(name)
        variant_path = self.templates_dir / meta["path"]

        metadata: dict = {}
        metadata_path = variant_path / "metadata.toml"
        if metadata_path.exists():
            with open(metadata_path, "rb") as f:
                metadata = tomllib.load(f)

        system_prompt_path = variant_path / "system.prompt"
        translate_prompt_path = variant_path / "translate.prompt"
        refine_prompt_path = variant_path / "refine.prompt"
        common_refine_path = self.templates_dir / "common" / "refine.prompt"

        if not system_prompt_path.exists():
            raise FileNotFoundError(
                f"System prompt not found for dependency variant '{name}'"
            )
        if not translate_prompt_path.exists():
            raise FileNotFoundError(
                f"Translate prompt not found for dependency variant '{name}'"
            )

        if refine_prompt_path.exists():
            refine_template = refine_prompt_path.read_text()
        elif common_refine_path.exists():
            refine_template = common_refine_path.read_text()
        else:
            raise FileNotFoundError(
                "No refine.prompt found in variant or common directory."
            )

        return DependencyVariantConfig(
            name=name,
            style=meta.get("style", "baseline"),
            description=meta["description"],
            system_prompt=system_prompt_path.read_text(),
            translate_template=translate_prompt_path.read_text(),
            refine_template=refine_template,
            metadata=metadata,
        )

    def default_variant(self) -> str:
        """Return the default variant specified in the registry metadata."""
        return self._registry["meta"]["default_variant"]

    def list_variants_by_tag(self, tag: str) -> list[str]:
        """Return variant names that include the supplied tag."""
        return [
            name
            for name, info in self._registry["variants"].items()
            if tag in info.get("tags", [])
        ]
