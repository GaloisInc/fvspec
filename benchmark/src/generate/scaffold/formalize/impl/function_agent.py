"""Implementation agent for function under test.

This agent generates complete Lean implementations (zero sorry) for the
function being tested, using function discovery and dependency context.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from inspect_ai.model import ChatMessageSystem, ChatMessageUser, get_model
from inspect_ai.solver import Generate, Solver, TaskState, solver
from pydantic import BaseModel, Field

from generate.scaffold.quality_assessment.lean_parsing import detect_eval_statements
from generate.scaffold.tools.declaration import all_lean_tools, call_lean_lsp_mcp
from generate.templates.impl import get_impl_function_prompts

logger = logging.getLogger(__name__)


class FunctionImplPayload(BaseModel):
    """Payload for function implementation generation."""

    function_name: str = Field(description="Function to implement")
    function_code: str | None = Field(
        default=None, description="Discovered function code (if available)"
    )
    dependencies: dict[str, str] = Field(
        default_factory=dict,
        description="Dependency implementations from formalize_impl",
    )
    variant: str = Field(
        default="control-functional", description="Implementation variant"
    )


class FunctionImplResult(BaseModel):
    """Result from function implementation generation."""

    success: bool = Field(description="Whether generation succeeded")
    lean_code: str | None = Field(
        default=None, description="Generated Lean implementation"
    )
    compiles: bool = Field(default=False, description="Whether code compiles")
    has_sorry: bool = Field(default=False, description="Whether code has sorry")
    attempts: int = Field(default=0, description="Number of refinement attempts")
    tool_calls: int = Field(default=0, description="Total tool calls made")
    error: str | None = Field(default=None, description="Error message if failed")
    has_eval_stripped: bool = Field(
        default=False,
        description="Whether #eval statements were stripped due to build failures",
    )


@solver
def function_impl_agent(
    payload: FunctionImplPayload,
    workspace: Path,
) -> Solver:
    """Generate Lean implementation for function under test using solver architecture.

    Goal: Complete, computable implementation (ZERO sorry).
    This should be a def with full implementation body.

    Loop terminates when model stops calling tools.

    Args:
        payload: Function implementation payload
        workspace: Workspace path for LSP

    Returns:
        Solver that generates implementation and stores result in state.metadata
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        # Check if model is available (will be None in test contexts)
        try:
            get_model()
        except ValueError:
            # No model configured (tests)
            result = FunctionImplResult(
                success=False,
                lean_code=None,
                compiles=False,
                has_sorry=False,
                attempts=0,
                tool_calls=0,
                error="No model configured",
            )
            state.metadata["impl_result"] = result.model_dump()
            return state

        # Get impl prompts based on variant
        system_prompt, user_template = get_impl_function_prompts(payload.variant)

        # Prepare template context
        context = {
            "function_name": payload.function_name,
            "function_code": payload.function_code,
            "dependencies": payload.dependencies,
        }

        # Clear inherited messages from parent state (e.g., Sample input with PBT code)
        # Impl agent should only see function-specific prompts, not orchestration context
        state.messages = []

        # Build initial messages for impl agent
        state.messages.append(ChatMessageSystem(content=system_prompt))
        state.messages.append(ChatMessageUser(content=user_template.render(context)))

        # Get all Lean tools (file writing + LSP analysis)
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
            result = FunctionImplResult(
                success=False,
                lean_code=None,
                compiles=False,
                has_sorry=False,
                attempts=attempts,
                tool_calls=tool_calls_count,
                error="No final message in response",
            )
            state.metadata["impl_result"] = result.model_dump()
            return state

        final_message = state.output.message
        if not hasattr(final_message, "text") or not final_message.text:
            result = FunctionImplResult(
                success=False,
                lean_code=None,
                compiles=False,
                has_sorry=False,
                attempts=attempts,
                tool_calls=tool_calls_count,
                error="No text in final message",
            )
            state.metadata["impl_result"] = result.model_dump()
            return state

        # Extract code from most recent <code> block in message history
        # This captures the agent's last validated implementation without
        # requiring redundant final output
        lean_code = _extract_code_from_history(state.messages)

        # Fallback to final message if no <code> blocks found in history
        if not lean_code and final_message.text:
            lean_code = _extract_code_block(final_message.text)

        if not lean_code:
            result = FunctionImplResult(
                success=False,
                lean_code=None,
                compiles=False,
                has_sorry=False,
                attempts=attempts,
                tool_calls=tool_calls_count,
                error="No code block found in final response",
            )
            state.metadata["impl_result"] = result.model_dump()
            return state

        # Validate the generated code
        # We need to check if it compiles AND has zero sorry
        impl_file = workspace / "Fvspec" / "Impl.lean"
        impl_file.parent.mkdir(parents=True, exist_ok=True)
        impl_file.write_text(lean_code)

        # Call lean_diagnostic_messages to check compilation
        try:
            lsp_result = call_lean_lsp_mcp(
                workspace=workspace,
                tool_name="lean_diagnostic_messages",
                arguments={"file_path": str(impl_file)},
            )
            diagnostics = ""
            content = lsp_result.get("content", [])
            if content and isinstance(content, list) and len(content) > 0:
                diagnostics = content[0].get("text", "")

            # Check for errors
            has_errors = bool(re.search(r"\berror:", diagnostics, re.IGNORECASE))

            # Check for sorry
            has_sorry = bool(re.search(r"\bsorry\b", lean_code))

            # Success if: compiles AND zero sorry
            success = not has_errors and not has_sorry

            # Post-agent #eval validation: strip failing #eval statements
            has_eval_stripped = False

            if has_errors and "#eval" in lean_code:
                # Code has errors with #eval present - check if errors are #eval-related
                eval_statements = detect_eval_statements(lean_code)

                if eval_statements:
                    # Check diagnostics for #eval-related errors
                    # Common patterns: "failed to synthesize instance", errors mentioning #eval
                    has_eval_errors = bool(
                        re.search(
                            r"#eval.*error|error.*#eval|failed to synthesize.*instance",
                            diagnostics,
                            re.IGNORECASE,
                        )
                    )

                    if has_eval_errors:
                        # Strip all #eval statements
                        lean_code = re.sub(
                            r"^#eval\s+[^\n]+\n?", "", lean_code, flags=re.MULTILINE
                        )

                        # Rewrite file without #eval
                        impl_file.write_text(lean_code)
                        has_eval_stripped = True

                        # Validate stripped version compiles
                        stripped_result = call_lean_lsp_mcp(
                            workspace=workspace,
                            tool_name="lean_diagnostic_messages",
                            arguments={"file_path": str(impl_file)},
                        )

                        # Update diagnostics with stripped version
                        stripped_content = stripped_result.get("content", [])
                        if (
                            stripped_content
                            and isinstance(stripped_content, list)
                            and len(stripped_content) > 0
                        ):
                            diagnostics = stripped_content[0].get("text", "")
                            has_errors = bool(
                                re.search(r"\berror:", diagnostics, re.IGNORECASE)
                            )
                            # Recalculate success after stripping #eval
                            success = not has_errors and not has_sorry

            result = FunctionImplResult(
                success=success,
                lean_code=lean_code,
                compiles=not has_errors,
                has_sorry=has_sorry,
                attempts=attempts,
                tool_calls=tool_calls_count,
                error=None if success else "Has errors or sorry",
                has_eval_stripped=has_eval_stripped,
            )

        except Exception as e:
            result = FunctionImplResult(
                success=False,
                lean_code=lean_code,
                compiles=False,
                has_sorry=False,
                attempts=attempts,
                tool_calls=tool_calls_count,
                error=f"Failed to validate: {e}",
            )

        # Store result in metadata for orchestration and quality assessment
        state.metadata["impl_result"] = result.model_dump()

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


def _extract_code_from_history(messages: list) -> str | None:
    """Extract Lean code by walking backwards through message history.

    Searches assistant messages in reverse chronological order for the most
    recent message containing <code>...</code> tags. This captures the agent's
    last validated implementation without requiring redundant final output.

    Args:
        messages: Full conversation history (list of ChatMessage objects)

    Returns:
        Extracted code from most recent <code> block, or None if not found
    """
    # Walk backwards through messages
    for msg in reversed(messages):
        # Only check assistant messages
        if not hasattr(msg, "role") or msg.role != "assistant":
            continue

        # Skip if no text content
        if not hasattr(msg, "text") or not msg.text:
            continue

        # Try to extract code from this message
        match = re.search(r"<code>(.*?)</code>", msg.text, re.DOTALL)
        if match:
            return match.group(1).strip()

    # No <code> blocks found in any assistant message
    return None
