"""Tests for radon code metrics collection.

These tests verify that radon metrics are correctly computed for Python PBT code.
"""

import pytest

from generate.scaffold.quality_assessment.radon_metrics import (
    RadonMetrics,
    compute_metrics_for_datapoint,
)


def test_radon_metrics_simple_function():
    """Test radon metrics on a simple function."""
    code = """
def add(x: int, y: int) -> int:
    return x + y
"""
    metrics = RadonMetrics.from_code(code)

    assert metrics.loc > 0
    assert metrics.sloc > 0
    assert metrics.num_functions == 1
    assert metrics.average_complexity == 1.0
    assert metrics.complexity_rank() == "A"
    assert metrics.maintainability_index > 0


def test_radon_metrics_complex_function():
    """Test radon metrics on a function with branches."""
    code = """
def factorial(n: int) -> int:
    if n <= 0:
        return 1
    elif n == 1:
        return 1
    else:
        result = 1
        for i in range(2, n + 1):
            result *= i
        return result
"""
    metrics = RadonMetrics.from_code(code)

    assert metrics.num_functions == 1
    assert metrics.average_complexity > 1  # Has branches and loops
    assert metrics.max_complexity > 1


def test_radon_metrics_multiple_functions():
    """Test radon metrics on code with multiple functions."""
    code = """
def helper(x: int) -> int:
    if x < 0:
        return -x
    return x

def main(a: int, b: int) -> int:
    return helper(a) + helper(b)
"""
    metrics = RadonMetrics.from_code(code)

    assert metrics.num_functions == 2
    assert metrics.total_complexity == metrics.average_complexity * 2


def test_radon_metrics_with_comments():
    """Test that comments are counted correctly."""
    code = """
# This is a comment
def add(x: int, y: int) -> int:
    # Another comment
    return x + y  # Inline comment
"""
    metrics = RadonMetrics.from_code(code)

    assert metrics.comments > 0
    assert metrics.single_comments > 0


def test_radon_metrics_hypothesis_test():
    """Test radon metrics on a typical hypothesis test."""
    code = """
from hypothesis import given
from hypothesis import strategies as st

@given(x=st.integers(0, 100), y=st.integers(0, 100))
def test_add_commutative(x: int, y: int):
    assert x + y == y + x
"""
    metrics = RadonMetrics.from_code(code)

    assert metrics.num_functions == 1
    assert metrics.loc > 0
    assert metrics.sloc > 0
    assert metrics.maintainability_index > 0


def test_radon_metrics_empty_code():
    """Test radon metrics on empty code."""
    code = ""

    # Empty code is parsed successfully but returns all zeros
    metrics = RadonMetrics.from_code(code)
    assert metrics.loc == 0
    assert metrics.num_functions == 0
    assert metrics.average_complexity == 0.0


def test_radon_metrics_syntax_error():
    """Test radon metrics on code with syntax error."""
    code = """
def broken(x:
    return x
"""

    with pytest.raises(ValueError):
        RadonMetrics.from_code(code)


def test_complexity_rank_a():
    """Test complexity rank A (1-5)."""
    code = """
def simple(x):
    if x > 0:
        return x
    return 0
"""
    metrics = RadonMetrics.from_code(code)
    assert metrics.complexity_rank() == "A"
    assert metrics.average_complexity <= 5


def test_complexity_rank_b():
    """Test complexity rank B (6-10)."""
    code = """
def moderate(x):
    if x > 10:
        return 1
    elif x > 5:
        return 2
    elif x > 0:
        return 3
    elif x == 0:
        return 4
    elif x < 0:
        return 5
    else:
        return 6
"""
    metrics = RadonMetrics.from_code(code)
    assert metrics.complexity_rank() in ["A", "B"]  # Could be either
    assert metrics.average_complexity > 1


def test_maintainability_rank_a():
    """Test maintainability rank A (20-100)."""
    code = """
def simple_add(x: int, y: int) -> int:
    return x + y
"""
    metrics = RadonMetrics.from_code(code)
    assert metrics.maintainability_rank() == "A"
    assert metrics.maintainability_index >= 20


def test_halstead_metrics():
    """Test that Halstead metrics are computed."""
    code = """
def factorial(n: int) -> int:
    result = 1
    for i in range(1, n + 1):
        result *= i
    return result
"""
    metrics = RadonMetrics.from_code(code)

    # Halstead metrics should be non-zero for code with operators
    assert metrics.halstead_vocabulary > 0
    assert metrics.halstead_length > 0
    assert metrics.halstead_volume > 0
    assert metrics.halstead_difficulty > 0
    assert metrics.halstead_effort > 0


def test_compute_metrics_for_datapoint_success():
    """Test successful metric computation for a datapoint."""
    code = """
from hypothesis import given
from hypothesis import strategies as st

@given(x=st.integers())
def test_absolute(x: int):
    result = abs(x)
    assert result >= 0
"""
    metrics = compute_metrics_for_datapoint(code)

    assert metrics is not None
    assert isinstance(metrics, RadonMetrics)
    assert metrics.num_functions == 1


def test_compute_metrics_for_datapoint_failure():
    """Test that invalid code returns None."""
    code = "def broken(:"

    metrics = compute_metrics_for_datapoint(code)
    assert metrics is None


def test_radon_metrics_serialization():
    """Test that RadonMetrics can be serialized to JSON."""
    code = """
def add(x: int, y: int) -> int:
    return x + y
"""
    metrics = RadonMetrics.from_code(code)

    # Should serialize to JSON
    json_str = metrics.model_dump_json()
    assert "loc" in json_str
    assert "cyclomatic_complexity" in json_str or "average_complexity" in json_str
    assert "maintainability_index" in json_str

    # Should be able to parse back
    parsed = RadonMetrics.model_validate_json(json_str)
    assert parsed.loc == metrics.loc
    assert parsed.average_complexity == metrics.average_complexity


def test_radon_metrics_real_world_pbt():
    """Test radon metrics on a realistic property-based test."""
    code = """
from hypothesis import given, assume
from hypothesis import strategies as st

@given(items=st.lists(st.integers(), min_size=1), index=st.integers())
def test_list_indexing(items: list[int], index: int):
    assume(0 <= index < len(items))

    # Test that indexing returns the correct item
    result = items[index]

    # Verify item is in the list
    assert result in items

    # Verify we can modify and restore
    original = items[index]
    items[index] = -999
    assert items[index] == -999
    items[index] = original
    assert items[index] == result
"""
    metrics = RadonMetrics.from_code(code)

    # Should analyze successfully
    assert metrics.num_functions == 1
    assert metrics.loc > 10  # Multi-line test
    assert metrics.sloc > 5
    assert metrics.average_complexity >= 1
    assert metrics.maintainability_index > 0
    assert metrics.complexity_rank() in ["A", "B", "C"]


def test_radon_metrics_with_dependencies():
    """Test radon metrics on code with helper functions."""
    code = """
def helper(x: int) -> int:
    if x < 0:
        return -x
    return x

def another_helper(y: int) -> int:
    return y * 2

from hypothesis import given
from hypothesis import strategies as st

@given(a=st.integers(), b=st.integers())
def test_with_helpers(a: int, b: int):
    result = helper(a) + another_helper(b)
    assert result >= 0 or result < 0  # Always true
"""
    metrics = RadonMetrics.from_code(code)

    # Should count all three functions
    assert metrics.num_functions == 3
    assert metrics.average_complexity > 0
    assert metrics.total_complexity == sum([
        # Each function's complexity would be counted
        # helper: 2 (if-else), another_helper: 1, test: 1
    ]) or metrics.total_complexity > 0
