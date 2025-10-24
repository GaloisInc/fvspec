"""Dataset helpers for building inspect_ai tasks."""

import json
import jsonlines
import random
from datetime import datetime
from pathlib import Path
from typing import Any

from generate.templates.spec import VariantRegistry, get_variant_prompts
from inspect_ai.dataset import MemoryDataset, Sample
from pydantic import BaseModel
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
    TimeElapsedColumn,
)
from rich.prompt import Confirm


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


def build_index(file_path: Path, index_path: Path | None = None) -> Path:
    """Build a byte-offset index for fast random access to JSONL file.

    Creates an index file that maps line numbers to byte positions in the JSONL file.
    This enables O(1) random access instead of O(n) streaming for sampling.

    Args:
        file_path: Path to the JSONL file to index
        index_path: Optional custom path for index file (defaults to file_path + ".index")

    Returns:
        Path to the created index file

    Note:
        This is a one-time operation that takes ~10-30 minutes for the 116GB pbts.jsonl.
        The index file is small (~1-2MB for 60k lines) and enables sub-second sampling.
    """
    if index_path is None:
        index_path = file_path.with_suffix(file_path.suffix + ".index")

    # Get file size for progress tracking
    file_size = file_path.stat().st_size

    offsets: list[int] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task(f"Indexing {file_path.name}...", total=file_size)

        with open(file_path, "rb") as f:
            offsets.append(0)  # First line starts at byte 0
            line_count = 0
            last_pos = 0

            while f.readline():
                current_pos = f.tell()
                offsets.append(current_pos)
                line_count += 1

                # Update progress based on bytes read
                progress.update(task, completed=current_pos)
                last_pos = current_pos

    # Remove the final offset (it's past EOF)
    offsets = offsets[:-1]

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
    ) as progress:
        task = progress.add_task(f"Writing index to {index_path.name}...")
        with open(index_path, "w") as f:
            json.dump({"offsets": offsets, "total_lines": len(offsets)}, f)
        progress.update(task, completed=1, total=1)

    print(
        f"✓ Index complete: {len(offsets):,} lines indexed ({index_path.stat().st_size / 1024 / 1024:.2f} MB)"
    )
    return index_path


def load_index(index_path: Path) -> dict[str, Any]:
    """Load a pre-built index file.

    Args:
        index_path: Path to the index file

    Returns:
        Dictionary with 'offsets' (list of byte positions) and 'total_lines' (int)
    """
    with open(index_path) as f:
        return json.load(f)  # type: ignore[no-any-return]


def sample_datapoints_indexed(
    file_path: Path, index_data: dict[str, Any], n: int, ranseed: int | None = 0
) -> list[Datapoint]:
    """Sample datapoints using a pre-built index for fast random access.

    Args:
        file_path: Path to the JSONL file
        index_data: Index data from load_index()
        n: Number of samples to draw
        ranseed: Random seed for reproducibility

    Returns:
        List of randomly sampled Datapoint objects
    """
    offsets: list[int] = index_data["offsets"]
    total_lines: int = index_data["total_lines"]

    rng = random.Random(ranseed)
    # Sample random line numbers
    sample_size = min(n, total_lines)
    selected_lines = rng.sample(range(total_lines), sample_size)

    # Seek directly to each line and read it
    datapoints: list[Datapoint] = []
    with open(file_path, "rb") as f:
        for line_num in sorted(selected_lines):  # Sort for sequential I/O
            f.seek(offsets[line_num])
            line = f.readline()
            obj = json.loads(line)
            datapoints.append(Datapoint(**obj))  # type: ignore[arg-type]

    # Shuffle to original random order
    rng.shuffle(datapoints)
    return datapoints


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
    skip_index: bool = False,
) -> list[Datapoint]:
    """Effectful function: read a JSONL file and sample ``n`` datapoints at random.

    Auto-detects if an index file exists (file_path + ".index"). If so, uses fast
    indexed sampling (O(sample_size)). Otherwise, offers to build an index or falls
    back to reservoir sampling (O(total_lines)).

    For the 116GB pbts.jsonl file:
    - With index: Sample 10 items in ~1 second
    - Without index: Sample 10 items in ~10 minutes (streams entire file)

    To create an index: `uv run fvspec index-data`
    """
    index_path = file_path.with_suffix(file_path.suffix + ".index")
    console = Console()

    if skip_index:
        # User explicitly requested to skip index
        console.print(
            "[yellow]⚠[/yellow] Skipping index (--skip-index), using reservoir sampling"
        )
    elif index_path.exists():
        # Fast path: Use pre-built index for O(sample_size) sampling
        console.print(f"[green]✓[/green] Using index file: {index_path.name}")
        index_data = load_index(index_path)
        return sample_datapoints_indexed(file_path, index_data, n, ranseed)
    else:
        # No index found - offer to build one
        console.print(f"[yellow]⚠[/yellow] No index found for {file_path.name}")
        console.print(f"   Building an index enables fast sampling (~1 sec vs ~10 min)")

        # Interactive prompt (defaults to Yes)
        should_build = Confirm.ask(
            "Build index now? (one-time ~10-30 min)", default=True
        )

        if should_build:
            # Build the index with progress bar
            build_index(file_path, index_path)
            console.print(f"[green]✓[/green] Index created! Using it for this run...")
            index_data = load_index(index_path)
            return sample_datapoints_indexed(file_path, index_data, n, ranseed)
        else:
            # Fall back to reservoir sampling with progress bar
            console.print(
                "[yellow]⚠[/yellow] Using slower reservoir sampling (streaming entire file)"
            )

    # Reservoir sampling path (reached if skip_index=True or no index and user declined to build)
    rng = random.Random(ranseed)
    reservoir: list[Datapoint] = []

    # Get file size for progress tracking
    file_size = file_path.stat().st_size

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
    ) as progress:
        task = progress.add_task(f"Sampling from {file_path.name}...", total=file_size)

        with open(file_path, "rb") as f:
            for idx in range(1000000000):  # Large number for iteration
                line = f.readline()
                if not line:
                    break

                obj = json.loads(line)
                datapoint = Datapoint(**obj)  # type: ignore[arg-type]

                if idx < n:
                    reservoir.append(datapoint)
                else:
                    # Reservoir sampling: randomly replace elements
                    j = rng.randint(0, idx)
                    if j < n:
                        reservoir[j] = datapoint

                # Update progress based on bytes read
                progress.update(task, completed=f.tell())

    return reservoir


def mk_dataset(
    path: Path,
    date_time: datetime,
    variant: str | None = None,
    sample_size: int = 100,
    ranseed: int | None = 0,
    skip_index: bool = False,
) -> MemoryDataset:
    """Create an inspect_ai dataset from scraped datapoints.

    Args:
        path: Path to the JSONL file containing scraped datapoints
        date_time: Timestamp for organizing output artifacts
        variant: Prompt variant name. If None, uses registry default.
        sample_size: Number of datapoints to sample from the dataset
        ranseed: Random seed used for sampling datapoints
        skip_index: Skip using index file and use reservoir sampling

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
            for datapoint in sample_datapoints(
                path, n=sample_size, ranseed=ranseed, skip_index=skip_index
            )
        ]
    )
