"""Prompts for the dependency autoformalization subagent."""

from generate.templates.impl.prompt import (
    DependencyPromptBundle,
    get_dependency_prompts,
)
from generate.templates.impl.registry import (
    DependencyVariantConfig,
    DependencyVariantRegistry,
)
from generate.templates.impl.strings import (
    BoundToolStrings,
    DependencyStrings,
    DepsLeanStrings,
    ErrorStrings,
    get_dependency_strings,
)

__all__ = [
    "get_dependency_prompts",
    "DependencyPromptBundle",
    "DependencyVariantRegistry",
    "DependencyVariantConfig",
    "get_dependency_strings",
    "DependencyStrings",
    "BoundToolStrings",
    "ErrorStrings",
    "DepsLeanStrings",
]
