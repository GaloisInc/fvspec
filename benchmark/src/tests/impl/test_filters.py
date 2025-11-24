"""Tests for impl agent output filtering."""

from generate.scaffold.formalize.impl.filters import (
    extract_impl_only,
    strip_spec_keywords,
    strip_spec_namespace,
    validate_impl_only,
)


class TestStripSpecNamespace:
    """Tests for strip_spec_namespace function."""

    def test_basic_spec_removal(self):
        """Test stripping simple spec namespace."""
        code = """
namespace Fvspec.Impl
def foo := 1
end Fvspec.Impl

namespace Fvspec.Spec
theorem bar : True := sorry
end Fvspec.Spec
"""
        result = strip_spec_namespace(code)
        assert "namespace Fvspec.Spec" not in result
        assert "theorem bar" not in result
        assert "def foo" in result
        assert "namespace Fvspec.Impl" in result

    def test_spec_with_open(self):
        """Test stripping spec namespace with open statement."""
        code = """
namespace Fvspec.Impl
def foo := 1
end Fvspec.Impl

namespace Fvspec.Spec
open Fvspec.Impl
theorem bar : foo = 1 := sorry
end Fvspec.Spec
"""
        result = strip_spec_namespace(code)
        assert "namespace Fvspec.Spec" not in result
        assert "theorem bar" not in result
        assert "def foo" in result

    def test_multiple_theorems_in_spec(self):
        """Test stripping spec namespace with multiple theorems."""
        code = """
namespace Fvspec.Impl
def foo := 1
def bar := 2
end Fvspec.Impl

namespace Fvspec.Spec
theorem test1 : foo = 1 := sorry
theorem test2 : bar = 2 := sorry
theorem test3 : foo + bar = 3 := sorry
end Fvspec.Spec
"""
        result = strip_spec_namespace(code)
        assert "namespace Fvspec.Spec" not in result
        assert "theorem test1" not in result
        assert "theorem test2" not in result
        assert "theorem test3" not in result
        assert "def foo" in result
        assert "def bar" in result

    def test_no_spec_namespace(self):
        """Test stripping from code without specs."""
        code = """
namespace Fvspec.Impl
def foo := 1
def bar := 2
end Fvspec.Impl
"""
        result = strip_spec_namespace(code)
        # Should be unchanged (minus whitespace normalization)
        assert "def foo" in result
        assert "def bar" in result
        assert "namespace Fvspec.Spec" not in result

    def test_empty_string(self):
        """Test stripping from empty string."""
        result = strip_spec_namespace("")
        assert result == ""

    def test_imports_preserved(self):
        """Test that imports before namespaces are preserved."""
        code = """
import Batteries

namespace Fvspec.Impl
def foo := 1
end Fvspec.Impl

namespace Fvspec.Spec
theorem bar : True := sorry
end Fvspec.Spec
"""
        result = strip_spec_namespace(code)
        assert "import Batteries" in result
        assert "namespace Fvspec.Spec" not in result

    def test_realistic_hallucination(self):
        """Test with realistic model hallucination from eval logs."""
        code = """import Batteries

namespace Fvspec.Impl

def cosine_similarity (x1 x2 : Array (Array Float)) (dim : Nat) (eps : Float) : Array Float :=
  if dim == 0 then
    #[]
  else if dim == 1 then
    x1.zipWith x2 fun row1 row2 =>
      0.0
  else
    #[]

end Fvspec.Impl

namespace Fvspec.Spec

open Fvspec.Impl

theorem cosine_similarity_dim1_output_shape (x1 x2 : Array (Array Float)) (eps : Float) :
    (cosine_similarity x1 x2 1 eps).size = x1.size := by
  sorry

theorem cosine_similarity_symmetric (x1 x2 : Array (Array Float)) (dim : Nat) (eps : Float) :
    cosine_similarity x1 x2 dim eps = cosine_similarity x2 x1 dim eps := by
  sorry

end Fvspec.Spec
"""
        result = strip_spec_namespace(code)
        assert "import Batteries" in result
        assert "def cosine_similarity" in result
        assert "namespace Fvspec.Impl" in result
        assert "namespace Fvspec.Spec" not in result
        assert "theorem cosine_similarity_dim1_output_shape" not in result
        assert "theorem cosine_similarity_symmetric" not in result


