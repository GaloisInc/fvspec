import re
from typing import cast

from inspect_ai.solver import TaskState
from pydantic import BaseModel, Field
from benchmark.scaffold.dataset import Datapoint


class QualityAssessment(BaseModel):
    """Quality assessment metrics for a generated Lean specification."""

    sample_id: int
    sample_name: str
    datetime: str
    model: str
    token_usage: int
    time: float
    num_messages: int
    num_generate_messages: int
    num_input_messages: int
    success: bool
    num_sorries: int
    lines_pbt: int
    lines_code: int
    percent_lines_added: float | None = Field(
        None, description="(lines_code - lines_pbt) / lines_pbt"
    )
    faithfulness: float | None = Field(
        None, description="AI-defined faithfulness score"
    )
    interest: float | None = Field(
        None, description="AI-defined interest/complexity score"
    )

    @classmethod
    def from_task_state(cls, state: TaskState) -> "QualityAssessment":
        """Extract quality metrics from a completed task state."""
        datapoint = cast(Datapoint, state.metadata.get("datapoint"))
        date_time = cast(str, state.metadata.get("date_time"))
        lines_pbt = datapoint.pbt.count("\n")

        # Extract code metrics
        pattern = r"(?s)<code>(.*?)</code>"
        mtch = re.search(pattern, state.messages[-1].text)
        if not mtch:
            success = False
            num_sorries = 0
            lines_code = 0
            percent_lines_added = 0.0
        else:
            code_snippet = mtch.group(1)
            success = True
            num_sorries = code_snippet.count("sorry")
            lines_code = code_snippet.count("\n")
            percent_lines_added = (lines_code - lines_pbt) / lines_pbt

        # Extract faithfulness metric
        f_pattern = r"Faithfulness.*:\s*([0-9]*.?[0-9]+)/([0-9]+)"
        f_mtch = re.search(f_pattern, state.messages[-1].text, re.IGNORECASE)
        faithfulness = None
        if f_mtch:
            faithfulness = float(f_mtch.group(1)) / float(f_mtch.group(2)) * 10.0

        # Extract interest metric
        i_pattern = r"Interest.*:\s*([0-9]*.?[0-9]+)/([0-9]+)"
        i_mtch = re.search(i_pattern, state.messages[-1].text, re.IGNORECASE)
        interest = None
        if i_mtch:
            interest = float(i_mtch.group(1)) / float(i_mtch.group(2)) * 10.0

        return cls(
            sample_id=datapoint.id,
            sample_name=datapoint.pbt_name,
            datetime=date_time,
            model=state.output.model,
            token_usage=state.token_usage,
            time=state.output.time,
            num_messages=len(state.messages),
            num_generate_messages=sum(
                1 for sm in state.messages if sm.source == "generate"
            ),
            num_input_messages=sum(1 for sm in state.messages if sm.source == "input"),
            lines_pbt=lines_pbt,
            success=success,
            num_sorries=num_sorries,
            lines_code=lines_code,
            percent_lines_added=percent_lines_added,
            faithfulness=faithfulness,
            interest=interest,
        )
