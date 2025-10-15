import re
from pathlib import Path
from typing import Callable, Awaitable, cast
from inspect_ai.tool import tool, ToolError
from inspect_ai.solver import TaskState
from inspect_ai.solver._task_state import sample_state
from benchmark.scaffold.dataset import Datapoint
from benchmark.scaffold.quality_assessment import QualityAssessment
from benchmark.scaffold.tools import utilio

LAKE_BUILD_CMD = ["lake", "build"]


@tool  # type: ignore[arg-type]
def lean_compile() -> Callable[[str], Awaitable[utilio.SubprocessResult]]:
    async def execute(code: str) -> utilio.SubprocessResult:
        """
        Typecheck Lean code using lake build in an isolated workspace.

        Creates a temporary Lake project workspace for the sample if it doesn't exist yet.
        Writes the code to Fvspec/<SampleID>.lean and runs lake build.

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

        # Write code to Fvspec/<SampleID>.lean
        fvspec_dir = workspace / "Fvspec"
        fvspec_dir.mkdir(exist_ok=True)

        spec_file = fvspec_dir / f"{sample_id}.lean"
        spec_file.write_text(code)

        # Run lake build
        stdout, stderr, exitcode = utilio.run_cmd(LAKE_BUILD_CMD, cwd=workspace)

        if exitcode != 0:
            raise ToolError(stderr)
        return stdout, stderr, exitcode

    return execute


def write_datapoint_to_disk(
    date_time: str, sample_id: str, datapoint: Datapoint, style: str = "functional"
) -> str:
    """
    Write the datapoint from text into
    artifacts/spec/<sample_id>/Datapoint.json.

    Args:
        date_time: datetime string used in directory structue.
        sample_id: Identifier for the current sample.
        datapoint: The datapoint from the metadata of the current sample.
        style: Prompt style used (functional or mvcgen).
    Returns:
        A message describing whether the write succeeded.
    """
    datapoint_file = utilio.get_output_filepath(
        date_time, sample_id, "Datapoint.json", style=style
    )
    return utilio.writeit(datapoint_file, datapoint.model_dump_json(indent=4))


def write_code_to_disk(
    date_time: str, sample_id: str, text: str, style: str = "functional"
) -> str:
    """
    Write the <code>...</code> snippet from text into
    artifacts/spec/<sample_id>/Spec.lean.

    Args:
        date_time: datetime string used in directory structue.
        sample_id: Identifier for the current sample.
        text: The output text possibly containing <code>...</code>.
        style: Prompt style used (functional or mvcgen).
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
        date_time, sample_id, "Spec.lean", style=style
    )
    return utilio.writeit(spec_file, code_snippet)


def write_qa_to_disk(
    date_time: str, sample_id: str, state: TaskState, style: str = "functional"
) -> str:
    """
    Write the QA results from the TaskState to
    artifacts/spec/<sample_id>/QA.json.

    Args:
        date_time: datetime string used in directory structue.
        sample_id: Identifier for the current sample.
        state: The task state after completion.
        style: Prompt style used (functional or mvcgen).
    Returns:
        A message describing whether the write succeeded.
    """

    # Fill in QA info
    qa = QualityAssessment.from_task_state(state)

    qa_file = utilio.get_output_filepath(date_time, sample_id, "QA.json", style=style)
    return utilio.writeit(qa_file, qa.model_dump_json(indent=4))


async def write_to_disk(state: TaskState):
    """
    Called after each sample in Task, writes the datapoint to a problem file and
    the task quality assessment results to a QA file.

    Also handles cleanup of the temporary workspace.

    Args:
        state: The current state after a sample completes.
    """
    date_time = cast(str, state.metadata.get("date_time"))
    datapoint = cast(Datapoint, state.metadata.get("datapoint"))
    style = cast(str, state.metadata.get("style", "functional"))
    sample_id = str(state.sample_id)

    ret_str_dp = write_datapoint_to_disk(date_time, sample_id, datapoint, style=style)

    # Only write code and QA if we have output
    if state.output and state.output.choices:
        ret_str_c = write_code_to_disk(
            date_time, sample_id, state.output.message.text, style=style
        )
        ret_str_qa = write_qa_to_disk(date_time, sample_id, state, style=style)
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
