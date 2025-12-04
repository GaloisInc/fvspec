"""Dataset module for building inspect_ai tasks from pbts_full.db.

This module provides a SQLModel-based interface to the pbts_full.db SQLite database.

Public API:
    - mk_dataset: Create dataset from pbts_full.db (primary interface)
    - mk_dataset_from_db: Alias for mk_dataset (explicit naming)
    - load_datapoints_by_id: Load specific datapoints from DB by ID
    - get_session: Get database session for custom queries
    - get_engine: Get database engine
    - get_overlapping_unit_tests: Reconstruct unit test overlaps from DB

    Types:
    - Datapoint: SQLModel type for PBT datapoints (DB rows)
    - Prompt: Shared DTO for test + dependencies
"""

from datetime import datetime
from pathlib import Path

from inspect_ai.dataset import MemoryDataset, Sample
from rich.console import Console

# DB models and functions
from generate.scaffold.dataset.connection import get_engine, get_session
from generate.scaffold.dataset.function_discovery import (
    FunctionInfo,
    lookup_function_exact,
)
from generate.scaffold.dataset.models import Datapoint
from generate.scaffold.dataset.queries import (
    get_overlapping_unit_tests,
)
from generate.scaffold.dataset.queries import (
    load_datapoints_by_id as _db_load_by_id,
)
from generate.scaffold.dataset.queries import (
    sample_datapoints as _db_sample,
)

# Shared structures
from generate.templates.models import Prompt
from generate.templates.spec import VariantRegistry, get_variant_prompts

__all__ = [
    # Primary interface
    "mk_dataset",
    "mk_dataset_from_db",  # Explicit alias
    "load_datapoints_by_id",
    # DB utilities
    "get_session",
    "get_engine",
    "get_overlapping_unit_tests",
    # Function discovery
    "lookup_function_exact",
    "FunctionInfo",
    # Shared utilities
    "datapoint_to_prompt",
    "extract_datapoint_unit_tests",
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

    # DB datapoint stores deps as JSON string
    return Prompt(
        pbt=dp.code,
        pbt_name=dp.name,
        function_name=function_name,
        deps=dp.get_deps(),
    )


def extract_datapoint_unit_tests(dp: Datapoint) -> str | None:
    """Extract unit tests from a datapoint's overlapping unit tests.

    Checks if the datapoint has associated unit tests from the database.
    Returns a placeholder string indicating unit tests are available.

    Args:
        dp: The datapoint containing the overlapping unit tests

    Returns:
        Placeholder string if unit tests are available, None otherwise

    Note:
        Unit tests are for EVALUATION only - they should NOT be shown to the model.
        The actual unit test code is passed to the units agent via orchestration,
        which accesses dp.unit_tests directly.

        This function's return value is only used by the QA system to determine
        if unit tests were available for this sample.
    """
    # Check if unit_tests field is non-empty
    # This field is populated by sample_datapoints() in queries.py
    if dp.unit_tests and len(dp.unit_tests) > 0:
        # Return a placeholder indicating unit tests are available
        # The count is used by QA metrics
        return f"-- {len(dp.unit_tests)} unit tests available from database"
    return None


def mk_initial_prompt(prompt: Prompt, variant: str | None = None) -> str:
    """Render the initial user prompt from a Prompt object.

    Args:
        prompt: The prompt containing test and dependencies
        variant: Variant name to use for template (uses registry default if None)

    Returns:
        Rendered initial prompt string
    """
    _, initial_template = get_variant_prompts(variant)
    # Render with the context expected by the template
    # impl_signatures is empty at dataset creation time (populated during orchestration)
    context = {
        "pbt_code": prompt.pbt,
        "pbt_name": prompt.pbt_name,
        "function_name": prompt.function_name,
        "impl_signatures": {},  # Empty at dataset creation - populated during spec agent phase
    }
    return initial_template.render(**context)


def mk_dataset(
    db_path: Path,
    date_time: datetime,
    variant: str | None = None,
    sample_size: int = 100,
    ranseed: int | None = 0,
    start_idx: int | None = None,
    end_idx: int | None = None,
    require_unit_tests: bool = False,
) -> MemoryDataset:
    """Create an inspect_ai dataset from pbts_full.db.

    Args:
        db_path: Path to the pbts_full.db SQLite database
        date_time: Timestamp for organizing output artifacts
        variant: Prompt variant name. If None, uses registry default.
        sample_size: Number of datapoints to sample from the dataset
        ranseed: Random seed used for sampling datapoints (Note: SQLite RANDOM() limitations)
        start_idx: Starting index for sequential sampling (0-indexed, inclusive)
        end_idx: Ending index for sequential sampling (0-indexed, exclusive)
        require_unit_tests: If True, only sample datapoints that have unit tests (default: False)

    Returns:
        MemoryDataset with randomly sampled datapoints (or sequential slice if indices provided)
    """
    # Get the actual variant name (resolve default if needed)
    registry = VariantRegistry()
    actual_variant = variant or registry.default_variant()

    # Sample datapoints from DB
    with get_session(db_path) as session:
        datapoints = _db_sample(
            session,
            n=sample_size,
            ranseed=ranseed,
            start_idx=start_idx,
            end_idx=end_idx,
            require_unit_tests=require_unit_tests,
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
        # Extract unit tests for evaluation (NOT shown to model)
        unit_tests_lspec = extract_datapoint_unit_tests(dp)

        samples.append(
            Sample(
                input=mk_initial_prompt(
                    datapoint_to_prompt(dp), variant=actual_variant
                ),
                metadata={
                    "datapoint": dp,
                    "date_time": date_time.strftime("%Y-%m-%dT%H-%M-%S"),
                    "variant": actual_variant,
                    "ranseed": ranseed,  # For artifact path naming
                    "start_idx": start_idx,  # For sequential run tracking
                    "end_idx": end_idx,  # For sequential run tracking
                    "unit_tests_lspec": unit_tests_lspec,  # For evaluation only
                },
                id=f"{dp.id:05d}_{dp.name}",
            )
        )

    return MemoryDataset(samples)


# Explicit alias for clarity
mk_dataset_from_db = mk_dataset


def load_datapoints_by_id(
    db_path: Path,
    datapoint_ids: list[int],
) -> dict[int, Datapoint]:
    """Load specific datapoints by ID from pbts_full.db.

    Args:
        db_path: Path to the pbts_full.db SQLite database
        datapoint_ids: List of datapoint IDs to load

    Returns:
        Dictionary mapping datapoint ID to Datapoint object
    """
    with get_session(db_path) as session:
        return _db_load_by_id(session, datapoint_ids)
