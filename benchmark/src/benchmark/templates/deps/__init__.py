"""Prompts for the dependency autoformalization subagent."""

from .prompt import (
    DependencyPromptBundle,
    get_dependency_prompts,
)
from .registry import DependencyVariantRegistry, DependencyVariantConfig

__all__ = [
    "get_dependency_prompts",
    "DependencyPromptBundle",
    "DependencyVariantRegistry",
    "DependencyVariantConfig",
]
