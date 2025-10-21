"""Tests for structural faithfulness metrics.

These tests verify that the objective structural metrics correctly analyze
Python and Lean code structure without relying on LLM self-assessment.
"""

import pytest
from generate.scaffold.quality_assessment import (
    StructuralFaithfulness,
    _extract_python_parameters,
    _extract_python_types,
    _extract_hypothesis_strategies,
    _count_python_assertions,
    _extract_dependency_names,
    _extract_lean_parameters,
    _extract_lean_types,
    _extract_lean_bounds,
    _compute_parameter_coverage,
    _compute_type_correspondence,
)


# Python parsing tests


def test_extract_python_parameters():
    """Test extraction of parameter names from Python functions."""
    code = """
def test_add(x: int, y: int):
    assert x + y == y + x
"""
    params = _extract_python_parameters(code)
    assert params == ["x", "y"]


def test_extract_python_parameters_with_self():
    """Test that 'self' parameter is excluded."""
    code = """
def test_method(self, x: int, y: int):
    assert x + y == y + x
"""
    params = _extract_python_parameters(code)
    assert params == ["x", "y"]


def test_extract_python_types():
    """Test extraction of type annotations."""
    code = """
def test_add(x: int, y: float, items: list):
    pass
"""
    types = _extract_python_types(code)
    assert types == {"x": "int", "y": "float", "items": "list"}


def test_extract_hypothesis_strategies_positional():
    """Test extraction of strategy bounds (positional args)."""
    code = """
@given(x=st.integers(0, 100), y=st.floats(0.0, 1.0))
def test_bounds(x, y):
    pass
"""
    strategies = _extract_hypothesis_strategies(code)
    assert "x" in strategies
    assert ("min_value", 0) in strategies["x"]
    assert ("max_value", 100) in strategies["x"]


def test_extract_hypothesis_strategies_keyword():
    """Test extraction of strategy bounds (keyword args)."""
    code = """
@given(x=st.integers(min_value=10, max_value=50))
def test_bounds(x):
    pass
"""
    strategies = _extract_hypothesis_strategies(code)
    assert "x" in strategies
    assert ("min_value", 10) in strategies["x"]
    assert ("max_value", 50) in strategies["x"]


def test_count_python_assertions():
    """Test counting assert statements."""
    code = """
def test_multiple(x, y):
    assert x >= 0
    assert y >= 0
    assert x + y > 0
"""
    count = _count_python_assertions(code)
    assert count == 3


def test_extract_dependency_names():
    """Test extraction of function names from dependencies."""
    deps = [
        "def helper(x): return x + 1",
        "def another_helper(y): return y * 2",
        "class MyClass:\n    pass",
    ]
    names = _extract_dependency_names(deps)
    assert "helper" in names
    assert "another_helper" in names
    assert "MyClass" in names


# Lean parsing tests


def test_extract_lean_parameters():
    """Test extraction of parameter names from Lean code."""
    code = """
theorem test_add (x y : Int) (z : Nat) :
  x + y + z = z + y + x := by sorry
"""
    params = _extract_lean_parameters(code)
    assert "x" in params
    assert "y" in params
    assert "z" in params


def test_extract_lean_types():
    """Test extraction of parameter types from Lean code."""
    code = """
def add (x y : Int) (z : Nat) : Int := x + y + z
"""
    types = _extract_lean_types(code)
    assert types["x"] == "Int"
    assert types["y"] == "Int"
    assert types["z"] == "Nat"


def test_extract_lean_bounds():
    """Test extraction of numeric bounds from Lean hypotheses."""
    code = """
theorem test (x : Int) (h1 : 0 ≤ x) (h2 : x ≤ 100) :
  0 ≤ x ∧ x ≤ 100 := by sorry
"""
    bounds = _extract_lean_bounds(code)
    assert "x" in bounds
    # Check that bounds contain min and max constraints
    bound_types = [b[0] for b in bounds["x"]]
    assert "min" in bound_types or "min_exclusive" in bound_types
    assert "max" in bound_types or "max_exclusive" in bound_types


# Metric computation tests


def test_compute_parameter_coverage_perfect():
    """Test parameter coverage with perfect match."""
    py_params = ["x", "y", "z"]
    lean_params = ["x", "y", "z"]
    coverage = _compute_parameter_coverage(py_params, lean_params)
    assert coverage == 1.0


def test_compute_parameter_coverage_partial():
    """Test parameter coverage with partial match."""
    py_params = ["x", "y", "z"]
    lean_params = ["x", "y"]
    coverage = _compute_parameter_coverage(py_params, lean_params)
    assert coverage == pytest.approx(2.0 / 3.0)


def test_compute_parameter_coverage_empty():
    """Test parameter coverage with no Python params."""
    py_params = []
    lean_params = ["x", "y"]
    coverage = _compute_parameter_coverage(py_params, lean_params)
    assert coverage == 1.0  # No params to check = success


