"""Unit test extraction and generation for fvspec benchmark.

This module provides tools to extract unit tests from Python property-based tests
and generate LSpec test suites for Lean 4.

Main entry points:
    - extract_unit_tests: Extract tests from PBT code via AST analysis
    - generate_test_suite: Generate LSpec code from test cases
    - FloatTestValidator: Validate float tests during evaluation

Example:
    >>> from generate.scaffold.units import extract_unit_tests, generate_test_suite
    >>>
    >>> pbt_code = '''
    ... X = [1, 2, 3]
    ... assert double(X) == [2, 4, 6]
    ... '''
    >>>
    >>> test_suite = extract_unit_tests(pbt_code, func_name="double")
    >>> if test_suite:
    ...     lean_code = generate_test_suite(test_suite)
    ...     print(lean_code)
"""

from generate.scaffold.units.ast_extractor import ASTExtractor
from generate.scaffold.units.float_validator import FloatTestValidator
from generate.scaffold.units.lspec_generator import generate_test_suite
from generate.scaffold.units.types import TestCase, TestSuite


def extract_unit_tests(pbt_code: str, func_name: str) -> TestSuite | None:
    """Extract unit tests from PBT code via AST analysis.

    Args:
        pbt_code: Python source code containing the property-based test
        func_name: Name of the function being tested

    Returns:
        TestSuite containing extracted tests, or None if no tests found

    Example:
        >>> code = '''
        ... X = [1, 2, 3]
        ... assert double(X) == [2, 4, 6]
        ... assert double([]) == []
        ... '''
        >>> suite = extract_unit_tests(code, func_name="double")
        >>> suite.exact_tests[0].inputs
        ['[1, 2, 3]']
    """
    extractor = ASTExtractor()
    tests = extractor.extract_tests(pbt_code, func_name=func_name)

    if not tests:
        return None

    # Separate exact and float tests
    exact_tests = [t for t in tests if not t.is_float]
    float_tests = [t for t in tests if t.is_float]

    return TestSuite(
        exact_tests=exact_tests,
        float_tests=float_tests,
        extraction_stats={
            "method": "ast",
            "count": len(tests),
            "exact_count": len(exact_tests),
            "float_count": len(float_tests),
        },
    )


__all__ = [
    "extract_unit_tests",
    "generate_test_suite",
    "FloatTestValidator",
    "TestCase",
    "TestSuite",
    "ASTExtractor",
]
