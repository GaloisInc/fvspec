"""Dataset module for building inspect_ai tasks from realpbt2.jsonl.

This module provides a JSONL-based interface to the realpbt2 dataset.

Public API:
    - mk_dataset: Create dataset from realpbt2.jsonl (primary interface)
    - load_datapoints_by_id: Load specific datapoints by ID
    - load_jsonl: Load all datapoints from JSONL file

    Types:
    - Datapoint: Pydantic model for PBT datapoints
    - Prompt: Shared DTO for test + dependencies
"""

from datetime import datetime
from pathlib import Path

from inspect_ai.dataset import MemoryDataset, Sample
from rich.console import Console

from generate.scaffold.dataset.function_discovery import (
    FunctionInfo,
)
from generate.scaffold.dataset.models import Datapoint
from generate.scaffold.dataset.queries import (
    load_datapoints_by_id as _load_by_id,
)
from generate.scaffold.dataset.queries import (
    load_jsonl,
)
from generate.scaffold.dataset.queries import (
    sample_datapoints as _sample,
)
from generate.templates.formalize import (
    FormalizationVariantRegistry as VariantRegistry,
)
from generate.templates.formalize import (
    get_formalization_prompts as get_variant_prompts,
)

# Shared structures
from generate.templates.models import Prompt

__all__ = [
    # Primary interface
    "mk_dataset",
    "load_datapoints_by_id",
    "load_jsonl",
    # Function discovery
    "FunctionInfo",
    # Shared utilities
    "datapoint_to_prompt",
    "mk_initial_prompt",
    # Types
    "Datapoint",
    "Prompt",
]


def datapoint_to_prompt(dp: Datapoint) -> Prompt:
    """Convert a datapoint to a prompt.

    Args:
        dp: The datapoint to convert

    Returns:
        A Prompt containing the property-based test, metadata, and dependencies
    """
    # Infer function name from test name (remove test_ prefix)
    function_name = dp.name.replace("test_", "").replace("Test", "")

    return Prompt(
        pbt=dp.code,
        pbt_name=dp.name,
        function_name=function_name,
        deps=dp.get_deps(),
    )


def mk_initial_prompt(prompt: Prompt, variant: str | None = None) -> str:
    """Render the initial user prompt from a Prompt object.

    Note: This is a placeholder for inspect_ai's Sample.input field.
    The actual prompt is constructed by the formalization agent during orchestration.

    Args:
        prompt: The prompt containing test and dependencies
        variant: Variant name to use for template (uses registry default if None)

    Returns:
        Rendered initial prompt string
    """
    _, initial_template = get_variant_prompts(variant)
    context = {
        "pbt_code": prompt.pbt,
        "function_name": prompt.function_name,
        "function_code": None,  # Not available at dataset creation time
        "pbt_summary": None,
        "dependencies": {},
    }
    return initial_template.render(**context)


def mk_dataset(
    data_path: Path,
    date_time: datetime,
    variant: str | None = None,
    sample_size: int = 100,
    ranseed: int | None = 0,
    start_idx: int | None = None,
    end_idx: int | None = None,
    git_commit: str | None = None,
    model: str | None = None,
) -> MemoryDataset:
    """Create an inspect_ai dataset from realpbt2.jsonl.

    Args:
        data_path: Path to the realpbt2.jsonl file
        date_time: Timestamp for organizing output artifacts
        variant: Prompt variant name. If None, uses registry default.
        sample_size: Number of datapoints to sample from the dataset
        ranseed: Random seed used for sampling datapoints
        start_idx: Starting index for sequential sampling (0-indexed, inclusive)
        end_idx: Ending index for sequential sampling (0-indexed, exclusive)
        git_commit: Git commit hash at generation time, stored in each sample's metadata.
        model: Model slug (e.g., "claude-sonnet-4-6"), stored in each sample's metadata for artifact path naming.

    Returns:
        MemoryDataset with randomly sampled datapoints (or sequential slice if indices provided)
    """
    # Get the actual variant name (resolve default if needed)
    registry = VariantRegistry()
    actual_variant = variant or registry.default_variant()

    # Load and sample datapoints from JSONL
    all_datapoints = load_jsonl(data_path)
    datapoints = _sample(
        all_datapoints,
        n=sample_size,
        ranseed=ranseed,
        start_idx=start_idx,
        end_idx=end_idx,
    )

    console = Console()
    # Adjust warning message for sequential vs random mode
    if start_idx is not None or end_idx is not None:
        expected_count = (end_idx or float("inf")) - (start_idx or 0)
        if len(datapoints) < expected_count:
            console.print(
                f"[yellow]⚠[/yellow] Sampled {len(datapoints)} datapoints (expected {expected_count} from indices)"
            )
    elif len(datapoints) < sample_size:
        console.print(
            f"[yellow]⚠[/yellow] Sampled {len(datapoints)} datapoints (requested {sample_size})"
        )

    samples = []
    for dp in datapoints:
        samples.append(
            Sample(
                input=mk_initial_prompt(
                    datapoint_to_prompt(dp), variant=actual_variant
                ),
                metadata={
                    "datapoint": dp,
                    "date_time": date_time.strftime("%Y-%m-%dT%H-%M-%S"),
                    "variant": actual_variant,
                    "model": model,  # For artifact path naming
                    "ranseed": ranseed,  # For artifact path naming
                    "start_idx": start_idx,  # For sequential run tracking
                    "end_idx": end_idx,  # For sequential run tracking
                    "git_commit": git_commit,  # Repo commit at generation time
                },
                id=f"{dp.id:05d}_{dp.name}",
            )
        )

    return MemoryDataset(samples)


def load_datapoints_by_id(
    data_path: Path,
    datapoint_ids: list[int],
) -> dict[int, Datapoint]:
    """Load specific datapoints by ID from realpbt2.jsonl.

    Args:
        data_path: Path to the realpbt2.jsonl file
        datapoint_ids: List of datapoint IDs to load

    Returns:
        Dictionary mapping datapoint ID to Datapoint object
    """
    all_datapoints = load_jsonl(data_path)
    return _load_by_id(all_datapoints, datapoint_ids)
