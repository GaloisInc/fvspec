"""Spec generation agent for creating Lean theorem statements from PBTs.

This module contains the spec agent that generates Lean specifications
(theorem statements with sorry proofs) from property-based tests,
using implementation signatures from the impl agent as context.
"""

from generate.scaffold.formalize_spec.agent import spec_generation_agent
from generate.scaffold.formalize_spec.models import (
    SpecPayload,
    SpecResult,
    SpecValidation,
)
from generate.scaffold.formalize_spec.runner import run_spec_agent
from generate.scaffold.formalize_spec.validator import (
    extract_signatures,
    validate_spec_output,
)

__all__ = [
    "SpecPayload",
    "SpecResult",
    "SpecValidation",
    "spec_generation_agent",
    "run_spec_agent",
    "validate_spec_output",
    "extract_signatures",
]
