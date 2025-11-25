"""Units generation agent using LLM-based test generation.

This agent generates Lean LSpec test suites from Python property-based tests,
replacing the deprecated AST-based extraction system.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from inspect_ai.model import ChatMessageSystem, ChatMessageUser, get_model
from inspect_ai.solver import Generate, Solver, TaskState, solver

from generate.scaffold.formalize.units.models import UnitsPayload, UnitsResult
from generate.scaffold.formalize.units.validator import validate_units_output
from generate.templates.units import get_variant_prompts

logger = logging.getLogger(__name__)


@solver
def units_generation_agent(
    payload: UnitsPayload,
    workspace: Path,
) -> Solver:
    """Generate Lean unit tests from PBT using solver architecture.

    Goal: LSpec test suite that validates implementation behavior.

    This agent uses LLM-based generation instead of AST extraction, providing
    more flexibility for handling complex test patterns and edge cases.

    Args:
        payload: Units generation payload
        workspace: Workspace path for LSP (not used in MVP, reserved for future)

    Returns:
        Solver that generates tests and stores result in state.metadata
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        # Check if model is available (will be None in test contexts)
        try:
            get_model()
        except ValueError:
            # No model configured (tests)
            result = UnitsResult(
                success=False,
                error="No model configured",
            )
            state.metadata["units_result"] = result.model_dump()
            return state

        # Get prompts (start with single "default" variant)
        system_prompt, user_template = get_variant_prompts("default")

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

        # Start without LSP tools for MVP - tests are simpler than specs
        # Can add later if needed: state.tools = lean_lsp_mcp_tools()

        # Run generation (single-shot for MVP)
        # Future: Could add tool_calls="loop" for iterative refinement
        state = await generate(state)

        # Extract code from <code>...</code> tags in final response
        # Use state.output.message.text to get string content (not list of content blocks)
        if not state.output or not state.output.message:
            lean_code = None
        elif hasattr(state.output.message, "text") and state.output.message.text:
            lean_code = extract_code_blocks(state.output.message.text)
        else:
            lean_code = None

        # Count assistant attempts (number of assistant responses)
        attempts = sum(
            1
            for msg in state.messages
            if hasattr(msg, "role") and msg.role == "assistant"
        )

        # Validate output
        if lean_code:
            validation = validate_units_output(lean_code)
            if validation.has_tests:
                result = UnitsResult(
                    success=True,
                    lean_code=lean_code,
                    test_count=count_tests(lean_code),
                    has_tests=True,
                    attempts=attempts,
                    tool_calls=0,  # No LSP tools in MVP
                )
            else:
                # Validation failed - include descriptive error message
                error_msg = (
                    "; ".join(validation.errors)
                    if validation.errors
                    else "Validation failed"
                )
                result = UnitsResult(
                    success=False,
                    lean_code=lean_code,
                    test_count=count_tests(lean_code),
                    has_tests=False,
                    error=error_msg,
                    attempts=attempts,
                    tool_calls=0,
                )
        else:
            result = UnitsResult(
                success=False,
                error="No code blocks found in response",
                attempts=attempts,
                tool_calls=0,
            )

        # Store result in metadata (will be moved to store by orchestration)
        state.metadata["units_result"] = result.model_dump()

        # Log result
        if result.success:
            logger.info(
                f"Units generation succeeded: {result.test_count} tests generated"
            )
        else:
            logger.warning(f"Units generation failed: {result.error}")

        return state

    return solve


def extract_code_blocks(content: str) -> str | None:
    """Extract Lean code from <code>...</code> tags.

    Args:
        content: Model response content

    Returns:
        Extracted Lean code, or None if no code blocks found
    """
    # Pattern matches <code>...</code> tags (non-greedy)
    pattern = r"<code>(.*?)</code>"
    matches = re.findall(pattern, content, re.DOTALL)

    if matches:
        # Return first code block (there should only be one)
        return matches[0].strip()

    return None


def count_tests(lean_code: str) -> int:
    """Count LSpec tests in generated code.

    Args:
        lean_code: Generated Lean code

    Returns:
        Number of tests found (counts 'test "name"' patterns)
    """
    # Count occurrences of 'test "..."' pattern
    # This matches test "anything" in the code
    pattern = r'test\s+"[^"]+"'
    matches = re.findall(pattern, lean_code)
    return len(matches)