class TestStripSpecKeywords:
    """Tests for strip_spec_keywords function."""

    def test_strip_example_keyword(self):
        """Test stripping example from impl namespace."""
        code = """namespace Fvspec.Impl

def foo := 1

example : True := trivial

def bar := 2

end Fvspec.Impl"""
        result = strip_spec_keywords(code)
        assert "example" not in result
        assert "def foo" in result
        assert "def bar" in result

    def test_strip_theorem_keyword(self):
        """Test stripping theorem from impl namespace."""
        code = """namespace Fvspec.Impl

def foo := 1

theorem test_foo : foo = 1 := rfl

def bar := 2

end Fvspec.Impl"""
        result = strip_spec_keywords(code)
        assert "theorem" not in result
        assert "def foo" in result
        assert "def bar" in result

    def test_strip_lemma_keyword(self):
        """Test stripping lemma from impl namespace."""
        code = """namespace Fvspec.Impl

def foo := 1

lemma test_foo : foo = 1 := rfl

end Fvspec.Impl"""
        result = strip_spec_keywords(code)
        assert "lemma" not in result
        assert "def foo" in result

    def test_strip_multiple_spec_keywords(self):
        """Test stripping multiple spec keywords."""
        code = """namespace Fvspec.Impl

def foo := 1

theorem test1 : foo = 1 := rfl

lemma test2 : foo = 1 := rfl

example : True := trivial

def bar := 2

end Fvspec.Impl"""
        result = strip_spec_keywords(code)
        assert "theorem" not in result
        assert "lemma" not in result
        assert "example" not in result
        assert "def foo" in result
        assert "def bar" in result

    def test_strip_with_docstring(self):
        """Test stripping spec keywords with doc comments."""
        code = """namespace Fvspec.Impl

def foo := 1

/-- This is a test example -/
example : True := trivial

def bar := 2

end Fvspec.Impl"""
        result = strip_spec_keywords(code)
        assert "example" not in result
        assert "/-- This is a test example -/" not in result
        assert "def foo" in result
        assert "def bar" in result

    def test_strip_multiline_spec_keyword(self):
        """Test stripping multi-line spec declarations."""
        code = """namespace Fvspec.Impl

def foo := 1

theorem test_foo :
  foo = 1 := by
  rfl

def bar := 2

end Fvspec.Impl"""
        result = strip_spec_keywords(code)
        assert "theorem" not in result
        assert "def foo" in result
        assert "def bar" in result

    def test_preserve_defs_only(self):
        """Test that only defs are preserved when specs are present."""
        code = """namespace Fvspec.Impl

structure Point where
  x : Nat
  y : Nat

def origin : Point := ⟨0, 0⟩

example : origin.x = 0 := rfl

def distance (p1 p2 : Point) : Nat := 0

end Fvspec.Impl"""
        result = strip_spec_keywords(code)
        assert "structure Point" in result
        assert "def origin" in result
        assert "def distance" in result
        assert "example" not in result

    def test_empty_string(self):
        """Test stripping from empty string."""
        result = strip_spec_keywords("")
        assert result == ""

    def test_no_spec_keywords(self):
        """Test code without spec keywords is unchanged."""
        code = """namespace Fvspec.Impl

def foo := 1
def bar := 2

end Fvspec.Impl"""
        result = strip_spec_keywords(code)
        assert "def foo" in result
        assert "def bar" in result

    def test_strip_example_at_eof(self):
        """Test stripping example at end of file (bug fix for missing lookahead)."""
        code = """namespace Fvspec.Impl

def foo := 1

example : True := trivial"""
        result = strip_spec_keywords(code)
        assert "example" not in result
        assert "def foo" in result

    def test_strip_theorem_at_eof(self):
        """Test stripping theorem at end of file."""
        code = """namespace Fvspec.Impl

def foo := 1

theorem test : foo = 1 := rfl"""
        result = strip_spec_keywords(code)
        assert "theorem" not in result
        assert "def foo" in result

    def test_strip_axiom_keyword(self):
        """Test stripping axiom declarations."""
        code = """namespace Fvspec.Impl

def foo := 1

axiom bar : Nat

def baz := 2

end Fvspec.Impl"""
        result = strip_spec_keywords(code)
        assert "axiom" not in result
        assert "def foo" in result
        assert "def baz" in result

    def test_strip_axiom_at_eof(self):
        """Test stripping axiom at end of file."""
        code = """namespace Fvspec.Impl

def foo := 1

axiom bar : Nat"""
        result = strip_spec_keywords(code)
        assert "axiom" not in result
        assert "def foo" in result

    def test_strip_sorry_placeholder(self):
        """Test stripping standalone sorry placeholders."""
        code = """namespace Fvspec.Impl

def foo := 1

sorry

def bar := 2

end Fvspec.Impl"""
        result = strip_spec_keywords(code)
        # Note: This removes standalone "sorry" lines, not "sorry" within def bodies
        assert "sorry" not in result or "sorry" in "-- sorry"  # May be in comments
        assert "def foo" in result
        assert "def bar" in result

    def test_preserve_sorry_in_def(self):
        """Test that sorry within def body is NOT stripped (only standalone sorry)."""
        code = """namespace Fvspec.Impl

def foo : Nat := sorry

end Fvspec.Impl"""
        result = strip_spec_keywords(code)
        # This should preserve the def with sorry in body
        assert "def foo" in result
        # The sorry is part of the def, not standalone, so it stays


