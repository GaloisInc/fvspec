"""Spec generation agent for creating Lean theorem statements from PBTs.

This module contains the spec agent that generates Lean specifications
(theorem statements with sorry proofs) from property-based tests,
using implementation signatures from the impl agent as context.
"""

from generate.scaffold.formalize_spec.models import (
    SpecPayload,
    SpecResult,
    SpecValidation,
)

__all__ = [
    "SpecPayload",
    "SpecResult",
    "SpecValidation",
]
