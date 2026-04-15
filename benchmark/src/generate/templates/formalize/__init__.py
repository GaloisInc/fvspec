"""Unified formalization prompt templates."""

from generate.templates.formalize.prompt import get_formalization_prompts
from generate.templates.formalize.registry import (
    FormalizationVariantConfig,
    FormalizationVariantRegistry,
)

__all__ = [
    "get_formalization_prompts",
    "FormalizationVariantConfig",
    "FormalizationVariantRegistry",
]
