"""Integration tests for spec generation agent."""

import pytest

from generate.scaffold.dataset import Datapoint
from generate.scaffold.formalize_spec import (
    SpecPayload,
    extract_signatures,
    run_spec_agent,
    spec_generation_agent,
)


class TestSpecAgentIntegration:
    """Integration tests for spec agent."""

    @pytest.mark.anyio
    async def test_spec_agent_stub_implementation(self, tmp_path):
        """Test that spec agent returns expected stub result."""
        payload = SpecPayload(
            pbt_code="def test_inc(x): assert inc(x) == x + 1",
            pbt_name="test_inc",
            impl_signatures={"inc": "def inc (x : Nat) : Nat"},
            function_name="inc",
            variant="control-functional",
        )

        result = await spec_generation_agent(payload, tmp_path)

        # Should return result indicating no model configured (test context)
        assert not result.success
        assert result.error is not None
        assert "no model configured" in result.error.lower()

    @pytest.mark.anyio
    async def test_run_spec_agent_with_datapoint(self, tmp_path):
        """Test runner with a datapoint."""
        datapoint = Datapoint(
            id=1,
            repo_id=1,
            name="test_increment",
            code="def test_increment(x): assert increment(x) == x + 1",
            summary="Test increment function",
            deps="[]",
            dep_names="[]",
        )

        impl_signatures = {"increment": "def increment (x : Nat) : Nat"}

        result = await run_spec_agent(
            datapoint=datapoint,
            impl_signatures=impl_signatures,
            variant="control-functional",
            workspace=tmp_path,
        )

        # Should complete (even if stub)
        assert result is not None
        assert isinstance(result.attempts, int)

    def test_extract_signatures_integration(self):
        """Test signature extraction from realistic Impl.lean."""
        impl_lean = """
-- Implementation of increment function
def increment (x : Nat) : Nat := x + 1

-- Helper function
def double (x : Nat) : Nat := x * 2

theorem increment_property (x : Nat) : increment x > x := by
  sorry
"""

        sigs = extract_signatures(impl_lean)

        assert "increment" in sigs
        assert "double" in sigs
        assert "increment_property" in sigs
        assert "def increment" in sigs["increment"]
        assert "theorem increment_property" in sigs["increment_property"]


class TestSpecPayloadCreation:
    """Test creating spec payloads from datapoints."""

    def test_payload_from_datapoint_fields(self):
        """Test that payload can be created from datapoint."""
        datapoint = Datapoint(
            id=5,
            repo_id=10,
            name="test_foo",
            code="def test_foo(): pass",
            summary="Test foo function",
            deps="[]",
            dep_names="[]",
        )

        impl_sigs = {"foo": "def foo : Bool"}

        payload = SpecPayload(
            pbt_code=datapoint.code,
            pbt_name=datapoint.name,
            impl_signatures=impl_sigs,
            function_name="foo",
            variant="mvcgen",
        )

        assert payload.pbt_code == datapoint.code
        assert payload.pbt_name == datapoint.name
        assert "foo" in payload.impl_signatures
        assert payload.variant == "mvcgen"
