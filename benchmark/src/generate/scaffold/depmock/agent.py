"""Dependency autoformalization agent and tool wrapper."""

from __future__ import annotations

from inspect_ai.agent import agent, AgentState, as_tool
from inspect_ai.model import ChatMessageSystem, ChatMessageUser
from inspect_ai.tool import Tool
from inspect_ai.util._store import store

from generate.templates.deps import get_dependency_prompts

from .models import DependencyPayload


def _ensure_system_message(state: AgentState, system_prompt: str) -> None:
    """Ensure the conversation contains a system prompt."""
    for message in state.messages:
        if isinstance(message, ChatMessageSystem):
            return
    state.messages.insert(0, ChatMessageSystem(content=system_prompt))


def _dependency_autoformalizer(
    state: AgentState,
    payload: DependencyPayload,
    diagnostics: str | None = None,
    variant: str | None = None,
) -> AgentState:
    """Populate the conversation with the appropriate depmock prompt.

    Args:
        state: Current AgentState conversation.
        payload: Dependency metadata and Python source to translate.
        diagnostics: Lean diagnostics from a previous attempt (if any).
        variant: Optional prompt variant override.
    """

    prompts = get_dependency_prompts(variant)
    _ensure_system_message(state, prompts.system_prompt)

    # Persist context for downstream tooling/debugging
    store().set("depmock_payload", payload.model_dump())
    store().set("depmock_variant", variant)
    store().set("depmock_normalization", payload.normalization.model_dump())

    if diagnostics:
        user_prompt = prompts.refine_template.render(
            payload.prompt_context(), diagnostics=diagnostics
        )
    else:
        user_prompt = prompts.translate_template.render(payload.prompt_context())

    state.messages.append(ChatMessageUser(content=user_prompt))
    return state


dependency_autoformalizer = agent(
    description="Translate a Python dependency snippet into Lean 4 code."
)(_dependency_autoformalizer)  # type: ignore[misc]


def autoformalize_dependency_tool(
    *, variant: str | None = None, description: str | None = None
) -> Tool:
    """Create a tool wrapping the dependency autoformalizer agent."""

    tool_description = description or (
        "Autoformalize a Python dependency into computable Lean code."
    )
    return as_tool(
        dependency_autoformalizer,
        description=tool_description,
        variant=variant,
    )
