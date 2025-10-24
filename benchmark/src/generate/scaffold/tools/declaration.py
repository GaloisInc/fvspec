"""Utility functions for persisting benchmark artifacts and tooling hooks."""

import re
from pathlib import Path
from typing import Callable, Awaitable, cast
from inspect_ai.tool import tool, ToolError, mcp_server_stdio, mcp_tools
from inspect_ai.solver import TaskState
from inspect_ai.scorer import Score
from inspect_ai.solver._task_state import sample_state
from generate.scaffold.dataset import Datapoint
from generate.scaffold.quality_assessment import QualityAssessment
from generate.scaffold.tools import utilio

LAKE_BUILD_CMD = ["lake", "build"]


@tool  # type: ignore[arg-type]
def lean_compile() -> Callable[[str], Awaitable[utilio.SubprocessResult]]:
    """Create an inspect_ai tool that typechecks Lean code via Lake."""

    async def execute(code: str) -> utilio.SubprocessResult:
        """Typecheck Lean code using lake build in an isolated workspace.

        Creates a temporary Lake project workspace for the sample if it doesn't exist yet.
        Writes the code to Fvspec/Basic.lean and runs lake build.

        Args:
            code: The Lean code to typecheck

        Returns:
            A tuple of stdout, stderr and exitcode.
        """
        # Get current task state to access metadata
        state = sample_state()
        if not state:
            raise ToolError("No task state available")

        sample_id = str(state.sample_id)

        # Create workspace if it doesn't exist yet
        if "workspace" not in state.metadata:
            workspace = utilio.create_sample_workspace(sample_id)
            state.metadata["workspace"] = str(workspace)
        else:
            workspace = Path(state.metadata["workspace"])

        # Write code to Fvspec/Basic.lean
        fvspec_dir = workspace / "Fvspec"
        fvspec_dir.mkdir(exist_ok=True)

        basic_file = fvspec_dir / "Basic.lean"

        # Ensure the generated file keeps the dependency import header
        header = f"-- Auto-generated spec for sample {sample_id}\n"
        deps_import = "import Fvspec.Deps\n\n"
        body = code if "import Fvspec.Deps" in code else deps_import + code
        basic_file.write_text(header + body)

        deps_meta = state.metadata.get("depmock") if state else None
        deps_file = fvspec_dir / "Deps.lean"
        if deps_meta:
            deps_text = deps_meta.get("lean_text")
            if isinstance(deps_text, str) and deps_text.strip():
                deps_file.write_text(deps_text)
            elif not deps_file.exists():
                deps_file.write_text("-- No dependency modules available\n")
        elif not deps_file.exists():
            deps_file.write_text("-- No dependency modules available\n")

        # Run lake build
        stdout, stderr, exitcode = utilio.run_cmd(LAKE_BUILD_CMD, cwd=workspace)

        if exitcode != 0:
            raise ToolError(stderr)
        return stdout, stderr, exitcode

    return execute


def lean_lsp_mcp() -> list:
    """Construct the Lean LSP MCP tool bundle used by benchmark agents."""
    lean_server = mcp_server_stdio(
        name="lean-lsp", command="uvx", args=["lean-lsp-mcp"]
    )

    return [
        lean_compile(),
        mcp_tools(
            lean_server,
            tools=[
                "lean_run_code",
                "lean_diagnostic_messages",
                "lean_hover_info",
                "lean_goal",
                "lean_completions",
                "lean_multi_attempt",
            ],
        ),
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
