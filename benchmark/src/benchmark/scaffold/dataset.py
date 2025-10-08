from datetime import datetime
import json
from pathlib import Path
import random
from pydantic import BaseModel
from inspect_ai.dataset import Sample, MemoryDataset
from benchmark.config import PromptStyle
from benchmark.templates.prompt import initial

random.seed(0)


class Datapoint(BaseModel, frozen=True):
    """A scraped property-based test datapoint with metadata."""

    id: int
    repo_id: int
    pbt_name: str
    pbt: str
    dep_names: list[str]
    deps: list[str]
    source: str
    summary: str | None
    hash: str
    summary_vector: str | None


class Prompt(BaseModel, frozen=True):
    """A simplified prompt containing the property-based test and its dependencies."""

    pbt: str
    deps: list[str]


def datapoint_to_prompt(dp: Datapoint) -> Prompt:
    """Convert a datapoint to a prompt by extracting test and dependencies.

    Args:
        dp: The datapoint to convert

    Returns:
        A Prompt containing the property-based test and dependencies
    """
    return Prompt(pbt=dp.pbt, deps=dp.deps)


def mk_initial(prompt: Prompt) -> str:
    """Render the initial user prompt from a Prompt object.

    Args:
        prompt: The prompt containing test and dependencies

    Returns:
        Rendered initial prompt string
    """
    return initial.render(pbt=prompt.pbt, deps=prompt.deps)


def load_datapoints(file_path: Path) -> list[Datapoint]:
    """Effectful function: reads a json file from disk"""
    with open(file_path) as f:
        data = json.load(f)
    return [Datapoint(**obj) for obj in data]  # type: ignore[arg-type]


def sample_datapoints(file_path: Path, n: int) -> list[Datapoint]:
    """Effectful function: reads a json file from disk and samples n datapoints at random"""
    dps = load_datapoints(file_path)
    return random.sample(dps, n)


def mk_dataset(
    path: Path, date_time: datetime, style: PromptStyle = PromptStyle.FUNCTIONAL
) -> MemoryDataset:
    """Create an inspect_ai dataset from scraped datapoints.

    Args:
        path: Path to the JSON file containing scraped datapoints
        date_time: Timestamp for organizing output artifacts
        style: Verification style (functional or mvcgen)

    Returns:
        MemoryDataset with 100 randomly sampled datapoints
    """
    return MemoryDataset(
        [
            Sample(
                input=mk_initial(datapoint_to_prompt(datapoint)),
                metadata={
                    "datapoint": datapoint,
                    "date_time": date_time.strftime("%Y-%m-%dT%H-%M-%S"),
                    "style": style.value,
                },
                id=f"{datapoint.id:05d}_{datapoint.pbt_name}",
            )
            for datapoint in sample_datapoints(path, n=100)
        ]
    )
