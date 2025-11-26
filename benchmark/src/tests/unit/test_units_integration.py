"""Integration tests for the units module."""

from generate.scaffold.formalize.units.v0 import extract_unit_tests, generate_test_suite


def test_end_to_end_simple():
    """Test end-to-end extraction and generation."""
    pbt_code = """
X = [1, 2, 3]
assert double(X) == [2, 4, 6]
assert double([]) == []
"""

    suite = extract_unit_tests(pbt_code, func_name="double")
    assert suite is not None
    assert len(suite.exact_tests) == 2

    lean_code = generate_test_suite(suite)
    assert "import LSpec" in lean_code
    assert "double [1, 2, 3]" in lean_code
    assert "double []" in lean_code


def test_end_to_end_with_floats():
    """Test end-to-end with mixed exact and float tests."""
    pbt_code = """
assert sqrt_int(4) == 2
assert sqrt(2.0) == 1.41421356
"""

    suite = extract_unit_tests(pbt_code, func_name="sqrt_int")
    assert suite is not None

    lean_code = generate_test_suite(suite)
    assert "import LSpec" in lean_code


def test_end_to_end_no_tests():
    """Test when no tests can be extracted."""
    pbt_code = """
import hypothesis
@given(st.integers())
def test_something(x):
    assert f(x) == g(x)
"""

    suite = extract_unit_tests(pbt_code, func_name="f")
    assert suite is None


def test_end_to_end_with_loop():
    """Test end-to-end with loop unrolling."""
    pbt_code = """
for i in [0, 1, 2]:
    assert factorial(i) == [1, 1, 2][i]
"""

    suite = extract_unit_tests(pbt_code, func_name="factorial")
    assert suite is not None
    assert len(suite.exact_tests) == 3

    lean_code = generate_test_suite(suite)
    assert "factorial 0 = 1" in lean_code
    assert "factorial 1 = 1" in lean_code
    assert "factorial 2 = 2" in lean_code


def test_end_to_end_with_parametrize():
    """Test end-to-end with pytest.mark.parametrize."""
    pbt_code = """
import pytest

@pytest.mark.parametrize("x,y,expected", [
    (1, 2, 3),
    (10, 20, 30),
    (0, 0, 0),
])
def test_add(x, y, expected):
    assert add(x, y) == expected
"""

    suite = extract_unit_tests(pbt_code, func_name="add")
    assert suite is not None
    assert len(suite.exact_tests) == 3

    lean_code = generate_test_suite(suite)
    assert "import LSpec" in lean_code
    assert "add 1 2 = 3" in lean_code
    assert "add 10 20 = 30" in lean_code
    assert "add 0 0 = 0" in lean_code
