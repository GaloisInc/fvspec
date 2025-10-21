"""Dependency autoformalization agent and tool wrapper."""

from __future__ import annotations

from typing import Any, Awaitable, Coroutine, Generator

from inspect_ai.agent import Agent, AgentState, agent, as_tool
from inspect_ai.model import ChatMessageSystem, ChatMessageUser
from inspect_ai.tool import Tool
from inspect_ai.util._store import store

from generate.templates.deps import get_dependency_prompts

from generate.scaffold.depmock.models import DependencyPayload


def _ensure_system_message(state: AgentState, system_prompt: str) -> None:
    """Ensure the conversation contains a system prompt."""
    for message in state.messages:
        if isinstance(message, ChatMessageSystem):
            return
    state.messages.insert(0, ChatMessageSystem(content=system_prompt))


class _DependencyAutoformalizerAgent(Awaitable[AgentState], Agent):
    """Agent invocation that injects dependency autoformalization prompts."""

    def __init__(
        self,
        *,
        state: AgentState | None,
        payload: DependencyPayload | dict,
        diagnostics: str | None,
        variant: str | None,
    ) -> None:
        self._initial_state = state
        self._payload = payload
        self._diagnostics = diagnostics
        self._variant = variant

    async def _execute(
        self,
        *,
        state: AgentState,
        payload: DependencyPayload | dict,
        diagnostics: str | None,
        variant: str | None,
    ) -> AgentState:
        payload_obj = (
            payload
            if isinstance(payload, DependencyPayload)
            else DependencyPayload.model_validate(payload)
        )

        prompts = get_dependency_prompts(variant)
        _ensure_system_message(state, prompts.system_prompt)

        # Persist context for downstream tooling/debugging
        store().set("depmock_payload", payload_obj.model_dump())
        store().set("depmock_variant", variant)
        store().set("depmock_normalization", payload_obj.normalization.model_dump())

        if diagnostics:
            user_prompt = prompts.refine_template.render(
                payload_obj.prompt_context(), diagnostics=diagnostics
            )
        else:
            user_prompt = prompts.translate_template.render(
                payload_obj.prompt_context()
            )

        state.messages.append(ChatMessageUser(content=user_prompt))
        return state

    def __await__(self) -> Generator[AgentState, None, AgentState]:
        if self._initial_state is None:
            raise RuntimeError(
                "Dependency autoformalizer requires an AgentState when awaited directly."
            )
        coroutine: Coroutine[Any, Any, AgentState] = self._execute(
            state=self._initial_state,
            payload=self._payload,
            diagnostics=self._diagnostics,
            variant=self._variant,
        )
        return coroutine.__await__()

    async def __call__(
        self,
        state: AgentState,
        *,
        payload: DependencyPayload | dict | None = None,
        diagnostics: str | None = None,
        variant: str | None = None,
    ) -> AgentState:
        """Support reusing the invocation as an Agent compatible callable."""
        resolved_payload = payload if payload is not None else self._payload
        resolved_diagnostics = (
            diagnostics if diagnostics is not None else self._diagnostics
        )
        resolved_variant = variant if variant is not None else self._variant
        return await self._execute(
            state=state,
            payload=resolved_payload,
            diagnostics=resolved_diagnostics,
            variant=resolved_variant,
        )


@agent(description="Translate a Python dependency snippet into Lean 4 code.")
def dependency_autoformalizer(
    state: AgentState,
    *,
    payload: DependencyPayload | dict,
    diagnostics: str | None = None,
    variant: str | None = None,
) -> _DependencyAutoformalizerAgent:
    """Populate the conversation with the dependency autoformalization prompt.

    Args:
        state: Current agent conversation state.
        payload: Structured dependency metadata (either a ``DependencyPayload`` or
            a JSON object with matching fields) containing the Python helper to translate.
        diagnostics: Optional Lean diagnostics from a previous attempt that should
            be surfaced to the agent for refinement.
        variant: Optional prompt variant override for dependency autoformalization.

    Returns:
        Agent invocation that will populate the conversation with the dependency
        translation prompt when executed.
    """
    return _DependencyAutoformalizerAgent(
        state=state,
        payload=payload,
        diagnostics=diagnostics,
        variant=variant,
    )


def autoformalize_dependency_tool(
    *,
    payload: DependencyPayload | None = None,
    diagnostics: str | None = None,
    variant: str | None = None,
    description: str | None = None,
) -> Tool:
    """Create a tool wrapping the dependency autoformalizer agent."""
    tool_description = description or (
        "Autoformalize a Python dependency into computable Lean code."
    )
    kwargs: dict[str, object] = {
        "description": tool_description,
    }
    if payload is not None:
        kwargs["payload"] = payload
    if diagnostics is not None:
        kwargs["diagnostics"] = diagnostics
    if variant is not None:
        kwargs["variant"] = variant

    return as_tool(
        dependency_autoformalizer,
        **kwargs,
    )
