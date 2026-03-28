"""Lean parsing utilities for quality assessment.

Uses simple string parsing instead of regex to avoid catastrophic
backtracking on complex Lean type signatures.
"""

import re


def _parse_paren_groups(code: str) -> list[str]:
    """Extract top-level parenthesized groups from code.

    Handles nested parens so that "(x : List (Nat × Nat))" is returned
    as a single group rather than being split at the inner close-paren.
    """
    groups = []
    depth = 0
    start = -1
    for i, ch in enumerate(code):
        if ch == "(":
            if depth == 0:
                start = i
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0 and start >= 0:
                groups.append(code[start + 1 : i])
                start = -1
    return groups


def extract_lean_parameters(code: str) -> list[str]:
    """Extract parameter names from Lean function/theorem definitions."""
    params = []
    for group in _parse_paren_groups(code):
        if ":" not in group:
            continue
        names_part = group.split(":", 1)[0].strip()
        for token in names_part.split():
            if token.isidentifier():
                params.append(token)
    return params


def extract_lean_types(code: str) -> dict[str, str]:
    """Extract parameter types from Lean code."""
    types = {}
    for group in _parse_paren_groups(code):
        if ":" not in group:
            continue
        names_part, type_part = group.split(":", 1)
        param_type = type_part.strip()
        for token in names_part.split():
            if token.isidentifier():
                types[token] = param_type
    return types


def extract_lean_bounds(code: str) -> dict[str, list[tuple[str, int | float]]]:
    """Extract numeric bounds from Lean hypotheses.

    Returns dict mapping param names to list of (op, value) tuples.
    Example: {"x": [("≤", 100), ("≥", 0)]}
    """
    bounds = {}

    # Match patterns like: 0 ≤ x, x ≤ 100, x < 50, etc.
    # Unicode operators: ≤ ≥ < > =
    bound_patterns = [
        (r"(\d+)\s*≤\s*(\w+)", "min", "≤"),  # 0 ≤ x
        (r"(\w+)\s*≤\s*(\d+)", "max", "≤"),  # x ≤ 100
        (r"(\d+)\s*≥\s*(\w+)", "max", "≥"),  # 100 ≥ x
        (r"(\w+)\s*≥\s*(\d+)", "min", "≥"),  # x ≥ 0
        (r"(\d+)\s*<\s*(\w+)", "min_exclusive", "<"),
        (r"(\w+)\s*<\s*(\d+)", "max_exclusive", "<"),
        (r"(\d+)\s*>\s*(\w+)", "max_exclusive", ">"),
        (r"(\w+)\s*>\s*(\d+)", "min_exclusive", ">"),
    ]

    for pattern, bound_type, op in bound_patterns:
        for match in re.finditer(pattern, code):
            if bound_type in ["min", "min_exclusive"]:
                value, param = match.group(1), match.group(2)
            else:
                param, value = match.group(1), match.group(2)

            try:
                value_num = int(value)
                if param not in bounds:
                    bounds[param] = []
                bounds[param].append((bound_type, value_num))
            except ValueError:
                # Skip values that cannot be converted to int (non-numeric bounds are ignored)
                pass

    return bounds


def count_lean_properties(code: str) -> int:
    """Count theorem/property statements in Lean code."""
    # Count 'theorem' and 'lemma' keywords
    count = len(re.findall(r"\btheorem\b", code))
    count += len(re.findall(r"\blemma\b", code))

    # Also count property assertions in theorem bodies
    # Look for common patterns like: result = ..., result ∈ ..., etc.
    count += len(re.findall(r"=\s*[^=]", code))  # Simple equality checks

    return max(1, count)  # At least 1 if code exists


def count_lean_theorems(code: str) -> int:
    """Count theorem and lemma declarations in Lean code.

    This counts only explicit theorem/lemma keywords, not property
    assertions within theorem bodies.
    """
    count = len(re.findall(r"\btheorem\b", code))
    count += len(re.findall(r"\blemma\b", code))
    return count


