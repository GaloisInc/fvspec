"""Utility functions for persisting benchmark artifacts and tooling hooks."""

import os
import re
import json
import subprocess
from pathlib import Path
from typing import Callable, Awaitable, cast, Any
from inspect_ai.tool import tool, ToolError, mcp_server_stdio, mcp_tools
from inspect_ai.solver import TaskState
from inspect_ai.scorer import Score
from inspect_ai.solver._task_state import sample_state
from generate.scaffold.dataset import Datapoint
from generate.scaffold.quality_assessment import QualityAssessment
from generate.scaffold.tools import utilio


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
def lean_diagnostic_messages() -> Callable[[str], Awaitable[str]]:
    """Get diagnostic messages for a Lean file using per-sample workspace."""

    async def execute(file_path: str) -> str:
        """Get all diagnostic messages (infos, warnings, errors) for a Lean file.

        Args:
            file_path: Path to the Lean file (relative to workspace or absolute)

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

        return str(result.get("content", [{}])[0].get("text", "No diagnostics"))

    return execute


@tool  # type: ignore[arg-type]
def lean_goal() -> Callable[[str, int, int | None], Awaitable[str]]:
    """Get proof goal at a specific location in a Lean file."""

    async def execute(file_path: str, line: int, column: int | None = None) -> str:
        """Get the proof goal at a specific location.

        Args:
            file_path: Path to the Lean file
            line: Line number
            column: Optional column number

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

        return str(result.get("content", [{}])[0].get("text", "No goal information"))

    return execute


@tool  # type: ignore[arg-type]
def lean_multi_attempt() -> Callable[[str, int, list[str]], Awaitable[str]]:
    """Try multiple proof tactics and return goal states for each."""

    async def execute(file_path: str, line: int, snippets: list[str]) -> str:
        """Attempt multiple Lean code snippets at a line and return diagnostics.

        This tool is useful to screen different proof attempts before committing
        to the most promising one.

        Args:
            file_path: Path to the Lean file
            line: Line number where to attempt the snippets
            snippets: List of Lean code snippets to try

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

        return str(result.get("content", [{}])[0].get("text", "No results"))

    return execute


@tool  # type: ignore[arg-type]
def lean_local_search() -> Callable[[str], Awaitable[str]]:
    """Search for Lean definitions and theorems in the local project and stdlib."""

    async def execute(query: str) -> str:
        """Search for definitions and theorems matching the query.

        This tool helps find existing declarations to prevent hallucinating APIs.
        Requires ripgrep (rg) to be installed.

        Args:
            query: Search query (identifier or pattern)

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

        return str(result.get("content", [{}])[0].get("text", "No results found"))

    return execute


def lean_lsp_mcp_tools() -> list:
    """Construct custom Lean LSP tools that work with per-sample workspaces.

    These tools spawn lean-lsp-mcp as a subprocess per call, setting the
    LEAN_PROJECT_PATH environment variable to the sample's workspace.
    This allows parallel execution while maintaining LSP functionality.
    """
    return [
        lean_diagnostic_messages(),
        lean_goal(),
        lean_multi_attempt(),
        lean_local_search(),
    ]


def write_datapoint_to_disk(
    date_time: str,
    sample_id: str,
    datapoint: Datapoint,
    variant: str,
) -> str:
    """Write datapoint metadata to the sample's artifact directory.

    Args:
        date_time: datetime string used in directory structue.
        sample_id: Identifier for the current sample.
        datapoint: The datapoint from the metadata of the current sample.
        variant: Prompt variant name.

    Returns:
        A message describing whether the write succeeded.
    """
    datapoint_file = utilio.get_output_filepath(
        date_time, sample_id, "datapoint.json", variant=variant
    )
    return utilio.writeit(datapoint_file, datapoint.model_dump_json(indent=4))


def write_code_to_disk(
    date_time: str,
    sample_id: str,
    text: str,
    variant: str,
) -> str:
    """Write the `<code>...</code>` snippet from text into `Spec.lean`.

    Args:
        date_time: datetime string used in directory structue.
        sample_id: Identifier for the current sample.
        text: The output text possibly containing <code>...</code>.
        variant: Prompt variant name.

    Returns:
        A message describing whether the write succeeded.
    """
    # Look for <code>...</code>
    pattern = r"(?s)<code>(.*?)</code>"
    mtch = re.search(pattern, text)
    if not mtch:
        return utilio.no_code_block_found(sample_id, text)
    code_snippet = mtch.group(1)

    spec_file = utilio.get_output_filepath(
        date_time, sample_id, "Spec.lean", variant=variant
    )
    return utilio.writeit(spec_file, code_snippet)


def write_qa_to_disk(
    date_time: str,
    sample_id: str,
    state: TaskState,
    variant: str,
) -> str:
    """Write quality-assessment results to `qa.json` for the sample.

    Args:
        date_time: datetime string used in directory structue.
        sample_id: Identifier for the current sample.
        state: The task state after completion.
        variant: Prompt variant name.

    Returns:
        A message describing whether the write succeeded.
    """
    # Fill in QA info
    qa = QualityAssessment.from_task_state(state)

    qa_file = utilio.get_output_filepath(
        date_time, sample_id, "qa.json", variant=variant
    )
    return utilio.writeit(qa_file, qa.model_dump_json(indent=4))


