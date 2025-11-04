"""Formalization agents for implementations and specifications."""

from generate.scaffold.formalize.impl import (
    DependencyPayload,
    DependencyResult,
    FunctionImplPayload,
    FunctionImplResult,
    function_impl_agent,
)
from generate.scaffold.formalize.spec import (
    SpecPayload,
    SpecResult,
    spec_generation_agent,
)

__all__ = [
    # Implementation formalization
    "DependencyPayload",
    "DependencyResult",
    "FunctionImplPayload",
    "FunctionImplResult",
    "function_impl_agent",
    # Specification formalization
    "SpecPayload",
    "SpecResult",
    "spec_generation_agent",
]
