"""Spec-generation prompt package."""

from generate.templates.spec.prompt import get_variant_prompts
from generate.templates.spec.registry import VariantConfig, VariantRegistry

__all__ = ["get_variant_prompts", "VariantRegistry", "VariantConfig"]
