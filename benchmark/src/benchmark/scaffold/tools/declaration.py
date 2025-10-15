import tempfile
import re
from typing import Callable, Awaitable, cast
from inspect_ai.tool import tool, ToolError
from inspect_ai.solver import TaskState
from benchmark.scaffold.dataset import Datapoint
from benchmark.scaffold.quality_assessment import QualityAssessment
from benchmark.scaffold.tools import utilio

LEAN_EXE = "lean"


@tool  # type: ignore[arg-type]
def lean_compile() -> Callable[[str], Awaitable[utilio.SubprocessResult]]:
    async def execute(code: str) -> utilio.SubprocessResult:
        """
        Typecheck Lean code.

        Args:
            code: The Lean code to typecheck

        Returns:
            A tuple of stdout, stderr and exitcode.
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".lean") as tmp:
            tmp.write(code)
            tmp.flush()
            stdout, stderr, exitcode = utilio.run_cmd([LEAN_EXE, tmp.name])
        if exitcode != 0:
            raise ToolError(stderr)
        return stdout, stderr, exitcode

    return execute


def write_datapoint_to_disk(
    date_time: str,
    sample_id: str,
    datapoint: Datapoint,
    variant: str,
) -> str:
    """
    Write the datapoint from text into
    artifacts/spec/<sample_id>/Datapoint.json.

    Args:
        date_time: datetime string used in directory structue.
        sample_id: Identifier for the current sample.
        datapoint: The datapoint from the metadata of the current sample.
        variant: Prompt variant name.
    Returns:
        A message describing whether the write succeeded.
    """
    datapoint_file = utilio.get_output_filepath(
        date_time, sample_id, "Datapoint.json", variant=variant
    )
    return utilio.writeit(datapoint_file, datapoint.model_dump_json(indent=4))


def write_code_to_disk(
    date_time: str,
    sample_id: str,
    text: str,
    variant: str,
) -> str:
    """
    Write the <code>...</code> snippet from text into
    artifacts/spec/<sample_id>/Spec.lean.

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
    """
    Write the QA results from the TaskState to
    artifacts/spec/<sample_id>/QA.json.

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
        date_time, sample_id, "QA.json", variant=variant
    )
    return utilio.writeit(qa_file, qa.model_dump_json(indent=4))


async def write_to_disk(state: TaskState):
    """
    Called after each sample in Task, writes the datapoint to a problem file and
    the task quality assessment results to a QA file.

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
        return ret_str_dp + "\n" + ret_str_c + "\n" + ret_str_qa
    return ret_str_dp + "\n" + "No output generated (task may have been interrupted)"
