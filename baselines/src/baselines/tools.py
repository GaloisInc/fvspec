"""Lean LSP MCP tool wrappers for inspect_ai.

Adapted from benchmark/src/generate/scaffold/tools/declaration.py.
"""

import json
import os
import subprocess
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from inspect_ai.solver._task_state import sample_state
from inspect_ai.tool import ToolCallView, ToolError, tool


def call_lean_lsp_mcp(
    workspace: Path, tool_name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Call a lean-lsp-mcp tool with the given workspace context.

    Args:
        workspace: Path to the Lake project workspace
        tool_name: Name of the MCP tool to call
        arguments: Tool arguments as a dictionary

    Returns:
        The tool result as a dictionary

    Raises:
        ToolError: If the MCP call fails
    """
    env = os.environ.copy()
    env["LEAN_PROJECT_PATH"] = str(workspace)
    env["LEAN_LOG_LEVEL"] = "ERROR"

    initialize_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "fvspec-baselines", "version": "1.0.0"},
        },
    }

    initialized_notification = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
    }

    tool_call_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }

    try:
        process = subprocess.Popen(
            ["uvx", "lean-lsp-mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
        )

        requests = (
            json.dumps(initialize_request)
            + "\n"
            + json.dumps(initialized_notification)
            + "\n"
            + json.dumps(tool_call_request)
            + "\n"
        )
        stdout, stderr = process.communicate(input=requests, timeout=30)

        for line in stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                response = json.loads(line)
                if response.get("id") == 2:
                    if "error" in response:
                        raise ToolError(f"MCP error: {response['error']}")
                    return response.get("result", {})
            except json.JSONDecodeError:
                continue

        raise ToolError(f"No valid response from lean-lsp-mcp. stderr: {stderr}")

    except subprocess.TimeoutExpired:
        process.kill()
        raise ToolError("lean-lsp-mcp call timed out")
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Failed to call lean-lsp-mcp: {e}")


def _get_workspace() -> Path:
    """Get workspace path from current sample state."""
    state = sample_state()
    if not state:
        raise ToolError("No task state available")
    workspace_path = state.metadata.get("workspace")
    if not workspace_path:
        raise ToolError("No workspace path found in metadata")
    return Path(workspace_path)


def _extract_text(result: dict[str, Any], fallback: str = "No results") -> str:
    """Extract text content from MCP result."""
    content = result.get("content", [])
    if content and isinstance(content, list) and len(content) > 0:
        return str(content[0].get("text", fallback))
    return fallback


@tool  # type: ignore[arg-type]
def write_lean_spec() -> Callable[[str, ToolCallView], Awaitable[str]]:
    """Write Lean code to Spec.lean in the workspace."""

    async def execute(code: str, view: ToolCallView) -> str:
        """Write Lean specification code to the workspace Spec.lean file.

        Args:
            code: The Lean code to write to Fvspec/Spec.lean
            view: Tool call context (provided by inspect_ai)

        Returns:
            Success message with file path and size
        """
        workspace = _get_workspace()
        spec_file = workspace / "Fvspec" / "Spec.lean"
        spec_file.parent.mkdir(parents=True, exist_ok=True)
        spec_file.write_text(code)
        return f"Wrote {len(code)} characters to {spec_file.relative_to(workspace)}"

    return execute


@tool  # type: ignore[arg-type]
def lean_diagnostic_messages() -> Callable[[str, ToolCallView], Awaitable[str]]:
    """Get diagnostic messages for a Lean file."""

    async def execute(file_path: str, view: ToolCallView) -> str:
        """Get all diagnostic messages (infos, warnings, errors) for a Lean file.

        Args:
            file_path: Path to the Lean file (relative to workspace or absolute)
            view: Tool call context (provided by inspect_ai)

        Returns:
            Diagnostic messages as formatted text
        """
        workspace = _get_workspace()
        result = call_lean_lsp_mcp(
            workspace=workspace,
            tool_name="lean_diagnostic_messages",
            arguments={"file_path": file_path},
        )
        return _extract_text(result, "No diagnostics")

    return execute


@tool  # type: ignore[arg-type]
def lean_goal() -> Callable[[str, int, int | None, ToolCallView], Awaitable[str]]:
    """Get proof goal at a specific location in a Lean file."""

    async def execute(
        file_path: str, line: int, column: int | None, view: ToolCallView
    ) -> str:
        """Get the proof goal at a specific location.

        Args:
            file_path: Path to the Lean file
            line: Line number
            column: Optional column number
            view: Tool call context (provided by inspect_ai)

        Returns:
            Goal state information
        """
        workspace = _get_workspace()
        arguments: dict[str, Any] = {"file_path": file_path, "line": line}
        if column is not None:
            arguments["column"] = column
        result = call_lean_lsp_mcp(
            workspace=workspace, tool_name="lean_goal", arguments=arguments
        )
        return _extract_text(result, "No goal information")

    return execute


@tool  # type: ignore[arg-type]
def lean_multi_attempt() -> Callable[
    [str, int, list[str], ToolCallView], Awaitable[str]
]:
    """Try multiple proof tactics and return goal states for each."""

    async def execute(
        file_path: str, line: int, snippets: list[str], view: ToolCallView
    ) -> str:
        """Attempt multiple Lean code snippets at a line and return diagnostics.

        Args:
            file_path: Path to the Lean file
            line: Line number where to attempt the snippets
            snippets: List of Lean code snippets to try
            view: Tool call context (provided by inspect_ai)

        Returns:
            Goal states and diagnostics for each snippet
        """
        workspace = _get_workspace()
        result = call_lean_lsp_mcp(
            workspace=workspace,
            tool_name="lean_multi_attempt",
            arguments={"file_path": file_path, "line": line, "snippets": snippets},
        )
        return _extract_text(result)

    return execute


@tool  # type: ignore[arg-type]
def lean_local_search() -> Callable[[str, ToolCallView], Awaitable[str]]:
    """Search for Lean definitions and theorems in the local project and stdlib."""

    async def execute(query: str, view: ToolCallView) -> str:
        """Search for definitions and theorems matching the query.

        Args:
            query: Search query (identifier or pattern)
            view: Tool call context (provided by inspect_ai)

        Returns:
            Matching declarations from the local project and standard library
        """
        workspace = _get_workspace()
        result = call_lean_lsp_mcp(
            workspace=workspace,
            tool_name="lean_local_search",
            arguments={"query": query},
        )
        return _extract_text(result, "No results found")

    return execute


def baselines_tools() -> list:
    """Get all tools for the proof-writing agent."""
    return [
        write_lean_spec(),
        lean_diagnostic_messages(),
        lean_goal(),
        lean_multi_attempt(),
        lean_local_search(),
    ]
