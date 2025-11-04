"""Tests for spec validation utilities."""

from generate.scaffold.formalize_spec.validator import (
    extract_signatures,
    validate_spec_output,
)


class TestValidateSpecOutput:
    """Tests for validate_spec_output function."""

    def test_valid_spec_with_sorry(self):
        """Test validation of valid spec with sorry (expected!)."""
        lean_code = """
theorem inc_property (x : Nat) : inc x = x + 1 := by
  sorry
"""
        diagnostics = ""  # No errors

        result = validate_spec_output(lean_code, diagnostics)

        assert result.valid
        assert result.compiles
        assert result.has_statements
        assert result.has_sorry  # This is GOOD for specs!
        assert len(result.errors) == 0

    def test_valid_spec_without_sorry(self):
        """Test validation of valid spec without sorry (unusual but OK)."""
        lean_code = """
def inc (x : Nat) : Nat := x + 1

theorem inc_property (x : Nat) : inc x = x + 1 := by
  rfl
"""
        diagnostics = ""

        result = validate_spec_output(lean_code, diagnostics)

        assert result.valid
        assert result.compiles
        assert result.has_statements
        assert not result.has_sorry  # No sorry used
        assert len(result.errors) == 0

    def test_invalid_spec_compile_error(self):
        """Test validation when spec has type errors."""
        lean_code = """
theorem foo (x : Nat) : x = "string" := by
  sorry
"""
        diagnostics = """
error: type mismatch
  "string"
has type
  String : Type
but is expected to have type
  Nat : Type
"""

        result = validate_spec_output(lean_code, diagnostics)

        assert not result.valid
        assert not result.compiles
        assert result.has_statements
        assert result.has_sorry
        assert "type errors" in result.errors[0]

    def test_invalid_spec_no_statements(self):
        """Test validation when spec has no theorem statements."""
        lean_code = """
-- Just comments, no actual statements
"""
        diagnostics = ""

        result = validate_spec_output(lean_code, diagnostics)

        assert not result.valid
        assert result.compiles  # No errors, but...
        assert not result.has_statements  # ...no statements either
        assert not result.has_sorry
        assert "No theorem/def statements" in result.errors[0]

    def test_invalid_spec_both_errors(self):
        """Test validation with both compile errors and no statements."""
        lean_code = """
-- Empty file with syntax error mentioned in diagnostics
"""
        diagnostics = "error: unexpected token"

        result = validate_spec_output(lean_code, diagnostics)

        assert not result.valid
        assert not result.compiles
        assert not result.has_statements
        assert len(result.errors) == 2

    def test_spec_with_lemma(self):
        """Test that lemmas are recognized as statements."""
        lean_code = """
lemma foo_lemma : True := by sorry
"""
        diagnostics = ""

        result = validate_spec_output(lean_code, diagnostics)

        assert result.valid
        assert result.has_statements

    def test_spec_with_axiom(self):
        """Test that axioms are recognized as statements."""
        lean_code = """
axiom foo : Nat → Bool
"""
        diagnostics = ""

        result = validate_spec_output(lean_code, diagnostics)

        assert result.valid
        assert result.has_statements

    def test_diagnostics_case_insensitive(self):
        """Test that error detection is case-insensitive."""
        lean_code = "theorem foo : True := sorry"
        diagnostics = "Error: something went wrong"  # Capital E

        result = validate_spec_output(lean_code, diagnostics)

        assert not result.compiles


class TestExtractSignatures:
    """Tests for extract_signatures function."""

    def test_extract_simple_def(self):
        """Test extracting a simple function definition."""
        impl = """
def inc (x : Nat) : Nat := x + 1
"""

        sigs = extract_signatures(impl)

        assert "inc" in sigs
        assert "def inc" in sigs["inc"]
        assert "(x : Nat) : Nat" in sigs["inc"]

    def test_extract_theorem(self):
        """Test extracting a theorem signature."""
        impl = """
theorem inc_property (x : Nat) : inc x = x + 1 := by
  rfl
"""

        sigs = extract_signatures(impl)

        assert "inc_property" in sigs
        assert "theorem inc_property" in sigs["inc_property"]
        assert "(x : Nat)" in sigs["inc_property"]

    def test_extract_multiple_signatures(self):
        """Test extracting multiple function signatures."""
        impl = """
def foo (x : Nat) : Nat := x + 1

def bar (x y : Nat) : Bool := x < y

theorem baz_property : True := trivial
"""

        sigs = extract_signatures(impl)

        assert len(sigs) == 3
        assert "foo" in sigs
        assert "bar" in sigs
        assert "baz_property" in sigs
        assert "Nat" in sigs["foo"]
        assert "Bool" in sigs["bar"]

    def test_extract_structure(self):
        """Test extracting a structure signature."""
        impl = """
structure Point where
  x : Nat
  y : Nat
"""

        sigs = extract_signatures(impl)

        assert "Point" in sigs
        assert "structure Point" in sigs["Point"]

    def test_extract_inductive(self):
        """Test extracting an inductive type signature."""
        impl = """
inductive Color where
  | Red
  | Green
  | Blue
"""

        sigs = extract_signatures(impl)

        assert "Color" in sigs
        assert "inductive Color" in sigs["Color"]

    def test_extract_with_complex_types(self):
        """Test extracting signatures with complex type annotations."""
        impl = """
def process (xs : List Nat) (f : Nat → Nat) : List Nat :=
  xs.map f
"""

        sigs = extract_signatures(impl)

        assert "process" in sigs
        assert "List Nat" in sigs["process"]
        assert "Nat → Nat" in sigs["process"]

    def test_extract_empty_file(self):
        """Test extracting from empty file."""
        impl = ""

        sigs = extract_signatures(impl)

        assert len(sigs) == 0

    def test_extract_with_comments(self):
        """Test extracting signatures ignores comments."""
        impl = """
-- This is a comment
def foo (x : Nat) : Nat := x + 1
-- Another comment
def bar : Bool := true
"""

        sigs = extract_signatures(impl)

        assert len(sigs) == 2
        assert "foo" in sigs
        assert "bar" in sigs

    def test_extract_class(self):
        """Test extracting a typeclass signature."""
        impl = """
class Monoid (α : Type) where
  empty : α
  append : α → α → α
"""

        sigs = extract_signatures(impl)

        assert "Monoid" in sigs
        assert "class Monoid" in sigs["Monoid"]

    def test_extract_lemma(self):
        """Test extracting a lemma signature."""
        impl = """
lemma add_comm (a b : Nat) : a + b = b + a := by
  sorry
"""

        sigs = extract_signatures(impl)

        assert "add_comm" in sigs
        assert "lemma add_comm" in sigs["add_comm"]
        assert "(a b : Nat)" in sigs["add_comm"]

    def test_extract_multiline_signature(self):
        """Test extracting a signature that spans multiple lines."""
        impl = """
def complex_function
  (x : Nat)
  (y : Bool)
  : Nat × Bool :=
  (x, y)
"""

        sigs = extract_signatures(impl)

        # Should capture the function name at least
        assert "complex_function" in sigs
