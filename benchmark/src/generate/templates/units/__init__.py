"""Units-generation prompt package."""

from generate.templates.units.prompt import get_variant_prompts
from generate.templates.units.registry import VariantConfig, VariantRegistry

__all__ = ["get_variant_prompts", "VariantRegistry", "VariantConfig"]
