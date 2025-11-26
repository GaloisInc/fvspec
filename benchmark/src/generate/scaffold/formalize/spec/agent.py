"""Spec generation agent using LSP tools.

This agent generates Lean theorem statements (with sorry proofs) from
property-based tests, using implementation signatures as context.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from inspect_ai.model import ChatMessageSystem, ChatMessageUser, get_model
from inspect_ai.solver import Generate, Solver, TaskState, solver

from generate.scaffold.formalize.spec.models import SpecPayload, SpecResult
from generate.scaffold.formalize.spec.validator import validate_spec_output
from generate.scaffold.tools.declaration import all_lean_tools, call_lean_lsp_mcp
from generate.templates.spec import get_variant_prompts

logger = logging.getLogger(__name__)


@solver
def spec_generation_agent(
    payload: SpecPayload,
    workspace: Path,
) -> Solver:
    """Generate Lean specification from PBT using solver architecture.

    Goal: Theorem statement that captures PBT invariants.
    Proof obligations SHOULD use 'sorry' - we're stating, not proving!

    Loop terminates when model stops calling tools.

    Args:
        payload: Spec generation payload
        workspace: Workspace path for LSP

    Returns:
        Solver that generates spec and stores result in state.metadata
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        # Check if model is available (will be None in test contexts)
        try:
            get_model()
        except ValueError:
            # No model configured (tests)
            result = SpecResult(
                success=False,
                lean_code=None,
                compiles=False,
                has_sorry=False,
                has_statements=False,
                attempts=0,
                tool_calls=0,
                error="No model configured",
            )
            state.metadata["spec_result"] = result.model_dump()
            return state

        # Get spec prompts based on variant
        system_prompt, user_template = get_variant_prompts(payload.variant)

        # Prepare template context
        context = {
            "pbt_code": payload.pbt_code,
            "pbt_name": payload.pbt_name,
            "function_name": payload.function_name,
            "impl_signatures": payload.impl_signatures,
        }

        # Build initial messages - append to state.messages
        state.messages.append(ChatMessageSystem(content=system_prompt))
        state.messages.append(ChatMessageUser(content=user_template.render(**context)))

        # Get all Lean tools (file writing + LSP analysis)
        # Workspace-aware tools that work with any Lean file
        tools = all_lean_tools()

        # Add tools to state
        state.tools = tools

        # Run iterative refinement loop using generate with tool_calls="loop"
        # This is the proper inspect_ai way - uses the injected generate function
        # Loop terminates when model stops calling tools
        state = await generate(state, tool_calls="loop")

        # Count tool calls from message history
        tool_calls_count = sum(
            1 for msg in state.messages if hasattr(msg, "tool_calls") and msg.tool_calls
        )

        # Calculate number of iterations (assistant responses)
        attempts = sum(
            1
            for msg in state.messages
            if hasattr(msg, "role") and msg.role == "assistant"
        )

        # Extract final response
        if not state.output or not state.output.message:
            result = SpecResult(
                success=False,
                lean_code=None,
                compiles=False,
                has_sorry=False,
                has_statements=False,
                attempts=attempts,
                tool_calls=tool_calls_count,
                error="No final message in response",
            )
            state.metadata["spec_result"] = result.model_dump()
            return state

        final_message = state.output.message
        if not hasattr(final_message, "text") or not final_message.text:
            result = SpecResult(
                success=False,
                lean_code=None,
                compiles=False,
                has_sorry=False,
                has_statements=False,
                attempts=attempts,
                tool_calls=tool_calls_count,
                error="No text in final message",
            )
            state.metadata["spec_result"] = result.model_dump()
            return state

        # Extract code from final response
        final_text = final_message.text
        lean_code = _extract_code_block(final_text)

        if not lean_code:
            result = SpecResult(
                success=False,
                lean_code=None,
                compiles=False,
                has_sorry=False,
                has_statements=False,
                attempts=attempts,
                tool_calls=tool_calls_count,
                error="No code block found in final response",
            )
            state.metadata["spec_result"] = result.model_dump()
            return state

        # Validate the generated code
        # We need to check if it compiles - write to workspace and check diagnostics
        spec_file = workspace / "Fvspec" / "Spec.lean"
        spec_file.parent.mkdir(parents=True, exist_ok=True)
        spec_file.write_text(lean_code)

        # Call lean_diagnostic_messages to check compilation
        # We need to import and call it directly

        try:
            lsp_result = call_lean_lsp_mcp(
                workspace=workspace,
                tool_name="lean_diagnostic_messages",
                arguments={"file_path": str(spec_file)},
            )
            diagnostics = ""
            content = lsp_result.get("content", [])
            if content and isinstance(content, list) and len(content) > 0:
                diagnostics = content[0].get("text", "")

            validation = validate_spec_output(lean_code, diagnostics)

            result = SpecResult(
                success=validation.valid,
                lean_code=lean_code,
                compiles=validation.compiles,
                has_sorry=validation.has_sorry,
                has_statements=validation.has_statements,
                attempts=attempts,
                tool_calls=tool_calls_count,
                error="; ".join(validation.errors) if validation.errors else None,
            )

        except Exception as e:
            result = SpecResult(
                success=False,
                lean_code=lean_code,
                compiles=False,
                has_sorry=False,
                has_statements=False,
                attempts=attempts,
                tool_calls=tool_calls_count,
                error=f"Failed to validate: {e}",
            )

        # Store result in metadata for orchestration and quality assessment
        state.metadata["spec_result"] = result.model_dump()

        return state

    return solve


def _extract_code_block(content: str) -> str:
    """Extract Lean code from <code>...</code> tags.

    Args:
        content: Agent response content

    Returns:
        Extracted code or original content if no tags found
    """
    match = re.search(r"<code>(.*?)</code>", content, re.DOTALL)
    return match.group(1).strip() if match else content.strip()
