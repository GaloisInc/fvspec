"""Dependency autoformalization agent and tool wrapper."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Awaitable, Callable, Coroutine, Generator

from inspect_ai.agent import Agent, AgentState, agent, as_tool
from inspect_ai.model import ChatMessageSystem, ChatMessageUser
from inspect_ai.solver._task_state import sample_state
from inspect_ai.tool import Tool, ToolError, tool
from inspect_ai.util._store import store

from generate.templates.deps import get_dependency_prompts
from generate.scaffold.depmock.cache import CacheProvenance, store_dependency_result
from generate.scaffold.depmock.models import DependencyPayload, DependencyResult
from generate.scaffold.tools import utilio


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
    """Create a tool wrapping the dependency autoformalizer agent.

    NOTE: This is the LEGACY tool that doesn't persist results. For use in the
    main task loop, use create_bound_dependency_tools() instead which creates
    per-dependency tools that persist their outputs.
    """
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


_CODE_BLOCK_PATTERN = re.compile(r"(?s)<code>(.*?)</code>")


def create_bound_dependency_tools(
    payloads: list[DependencyPayload],
    *,
    variant: str | None = None,
) -> list[Tool]:
    """Create per-dependency tools that run autoformalizer and persist results.

    Each tool is bound to a specific dependency payload and will:
    1. Run the dependency autoformalizer agent when called
    2. Extract the generated Lean code
    3. Persist it to cache and the sample's deps/ directory
    4. Update Deps.lean with the new module
    5. Return a success message to the main agent

    Args:
        payloads: List of dependency payloads to create tools for
        variant: Optional prompt variant for dependency translation

    Returns:
        List of tools, one per dependency
    """
    tools: list[Tool] = []

    for payload in payloads:
        tool_name = f"autoformalize_{payload.dep_name}"
        tool_description = (
            f"Formalize the `{payload.dep_name}` Python dependency into "
            f"computable Lean code. This will generate the Lean module "
            f"Fvspec.Deps.{payload.lean_module_name}."
        )

        # Set docstring dynamically (used as tool description)
        def make_tool_func(
            bound_payload: DependencyPayload = payload,
            bound_variant: str | None = variant,
        ) -> Callable[[], Awaitable[str]]:  # type: ignore[misc]
            async def execute() -> str:
                """Run autoformalizer and persist result for this dependency."""
                # Get task state
                state = sample_state()
                if not state:
                    raise ToolError("No task state available")

                # Create the agent tool (without name parameter!)
                agent_tool = as_tool(
                    dependency_autoformalizer,
                    description=tool_description,
                    payload=bound_payload,
                    variant=bound_variant,
                )

                # Call the agent tool with a descriptive input message
                # Note: The agent builds its own prompts from the payload, so this
                # input might be supplementary or ignored depending on as_tool() behavior
                result_text = await agent_tool(
                    input=f"Translate the `{bound_payload.dep_name}` Python dependency into computable Lean 4 code."
                )

                # Extract code from <code>...</code> tags
                match = _CODE_BLOCK_PATTERN.search(result_text)
                if not match:
                    raise ToolError(
                        f"Autoformalizer for {bound_payload.dep_name} did not return "
                        "Lean code in <code>...</code> tags"
                    )

                lean_code = match.group(1).strip()

                # Create result
                result = DependencyResult(
                    lean_module=bound_payload.lean_module_name,
                    lean_code=lean_code,
                    variant=variant,
                    status="ok",
                    diagnostics=None,
                )

                # Persist to cache
                from generate.scaffold.depmock.cache import _cache_root

                provenance = CacheProvenance(
                    model=str(state.model) if state.model else None,
                    run_id=str(state.sample_id),
                )
                record = store_dependency_result(
                    bound_payload,
                    result,
                    cache_root=_cache_root(),
                    provenance=provenance,
                )

                # Write to sample's deps/ directory
                date_time = state.metadata.get("date_time")
                variant_meta = state.metadata.get("variant")
                if date_time and variant_meta:
                    sample_dir = utilio.get_sample_output_dir(
                        str(date_time), str(state.sample_id), str(variant_meta)
                    )
                    deps_dir = sample_dir / "deps"
                    deps_dir.mkdir(parents=True, exist_ok=True)

                    module_file = deps_dir / f"{bound_payload.lean_module_name}.lean"
                    module_file.write_text(lean_code)

                    # Update Deps.lean (regenerate from all modules in deps/)
                    _update_deps_lean(deps_dir, sample_dir)

                return (
                    f"Successfully formalized {bound_payload.dep_name} as "
                    f"Fvspec.Deps.{bound_payload.lean_module_name}. "
                    f"Use `import Fvspec.Deps` to access it."
                )

            return execute

        # Set the docstring and apply tool decorator
        make_tool_func.__doc__ = tool_description
        decorated_tool = tool(name=tool_name)(make_tool_func)  # type: ignore[arg-type]
        tools.append(decorated_tool())

    return tools


def _update_deps_lean(deps_dir: Path, sample_dir: Path) -> None:
    """Regenerate Deps.lean from all module files in deps/ directory.

    Args:
        deps_dir: Directory containing individual .lean module files
        sample_dir: Sample output directory where Deps.lean should be written
    """
    modules: list[str] = []

    for lean_file in sorted(deps_dir.glob("*.lean")):
        if lean_file.name != "Deps.lean":
            modules.append(lean_file.read_text().strip())

    if modules:
        body = "\n\n".join(modules)
        lean_text = f"namespace Fvspec.Deps\n\n{body}\n\nend Fvspec.Deps\n"
    else:
        lean_text = "-- No dependencies\n"

    deps_lean_file = sample_dir / "Deps.lean"
    deps_lean_file.write_text(lean_text)
