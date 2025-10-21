"""Prompts for the dependency autoformalization subagent."""

from generate.templates.deps.prompt import (
    DependencyPromptBundle,
    get_dependency_prompts,
)
from generate.templates.deps.registry import (
    DependencyVariantConfig,
    DependencyVariantRegistry,
)

__all__ = [
    "get_dependency_prompts",
    "DependencyPromptBundle",
    "DependencyVariantRegistry",
    "DependencyVariantConfig",
]