def detect_trivial_unit_theorems(spec_code: str) -> int:
    """Count trivial theorems that just assert Unit-typed functions equal ().

    These theorems arise when:
    1. Implementation discovery fails → stub with `def foo : Unit := sorry`
    2. Spec agent generates trivial `theorem foo_check : foo = () := by plausible`
    3. Plausibility passes (tautology) but provides no verification value

    Pattern: theorem <name> : <ident> = () := by ...

    Args:
        spec_code: Generated Lean specification code

    Returns:
        Number of trivial Unit equality theorems detected

    Examples:
        >>> code = "theorem top_k_1_check : top_k_1 = () := by plausible"
        >>> detect_trivial_unit_theorems(code)
        1
    """
    # Match: theorem <name> : <ident> = () := by ...
    # Captures theorems asserting a function equals unit value
    pattern = r"theorem\s+\w+\s*:\s*(\w+)\s*=\s*\(\)\s*:=\s*by"
    matches = re.findall(pattern, spec_code)
    return len(matches)


def detect_unit_stub_in_impl(impl_code: str) -> bool:
    """Detect if implementation is a Unit stub (discovery failed).

    When function discovery fails, impl agent generates:
    `def <name> : Unit := sorry`

    This indicates the function source wasn't found and only a placeholder exists.

    Args:
        impl_code: Implementation code from Impl.lean

    Returns:
        True if Unit stub detected, False otherwise

    Examples:
        >>> code = "def top_k_1 : Unit := sorry"
        >>> detect_unit_stub_in_impl(code)
        True
    """
    # Match: def <name> : Unit := sorry
    pattern = r"def\s+\w+\s*:\s*Unit\s*:=\s*sorry"
    return bool(re.search(pattern, impl_code))


def detect_eval_statements(lean_code: str) -> list[str]:
    r"""Detect #eval statements in Lean code.

    #eval statements are encouraged during the agent loop to verify computability
    of implementations. Post-agent, they may be stripped if they cause build
    failures (e.g., if the function still contains `sorry` or has other issues).

    Args:
        lean_code: Lean code to check for #eval statements

    Returns:
        List of #eval statements found (each as a string)

    Examples:
        >>> code = "#eval fibonacci 0\n#eval fibonacci 5"
        >>> detect_eval_statements(code)
        ['#eval fibonacci 0', '#eval fibonacci 5']
    """
    # Match: #eval <expression> (up to newline or end of string)
    # This captures the full #eval statement including the expression
    pattern = r"^#eval\s+[^\n]+"
    matches = re.findall(pattern, lean_code, re.MULTILINE)
    return matches


def extract_hypothesis_strategies(
    code: str,
) -> dict[str, list[tuple[str, int | float]]]:
    """Extract Hypothesis strategy bounds from @given decorator.

    Returns dict mapping param names to list of (constraint_type, value) tuples.
    Example: {"x": [("min_value", 0), ("max_value", 100)]}
    """
    strategies = {}

    # Match patterns like: x=st.integers(0, 100) or x=st.integers(min_value=0, max_value=100)
    param_pattern = r"(\w+)\s*=\s*st\.(\w+)\([^)]*\)"

    for match in re.finditer(param_pattern, code):
        param_name = match.group(1)
        strategy_type = match.group(2)
        strategy_call = match.group(0)

        bounds = []

        # Extract positional bounds for integers/floats
        if strategy_type in ["integers", "floats"]:
            # Match: st.integers(0, 100)
            pos_pattern = r"st\.\w+\((\d+),\s*(\d+)\)"
            pos_match = re.search(pos_pattern, strategy_call)
            if pos_match:
                bounds.append(("min_value", int(pos_match.group(1))))
                bounds.append(("max_value", int(pos_match.group(2))))

        # Extract keyword bounds
        for kw in ["min_value", "max_value", "min_size", "max_size"]:
            kw_pattern = rf"{kw}\s*=\s*(\d+)"
            kw_match = re.search(kw_pattern, strategy_call)
            if kw_match:
                bounds.append((kw, int(kw_match.group(1))))

        if bounds:
            strategies[param_name] = bounds

    return strategies
