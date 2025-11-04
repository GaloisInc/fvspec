"""Implementation agent for function under test.

This agent generates complete Lean implementations (zero sorry) for the
function being tested, using function discovery and dependency context.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from inspect_ai._util.registry import registry_info  # type: ignore
from inspect_ai.model import (
    ChatMessageSystem,
    ChatMessageTool,
    ChatMessageUser,
    get_model,
)
from inspect_ai.tool import ToolCallError, ToolCallView
from pydantic import BaseModel, Field

from generate.templates.impl import get_impl_function_prompts

logger = logging.getLogger(__name__)


class FunctionImplPayload(BaseModel):
    """Payload for function implementation generation."""

    pbt_code: str = Field(description="Property-based test code")
    pbt_name: str = Field(description="Test function name")
    function_name: str = Field(description="Function under test name")
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


async def function_impl_agent(
    payload: FunctionImplPayload,
    workspace: Path,
    max_attempts: int = 32,
) -> FunctionImplResult:
    """Generate Lean implementation for function under test.

    Goal: Complete, computable implementation (ZERO sorry).
    This should be a def with full implementation body.

    Loops until:
    - Code compiles (no type errors)
    - Has zero sorry (fully implemented)

    Args:
        payload: Function implementation payload
        workspace: Workspace path for LSP
        max_attempts: Maximum refinement iterations

    Returns:
        Function implementation result
    """
    # Get impl prompts based on variant
    system_prompt, user_template = get_impl_function_prompts(payload.variant)

    # Prepare template context
    context = {
        "pbt_code": payload.pbt_code,
        "pbt_name": payload.pbt_name,
        "function_name": payload.function_name,
        "function_code": payload.function_code,
        "dependencies": payload.dependencies,
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
        return FunctionImplResult(
            success=False,
            lean_code=None,
            compiles=False,
            has_sorry=False,
            attempts=0,
            tool_calls=0,
            error="No model configured",
        )

    # Get LSP tools from workspace
    from generate.scaffold.tools.declaration import lean_lsp_mcp_tools

    tools = lean_lsp_mcp_tools()

    # Build tool name lookup
    tools_by_name = {}
    for t in tools:
        info = registry_info(t)
        if info and info.name:
            tool_name = info.name.split("/")[-1] if "/" in info.name else info.name
            tools_by_name[tool_name] = t

    # Run iterative refinement loop
    attempts = 0
    tool_calls_count = 0
    impl_file = workspace / "Fvspec" / "Impl.lean"

    for attempt in range(max_attempts):
        attempts = attempt + 1

        # Generate response
        response = await model.generate(messages, tools=tools)
        messages.append(response.message)

        # Check if model wants to call tools
        if response.message.tool_calls:
            tool_calls_count += len(response.message.tool_calls)

            # Execute all tool calls
            tool_results = []
            for tool_call in response.message.tool_calls:
                tool = tools_by_name.get(tool_call.function)
                if tool:
                    try:
                        view = ToolCallView(call=tool_call.view)
                        result = await tool(**{**tool_call.arguments, "view": view})
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
                                error=ToolCallError(message=str(e), type="unknown"),
                            )
                        )
                else:
                    available_tools = ", ".join(tools_by_name.keys())
                    tool_results.append(
                        ChatMessageTool(
                            tool_call_id=tool_call.id,
                            function=tool_call.function,
                            content=f"Tool '{tool_call.function}' not available. Available: {available_tools}",
                            error=ToolCallError(
                                message=f"Tool '{tool_call.function}' not found",
                                type="unknown",
                            ),
                        )
                    )

            messages.extend(tool_results)
        else:
            # No tool calls - agent is done
            # Extract code from response
            final_text = response.message.text or ""
            lean_code = _extract_code_block(final_text)

            if not lean_code:
                return FunctionImplResult(
                    success=False,
                    lean_code=None,
                    compiles=False,
                    has_sorry=False,
                    attempts=attempts,
                    tool_calls=tool_calls_count,
                    error="No code block found in final response",
                )

            # Validate the generated code
            # We need to check if it compiles AND has zero sorry
            impl_file.parent.mkdir(parents=True, exist_ok=True)
            impl_file.write_text(lean_code)

            # Call lean_diagnostic_messages to check compilation
            from generate.scaffold.tools.declaration import call_lean_lsp_mcp

            try:
                result = call_lean_lsp_mcp(
                    workspace=workspace,
                    tool_name="lean_diagnostic_messages",
                    arguments={"file_path": str(impl_file)},
                )
                diagnostics = ""
                content = result.get("content", [])
                if content and isinstance(content, list) and len(content) > 0:
                    diagnostics = content[0].get("text", "")

                # Check for errors
                has_errors = bool(re.search(r"\berror:", diagnostics, re.IGNORECASE))

                # Check for sorry
                has_sorry = bool(re.search(r"\bsorry\b", lean_code))

                # Success if: compiles AND zero sorry
                success = not has_errors and not has_sorry

                return FunctionImplResult(
                    success=success,
                    lean_code=lean_code,
                    compiles=not has_errors,
                    has_sorry=has_sorry,
                    attempts=attempts,
                    tool_calls=tool_calls_count,
                    error=None if success else "Has errors or sorry",
                )

            except Exception as e:
                return FunctionImplResult(
                    success=False,
                    lean_code=lean_code,
                    compiles=False,
                    has_sorry=False,
                    attempts=attempts,
                    tool_calls=tool_calls_count,
                    error=f"Failed to validate: {e}",
                )

    # Max attempts reached
    return FunctionImplResult(
        success=False,
        lean_code=None,
        compiles=False,
        has_sorry=False,
        attempts=attempts,
        tool_calls=tool_calls_count,
        error=f"Max attempts ({max_attempts}) reached",
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
