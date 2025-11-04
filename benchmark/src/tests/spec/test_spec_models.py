"""Tests for spec generation models."""

import pytest
from pydantic import ValidationError

from generate.scaffold.formalize.spec.models import (
    SpecPayload,
    SpecResult,
    SpecValidation,
)


class TestSpecPayload:
    """Tests for SpecPayload model."""

    def test_spec_payload_creation(self):
        """Test creating a spec payload with all fields."""
        payload = SpecPayload(
            pbt_code="def test_inc(x): assert inc(x) == x + 1",
            pbt_name="test_inc",
            impl_signatures={"inc": "def inc (x : Nat) : Nat"},
            function_name="inc",
            variant="functional",
        )

        assert payload.pbt_code == "def test_inc(x): assert inc(x) == x + 1"
        assert payload.pbt_name == "test_inc"
        assert "inc" in payload.impl_signatures
        assert payload.function_name == "inc"
        assert payload.variant == "functional"

    def test_spec_payload_immutable(self):
        """Test that SpecPayload is immutable (frozen)."""
        payload = SpecPayload(
            pbt_code="test",
            pbt_name="test_foo",
            function_name="foo",
            variant="functional",
        )

        with pytest.raises(ValidationError):
            payload.pbt_code = "modified"  # type: ignore

    def test_spec_payload_default_impl_signatures(self):
        """Test that impl_signatures defaults to empty dict."""
        payload = SpecPayload(
            pbt_code="test",
            pbt_name="test_foo",
            function_name="foo",
            variant="functional",
        )

        assert payload.impl_signatures == {}

    def test_spec_payload_serialization(self):
        """Test payload can be serialized and deserialized."""
        payload = SpecPayload(
            pbt_code="def test_inc(x): pass",
            pbt_name="test_inc",
            impl_signatures={"inc": "def inc (x : Nat) : Nat"},
            function_name="inc",
            variant="mvcgen",
        )

        # Serialize
        json_str = payload.model_dump_json()
        assert "test_inc" in json_str
        assert "mvcgen" in json_str

        # Deserialize
        restored = SpecPayload.model_validate_json(json_str)
        assert restored.pbt_name == payload.pbt_name
        assert restored.variant == payload.variant
        assert restored.impl_signatures == payload.impl_signatures


class TestSpecValidation:
    """Tests for SpecValidation model."""

    def test_valid_spec(self):
        """Test validation of a valid spec (compiles + has statements)."""
        validation = SpecValidation(
            compiles=True,
            has_statements=True,
            has_sorry=True,  # This is GOOD for specs!
            valid=True,
            errors=[],
        )

        assert validation.compiles
        assert validation.has_statements
        assert validation.has_sorry  # Expected for theorem statements
        assert validation.valid
        assert len(validation.errors) == 0

    def test_invalid_spec_no_statements(self):
        """Test validation when spec has no statements."""
        validation = SpecValidation(
            compiles=True,
            has_statements=False,
            has_sorry=False,
            valid=False,
            errors=["No theorem/def statements found"],
        )

        assert validation.compiles
        assert not validation.has_statements
        assert not validation.valid
        assert len(validation.errors) == 1

    def test_invalid_spec_compile_error(self):
        """Test validation when spec doesn't compile."""
        validation = SpecValidation(
            compiles=False,
            has_statements=True,
            has_sorry=True,
            valid=False,
            errors=["Type error in theorem statement"],
        )

        assert not validation.compiles
        assert validation.has_statements
        assert not validation.valid
        assert len(validation.errors) == 1

    def test_spec_validation_immutable(self):
        """Test that SpecValidation is immutable."""
        validation = SpecValidation(
            compiles=True, has_statements=True, has_sorry=True, valid=True
        )

        with pytest.raises(ValidationError):
            validation.compiles = False  # type: ignore


class TestSpecResult:
    """Tests for SpecResult model."""

    def test_successful_result(self):
        """Test creating a successful spec result."""
        result = SpecResult(
            success=True,
            lean_code="theorem foo : True := by sorry",
            compiles=True,
            has_sorry=True,
            has_statements=True,
            attempts=3,
            tool_calls=5,
        )

        assert result.success
        assert result.lean_code is not None
        assert result.compiles
        assert result.has_sorry  # Expected for specs
        assert result.has_statements
        assert result.attempts == 3
        assert result.tool_calls == 5
        assert result.error is None

    def test_failed_result(self):
        """Test creating a failed spec result."""
        result = SpecResult(
            success=False,
            lean_code=None,
            compiles=False,
            has_sorry=False,
            has_statements=False,
            attempts=16,
            tool_calls=30,
            error="Max attempts reached, code still has errors",
        )

        assert not result.success
        assert result.lean_code is None
        assert not result.compiles
        assert result.attempts == 16
        assert result.error is not None

    def test_result_default_values(self):
        """Test that SpecResult has sensible defaults."""
        result = SpecResult(success=False)

        assert not result.success
        assert result.lean_code is None
        assert not result.compiles
        assert not result.has_sorry
        assert not result.has_statements
        assert result.attempts == 0
        assert result.tool_calls == 0
        assert result.error is None

    def test_result_prompt_dict(self):
        """Test converting result to dict for template rendering."""
        result = SpecResult(
            success=True,
            lean_code="theorem foo : True := sorry",
            compiles=True,
            has_sorry=True,
            has_statements=True,
            attempts=2,
            tool_calls=4,
        )

        prompt_dict = result.prompt_dict()

        assert prompt_dict["success"] is True
        assert "theorem foo" in prompt_dict["lean_code"]  # type: ignore
        assert prompt_dict["compiles"] is True
        assert prompt_dict["has_sorry"] is True
        assert prompt_dict["attempts"] == 2
        assert prompt_dict["tool_calls"] == 4

    def test_result_serialization(self):
        """Test result can be serialized and deserialized."""
        result = SpecResult(
            success=True,
            lean_code="def foo : Nat := 42",
            compiles=True,
            has_sorry=False,
            has_statements=True,
            attempts=1,
            tool_calls=2,
            error=None,
        )

        # Serialize
        json_str = result.model_dump_json()
        assert "foo" in json_str

        # Deserialize
        restored = SpecResult.model_validate_json(json_str)
        assert restored.success == result.success
        assert restored.lean_code == result.lean_code
        assert restored.compiles == result.compiles
        assert restored.attempts == result.attempts
