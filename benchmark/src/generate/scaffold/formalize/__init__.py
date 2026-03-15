"""Formalization agents for implementations and specifications."""

from generate.scaffold.formalize.agent import (
    FormalizationPayload,
    FormalizationResult,
    formalization_agent,
)
from generate.scaffold.formalize.impl import (
    DependencyPayload,
    DependencyResult,
    FunctionImplPayload,
    FunctionImplResult,
    function_impl_agent,
)

__all__ = [
    # Unified formalization agent
    "FormalizationPayload",
    "FormalizationResult",
    "formalization_agent",
    # Implementation formalization (used for deps)
    "DependencyPayload",
    "DependencyResult",
    "FunctionImplPayload",
    "FunctionImplResult",
    "function_impl_agent",
]