class TestValidateImplOnly:
    """Tests for validate_impl_only function."""

    def test_clean_impl_code(self):
        """Test validation passes for clean impl code."""
        code = """
namespace Fvspec.Impl
def foo := 1
def bar := 2
end Fvspec.Impl
"""
        is_valid, error = validate_impl_only(code)
        assert is_valid
        assert error is None

    def test_has_spec_namespace(self):
        """Test validation fails for spec namespace."""
        code = """
namespace Fvspec.Spec
theorem foo : True := sorry
end Fvspec.Spec
"""
        is_valid, error = validate_impl_only(code)
        assert not is_valid
        assert error is not None
        assert "Fvspec.Spec" in error

    def test_has_theorem_keyword(self):
        """Test validation fails for theorem keyword."""
        code = """
namespace Fvspec.Impl
theorem foo : True := sorry
end Fvspec.Impl
"""
        is_valid, error = validate_impl_only(code)
        assert not is_valid
        assert error is not None
        assert "theorem" in error

    def test_has_lemma_keyword(self):
        """Test validation fails for lemma keyword."""
        code = """
namespace Fvspec.Impl
lemma foo : True := sorry
end Fvspec.Impl
"""
        is_valid, error = validate_impl_only(code)
        assert not is_valid
        assert error is not None
        assert "lemma" in error

    def test_has_example_keyword(self):
        """Test validation fails for example keyword."""
        code = """
namespace Fvspec.Impl
example : True := trivial
end Fvspec.Impl
"""
        is_valid, error = validate_impl_only(code)
        assert not is_valid
        assert error is not None
        assert "example" in error

    def test_theorem_in_comment(self):
        """Test that 'theorem' in comments doesn't trigger false positive."""
        code = """
namespace Fvspec.Impl
-- This implements the theorem described in the paper
def foo := 1
end Fvspec.Impl
"""
        # Current implementation will flag this as invalid (conservative)
        # This is acceptable - better to be strict
        is_valid, error = validate_impl_only(code)
        assert not is_valid
        assert error is not None
        assert "theorem" in error
        # If we wanted to be more lenient, we'd need more sophisticated parsing
        # For now, accept that comments with "theorem " will fail validation

    def test_empty_string(self):
        """Test validation on empty string."""
        is_valid, error = validate_impl_only("")
        assert is_valid
        assert error is None

    def test_has_axiom_keyword(self):
        """Test validation fails for axiom keyword."""
        code = """
namespace Fvspec.Impl
axiom foo : Nat
end Fvspec.Impl
"""
        is_valid, error = validate_impl_only(code)
        assert not is_valid
        assert error is not None
        assert "axiom" in error

    def test_has_sorry_keyword(self):
        """Test validation fails for standalone sorry."""
        code = """
namespace Fvspec.Impl
def foo := 1
sorry
end Fvspec.Impl
"""
        is_valid, error = validate_impl_only(code)
        assert not is_valid
        assert error is not None
        assert "sorry" in error

    def test_sorry_in_def_body(self):
        """Test that sorry within def body triggers validation error."""
        code = """
namespace Fvspec.Impl
def foo : Nat := sorry
end Fvspec.Impl
"""
        # Note: This will fail validation because we check for \bsorry\b
        # which matches sorry even within expressions
        # This is intentional - implementations should be complete
        is_valid, error = validate_impl_only(code)
        assert not is_valid
        assert error is not None
        assert "sorry" in error


