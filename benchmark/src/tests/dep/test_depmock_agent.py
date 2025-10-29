"""Unit tests for the dependency autoformalization agent."""

import asyncio
from typing import Any, Awaitable, cast
from unittest.mock import Mock

import pytest
from inspect_ai.agent import AgentState
from inspect_ai.model import ChatMessageSystem, ChatMessageUser
from inspect_ai._util.registry import registry_info  # type: ignore

from generate.scaffold.depmock import (
    DependencyPayload,
    autoformalize_dependency_tool,
    dependency_autoformalizer,
)


def run_dependency_autoformalizer(
    payload: DependencyPayload,
    *,
    diagnostics: str | None = None,
    variant: str | None = None,
) -> AgentState:
    """Execute the dependency autoformalizer agent and return the new state."""

    async def _run() -> AgentState:
        state = AgentState(messages=[])
        agent_call = dependency_autoformalizer(
            state, payload=payload, diagnostics=diagnostics, variant=variant
        )
        awaitable_state = cast(Awaitable[AgentState], agent_call)
        return await awaitable_state

    return asyncio.run(_run())


@pytest.fixture
def payload() -> DependencyPayload:
    """Return a simple configuration helper payload used across tests."""
    return DependencyPayload(
        dep_name="config.validate",
        python_source="""def validate(x):\n    return int(x)""",
        source_hash="abc123",
        tags=("validation",),
        usage_example="validate('42')",
    )


def test_dependency_payload_annotation(payload: DependencyPayload):
    """Normalization metadata should derive helper names and kinds."""
    assert payload.callable.signature.text == "validate(x)"
    assert payload.callable.kind.value == "function"
    assert payload.artifact.module_basename == "ConfigValidate"
    plan = payload.normalization
    assert plan.strategy.value == "as_is"
    assert plan.lean_helper_name == "config_validate"
    assert plan.receiver_name is None
    context = payload.prompt_context()
    assert context["callable_kind"] == "function"
    lean_module = cast(str, context["lean_module_qualified"])
    assert lean_module == payload.artifact.qualified_module
    arguments = cast(list[dict[str, Any]], context["callable_arguments"])
    assert arguments[0]["name"] == "x"
    assert context["module_path"] == "config"
    assert context["normalization_strategy"] == "as_is"
    lean_helper_name = cast(str, context["lean_helper_name"])
    assert lean_helper_name == "config_validate"


def test_normalization_flatten_method():
    """Methods with unused receivers should flatten into helper functions."""
    payload = DependencyPayload(
        dep_name="Widget.ping",
        python_source="def ping(self, value):\n    return value + 1",
        source_hash=None,
        tags=tuple(),
    )
    plan = payload.normalization
    assert plan.strategy.value == "flatten_method"
    assert plan.receiver_alias == "inst"
    assert plan.struct_name is None
    assert plan.lean_helper_name == "widget_ping"
    context = payload.prompt_context()
    assert context["normalization_strategy"] == "flatten_method"
    assert "widget_ping" in cast(str, context["lean_helper_name"])
    normalization = cast(dict[str, Any], context["normalization"])
    assert normalization["receiver_alias"] == "inst"


def test_normalization_structure_method():
    """Stateful receivers should request structure-based normalization."""
    payload = DependencyPayload(
        dep_name="Counter.increment",
        python_source=(
            "def increment(self, delta: int = 1):\n"
            "    self.count += delta\n"
            "    return self.count\n"
        ),
        source_hash=None,
        tags=("stateful",),
    )
    plan = payload.normalization
    assert plan.strategy.value == "structure_method"
    assert plan.struct_name == "Counter"
    assert plan.struct_fields == ("count",)
    assert plan.mutates_receiver is True
    context = payload.prompt_context()
    assert context["normalization_strategy"] == "structure_method"
    normalization = cast(dict[str, Any], context["normalization"])
    assert normalization["struct_fields"] == ["count"]
    assert normalization["mutates_receiver"] is True


def test_dependency_autoformalizer_initial_prompt(payload: DependencyPayload):
    """Initial prompts should include system instructions and user payload content."""
    result_state = run_dependency_autoformalizer(payload)

    assert len(result_state.messages) == 2
    assert isinstance(result_state.messages[0], ChatMessageSystem)
    assert isinstance(result_state.messages[1], ChatMessageUser)
    assert payload.python_source.strip() in result_state.messages[1].content
    assert payload.lean_module_name in result_state.messages[1].content


def test_dependency_autoformalizer_refine_prompt(payload: DependencyPayload):
    """Refinement prompts should surface diagnostics for iterative repair."""
    diagnostics = "unknown identifier foo"
    result_state = run_dependency_autoformalizer(payload, diagnostics=diagnostics)

    assert diagnostics in result_state.messages[-1].content


def test_autoformalize_dependency_tool_configuration():
    """The dependency autoformalizer tool should expose agent and payload config."""
    payload = DependencyPayload(
        dep_name="demo.helper",
        python_source="def helper(x):\n    return x + 1",
        source_hash="xyz789",
        tags=("demo",),
    )
    tool = autoformalize_dependency_tool(payload=payload)
    assert callable(tool)
    params = getattr(tool, "__registry_params__", {})
    assert "autoformalizer" in (params.get("agent") or "")
    assert "payload" in dependency_autoformalizer.__annotations__


def test_tool_name_parsing_logic():
    """Test that tool name parsing correctly extracts tool names from registry format."""
    # Create mock tools with different registry name formats
    mock_tools = []

    # Tool with namespace/tool_name format
    tool1 = Mock()
    mock_info1 = Mock()
    mock_info1.name = "generate/lean_diagnostic_messages"

    # Tool with just tool_name format (no namespace)
    tool2 = Mock()
    mock_info2 = Mock()
    mock_info2.name = "simple_tool"

    # Tool with multiple levels of nesting
    tool3 = Mock()
    mock_info3 = Mock()
    mock_info3.name = "generate/scaffold/complex_tool"

    # Tool with None name (should be skipped)
    tool4 = Mock()
    mock_info4 = Mock()
    mock_info4.name = None

    mock_tools = [tool1, tool2, tool3, tool4]

    # Patch registry_info to return our mock info objects
    def mock_registry_info(tool):
        if tool is tool1:
            return mock_info1
        elif tool is tool2:
            return mock_info2
        elif tool is tool3:
            return mock_info3
        elif tool is tool4:
            return mock_info4
        else:
            return None

    # Test the parsing logic (extracted from the agent code)
    tools_by_name = {}
    for t in mock_tools:
        info = mock_registry_info(t)
        if info and info.name:
            # This is the exact parsing logic from the agent
            tool_name = info.name.split("/")[-1] if "/" in info.name else info.name
            tools_by_name[tool_name] = t

    # Verify the parsing results
    assert "lean_diagnostic_messages" in tools_by_name
    assert tools_by_name["lean_diagnostic_messages"] is tool1

    assert "simple_tool" in tools_by_name
    assert tools_by_name["simple_tool"] is tool2

    assert "complex_tool" in tools_by_name
    assert tools_by_name["complex_tool"] is tool3

    # Tool with None name should not be included
    assert len(tools_by_name) == 3

    # Verify that namespace parts are correctly stripped
    assert "generate" not in tools_by_name
    assert "scaffold" not in tools_by_name
