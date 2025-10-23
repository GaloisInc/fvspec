"""Dataset helpers for building inspect_ai tasks."""

import jsonlines
import random
from datetime import datetime
from pathlib import Path
from typing import Any

from generate.templates.spec import VariantRegistry, get_variant_prompts
from inspect_ai.dataset import MemoryDataset, Sample
from pydantic import BaseModel


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
    mode: str | None = None
    summaryversion: int | None = None
    summaryconfidence: int | None = None
    has_overlap_data: bool | None = None
    repo_name: str | None = None
    repo_url: str | None = None
    analysis_timestamp: str | None = None
    pbt_summary: str | None = None
    pbt_functions: list[str] | None = None
    overlapping_tests: list[dict[str, Any]] | None = None


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
    """Effectful function: read a JSONL file from disk.

    WARNING: This loads all datapoints into memory. For the full 116GB pbts.jsonl file,
    use sample_datapoints() instead to avoid memory exhaustion.
    """
    with jsonlines.open(file_path) as reader:
        return [Datapoint(**obj) for obj in reader]  # type: ignore[arg-type]


def sample_datapoints(
    file_path: Path,
    n: int,
    ranseed: int | None = 0,
) -> list[Datapoint]:
    """Effectful function: read a JSONL file and sample ``n`` datapoints at random.

    Uses reservoir sampling to avoid loading the entire 116GB dataset into memory.
    """
    rng = random.Random(ranseed)
    reservoir: list[Datapoint] = []

    with jsonlines.open(file_path) as reader:
        for idx, obj in enumerate(reader):
            datapoint = Datapoint(**obj)  # type: ignore[arg-type]

            if idx < n:
                reservoir.append(datapoint)
            else:
                # Reservoir sampling: randomly replace elements
                j = rng.randint(0, idx)
                if j < n:
                    reservoir[j] = datapoint

    return reservoir


def mk_dataset(
    path: Path,
    date_time: datetime,
    variant: str | None = None,
    sample_size: int = 100,
    ranseed: int | None = 0,
) -> MemoryDataset:
    """Create an inspect_ai dataset from scraped datapoints.

    Args:
        path: Path to the JSONL file containing scraped datapoints
        date_time: Timestamp for organizing output artifacts
        variant: Prompt variant name. If None, uses registry default.
        sample_size: Number of datapoints to sample from the dataset
        ranseed: Random seed used for sampling datapoints

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
            for datapoint in sample_datapoints(path, n=sample_size, ranseed=ranseed)
        ]
    )
