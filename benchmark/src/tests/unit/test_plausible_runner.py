"""Tests for plausible_runner module."""

from generate.scaffold.formalize.plausible_runner import _check_testability


class TestCheckTestability:
    """Test the testability checking logic."""

    def test_existential_quantifier_detected(self) -> None:
        """Test that existential quantifiers are detected."""
        spec_with_existential = """
import Plausible

theorem foo (p q : Int) (h : q ≠ 0) :
  ∃ k : Int, p = q * k + mod p q := sorry
"""
        is_testable, reasons = _check_testability(spec_with_existential)
        assert not is_testable
        assert len(reasons) == 1
        assert "existential quantifiers" in reasons[0]
        assert "∃" in reasons[0]

    def test_existential_exists_keyword_detected(self) -> None:
        """Test that 'Exists' keyword is detected."""
        spec_with_exists = """
import Plausible

theorem foo (p q : Int) (h : q ≠ 0) :
  Exists (fun k => p = q * k + mod p q) := sorry
"""
        is_testable, reasons = _check_testability(spec_with_exists)
        assert not is_testable
        assert len(reasons) == 1
        assert "existential quantifiers" in reasons[0]

    def test_opaque_value_type_detected(self) -> None:
        """Test that opaque Value type without Arbitrary is detected."""
        spec_with_value = """
import Plausible

def foo (x : Value) : Bool := sorry

theorem bar (x : Value) : foo x = true := sorry
"""
        is_testable, reasons = _check_testability(spec_with_value)
        assert not is_testable
        assert any("Value" in reason and "Arbitrary" in reason for reason in reasons)

    def test_opaque_qtensor_type_detected(self) -> None:
        """Test that opaque QTensor type without Arbitrary is detected."""
        spec_with_qtensor = """
import Plausible

structure QTensor where
  data : List Int
  scale : Float

theorem quantize_preserves_scale (qx : QTensor) :
  qx.scale > 0 := sorry
"""
        is_testable, reasons = _check_testability(spec_with_qtensor)
        assert not is_testable
        assert any("QTensor" in reason and "Arbitrary" in reason for reason in reasons)

    def test_type_with_deriving_arbitrary_is_testable(self) -> None:
        """Test that types with deriving Arbitrary are considered testable."""
        spec_with_arbitrary = """
import Plausible

inductive Device where
  | cpu : Device
  | cuda : Device
  deriving Repr, DecidableEq, Arbitrary

theorem device_eq_decidable (d1 d2 : Device) :
  (d1 = d2) ∨ (d1 ≠ d2) := sorry
"""
        is_testable, reasons = _check_testability(spec_with_arbitrary)
        # Should be testable - Device has Arbitrary
        assert is_testable
        assert len(reasons) == 0

    def test_simple_nat_theorem_is_testable(self) -> None:
        """Test that theorems with only builtin types are testable."""
        spec_simple = """
import Plausible

def mod (p q : Int) : Int := p - (Int.ediv p q) * q

theorem mod_bounded (p q : Int) (h : q ≠ 0) :
  (mod p q).natAbs < q.natAbs := sorry
"""
        is_testable, reasons = _check_testability(spec_simple)
        assert is_testable
        assert len(reasons) == 0

    def test_multiple_issues_detected(self) -> None:
        """Test that multiple testability issues are all reported."""
        spec_multiple_issues = """
import Plausible

structure QTensor where
  data : List Int

def foo (x : Value) : Bool := sorry

theorem has_existential (q : QTensor) :
  ∃ n : Nat, q.data.length = n := sorry

theorem uses_value (v : Value) :
  foo v = true := sorry
"""
        is_testable, reasons = _check_testability(spec_multiple_issues)
        assert not is_testable
        # Should detect: existential, QTensor without Arbitrary, Value without Arbitrary
        assert len(reasons) >= 2
        assert any("existential" in reason.lower() for reason in reasons)
        # At least one of the opaque types should be detected
        assert any("Value" in reason or "QTensor" in reason for reason in reasons)

    def test_empty_spec_is_testable(self) -> None:
        """Test that empty or minimal specs are considered testable."""
        spec_empty = """
import Plausible
"""
        is_testable, reasons = _check_testability(spec_empty)
        assert is_testable
        assert len(reasons) == 0

    def test_tensor_metadata_not_flagged(self) -> None:
        """Test that TensorMetadata is not flagged as Tensor."""
        spec_with_metadata = """
import Plausible

structure TensorMetadata where
  shape : List Nat
  deriving Repr

theorem foo (t : TensorMetadata) :
  t.shape.length > 0 := sorry
"""
        is_testable, reasons = _check_testability(spec_with_metadata)
        # TensorMetadata is not in our list of known opaque types
        # Our design only flags specific known types (Value, QTensor, FTensor, Tensor)
        # TensorMetadata should be testable (not flagged) even without Arbitrary
        # because it's not one of the common opaque types we're checking for
        assert is_testable
        assert len(reasons) == 0
