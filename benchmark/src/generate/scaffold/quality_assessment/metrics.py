"""Metric computation utilities for quality assessment."""


def compute_parameter_coverage(py_params: list[str], lean_params: list[str]) -> float:
    """Compute fraction of Python parameters found in Lean."""
    if not py_params:
        return 1.0  # No params to check

    py_set = set(py_params)
    lean_set = set(lean_params)
    matched = py_set & lean_set

    return len(matched) / len(py_set)


def compute_type_correspondence(
    py_types: dict[str, str], lean_types: dict[str, str]
) -> float:
    """Compute fraction of Python types correctly mapped to Lean."""
    if not py_types:
        return 1.0

    # Type mapping rules
    TYPE_MAP = {
        "int": ["Int", "Nat", "ℕ", "ℤ", "Integer"],
        "float": ["Float", "Real", "ℝ"],
        "str": ["String"],
        "bool": ["Bool", "Prop"],
        "list": ["List", "Array"],
        "dict": ["Map", "HashMap", "Finmap"],
        "set": ["Set", "Finset"],
    }

    correct = 0
    total = 0

    for param, py_type in py_types.items():
        if param in lean_types:
            total += 1
            lean_type = lean_types[param]

            # Check if mapping is sensible
            if py_type in TYPE_MAP:
                if any(lt in lean_type for lt in TYPE_MAP[py_type]):
                    correct += 1
            else:
                # Unknown type, be lenient (might be custom type)
                correct += 0.5

    return correct / total if total > 0 else 1.0


def compute_strategy_coverage(
    py_strategies: dict[str, list[tuple[str, int | float]]],
    lean_bounds: dict[str, list[tuple[str, int | float]]],
) -> float:
    """Compute fraction of Hypothesis strategy bounds found in Lean."""
    if not py_strategies:
        return 1.0

    total_bounds = 0
    matched_bounds = 0

    for param, py_bounds in py_strategies.items():
        for bound_type, value in py_bounds:
            total_bounds += 1

            # Check if similar bound exists in Lean
            if param in lean_bounds:
                for lean_bound_type, lean_value in lean_bounds[param]:
                    # Match min_value with min/≥, max_value with max/≤
                    if bound_type == "min_value" and "min" in lean_bound_type:
                        if abs(value - lean_value) <= 1:  # Allow small differences
                            matched_bounds += 1
                            break
                    elif bound_type == "max_value" and "max" in lean_bound_type:
                        if abs(value - lean_value) <= 1:
                            matched_bounds += 1
                            break

    return matched_bounds / total_bounds if total_bounds > 0 else 1.0


def compute_assertion_coverage(py_assertions: int, lean_properties: int) -> float:
    """Compute ratio of Lean properties to Python assertions."""
    if py_assertions == 0:
        return 1.0 if lean_properties > 0 else 0.0

    # Ideal: at least as many Lean properties as Python assertions
    ratio = lean_properties / py_assertions
    return min(1.0, ratio)  # Cap at 1.0


def compute_dependency_coverage(dep_names: list[str], lean_code: str) -> float:
    """Compute fraction of dependency names found in Lean code."""
    if not dep_names:
        return 1.0

    found = sum(1 for name in dep_names if name in lean_code)
    return found / len(dep_names)
