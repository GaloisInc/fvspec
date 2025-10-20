"""Unit tests for the dependency autoformalization agent."""

import pytest
from inspect_ai.agent import AgentState
from inspect_ai.model import ChatMessageSystem, ChatMessageUser

from benchmark.scaffold.depmock import (
    DependencyPayload,
    autoformalize_dependency_tool,
    dependency_autoformalizer,
)
from benchmark.scaffold.depmock.agent import _dependency_autoformalizer


@pytest.fixture
def payload() -> DependencyPayload:
    return DependencyPayload(
        dep_name="config.validate",
        python_source="""def validate(x):\n    return int(x)""",
        source_hash="abc123",
        tags=["validation"],
        usage_example="validate('42')",
    )


def test_dependency_autoformalizer_initial_prompt(payload: DependencyPayload):
    state = AgentState(messages=[])

    result_state = _dependency_autoformalizer(state, payload=payload)

    assert len(result_state.messages) == 2
    assert isinstance(result_state.messages[0], ChatMessageSystem)
    assert isinstance(result_state.messages[1], ChatMessageUser)
    assert payload.python_source.strip() in result_state.messages[1].content
    assert payload.lean_module_name in result_state.messages[1].content


def test_dependency_autoformalizer_refine_prompt(payload: DependencyPayload):
    diagnostics = "unknown identifier foo"
    state = AgentState(messages=[])

    result_state = _dependency_autoformalizer(
        state, payload=payload, diagnostics=diagnostics
    )

    assert diagnostics in result_state.messages[-1].content


def test_autoformalize_dependency_tool_configuration():
    tool = autoformalize_dependency_tool()
    assert callable(tool)
    params = getattr(tool, "__registry_params__", {})
    assert "autoformalizer" in (params.get("agent") or "")
    assert "payload" in dependency_autoformalizer.__annotations__
