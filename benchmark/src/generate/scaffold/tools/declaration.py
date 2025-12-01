"""Utility functions for persisting benchmark artifacts and tooling hooks."""

import json
import os
import re
import subprocess
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, cast

from inspect_ai.scorer import Score
from inspect_ai.solver import TaskState
from inspect_ai.solver._task_state import sample_state
from inspect_ai.tool import ToolCallView, ToolError, tool

from generate.scaffold.dataset import Datapoint
from generate.scaffold.quality_assessment import QualityAssessment
from generate.scaffold.quality_assessment.lean_parsing import (
    detect_eval_statements,
)
from generate.scaffold.tools import utilio
from generate.scaffold.wandb_logger import log_sample_to_wandb


def call_lean_lsp_mcp(
    workspace: Path, tool_name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    """Call a lean-lsp-mcp tool with the given workspace context.

    Args:
        workspace: Path to the Lake project workspace
        tool_name: Name of the MCP tool to call (e.g., "lean_diagnostic_messages")
        arguments: Tool arguments as a dictionary

    Returns:
        The tool result as a dictionary

    Raises:
        ToolError: If the MCP call fails
    """
    # Set up environment with project path
    env = os.environ.copy()
    env["LEAN_PROJECT_PATH"] = str(workspace)
    env["LEAN_LOG_LEVEL"] = "ERROR"  # Reduce noise

    # MCP requires a proper initialization handshake before tool calls:
    # 1. Send initialize request (id=1)
    # 2. Send initialized notification (no id)
    # 3. Send tool call request (id=2)

    initialize_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "fvspec-benchmark", "version": "1.0.0"},
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
        # Spawn lean-lsp-mcp subprocess
        process = subprocess.Popen(
            ["uvx", "lean-lsp-mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
        )

        # Send all requests as newline-separated JSON objects
        requests = (
            json.dumps(initialize_request)
            + "\n"
            + json.dumps(initialized_notification)
            + "\n"
            + json.dumps(tool_call_request)
            + "\n"
        )
        stdout, stderr = process.communicate(input=requests, timeout=30)

        # Parse JSON-RPC responses
        # We're looking for the tool call response with id=2
        for line in stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                response = json.loads(line)
                # Look for tool call response (id=2)
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
    except Exception as e:
        raise ToolError(f"Failed to call lean-lsp-mcp: {e}")


@tool  # type: ignore[arg-type]
def lean_diagnostic_messages() -> Callable[[str, ToolCallView], Awaitable[str]]:
    """Get diagnostic messages for a Lean file using per-sample workspace."""

    async def execute(file_path: str, view: ToolCallView) -> str:
        # view: Required by inspect_ai but not used in this tool
        """Get all diagnostic messages (infos, warnings, errors) for a Lean file.

        Args:
            file_path: Path to the Lean file (relative to workspace or absolute)
            view: Tool call context (provided by inspect_ai)

        Returns:
            Diagnostic messages as formatted text
        """
        state = sample_state()
        if not state:
            raise ToolError("No task state available")

        # Get workspace path
        workspace_path = state.metadata.get("workspace")
        if not workspace_path:
            raise ToolError("No workspace path found in metadata")

        workspace = Path(workspace_path)

        # Call lean-lsp-mcp with this sample's workspace
        result = call_lean_lsp_mcp(
            workspace=workspace,
            tool_name="lean_diagnostic_messages",
            arguments={"file_path": file_path},
        )

        content = result.get("content", [])
        if content and isinstance(content, list) and len(content) > 0:
            return str(content[0].get("text", "No diagnostics"))
        return "No diagnostics"

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
        state = sample_state()
        if not state:
            raise ToolError("No task state available")

        workspace_path = state.metadata.get("workspace")
        if not workspace_path:
            raise ToolError("No workspace path found in metadata")

        workspace = Path(workspace_path)

        arguments = {"file_path": file_path, "line": line}
        if column is not None:
            arguments["column"] = column

        result = call_lean_lsp_mcp(
            workspace=workspace, tool_name="lean_goal", arguments=arguments
        )

        content = result.get("content", [])
        if content and isinstance(content, list) and len(content) > 0:
            return str(content[0].get("text", "No goal information"))
        return "No goal information"

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

        This tool is useful to screen different proof attempts before committing
        to the most promising one.

        Args:
            file_path: Path to the Lean file
            line: Line number where to attempt the snippets
            snippets: List of Lean code snippets to try
            view: Tool call context (provided by inspect_ai)

        Returns:
            Goal states and diagnostics for each snippet
        """
        state = sample_state()
        if not state:
            raise ToolError("No task state available")

        workspace_path = state.metadata.get("workspace")
        if not workspace_path:
            raise ToolError("No workspace path found in metadata")

        workspace = Path(workspace_path)

        result = call_lean_lsp_mcp(
            workspace=workspace,
            tool_name="lean_multi_attempt",
            arguments={"file_path": file_path, "line": line, "snippets": snippets},
        )

        content = result.get("content", [])
        if content and isinstance(content, list) and len(content) > 0:
            return str(content[0].get("text", "No results"))
        return "No results"

    return execute


@tool  # type: ignore[arg-type]
def lean_local_search() -> Callable[[str, ToolCallView], Awaitable[str]]:
    """Search for Lean definitions and theorems in the local project and stdlib."""

    async def execute(query: str, view: ToolCallView) -> str:
        """Search for definitions and theorems matching the query.

        This tool helps find existing declarations to prevent hallucinating APIs.
        Requires ripgrep (rg) to be installed.

        Args:
            query: Search query (identifier or pattern)
            view: Tool call context (provided by inspect_ai)

        Returns:
            Matching declarations from the local project and standard library
        """
        state = sample_state()
        if not state:
            raise ToolError("No task state available")

        workspace_path = state.metadata.get("workspace")
        if not workspace_path:
            raise ToolError("No workspace path found in metadata")

        workspace = Path(workspace_path)

        result = call_lean_lsp_mcp(
            workspace=workspace,
            tool_name="lean_local_search",
            arguments={"query": query},
        )

        content = result.get("content", [])
        if content and isinstance(content, list) and len(content) > 0:
            return str(content[0].get("text", "No results found"))
        return "No results found"

    return execute


@tool  # type: ignore[arg-type]
def write_lean_impl() -> Callable[[str, ToolCallView], Awaitable[str]]:
    """Write Lean implementation code to Impl.lean in the workspace for LSP analysis.

    This tool allows the impl agent to iteratively develop implementation code by
    writing it to the workspace where MCP tools (lean_diagnostic_messages, etc.)
    can analyze it. The agent should:

    1. Write initial Lean code using this tool
    2. Use lean_diagnostic_messages to check for errors
    3. Refine and rewrite the code as needed
    4. Repeat until satisfied

    The final code will be extracted from <code>...</code> tags during cleanup.
    """

    async def execute(code: str, view: ToolCallView) -> str:
        """Write Lean implementation code to the workspace Impl.lean file.

        Args:
            code: The Lean code to write to Fvspec/Impl.lean
            view: Tool call context (provided by inspect_ai)

        Returns:
            Success message with file path and size, plus warnings if #eval detected
        """
        state = sample_state()
        if not state:
            raise ToolError("No task state available")

        workspace_path = state.metadata.get("workspace")
        if not workspace_path:
            raise ToolError("No workspace path found in metadata")

        workspace = Path(workspace_path)
        impl_file = workspace / "Fvspec" / "Impl.lean"

        # Ensure the directory exists
        impl_file.parent.mkdir(parents=True, exist_ok=True)

        # Write the code
        impl_file.write_text(code)

        # Return simple success message - #eval is allowed and encouraged for computability testing
        return f"Wrote {len(code)} characters to {impl_file.relative_to(workspace)}"

    return execute


@tool  # type: ignore[arg-type]
def write_lean_spec() -> Callable[[str, ToolCallView], Awaitable[str]]:
    """Write Lean code to Spec.lean in the workspace for LSP analysis.

    This tool allows the spec agent to iteratively develop theorem statements by
    writing them to the workspace where MCP tools (lean_diagnostic_messages, etc.)
    can analyze them. The agent should:

    1. Write initial Lean code using this tool
    2. Use lean_diagnostic_messages to check for errors
    3. Use lean_goal to inspect proof states
    4. Refine and rewrite the code as needed
    5. Repeat until satisfied

    The final code will be extracted from <code>...</code> tags during cleanup.
    """

    async def execute(code: str, view: ToolCallView) -> str:
        """Write Lean code to the workspace Spec.lean file.

        Args:
            code: The Lean code to write to Fvspec/Spec.lean
            view: Tool call context (provided by inspect_ai)

        Returns:
            Success message with file path and size
        """
        state = sample_state()
        if not state:
            raise ToolError("No task state available")

        workspace_path = state.metadata.get("workspace")
        if not workspace_path:
            raise ToolError("No workspace path found in metadata")

        workspace = Path(workspace_path)
        spec_file = workspace / "Fvspec" / "Spec.lean"

        # Ensure the directory exists
        spec_file.parent.mkdir(parents=True, exist_ok=True)

        # Check for #eval statements before writing
        eval_statements = detect_eval_statements(code)

        # Write the code
        spec_file.write_text(code)

        # Build response message
        base_msg = f"Wrote {len(code)} characters to {spec_file.relative_to(workspace)}"

        if eval_statements:
            # Store eval violations in metadata for QA
            # Use separate key to distinguish spec vs impl violations
            if "spec_eval_violations" not in state.metadata:
                state.metadata["spec_eval_violations"] = []
            state.metadata["spec_eval_violations"].extend(eval_statements)

            warning = (
                f"\n\n⚠️ WARNING: Detected {len(eval_statements)} #eval statement(s) in specification code.\n"
                f"#eval statements should NOT be included in Spec.lean because:\n"
                f"1. Spec.lean should only contain theorem declarations (with sorry), not executable code\n"
                f"2. If you're including Impl definitions here, they belong in Impl.lean instead\n"
                f"3. #eval indicates testing behavior which belongs in Tests.lean\n\n"
                f"Found:\n"
            )
            for stmt in eval_statements:
                warning += f"  - {stmt}\n"

            warning += "\nPlease remove these #eval statements. Specifications should only declare theorems, not execute code."

            return base_msg + warning

        return base_msg

    return execute


@tool  # type: ignore[arg-type]
def write_lean_tests() -> Callable[[str, ToolCallView], Awaitable[str]]:
    """Write Lean test code to Tests.lean in the workspace for LSP analysis.

    This tool allows the units agent to iteratively develop LSpec test code by
    writing it to the workspace where MCP tools (lean_diagnostic_messages, etc.)
    can analyze it. The agent should:

    1. Write initial test code using this tool
    2. Use lean_diagnostic_messages to check for errors
    3. Refine and rewrite the code as needed
    4. Repeat until satisfied

    The final code will be extracted from <code>...</code> tags during cleanup.
    """

    async def execute(code: str, view: ToolCallView) -> str:
        """Write Lean test code to the workspace Tests.lean file.

        Args:
            code: The Lean test code to write to Fvspec/Tests.lean
            view: Tool call context (provided by inspect_ai)

        Returns:
            Success message with file path and size
        """
        state = sample_state()
        if not state:
            raise ToolError("No task state available")

        workspace_path = state.metadata.get("workspace")
        if not workspace_path:
            raise ToolError("No workspace path found in metadata")

        workspace = Path(workspace_path)
        tests_file = workspace / "Fvspec" / "Tests.lean"

        # Ensure the directory exists
        tests_file.parent.mkdir(parents=True, exist_ok=True)

        # Write the code
        tests_file.write_text(code)

        return f"Wrote {len(code)} characters to {tests_file.relative_to(workspace)}"

    return execute


def workspace_utility_tools() -> list:
    """Construct workspace utility tools for file writing.

    These tools allow agents to write Lean files to the workspace for iterative
    development. They don't interact with LSP/MCP - they just write files.

    Each agent gets all three tools, but should only use their designated file:
    - Impl agent: write_lean_impl() -> Impl.lean
    - Spec agent: write_lean_spec() -> Spec.lean
    - Units agent: write_lean_tests() -> Tests.lean
    """
    return [
        write_lean_impl(),
        write_lean_spec(),
        write_lean_tests(),
    ]


def lean_lsp_mcp_tools() -> list:
    """Construct Lean LSP tools that wrap lean-lsp-mcp server.

    These tools spawn lean-lsp-mcp as a subprocess per call, setting the
    LEAN_PROJECT_PATH environment variable to the sample's workspace.
    This allows parallel execution while maintaining LSP functionality.

    These are wrappers around the actual MCP server tools.
    """
    return [
        lean_diagnostic_messages(),
        lean_goal(),
        lean_multi_attempt(),
        lean_local_search(),
    ]


def all_lean_tools() -> list:
    """Get all tools for Lean development (utility + LSP).

    Combines workspace utility tools (file writing) with LSP analysis tools.
    This is the standard tool set for spec and units agents.
    """
    return workspace_utility_tools() + lean_lsp_mcp_tools()


def write_datapoint_to_disk(
    date_time: str,
    sample_id: str,
    datapoint: Datapoint,
    variant: str,
    ranseed: int | None = None,
    start_idx: int | None = None,
    end_idx: int | None = None,
) -> str:
    """Write datapoint metadata to the sample's artifact directory.

    Args:
        date_time: datetime string used in directory structue.
        sample_id: Identifier for the current sample.
        datapoint: The datapoint from the metadata of the current sample.
        variant: Prompt variant name.
        ranseed: Random seed used for sampling (optional, included in path when provided).
        start_idx: Starting index for sequential sampling (optional).
        end_idx: Ending index for sequential sampling (optional).

    Returns:
        A message describing whether the write succeeded.
    """
    datapoint_file = utilio.get_output_filepath(
        date_time,
        sample_id,
        "datapoint.json",
        variant=variant,
        ranseed=ranseed,
        start_idx=start_idx,
        end_idx=end_idx,
    )
    return utilio.writeit(datapoint_file, datapoint.model_dump_json(indent=4))


def write_code_to_disk(
    date_time: str,
    sample_id: str,
    text: str,
    variant: str,
    workspace: Path | None = None,
    ranseed: int | None = None,
    start_idx: int | None = None,
    end_idx: int | None = None,
) -> str:
    """Write the `<code>...</code>` snippet from text into `Spec.lean`.

    Extracts the final Lean code from <code>...</code> tags in the agent's
    output and saves it to the artifacts directory for permanent storage.

    If no <code> block is found but the workspace contains a Spec.lean file
    (written via write_lean_spec tool during execution), uses that as a fallback.

    Args:
        date_time: datetime string used in directory structue.
        sample_id: Identifier for the current sample.
        text: The output text possibly containing <code>...</code>.
        variant: Prompt variant name.
        workspace: Optional workspace tmpdir path for fallback.
        ranseed: Random seed used for sampling (optional, included in path when provided).
        start_idx: Starting index for sequential sampling (optional).
        end_idx: Ending index for sequential sampling (optional).

    Returns:
        A message describing whether the write succeeded.
    """
    # Look for <code>...</code>
    pattern = r"(?s)<code>(.*?)</code>"
    mtch = re.search(pattern, text)

    if mtch:
        # Prefer explicit <code> block from agent's final message
        code_snippet = mtch.group(1)
    elif workspace:
        # Fallback: check if agent wrote to workspace via write_lean_spec
        workspace_spec = workspace / "Fvspec" / "Spec.lean"
        if workspace_spec.exists():
            code_snippet = workspace_spec.read_text()
        else:
            return utilio.no_code_block_found(sample_id, text)
    else:
        return utilio.no_code_block_found(sample_id, text)

    # Write to artifacts directory (permanent storage)
    spec_file = utilio.get_output_filepath(
        date_time,
        sample_id,
        "Spec.lean",
        variant=variant,
        ranseed=ranseed,
        start_idx=start_idx,
        end_idx=end_idx,
    )
    result = utilio.writeit(spec_file, code_snippet)

    return result


def write_qa_to_disk(
    date_time: str,
    sample_id: str,
    state: TaskState,
    variant: str,
    ranseed: int | None = None,
    start_idx: int | None = None,
    end_idx: int | None = None,
) -> str:
    """Write quality-assessment results to `qa.json` for the sample.

    Args:
        date_time: datetime string used in directory structue.
        sample_id: Identifier for the current sample.
        state: The task state after completion.
        variant: Prompt variant name.
        ranseed: Random seed used for sampling (optional, included in path when provided).
        start_idx: Starting index for sequential sampling (optional).
        end_idx: Ending index for sequential sampling (optional).

    Returns:
        A message describing whether the write succeeded.
    """
    # Fill in QA info
    qa = QualityAssessment.from_task_state(state)

    qa_file = utilio.get_output_filepath(
        date_time,
        sample_id,
        "qa.json",
        variant=variant,
        ranseed=ranseed,
        start_idx=start_idx,
        end_idx=end_idx,
    )
    return utilio.writeit(qa_file, qa.model_dump_json(indent=4))


def write_unit_tests_to_disk(
    date_time: str,
    sample_id: str,
    state: TaskState,
    variant: str,
    workspace: Path | None = None,
    ranseed: int | None = None,
    start_idx: int | None = None,
    end_idx: int | None = None,
) -> str:
    """Write generated unit tests to `Tests.lean` for the sample.

    Unit tests are generated by the LLM-based units agent from Python PBTs.
    This replaces the deprecated AST extraction system.

    Always writes Tests.lean even if empty (lake-template expects it).

    Args:
        date_time: datetime string used in directory structure.
        sample_id: Identifier for the current sample.
        state: The task state containing units_result in store.
        variant: Prompt variant name.
        workspace: Optional workspace tmpdir path for MCP tools.
        ranseed: Random seed used for sampling (optional, included in path when provided).
        start_idx: Starting index for sequential sampling (optional).
        end_idx: Ending index for sequential sampling (optional).

    Returns:
        A message describing whether the write succeeded.
    """
    # Extract units result from store (generated by units agent)
    units_result_data = state.store.get("units_result", {})
    units_result_lean = (
        units_result_data.get("lean_code")
        if isinstance(units_result_data, dict)
        else None
    )
    datapoint = cast(Datapoint, state.metadata.get("datapoint"))

    # Generate Tests.lean content
    # Note: Imports are provided by lake-template/Fvspec/Tests.lean
    if units_result_lean:
        # We have generated tests from units agent - add metadata
        func_name = datapoint.name.removeprefix("test_")

        # Count tests in generated code
        num_tests = (
            units_result_data.get("test_count", 0)
            if isinstance(units_result_data, dict)
            else 0
        )

        tests_content = f"""-- Unit tests generated by LLM from property-based test
-- Function: {func_name}
-- Generation method: LLM-based units agent
-- Tests: {num_tests}

{units_result_lean}
"""
    else:
        # No tests generated - write explanation
        error_msg = (
            units_result_data.get("error", "Unknown error")
            if isinstance(units_result_data, dict)
            else "No units result"
        )
        tests_content = f"""-- No unit tests could be generated from the property-based test
-- Reason: {error_msg}
--
-- The units agent was unable to extract or generate meaningful test cases.
-- This may be because:
--   - The test uses only Hypothesis strategies (no concrete examples)
--   - The test logic is too complex to translate
--   - The LLM was unable to infer appropriate test cases
"""

    # Write to artifacts directory (permanent storage)
    # For artifacts, prepend the template imports since we're writing from scratch
    template_imports = """import LSpec
import Fvspec.Spec

"""
    tests_file = utilio.get_output_filepath(
        date_time,
        sample_id,
        "Tests.lean",
        variant=variant,
        ranseed=ranseed,
        start_idx=start_idx,
        end_idx=end_idx,
    )
    result = utilio.writeit(tests_file, template_imports + tests_content)

    # Also write to workspace if provided (for potential MCP usage)
    # For workspace, append to existing template file to preserve imports
    if workspace:
        workspace_tests = workspace / "Fvspec" / "Tests.lean"
        if workspace_tests.exists():
            # Append to existing template content
            existing = workspace_tests.read_text()
            workspace_tests.write_text(existing + "\n" + tests_content)
        else:
            # Template not copied yet, write with imports
            workspace_tests.parent.mkdir(parents=True, exist_ok=True)
            workspace_tests.write_text(template_imports + tests_content)

    return result


def _qa_to_scores(qa: QualityAssessment) -> dict[str, Score]:
    """Convert QualityAssessment metrics to inspect_ai Score objects.

    This function now delegates to QualityAssessment.to_inspect_scores()
    to maintain a single source of truth for metric definitions.

    Args:
        qa: Quality assessment with computed metrics

    Returns:
        Dictionary mapping score names to Score objects for inspect_ai viewer
    """
    return qa.to_inspect_scores()


async def write_to_disk(state: TaskState) -> None:
    """Persist sample outputs and register quality metrics for inspect_ai.

    Writes the datapoint metadata, extracted Lean code, and QA report to disk
    for the current sample. The function also registers quality scores for the
    inspect_ai viewer and cleans up any temporary workspaces.

    Tmpdir Cleanup (Normal Path):
    This is the cleanup phase of the tmpdir lifecycle:
    1. Extracts workspace path from state.metadata["workspace"]
    2. Writes Lean code to both artifacts dir (permanent) and workspace (for MCP)
    3. Calls cleanup_sample_workspace() which:
       - Removes the tmpdir
       - Unregisters from atexit _active_workspaces tracking
    4. If cleanup fails, atexit handler ensures cleanup on process exit

    Additionally logs metrics to wandb if enabled.

    Args:
        state: The current state after a sample completes.
    """
    date_time = cast(str, state.metadata.get("date_time"))
    datapoint = cast(Datapoint, state.metadata.get("datapoint"))
    variant = cast(str, state.metadata.get("variant"))
    ranseed = state.metadata.get("ranseed")  # May be None
    start_idx = state.metadata.get("start_idx")  # May be None
    end_idx = state.metadata.get("end_idx")  # May be None
    sample_id = str(state.sample_id)

    # Get workspace path if available
    workspace_path = state.metadata.get("workspace")
    workspace = Path(workspace_path) if workspace_path else None

    # Write datapoint metadata (return value available for future logging)
    _ = write_datapoint_to_disk(
        date_time,
        sample_id,
        datapoint,
        variant=variant,
        ranseed=ranseed,
        start_idx=start_idx,
        end_idx=end_idx,
    )

    # Only write code and QA if we have output
    if state.output and state.output.choices:
        # Write generated Spec.lean code (return value available for future logging)
        _ = write_code_to_disk(
            date_time,
            sample_id,
            state.output.message.text,
            variant=variant,
            workspace=workspace,
            ranseed=ranseed,
            start_idx=start_idx,
            end_idx=end_idx,
        )

        # Also copy Impl.lean from workspace if it exists
        if workspace:
            workspace_impl = workspace / "Fvspec" / "Impl.lean"
            if workspace_impl.exists():
                impl_code = workspace_impl.read_text()
                impl_file = utilio.get_output_filepath(
                    date_time,
                    sample_id,
                    "Impl.lean",
                    variant=variant,
                    ranseed=ranseed,
                    start_idx=start_idx,
                    end_idx=end_idx,
                )
                _ = utilio.writeit(impl_file, impl_code)

        # Write extracted unit tests (return value available for future logging)
        _ = write_unit_tests_to_disk(
            date_time,
            sample_id,
            state,
            variant=variant,
            workspace=workspace,
            ranseed=ranseed,
            start_idx=start_idx,
            end_idx=end_idx,
        )

        # Write quality assessment report (return value available for future logging)
        _ = write_qa_to_disk(
            date_time,
            sample_id,
            state,
            variant=variant,
            ranseed=ranseed,
            start_idx=start_idx,
            end_idx=end_idx,
        )

        # Extract quality assessment and register metrics as scores
        qa = QualityAssessment.from_task_state(state)
        state.scores = _qa_to_scores(qa)

        # Log to wandb if enabled
        log_sample_to_wandb(state)

    # Clean up workspace if it exists
    workspace_path = state.metadata.get("workspace")
    if workspace_path:
        utilio.cleanup_sample_workspace(Path(workspace_path))

    # Safety net: Close database session if still open
    # (Should already be closed in orchestration, but ensure cleanup)
    db_session = state.metadata.get("db_session")
    if db_session:
        try:
            db_session.close()
        except Exception:
            pass  # Ignore errors on safety net cleanup
