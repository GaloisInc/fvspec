"""Pytest tests for function_discovery module.

These tests cover tree-sitter parsing, stdlib detection, and other
database-independent functionality.
"""

from generate.scaffold.dataset.function_discovery import (
    extract_test_calls,
    identify_primary_call,
    infer_target_from_test_class,
    is_stdlib,
    parse_test_class,
)


class TestParseTestClass:
    """Test parsing test class inheritance."""

    def test_unittest_test_case(self):
        """Test parsing unittest.TestCase subclass."""
        code = """
import unittest

class TestMyClass(unittest.TestCase):
    def test_something(self):
        pass
"""
        result = parse_test_class(code)
        assert result is not None
        class_name, parent = result
        assert class_name == "TestMyClass"
        assert parent == "unittest.TestCase"

    def test_pytest_style(self):
        """Test that pytest-style tests (no class) return None."""
        code = """
def test_something():
    assert True
"""
        result = parse_test_class(code)
        assert result is None

    def test_nested_class(self):
        """Test parsing nested test class."""
        code = """
class Outer:
    class TestInner(object):
        pass
"""
        result = parse_test_class(code)
        assert result is not None
        class_name, parent = result
        assert class_name == "Outer"  # Gets first class


class TestInferTargetFromTestClass:
    """Test inferring target class from test class name."""

    def test_test_prefix(self):
        """Test removing 'Test' prefix."""
        assert infer_target_from_test_class("TestMyClass", None) == "MyClass"
        assert infer_target_from_test_class("TestFooBar", None) == "FooBar"

    def test_test_suffix(self):
        """Test removing 'Test' suffix."""
        assert infer_target_from_test_class("MyClassTest", None) == "MyClass"
        assert infer_target_from_test_class("FooBarTest", None) == "FooBar"

    def test_no_test_pattern(self):
        """Test that non-test class names return None."""
        assert infer_target_from_test_class("MyClass", None) is None
        assert infer_target_from_test_class("FooBar", None) is None


class TestExtractTestCalls:
    """Test extracting function calls from test code."""

    def test_simple_function_call(self):
        """Test extracting simple function call."""
        code = """
def test_foo():
    result = my_function(42)
"""
        calls = extract_test_calls(code)
        assert len(calls) > 0
        func_names = [name for name, _ in calls]
        assert "my_function" in func_names

    def test_method_call(self):
        """Test extracting method call."""
        code = """
def test_foo():
    obj.method(42)
"""
        calls = extract_test_calls(code)
        assert len(calls) > 0
        func_names = [name for name, _ in calls]
        assert "obj.method" in func_names

    def test_nested_attribute(self):
        """Test extracting nested attribute call."""
        code = """
def test_foo():
    hashutil.md5_file_b64('test.bin')
"""
        calls = extract_test_calls(code)
        assert len(calls) > 0
        func_names = [name for name, _ in calls]
        assert "hashutil.md5_file_b64" in func_names


class TestIdentifyPrimaryCall:
    """Test identifying primary function call from test."""

    def test_filters_assertions(self):
        """Test that assertion calls are filtered out."""
        calls = [
            ("assertEqual", "method"),
            ("my_function", "direct"),
            ("assertTrue", "method"),
        ]
        primary = identify_primary_call(calls)
        assert primary == "my_function"

    def test_filters_hypothesis(self):
        """Test that Hypothesis strategies are filtered out."""
        calls = [
            ("st.integers", "method"),
            ("st.floats", "method"),
            ("my_function", "direct"),
        ]
        primary = identify_primary_call(calls)
        assert primary == "my_function"

    def test_most_common_wins(self):
        """Test that most common non-infrastructure call wins."""
        calls = [
            ("foo", "direct"),
            ("bar", "direct"),
            ("bar", "direct"),
            ("assert", "direct"),
        ]
        primary = identify_primary_call(calls)
        assert primary == "bar"

    def test_empty_after_filtering(self):
        """Test returns None when all calls are infrastructure."""
        calls = [
            ("assertEqual", "method"),
            ("st.integers", "method"),
            ("assertTrue", "method"),
        ]
        primary = identify_primary_call(calls)
        assert primary is None


class TestIsStdlib:
    """Test stdlib detection."""

    def test_builtins(self):
        """Test that builtins are detected."""
        assert is_stdlib("open") is True
        assert is_stdlib("len") is True
        assert is_stdlib("print") is True
        assert is_stdlib("int") is True

    def test_stdlib_modules(self):
        """Test that stdlib module functions are detected."""
        assert is_stdlib("base64.b64encode") is True
        assert is_stdlib("hashlib.md5") is True
        assert is_stdlib("os.path.join") is True
        assert is_stdlib("json.loads") is True

    def test_third_party_axiomized(self):
        """Test that axiomized third-party modules are detected."""
        assert is_stdlib("numpy.array") is True
        assert is_stdlib("torch.tensor") is True
        assert is_stdlib("pandas.DataFrame") is True

    def test_custom_functions(self):
        """Test that custom functions are NOT detected as stdlib."""
        assert is_stdlib("my_function") is False
        assert is_stdlib("hashutil.md5_file") is False
        assert is_stdlib("MyClass.method") is False

    def test_module_aliases(self):
        """Test handling of module aliases."""
        # Note: "np" is not in STDLIB_MODULES, so np.array returns False
        # This is a known limitation - aliases need explicit handling
        assert (
            is_stdlib("np.array") is False
        )  # Expected behavior with current implementation
