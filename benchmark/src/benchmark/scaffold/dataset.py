from datetime import datetime
import json
from pathlib import Path
import random
from pydantic import BaseModel
from inspect_ai.dataset import Sample, MemoryDataset
from benchmark.templates.spec import get_variant_prompts, VariantRegistry

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


def mk_initial(prompt: Prompt, variant: str | None = None) -> str:
    """Render the initial user prompt from a Prompt object.

    Args:
        prompt: The prompt containing test and dependencies
        variant: Variant name to use for template (uses registry default if None)

    Returns:
        Rendered initial prompt string
    """
    _, initial_template = get_variant_prompts(variant)
    return initial_template.render(pbt=prompt.pbt, deps=prompt.deps)


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
    path: Path,
    date_time: datetime,
    variant: str | None = None,
    sample_size: int = 100,
) -> MemoryDataset:
    """Create an inspect_ai dataset from scraped datapoints.

    Args:
        path: Path to the JSON file containing scraped datapoints
        date_time: Timestamp for organizing output artifacts
        variant: Prompt variant name. If None, uses registry default.
        sample_size: Number of datapoints to sample from the dataset

    Returns:
        MemoryDataset with randomly sampled datapoints
    """
    # Get the actual variant name (resolve default if needed)
    registry = VariantRegistry()
    actual_variant = variant or registry.default_variant()

    return MemoryDataset(
        [
            Sample(
                input=mk_initial(
                    datapoint_to_prompt(datapoint), variant=actual_variant
                ),
                metadata={
                    "datapoint": datapoint,
                    "date_time": date_time.strftime("%Y-%m-%dT%H-%M-%S"),
                    "variant": actual_variant,
                },
                id=f"{datapoint.id:05d}_{datapoint.pbt_name}",
            )
            for datapoint in sample_datapoints(path, n=sample_size)
        ]
    )
