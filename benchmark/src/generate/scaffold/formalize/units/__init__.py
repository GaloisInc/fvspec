"""Units generation agent for fvspec benchmark.

This module contains the LLM-based units agent that generates LSpec test
suites from Python property-based tests. It replaces the deprecated AST-based
extraction system.

Public API:
    - UnitsPayload: Input payload for units agent
    - UnitsResult: Output result from units agent
    - UnitsValidation: Validation result for generated tests
    - units_generation_agent: Main solver function
    - validate_units_output: Validation function
"""

from generate.scaffold.formalize.units.agent import units_generation_agent
from generate.scaffold.formalize.units.models import (
    UnitsPayload,
    UnitsResult,
    UnitsValidation,
)
from generate.scaffold.formalize.units.validator import validate_units_output

__all__ = [
    "UnitsPayload",
    "UnitsResult",
    "UnitsValidation",
    "units_generation_agent",
    "validate_units_output",
]
