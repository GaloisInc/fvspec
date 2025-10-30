"""Tests for LSpec code generation."""

from generate.scaffold.units.lspec_generator import (
    generate_float_eval,
    generate_lean_test,
    generate_test_suite,
)
from generate.scaffold.units.models import TestCase, TestSuite


def test_generate_lean_test_simple():
    """Test generating a simple LSpec test."""
    test = TestCase(
        func_name="double",
        inputs=["5"],
        expected_output="10",
        test_name="double of 5",
    )

    result = generate_lean_test(test)
    assert result == 'test "double of 5" (double 5 = 10)'


def test_generate_lean_test_multiple_inputs():
    """Test generating test with multiple inputs."""
    test = TestCase(
        func_name="add",
        inputs=["2", "3"],
        expected_output="5",
        test_name="add two numbers",
    )

    result = generate_lean_test(test)
    assert result == 'test "add two numbers" (add 2 3 = 5)'


def test_generate_lean_test_list():
    """Test generating test with list."""
    test = TestCase(
        func_name="reverse",
        inputs=["[1, 2, 3]"],
        expected_output="[3, 2, 1]",
        test_name="reverse list",
    )

    result = generate_lean_test(test)
    assert result == 'test "reverse list" (reverse [1, 2, 3] = [3, 2, 1])'


def test_generate_float_eval():
    """Test generating float eval with comment."""
    test = TestCase(
        func_name="sqrt",
        inputs=["2.0"],
        expected_output="1.41421356",
        is_float=True,
        rtol=1e-5,
        atol=1e-8,
        test_name="sqrt of 2",
    )

    result = generate_float_eval(test)
    assert "-- Expected: ~1.41421356" in result
    assert "rtol=1e-05" in result
    assert "atol=1e-08" in result
    assert "#eval sqrt 2.0" in result


def test_generate_test_suite_exact_only():
    """Test generating suite with only exact tests."""
    suite = TestSuite(
        exact_tests=[
            TestCase(
                func_name="double",
                inputs=["1"],
                expected_output="2",
                test_name="test1",
            ),
            TestCase(
                func_name="double",
                inputs=["2"],
                expected_output="4",
                test_name="test2",
            ),
        ],
        float_tests=[],
        extraction_stats={"method": "ast", "count": 2},
    )

    result = generate_test_suite(suite)

    # Check structure
    assert "import LSpec" in result
    assert "def tests : TestSeq :=" in result
    assert 'test "test1" (double 1 = 2) $' in result
    assert 'test "test2" (double 2 = 4)' in result
    assert "#lspec tests" in result

    # Make sure second test doesn't have $ (it's the last one)
    lines = result.split("\n")
    test2_line = [l for l in lines if "test2" in l][0]
    assert not test2_line.endswith("$")


def test_generate_test_suite_float_only():
    """Test generating suite with only float tests."""
    suite = TestSuite(
        exact_tests=[],
        float_tests=[
            TestCase(
                func_name="sqrt",
                inputs=["2.0"],
                expected_output="1.41421356",
                is_float=True,
                test_name="sqrt test",
            )
        ],
        extraction_stats={"method": "ast", "count": 1},
    )

    result = generate_test_suite(suite)

    assert "import LSpec" in result
    assert "-- Float tests (external validation)" in result
    assert "-- Expected: ~1.41421356" in result
    assert "#eval sqrt 2.0" in result


def test_generate_test_suite_mixed():
    """Test generating suite with both exact and float tests."""
    suite = TestSuite(
        exact_tests=[
            TestCase(
                func_name="f",
                inputs=["1"],
                expected_output="2",
                test_name="exact test",
            )
        ],
        float_tests=[
            TestCase(
                func_name="f",
                inputs=["1.5"],
                expected_output="2.5",
                is_float=True,
                test_name="float test",
            )
        ],
        extraction_stats={"method": "ast", "count": 2},
    )

    result = generate_test_suite(suite)

    # Should have both sections
    assert "def tests : TestSeq :=" in result
    assert "#lspec tests" in result
    assert "-- Float tests (external validation)" in result
    assert "#eval" in result


def test_generate_test_suite_single_test():
    """Test generating suite with single test (no $ separator)."""
    suite = TestSuite(
        exact_tests=[
            TestCase(
                func_name="id",
                inputs=["5"],
                expected_output="5",
                test_name="identity",
            )
        ],
        float_tests=[],
        extraction_stats={"method": "ast", "count": 1},
    )

    result = generate_test_suite(suite)

    # Single test should not have $
    assert 'test "identity" (id 5 = 5)' in result
    assert "$" not in result
