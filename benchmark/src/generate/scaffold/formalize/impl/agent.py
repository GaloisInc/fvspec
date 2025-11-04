"""Dependency autoformalization agent and tool wrapper."""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable, Coroutine, Generator
from pathlib import Path
from typing import Any

from inspect_ai._util.registry import registry_info  # type: ignore
from inspect_ai.agent import Agent, AgentState, agent, as_tool
from inspect_ai.model import (
    ChatMessageSystem,
    ChatMessageTool,
    ChatMessageUser,
    get_model,
)
from inspect_ai.solver._task_state import sample_state
from inspect_ai.tool import Tool, ToolCallError, ToolCallView, ToolError, tool
from inspect_ai.util._store import store

from generate.scaffold.formalize.impl.cache import (
    CacheProvenance,
    store_dependency_result,
)
from generate.scaffold.formalize.impl.models import DependencyPayload, DependencyResult
from generate.scaffold.tools import utilio
from generate.templates.impl import get_dependency_prompts
from generate.templates.impl.strings import get_dependency_strings

# Module-level logger to avoid multiple instantiations
logger = logging.getLogger(__name__)


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
        store().set("formalize_impl_payload", payload_obj.model_dump())
        store().set("formalize_impl_variant", variant)
        store().set(
            "formalize_impl_normalization", payload_obj.normalization.model_dump()
        )

        if diagnostics:
            user_prompt = prompts.refine_template.render(
                payload_obj.prompt_context(), diagnostics=diagnostics
            )
        else:
            user_prompt = prompts.translate_template.render(
                payload_obj.prompt_context()
            )

        state.messages.append(ChatMessageUser(content=user_prompt))

        # Run an agent loop with LSP tools to iteratively develop and validate the code.
        # get_model() raises ValueError when no model is configured (e.g., in unit tests).
        # In test contexts, we return the state with just the prompts added for validation.
        try:
            model = get_model()

            # Get tools from TaskState for LSP feedback (AgentState doesn't have tools)
            task_state = sample_state()
            all_tools = task_state.tools if task_state else []

            # Pass all tools to model.generate - inspect_ai will handle tool naming
            # The tools are @tool-decorated functions that inspect_ai knows how to serialize
            tools = all_tools

            # Build tool name lookup using inspect_ai's registry system
            #
            # ASSUMPTION: Registry names follow 'namespace/tool_name' format.
            # Tools in inspect_ai have hierarchical names like "generate/lean_diagnostic_messages"
            # in the registry, but the model API uses just the tool name part (e.g., "lean_diagnostic_messages").
            # This parsing extracts the final component after the last "/" separator.
            #
            # If the registry format changes or tools don't follow this naming convention,
            # this parsing logic will need to be updated accordingly.
            tools_by_name = {}
            for t in tools:
                info = registry_info(t)
                if info and info.name:
                    # Parse tool name from registry format: "namespace/tool_name" -> "tool_name"
                    tool_name = (
                        info.name.split("/")[-1] if "/" in info.name else info.name
                    )
                    tools_by_name[tool_name] = t

            # Run an agent loop manually to allow iterative tool usage
            # Max 16 iterations to allow sufficient refinement for complex dependencies
            max_tool_iterations = 16
            for _ in range(max_tool_iterations):
                response = await model.generate(state.messages, tools=tools)
                state.messages.append(response.message)
                state.output = response

                # Check if model wants to call tools
                if response.message.tool_calls:
                    # Execute all tool calls and collect results
                    # IMPORTANT: All tool results must be appended together as consecutive messages
                    # immediately after the assistant's tool_use message
                    tool_results = []
                    for tool_call in response.message.tool_calls:
                        tool = tools_by_name.get(tool_call.function)
                        if tool:
                            try:
                                # ToolCallView.call expects ToolCallContent, which is in tool_call.view
                                view = ToolCallView(call=tool_call.view)
                                # Unpack arguments dict with view included
                                result = await tool(
                                    **{**tool_call.arguments, "view": view}
                                )
                                tool_results.append(
                                    ChatMessageTool(
                                        tool_call_id=tool_call.id,
                                        function=tool_call.function,
                                        content=str(result),
                                    )
                                )
                            except Exception as e:
                                tool_results.append(
                                    ChatMessageTool(
                                        tool_call_id=tool_call.id,
                                        function=tool_call.function,
                                        content=str(e),
                                        error=ToolCallError(
                                            message=str(e), type="unknown"
                                        ),
                                    )
                                )
                        else:
                            # Tool not found - return error so API doesn't complain about missing tool_result
                            available_tools = ", ".join(tools_by_name.keys())
                            tool_results.append(
                                ChatMessageTool(
                                    tool_call_id=tool_call.id,
                                    function=tool_call.function,
                                    content=f"Tool '{tool_call.function}' not available. Available tools: {available_tools}",
                                    error=ToolCallError(
                                        message=f"Tool '{tool_call.function}' not found",
                                        type="unknown",
                                    ),
                                )
                            )

                    # Append all tool results together
                    state.messages.extend(tool_results)
                else:
                    # No tool calls - agent is done
                    break
        except ValueError:
            # No model configured - return state with prompts for inspection
            pass

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