def _qa_to_scores(qa: QualityAssessment) -> dict[str, Score]:
    """Convert QualityAssessment metrics to inspect_ai Score objects.

    Args:
        qa: Quality assessment with computed metrics

    Returns:
        Dictionary mapping score names to Score objects for inspect_ai viewer
    """
    scores = {
        "token_usage": Score(
            value=qa.token_usage,
            explanation=f"Total tokens used: {qa.token_usage}",
        ),
        "time": Score(
            value=qa.time,
            explanation=f"Execution time: {qa.time:.2f}s",
        ),
        "num_messages": Score(
            value=qa.num_messages,
            explanation=f"Total messages exchanged: {qa.num_messages}",
        ),
        "success": Score(
            value="C" if qa.success else "I",
            explanation="Successfully generated Lean code in <code> tags"
            if qa.success
            else "Failed to generate valid Lean code",
        ),
        "num_sorries": Score(
            value=qa.num_sorries,
            explanation=f"Number of 'sorry' placeholders in generated code: {qa.num_sorries}",
        ),
        "lines_code": Score(
            value=qa.lines_code,
            explanation=f"Lines of Lean code generated: {qa.lines_code}",
        ),
        "num_deps": Score(
            value=qa.num_deps,
            explanation=f"Number of dependencies in sample: {qa.num_deps}",
        ),
    }

    # Add optional metrics if available
    if qa.percent_lines_added is not None:
        scores["percent_lines_added"] = Score(
            value=qa.percent_lines_added,
            explanation=f"Percent lines added relative to Python test: {qa.percent_lines_added:.1%}",
        )

    if qa.faithfulness_subjective is not None:
        scores["faithfulness_subjective"] = Score(
            value=qa.faithfulness_subjective,
            explanation=f"AI self-reported faithfulness (0-10): {qa.faithfulness_subjective:.1f}",
        )

    if qa.interest_subjective is not None:
        scores["interest_subjective"] = Score(
            value=qa.interest_subjective,
            explanation=f"AI self-reported complexity/interest (0-10): {qa.interest_subjective:.1f}",
        )

    # Add structural faithfulness metrics if available
    if qa.structural_faithfulness is not None:
        sf = qa.structural_faithfulness
        scores["structural_faithfulness_overall"] = Score(
            value=sf.overall,
            explanation=f"Weighted average of structural metrics: {sf.overall:.2%}",
        )
        scores["parameter_coverage"] = Score(
            value=sf.parameter_coverage,
            explanation=f"Fraction of Python parameters found in Lean: {sf.parameter_coverage:.2%}",
        )
        scores["type_correspondence"] = Score(
            value=sf.type_correspondence,
            explanation=f"Fraction of Python types correctly mapped to Lean: {sf.type_correspondence:.2%}",
        )
        scores["strategy_coverage"] = Score(
            value=sf.strategy_coverage,
            explanation=f"Fraction of Hypothesis strategy bounds found in Lean: {sf.strategy_coverage:.2%}",
        )
        scores["assertion_coverage"] = Score(
            value=sf.assertion_coverage,
            explanation=f"Ratio of Lean properties to Python assertions: {sf.assertion_coverage:.2%}",
        )
        scores["dependency_coverage"] = Score(
            value=sf.dependency_coverage,
            explanation=f"Fraction of dependency names found in Lean: {sf.dependency_coverage:.2%}",
        )

    return scores


async def write_to_disk(state: TaskState):
    """Persist sample outputs and register quality metrics for inspect_ai.

    Writes the datapoint metadata, extracted Lean code, and QA report to disk
    for the current sample. The function also registers quality scores for the
    inspect_ai viewer and cleans up any temporary workspaces.

    Additionally logs metrics to wandb if enabled.

    Args:
        state: The current state after a sample completes.
    """
    date_time = cast(str, state.metadata.get("date_time"))
    datapoint = cast(Datapoint, state.metadata.get("datapoint"))
    variant = cast(str, state.metadata.get("variant"))
    sample_id = str(state.sample_id)

    ret_str_dp = write_datapoint_to_disk(
        date_time, sample_id, datapoint, variant=variant
    )

    # Only write code and QA if we have output
    if state.output and state.output.choices:
        ret_str_c = write_code_to_disk(
            date_time,
            sample_id,
            state.output.message.text,
            variant=variant,
        )
        ret_str_qa = write_qa_to_disk(date_time, sample_id, state, variant=variant)

        # Extract quality assessment and register metrics as scores
        qa = QualityAssessment.from_task_state(state)
        state.scores = _qa_to_scores(qa)

        # Log to wandb if enabled
        from generate.scaffold.wandb_logger import log_sample_to_wandb

        log_sample_to_wandb(state)

        result = ret_str_dp + "\n" + ret_str_c + "\n" + ret_str_qa
    else:
        result = (
            ret_str_dp + "\n" + "No output generated (task may have been interrupted)"
        )

    # Clean up workspace if it exists
    workspace_path = state.metadata.get("workspace")
    if workspace_path:
        utilio.cleanup_sample_workspace(Path(workspace_path))

    return result
