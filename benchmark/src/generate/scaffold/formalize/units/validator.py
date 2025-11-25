"""Validation for units agent output."""

from __future__ import annotations

from generate.scaffold.formalize.units.models import UnitsValidation


def validate_units_output(lean_code: str) -> UnitsValidation:
    """Validate generated Tests.lean output.

    Performs basic syntax and structure checks without requiring compilation.
    Compilation validation can be added in future iteration.

    Args:
        lean_code: Generated Lean code

    Returns:
        Validation result with success status and any errors
    """
    errors = []

    # Check for LSpec import
    if "import LSpec" not in lean_code:
        errors.append("Missing 'import LSpec' statement")

    # Check for Fvspec.Spec import
    if "import Fvspec.Spec" not in lean_code:
        errors.append("Missing 'import Fvspec.Spec' statement")

    # Check for at least one test (look for 'test "name"' pattern)
    has_tests = 'test "' in lean_code
    if not has_tests:
        errors.append("No tests found (no 'test \"name\"' patterns)")

    # Check for basic LSpec syntax patterns
    # Either has 'test ' calls or defines TestSeq
    valid_syntax = ("test " in lean_code) or ("TestSeq" in lean_code)
    if not valid_syntax:
        errors.append("Invalid LSpec syntax (no 'test' or 'TestSeq' found)")

    # Overall validity: must have tests and valid syntax
    valid = has_tests and valid_syntax

    return UnitsValidation(
        has_tests=has_tests,
        valid_lspec_syntax=valid_syntax,
        compiles=False,  # Not checked in MVP
        valid=valid,
        errors=errors,
    )
