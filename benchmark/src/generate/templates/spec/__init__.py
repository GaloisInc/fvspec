"""Spec-generation prompt package."""

from .prompt import get_variant_prompts
from .registry import VariantRegistry, VariantConfig

__all__ = ["get_variant_prompts", "VariantRegistry", "VariantConfig"]
