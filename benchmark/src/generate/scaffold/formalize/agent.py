"""Unified formalization agent for Impl.lean and Spec.lean generation.

Replaces the separate impl/spec/units three-agent architecture with a single
agent that sees full context (PBT + summary + discovered code) and produces
both files. Uses a two-phase pattern: iterative tool use followed by
structured output collection.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from inspect_ai.model import (
    ChatMessageSystem,
    ChatMessageUser,
    get_model,
)
from inspect_ai.solver import Generate, Solver, TaskState, solver
from pydantic import BaseModel, Field

from generate.scaffold.tools.declaration import all_lean_tools, call_lean_lsp_mcp
from generate.templates.formalize import get_formalization_prompts

logger = logging.getLogger(__name__)


class FormalizationPayload(BaseModel):
    """Input payload for the unified formalization agent."""

    function_name: str
    function_code: str | None = Field(
        default=None, description="Discovered function code (None if discovery failed)"
    )
    pbt_code: str = Field(description="Property-based test code (always available)")
    pbt_summary: str | None = Field(
        default=None, description="Natural language description from DB"
    )
    dependencies: dict[str, str] = Field(
        default_factory=dict, description="Filtered dep name → lean code"
    )
    variant: str = Field(default="control-functional")


class FormalizationResult(BaseModel):
    """Result from the unified formalization agent."""

    impl_code: str = Field(description="Final Impl.lean content")
    spec_code: str = Field(description="Final Spec.lean content")
    reasoning: str = Field(
        default="", description="Brief explanation of approach taken"
    )


@solver
def formalization_agent(payload: FormalizationPayload, workspace: Path) -> Solver:
    """Unified formalization agent that produces both Impl.lean and Spec.lean.

    Two-phase pattern:
    1. Iterative development with LSP tools (tool_calls="loop")
    2. Structured final output collection (response_schema)

    Args:
        payload: Formalization input (PBT, function code, deps, etc.)
        workspace: Per-sample workspace for Lean files

    Returns:
        Solver that generates both files and stores FormalizationResult in state.store
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        # Check if model is available
        try:
            get_model()
        except ValueError:
            result = FormalizationResult(
                impl_code="namespace Fvspec.Impl\n\nend Fvspec.Impl\n",
                spec_code="import Fvspec.Impl\n\nnamespace Fvspec.Spec\n\nend Fvspec.Spec\n",
                reasoning="No model configured",
            )
            state.store.set("formalization_result", result.model_dump())
            return state

        system_prompt, user_template = get_formalization_prompts(payload.variant)

        context = {
            "function_name": payload.function_name,
            "function_code": payload.function_code,
            "pbt_code": payload.pbt_code,
            "pbt_summary": payload.pbt_summary,
            "dependencies": payload.dependencies,
        }

        # Clear inherited messages — agent gets its own conversation
        state.messages = []
        state.messages.append(ChatMessageSystem(content=system_prompt))
        state.messages.append(ChatMessageUser(content=user_template.render(context)))

        # All Lean tools: write_lean_impl + write_lean_spec + LSP
        state.tools = all_lean_tools()

        # Phase 1: Iterative development with tools
        state = await generate(state, tool_calls="loop")

        # Count tool calls from message history
        tool_calls_count = sum(
            1 for msg in state.messages if hasattr(msg, "tool_calls") and msg.tool_calls
        )

        # Read final result from workspace files (agent wrote them via tools)
        result = _read_result_from_workspace(workspace)

        # Validate both files via LSP
        _validate_workspace_files(workspace, state)

        state.store.set("formalization_result", result.model_dump())
        state.store.set("formalization_tool_calls", tool_calls_count)

        return state

    return solve


def _read_result_from_workspace(workspace: Path) -> FormalizationResult:
    """Read Impl.lean and Spec.lean from workspace after agent execution.

    Falls back to empty namespace stubs if files don't exist.
    """
    impl_file = workspace / "Fvspec" / "Impl.lean"
    spec_file = workspace / "Fvspec" / "Spec.lean"

    impl_code = (
        impl_file.read_text()
        if impl_file.exists()
        else "namespace Fvspec.Impl\n\nend Fvspec.Impl\n"
    )
    spec_code = (
        spec_file.read_text()
        if spec_file.exists()
        else "import Fvspec.Impl\n\nnamespace Fvspec.Spec\n\nend Fvspec.Spec\n"
    )

    return FormalizationResult(
        impl_code=impl_code,
        spec_code=spec_code,
        reasoning="Read from workspace files after tool-based development",
    )


def _validate_workspace_files(workspace: Path, state: TaskState) -> None:
    """Validate both Lean files via LSP diagnostics. Stores results in state.store."""
    impl_file = workspace / "Fvspec" / "Impl.lean"
    spec_file = workspace / "Fvspec" / "Spec.lean"

    # Validate Impl.lean
    impl_compiles = False
    impl_has_sorry = False
    if impl_file.exists():
        try:
            impl_code = impl_file.read_text()
            impl_has_sorry = bool(re.search(r"\bsorry\b", impl_code))

            lsp_result = call_lean_lsp_mcp(
                workspace=workspace,
                tool_name="lean_diagnostic_messages",
                arguments={"file_path": str(impl_file)},
            )
            diagnostics = ""
            content = lsp_result.get("content", [])
            if content and isinstance(content, list) and len(content) > 0:
                diagnostics = content[0].get("text", "")
            impl_compiles = not bool(re.search(r"\berror:", diagnostics, re.IGNORECASE))
        except Exception as e:
            logger.warning(f"Impl.lean validation failed: {e}")

    # Validate Spec.lean
    spec_compiles = False
    spec_has_statements = False
    if spec_file.exists():
        try:
            spec_code = spec_file.read_text()
            spec_has_statements = bool(re.search(r"\b(theorem|lemma|def)\b", spec_code))

            lsp_result = call_lean_lsp_mcp(
                workspace=workspace,
                tool_name="lean_diagnostic_messages",
                arguments={"file_path": str(spec_file)},
            )
            diagnostics = ""
            content = lsp_result.get("content", [])
            if content and isinstance(content, list) and len(content) > 0:
                diagnostics = content[0].get("text", "")
            spec_compiles = not bool(re.search(r"\berror:", diagnostics, re.IGNORECASE))
        except Exception as e:
            logger.warning(f"Spec.lean validation failed: {e}")

    state.store.set(
        "validation",
        {
            "impl_compiles": impl_compiles,
            "impl_has_sorry": impl_has_sorry,
            "spec_compiles": spec_compiles,
            "spec_has_statements": spec_has_statements,
        },
    )
