"""Unit test filtering for semantic PBT-unit test linking.

This module provides filtering functions to improve unit test extraction by:
1. Extracting functions that are actually asserted on (not just called)
2. Fuzzy matching target function names with asserted function names
3. Filtering unit tests to only those that semantically test the target function

Phase 2 of the unit test extraction pipeline (follows utility function filtering).
"""

from typing import Any

from generate.scaffold.units.ast_extractor import get_asserted_functions


def fuzzy_match_function_names(target: str, candidate: str) -> bool:
    """Check if two function names match with fuzzy matching.

    Handles common variations:
    - Case insensitive matching
    - Underscore/camelCase normalization
    - Substring matching (tile matches tiling, tiled)
    - Plural/singular forms

    Args:
        target: Target function name (from PBT name inference)
        candidate: Candidate function name (from unit test assertions)

    Returns:
        True if names match, False otherwise

    Examples:
        >>> fuzzy_match_function_names("tile", "tile")
        True
        >>> fuzzy_match_function_names("tile", "Tile")
        True
        >>> fuzzy_match_function_names("tile", "tiling")
        True
        >>> fuzzy_match_function_names("tile", "tiled")
        True
        >>> fuzzy_match_function_names("convolution", "conv")
        False  # Too short, could be ambiguous
        >>> fuzzy_match_function_names("process", "preprocessing")
        True  # target is substring
    """
    if not target or not candidate:
        return False

    # Normalize to lowercase
    target_lower = target.lower()
    candidate_lower = candidate.lower()

    # Exact match
    if target_lower == candidate_lower:
        return True

    # Substring match (target in candidate or candidate in target)
    # Require min length to avoid false positives (e.g., "do" matching "redo")
    MIN_SUBSTRING_LENGTH = 4
    if len(target_lower) >= MIN_SUBSTRING_LENGTH:
        if target_lower in candidate_lower or candidate_lower in target_lower:
            return True

    # Try removing common suffixes/prefixes
    # Remove trailing: _op, _operator, _fn, _func, _function
    suffixes = ["_op", "_operator", "_fn", "_func", "_function"]
    target_stripped = target_lower
    candidate_stripped = candidate_lower

    for suffix in suffixes:
        if target_stripped.endswith(suffix):
            target_stripped = target_stripped[: -len(suffix)]
        if candidate_stripped.endswith(suffix):
            candidate_stripped = candidate_stripped[: -len(suffix)]

    if target_stripped == candidate_stripped:
        return True

    # Check for common variations (ing, ed, s endings)
    variations = [
        (target_lower, candidate_lower + "ing"),
        (target_lower, candidate_lower + "ed"),
        (target_lower, candidate_lower + "s"),
        (target_lower + "ing", candidate_lower),
        (target_lower + "ed", candidate_lower),
        (target_lower + "s", candidate_lower),
    ]

    for var1, var2 in variations:
        if var1 == var2:
            return True

    return False


def extract_tested_function(
    unit_test_code: str,
    unit_test_name: str,
    target_function: str,
) -> str | None:
    """Infer which function a unit test is actually testing.

    Uses multiple heuristics:
    1. Functions that appear in assert statements (highest confidence)
    2. Function name mentioned in test name
    3. Function name in docstring

    Args:
        unit_test_code: Python source code of the unit test
        unit_test_name: Name of the unit test function
        target_function: Target function name we're looking for

    Returns:
        Name of the tested function if it matches target (with fuzzy matching),
        None otherwise

    Examples:
        >>> code = '''
        ... def test_tile():
        ...     result = tile([1, 2], 3)
        ...     assert result == [1, 2, 1, 2, 1, 2]
        ... '''
        >>> extract_tested_function(code, "test_tile", "tile")
        'tile'

        >>> code = '''
        ... def test_preprocessing():
        ...     data = load_data()
        ...     result = preprocess(data)
        ...     assert validate(result)
        ... '''
        >>> extract_tested_function(code, "test_preprocessing", "preprocess")
        'preprocess'  # Fuzzy matches test name
    """
    # Strategy 1: Check asserted functions
    asserted_funcs = get_asserted_functions(unit_test_code)

    for func in asserted_funcs:
        if fuzzy_match_function_names(target_function, func):
            return func

    # Strategy 2: Check if target function name appears in test name
    # test_tile → tile, test_convolution_transpose → convolution_transpose
    if fuzzy_match_function_names(target_function, unit_test_name):
        return target_function

    # Strategy 3: Check docstring (if we can extract it)
    try:
        import ast

        tree = ast.parse(unit_test_code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                docstring = ast.get_docstring(node)
                if docstring and target_function.lower() in docstring.lower():
                    return target_function
    except SyntaxError:
        pass

    return None


def filter_unit_tests_by_assertions(
    unit_tests: list[dict[str, Any]],
    target_function: str,
) -> list[dict[str, Any]]:
    """Filter unit tests to only those that assert on the target function.

    This is Phase 2 filtering (after Phase 1 utility function filtering).

    Args:
        unit_tests: List of unit test dictionaries with 'code' and 'name' keys
        target_function: Target function name to filter for

    Returns:
        Filtered list of unit tests that actually test the target function

    Examples:
        >>> tests = [
        ...     {"code": "assert tile([1], 2) == [1, 1]", "name": "test_tile"},
        ...     {"code": "assert validate(data)", "name": "test_validation"},
        ... ]
        >>> filter_unit_tests_by_assertions(tests, "tile")
        [{"code": "assert tile([1], 2) == [1, 1]", "name": "test_tile"}]
    """
    filtered = []

    for unit_test in unit_tests:
        code = unit_test.get("code", "")
        name = unit_test.get("name", "")

        # Check if this unit test actually tests the target function
        tested_func = extract_tested_function(code, name, target_function)

        if tested_func:
            filtered.append(unit_test)

    return filtered