@agent(description=get_dependency_strings().agent_description)
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
    strings = get_dependency_strings()
    tool_description = description or strings.legacy_tool_description
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
_DEFINITION_PATTERN = re.compile(
    r"^\s*(?:def|abbrev|structure|inductive|theorem|class|instance)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
    re.MULTILINE,
)
_MARKDOWN_CODE_BLOCK_PATTERN = re.compile(r"(?s)```(?:lean)?\s*(.*?)```")
_IMPORT_PATTERN = re.compile(r"^import\s+.*$", re.MULTILINE)


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
    # Track discovered function under test (if any)
    if payloads and "function_under_test" in payloads[0].tags:
        discovered = payloads[0]
        # Extract discovery method from tags (second tag is the method)
        discovery_method = discovered.tags[1] if len(discovered.tags) > 1 else "unknown"
        logger.info(
            f"✓ Discovered function under test: {discovered.dep_name} "
            f"(confidence={discovered.confidence:.2f}, method={discovery_method})"
        )

    strings = get_dependency_strings()
    tools: list[Tool] = []

    for payload in payloads:
        tool_name = f"formalize_impl_autoformalize_{payload.dep_name}"
        tool_description = strings.bound_tool.description.format(
            dep_name=payload.dep_name,
            lean_module_name=payload.lean_module_name,
        )

        # Set docstring dynamically (used as tool description)
        def make_tool_func(
            bound_payload: DependencyPayload = payload,
            bound_variant: str | None = variant,
        ) -> Callable[[ToolCallView], Awaitable[str]]:  # type: ignore[misc]
            async def execute(view: ToolCallView) -> str:
                """Run autoformalizer and persist result for this dependency.

                Args:
                    view: Tool call context (provided by inspect_ai)
                """
                strings = get_dependency_strings()

                # Get task state
                state = sample_state()
                if not state:
                    raise ToolError(strings.errors.no_task_state)

                # Create the agent tool with bound payload and variant
                # The agent will internally render the full translation prompt
                agent_tool = as_tool(
                    dependency_autoformalizer,
                    description=tool_description,
                    payload=bound_payload,
                    variant=bound_variant,
                )

                # Call the agent tool with a simple trigger message
                # The agent handles all prompt rendering internally based on bound payload/variant
                trigger = strings.bound_tool.trigger_message.format(
                    dep_name=bound_payload.dep_name
                )
                result = await agent_tool(input=trigger)

                # Convert result to string (handle list of content blocks or plain string)
                if isinstance(result, list):
                    # Extract text from content blocks (ContentText objects)
                    text_parts = []
                    for item in result:
                        if hasattr(item, "text"):
                            text_parts.append(item.text)
                        elif isinstance(item, str):
                            text_parts.append(item)
                        else:
                            # Unexpected content type - log and convert to string
                            logger.warning(
                                f"Unexpected content type in agent result for {bound_payload.dep_name}: "
                                f"{type(item).__name__}. Converting to string."
                            )
                            text_parts.append(str(item))
                    result_text = "".join(text_parts)
                elif isinstance(result, str):
                    result_text = result
                else:
                    # Unexpected result type - log and convert to string
                    logger.warning(
                        f"Unexpected agent result type for {bound_payload.dep_name}: "
                        f"{type(result).__name__}. Converting to string."
                    )
                    result_text = str(result)

                # Defensive: ensure result_text is actually a string
                if not isinstance(result_text, str):
                    raise ToolError(
                        f"Internal error: result_text is {type(result_text).__name__} "
                        f"instead of str for {bound_payload.dep_name}"
                    )

                # Extract code from <code>...</code> tags or markdown ```lean ... ``` blocks
                match = _CODE_BLOCK_PATTERN.search(result_text)
                if match:
                    lean_code = match.group(1).strip()
                else:
                    # Try markdown code fence format as silent fallback
                    match = _MARKDOWN_CODE_BLOCK_PATTERN.search(result_text)
                    if match:
                        lean_code = match.group(1).strip()
                    else:
                        # Neither format found - provide helpful context
                        preview = (
                            result_text[:512] + "..."
                            if len(result_text) > 512
                            else result_text
                        )
                        raise ToolError(
                            strings.errors.missing_code_tags_with_preview.format(
                                dep_name=bound_payload.dep_name,
                                preview=preview,
                            )
                        )

                # Extract the actual function/definition names from the Lean code
                # Look for def, abbrev, structure, inductive, theorem patterns
                definitions = _DEFINITION_PATTERN.findall(lean_code)

                # Build a human-readable list of definitions
                if definitions:
                    # Use the first definition as the primary one for the message
                    primary_def = definitions[0]
                    if len(definitions) > 1:
                        def_list = f"`{primary_def}` (and {len(definitions) - 1} other definition(s))"
                    else:
                        def_list = f"`{primary_def}`"
                else:
                    # Fallback if we can't parse definitions
                    def_list = "definitions"

                # Create result
                result = DependencyResult(
                    lean_module=bound_payload.lean_module_name,
                    lean_code=lean_code,
                    variant=variant,
                    status="ok",
                    diagnostics=None,
                )

                # Persist to cache
                from generate.scaffold.formalize.impl.cache import _cache_root

                provenance = CacheProvenance(
                    model=str(state.model) if state.model else None,
                    run_id=str(state.sample_id),
                )
                _record = store_dependency_result(
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
                    deps_lean_content = _update_deps_lean(deps_dir, sample_dir)
                else:
                    deps_lean_content = ""

                return strings.bound_tool.success_message.format(
                    dep_name=bound_payload.dep_name,
                    def_list=def_list,
                    deps_lean_content=deps_lean_content,
                )

            return execute

        # Set the docstring and apply tool decorator
        make_tool_func.__doc__ = tool_description
        decorated_tool = tool(name=tool_name)(make_tool_func)  # type: ignore[arg-type]
        tools.append(decorated_tool())

    return tools


def _update_deps_lean(deps_dir: Path, sample_dir: Path) -> str:
    """Regenerate Deps.lean from all module files in deps/ directory.

    Args:
        deps_dir: Directory containing individual .lean module files
        sample_dir: Sample output directory where Deps.lean should be written

    Returns:
        The content of the generated Deps.lean file
    """
    strings = get_dependency_strings()
    modules: list[str] = []

    for lean_file in sorted(deps_dir.glob("*.lean")):
        if lean_file.name != "Deps.lean":
            modules.append(lean_file.read_text().strip())

    if modules:
        # Extract all imports and move them to the top
        all_imports: list[str] = []
        cleaned_modules: list[str] = []

        for module in modules:
            # Extract imports from this module
            imports = _IMPORT_PATTERN.findall(module)
            all_imports.extend(imports)
            # Remove imports from module content
            cleaned = _IMPORT_PATTERN.sub("", module).strip()
            if cleaned:  # Only add non-empty modules
                cleaned_modules.append(cleaned)

        # Deduplicate and sort imports
        unique_imports = sorted(set(all_imports))

        # Build final file: imports at top, then module contents
        parts = []
        if unique_imports:
            parts.append("\n".join(unique_imports))
        if cleaned_modules:
            parts.append("\n\n".join(cleaned_modules))

        lean_text = "\n\n".join(parts) + "\n"
    else:
        lean_text = strings.deps_lean.empty

    deps_lean_file = sample_dir / "Deps.lean"
    deps_lean_file.write_text(lean_text)
    return lean_text
