"""Spec generation agent using LSP tools.

This agent generates Lean theorem statements (with sorry proofs) from
property-based tests, using implementation signatures as context.
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

from generate.scaffold.formalize.spec.models import SpecPayload, SpecResult
from generate.scaffold.formalize.spec.validator import validate_spec_output
from generate.templates.spec import get_variant_prompts

logger = logging.getLogger(__name__)


async def spec_generation_agent(
    payload: SpecPayload,
    workspace: Path,
    max_attempts: int = 32,
) -> SpecResult:
    """Generate Lean specification from PBT using impl signatures.

    Goal: Theorem statement that captures PBT invariants.
    Proof obligations SHOULD use 'sorry' - we're stating, not proving!

    Loops until:
    - Code compiles (no type errors)
    - Has proper theorem statements

    Args:
        payload: Spec generation payload
        workspace: Workspace path for LSP
        max_attempts: Maximum refinement iterations

    Returns:
        Spec generation result
    """
    # Get spec prompts based on variant
    system_prompt, user_template = get_variant_prompts(payload.variant)

    # Prepare template context
    context = {
        "pbt_code": payload.pbt_code,
        "pbt_name": payload.pbt_name,
        "function_name": payload.function_name,
        "impl_signatures": payload.impl_signatures,
    }

    # Build initial messages
    messages = [
        ChatMessageSystem(content=system_prompt),
        ChatMessageUser(content=user_template.render(context)),
    ]

    # Try to get model (will fail in tests)
    try:
        model = get_model()
    except ValueError:
        # No model configured (tests)
        return SpecResult(
            success=False,
            lean_code=None,
            compiles=False,
            has_sorry=False,
            has_statements=False,
            attempts=0,
            tool_calls=0,
            error="No model configured",
        )

    # Get LSP tools from workspace
    # We'll use the same LSP tools as the impl agent
    # (they're workspace-aware and work with any Lean file)
    from generate.scaffold.tools.declaration import lean_lsp_mcp_tools

    tools = lean_lsp_mcp_tools()

    # Run iterative refinement loop using generate_loop
    # Loop terminates when model stops calling tools
    conversation, output = await model.generate_loop(
        input=messages,
        tools=tools,
    )

    # Count tool calls from message history
    tool_calls_count = sum(
        1 for msg in conversation if hasattr(msg, "tool_calls") and msg.tool_calls
    )

    # Calculate number of iterations (assistant responses)
    attempts = sum(
        1 for msg in conversation if hasattr(msg, "role") and msg.role == "assistant"
    )

    # Extract final response
    final_message = output.message
    if not final_message or not hasattr(final_message, "text"):
        return SpecResult(
            success=False,
            lean_code=None,
            compiles=False,
            has_sorry=False,
            has_statements=False,
            attempts=attempts,
            tool_calls=tool_calls_count,
            error="No final message in response",
        )

    # Extract code from final response
    final_text = final_message.text or ""
    lean_code = _extract_code_block(final_text)

    if not lean_code:
        return SpecResult(
            success=False,
            lean_code=None,
            compiles=False,
            has_sorry=False,
            has_statements=False,
            attempts=attempts,
            tool_calls=tool_calls_count,
            error="No code block found in final response",
        )

    # Validate the generated code
    # We need to check if it compiles - write to workspace and check diagnostics
    spec_file = workspace / "Fvspec" / "Spec.lean"
    spec_file.parent.mkdir(parents=True, exist_ok=True)
    spec_file.write_text(lean_code)

    # Call lean_diagnostic_messages to check compilation
    # We need to import and call it directly
    from generate.scaffold.tools.declaration import call_lean_lsp_mcp

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

        return SpecResult(
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
        return SpecResult(
            success=False,
            lean_code=lean_code,
            compiles=False,
            has_sorry=False,
            has_statements=False,
            attempts=attempts,
            tool_calls=tool_calls_count,
            error=f"Failed to validate: {e}",
        )


def _extract_code_block(content: str) -> str:
    """Extract Lean code from <code>...</code> tags.

    Args:
        content: Agent response content

    Returns:
        Extracted code or original content if no tags found
    """
    match = re.search(r"<code>(.*?)</code>", content, re.DOTALL)
    return match.group(1).strip() if match else content.strip()
