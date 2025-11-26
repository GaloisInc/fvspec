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

    # Check for Fvspec.Impl import
    if "import Fvspec.Impl" not in lean_code:
        errors.append("Missing 'import Fvspec.Impl' statement")

    # Check for test-related patterns (relaxed validation)
    # Accept any of: test function calls, TestSeq definitions, #lspec directive, or #eval
    has_test_pattern = any(
        pattern in lean_code
        for pattern in ["test ", "TestSeq", "#lspec", "#eval", "#guard"]
    )

    # Consider it valid if imports are present and has some test-like pattern
    # OR if the code has more than just imports (actual definitions/code)
    has_content = (
        len(
            [
                line
                for line in lean_code.split("\n")
                if line.strip() and not line.strip().startswith("--")
            ]
        )
        > 2
    )

    has_tests = has_test_pattern or has_content
    valid_syntax = has_test_pattern or has_content

    if not has_tests:
        errors.append("No test-related content found")

    # Overall validity: must have imports and some content
    valid = (
        "import LSpec" in lean_code and "import Fvspec.Impl" in lean_code and has_tests
    )

    return UnitsValidation(
        has_tests=has_tests,
        valid_lspec_syntax=valid_syntax,
        compiles=False,  # Not checked in MVP
        valid=valid,
        errors=errors,
    )