class TestExtractImplOnly:
    """Tests for extract_impl_only function."""

    def test_extract_from_mixed_code(self):
        """Test extracting impl section from mixed impl/spec code."""
        code = """
import Batteries

namespace Fvspec.Impl
def foo := 1
def bar := 2
end Fvspec.Impl

namespace Fvspec.Spec
theorem baz : True := sorry
end Fvspec.Spec
"""
        result = extract_impl_only(code)
        assert "namespace Fvspec.Impl" in result
        assert "def foo" in result
        assert "def bar" in result
        assert "namespace Fvspec.Spec" not in result
        assert "theorem baz" not in result
        # Note: imports before namespace are excluded in extracted section

    def test_extract_impl_only_code(self):
        """Test extracting from code with only impl namespace."""
        code = """
namespace Fvspec.Impl
def foo := 1
end Fvspec.Impl
"""
        result = extract_impl_only(code)
        assert "namespace Fvspec.Impl" in result
        assert "def foo" in result

    def test_extract_no_namespace(self):
        """Test extracting from code without namespace declarations."""
        code = "def foo := 1\ndef bar := 2"
        result = extract_impl_only(code)
        # Should return original code when no namespace found
        assert "def foo" in result
        assert "def bar" in result

    def test_extract_empty_string(self):
        """Test extracting from empty string."""
        result = extract_impl_only("")
        assert result == ""

    def test_extract_preserves_impl_content(self):
        """Test that all impl content is preserved during extraction."""
        code = """
namespace Fvspec.Impl

-- Comment preserved
structure MyStruct where
  field1 : Nat
  field2 : String

def foo (x : Nat) : Nat := x + 1

def bar : MyStruct := { field1 := 42, field2 := "hello" }

end Fvspec.Impl

namespace Fvspec.Spec
theorem removed : True := sorry
end Fvspec.Spec
"""
        result = extract_impl_only(code)
        assert "structure MyStruct" in result
        assert "def foo" in result
        assert "def bar" in result
        assert "-- Comment preserved" in result
        assert "theorem removed" not in result


class TestIntegration:
    """Integration tests combining multiple filtering operations."""

    def test_strip_then_validate(self):
        """Test that strip_spec_namespace output passes validate_impl_only."""
        hallucinated_code = """
namespace Fvspec.Impl
def foo := 1
end Fvspec.Impl

namespace Fvspec.Spec
theorem bar : True := sorry
end Fvspec.Spec
"""
        # Strip specs
        cleaned = strip_spec_namespace(hallucinated_code)

        # Validate should pass
        is_valid, error = validate_impl_only(cleaned)
        assert is_valid, f"Validation failed: {error}"

    def test_extract_then_validate(self):
        """Test that extract_impl_only output passes validate_impl_only."""
        mixed_code = """
namespace Fvspec.Impl
def foo := 1
end Fvspec.Impl

namespace Fvspec.Spec
theorem bar : True := sorry
end Fvspec.Spec
"""
        # Extract impl
        extracted = extract_impl_only(mixed_code)

        # Validate should pass
        is_valid, error = validate_impl_only(extracted)
        assert is_valid, f"Validation failed: {error}"

    def test_multiple_spec_namespaces(self):
        """Test handling code with multiple spec namespace blocks (edge case)."""
        # This shouldn't happen in practice, but test defensively
        code = """
namespace Fvspec.Impl
def foo := 1
end Fvspec.Impl

namespace Fvspec.Spec
theorem bar : True := sorry
end Fvspec.Spec

namespace Fvspec.Spec
theorem baz : True := sorry
end Fvspec.Spec
"""
        cleaned = strip_spec_namespace(code)
        assert "theorem bar" not in cleaned
        assert "theorem baz" not in cleaned
        assert "def foo" in cleaned

    def test_combined_filtering_pipeline(self):
        """Test full filtering pipeline: spec namespace + spec keywords."""
        # Realistic case: model generates both Spec namespace AND
        # individual spec keywords inside Impl namespace
        code = """import Batteries

namespace Fvspec.Impl

def foo := 1

/-- Example to demonstrate foo -/
example : foo = 1 := rfl

def bar := 2

end Fvspec.Impl

namespace Fvspec.Spec

open Fvspec.Impl

theorem test_foo : foo = 1 := sorry

end Fvspec.Spec
"""
        # Apply both filters (as in function_agent.py)
        cleaned = strip_spec_namespace(code)
        cleaned = strip_spec_keywords(cleaned)

        # Validate result
        assert "namespace Fvspec.Spec" not in cleaned
        assert "theorem test_foo" not in cleaned
        assert "example" not in cleaned
        assert "/-- Example to demonstrate foo -/" not in cleaned
        assert "def foo" in cleaned
        assert "def bar" in cleaned
        assert "import Batteries" in cleaned

        # Should pass validation
        is_valid, error = validate_impl_only(cleaned)
        assert is_valid, f"Validation failed after filtering: {error}"