def test_compute_type_correspondence():
    """Test type correspondence checking."""
    py_types = {"x": "int", "y": "float", "z": "list"}
    lean_types = {"x": "Int", "y": "Real", "z": "List"}
    correspondence = _compute_type_correspondence(py_types, lean_types)
    assert correspondence == 1.0  # All types map correctly


def test_compute_type_correspondence_wrong_type():
    """Test type correspondence with incorrect mapping."""
    py_types = {"x": "int", "y": "str"}
    lean_types = {"x": "Int", "y": "Int"}  # Wrong: should be String
    correspondence = _compute_type_correspondence(py_types, lean_types)
    assert correspondence < 1.0  # Should detect mismatch


# Integration tests


def test_structural_faithfulness_simple_example():
    """Test structural metrics on a simple example."""
    python_code = """
from hypothesis import given
from hypothesis import strategies as st

@given(x=st.integers(0, 100), y=st.integers(0, 50))
def test_add(x: int, y: int):
    result = x + y
    assert result >= 0
    assert result <= 150
"""

    lean_code = """
def add (x y : Int) : Int := x + y

theorem test_add (x y : Int) (h1 : 0 ≤ x ∧ x ≤ 100) (h2 : 0 ≤ y ∧ y ≤ 50) :
  let result := add x y
  0 ≤ result ∧ result ≤ 150 := by
  sorry
"""

    metrics = StructuralFaithfulness.from_codes(
        python_pbt=python_code, python_deps=[], lean_code=lean_code
    )

    # All parameters should be found
    assert metrics.parameter_coverage >= 0.9

    # Type correspondence should be good (int → Int)
    assert metrics.type_correspondence >= 0.9

    # Strategy bounds should be detected
    assert metrics.strategy_coverage >= 0.5

    # Assertions should be covered
    assert metrics.assertion_coverage >= 0.5

    # Overall should be reasonable
    assert 0.0 <= metrics.overall <= 1.0
    assert metrics.overall >= 0.5


def test_structural_faithfulness_with_dependencies():
    """Test structural metrics with dependencies."""
    python_code = """
from hypothesis import given
from hypothesis import strategies as st

@given(x=st.integers())
def test_helper_use(x: int):
    result = helper(x)
    assert result > x
"""

    python_deps = ["def helper(x): return x + 1"]

    lean_code = """
def helper (x : Int) : Int := x + 1

theorem test_helper_use (x : Int) :
  helper x > x := by
  sorry
"""

    metrics = StructuralFaithfulness.from_codes(
        python_pbt=python_code, python_deps=python_deps, lean_code=lean_code
    )

    # Dependency name should be found
    assert metrics.dependency_coverage == 1.0


def test_structural_faithfulness_missing_params():
    """Test structural metrics when parameters are missing."""
    python_code = """
def test_three_params(x: int, y: int, z: int):
    assert x + y + z >= 0
"""

    lean_code = """
theorem test_two_params (x y : Int) :
  x + y >= 0 := by sorry
"""

    metrics = StructuralFaithfulness.from_codes(
        python_pbt=python_code, python_deps=[], lean_code=lean_code
    )

    # Should detect that one parameter is missing
    assert metrics.parameter_coverage < 1.0
    assert metrics.parameter_coverage >= 0.6  # 2 out of 3


def test_structural_faithfulness_wrong_types():
    """Test structural metrics with incorrect type mappings."""
    python_code = """
def test_types(x: int, text: str):
    assert len(text) > 0
"""

    lean_code = """
theorem test_types (x : Int) (text : Int) :
  text > 0 := by sorry
"""

    metrics = StructuralFaithfulness.from_codes(
        python_pbt=python_code, python_deps=[], lean_code=lean_code
    )

    # Should detect type mismatch (str → Int is wrong)
    assert metrics.type_correspondence < 1.0


def test_structural_faithfulness_empty_code():
    """Test structural metrics with empty/malformed code."""
    metrics = StructuralFaithfulness.from_codes(
        python_pbt="", python_deps=[], lean_code=""
    )

    # Should not crash, should return default values
    assert 0.0 <= metrics.overall <= 1.0


def test_structural_faithfulness_serialization():
    """Test that StructuralFaithfulness serializes correctly."""
    metrics = StructuralFaithfulness(
        parameter_coverage=0.8,
        type_correspondence=0.9,
        strategy_coverage=0.7,
        assertion_coverage=0.85,
        dependency_coverage=1.0,
        overall=0.85,
    )

    # Should serialize to JSON
    json_str = metrics.model_dump_json()
    assert "parameter_coverage" in json_str
    assert "0.8" in json_str

    # Should be able to parse back
    parsed = StructuralFaithfulness.model_validate_json(json_str)
    assert parsed.parameter_coverage == 0.8
    assert parsed.overall == 0.85
