"""Dataset module for building inspect_ai tasks from PBT data.

This module provides interfaces for both legacy JSONL files and the new SQLite database.
The DB-based interface is preferred for new code.

Public API:
    # DB-based (preferred):
    - mk_dataset_from_db: Create dataset from pbts_full.db
    - load_datapoints_by_id_from_db: Load specific datapoints from DB

    # Legacy JSONL (backward compatibility):
    - mk_dataset: Create dataset from pbts.jsonl
    - sample_datapoints: Sample from JSONL with optional indexing
    - load_datapoints_by_id: Load by ID from JSONL
    - build_index, build_id_index: Index management for JSONL

    # Shared utilities:
    - datapoint_to_prompt: Convert datapoint to Prompt
    - extract_datapoint_unit_tests: Extract unit tests from datapoint
    - mk_initial_prompt: Render initial prompt from Prompt object
"""

from datetime import datetime
from pathlib import Path

from inspect_ai.dataset import MemoryDataset, Sample
from rich.console import Console

# DB-based models and functions
from generate.scaffold.dataset.connection import get_engine, get_session

# Legacy JSONL functions
from generate.scaffold.dataset.legacy_jsonl import (
    Datapoint as JSONLDatapoint,
)
from generate.scaffold.dataset.legacy_jsonl import (
    build_id_index,
    build_index,
    load_datapoints,
    load_datapoints_by_id,
    load_index,
    sample_datapoints,
    sample_datapoints_indexed,
)
from generate.scaffold.dataset.models import Datapoint as DBDatapoint
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
from generate.scaffold.structures import Prompt
from generate.scaffold.units import extract_unit_tests, generate_test_suite
from generate.templates.spec import VariantRegistry, get_variant_prompts

__all__ = [
    # DB-based functions (preferred)
    "mk_dataset_from_db",
    "load_datapoints_by_id_from_db",
    "get_session",
    "get_engine",
    "get_overlapping_unit_tests",
    # Legacy JSONL functions (backward compatibility)
    "mk_dataset",
    "sample_datapoints",
    "load_datapoints_by_id",
    "load_datapoints",
    "build_index",
    "build_id_index",
    "load_index",
    "sample_datapoints_indexed",
    # Shared utilities
    "datapoint_to_prompt",
    "extract_datapoint_unit_tests",
    "mk_initial_prompt",
    # Models (for type hints)
    "Prompt",
    "JSONLDatapoint",
    "DBDatapoint",
]


def datapoint_to_prompt(dp: JSONLDatapoint | DBDatapoint) -> Prompt:
    """Convert a datapoint (JSONL or DB) to a prompt.

    Args:
        dp: The datapoint to convert (either JSONLDatapoint or DBDatapoint)

    Returns:
        A Prompt containing the property-based test and dependencies
    """
    if isinstance(dp, DBDatapoint):
        # DB datapoint stores deps as JSON string
        return Prompt(pbt=dp.code, deps=dp.get_deps())
    else:
        # JSONL datapoint has direct list fields
        return Prompt(pbt=dp.pbt, deps=dp.deps)


def extract_datapoint_unit_tests(dp: JSONLDatapoint | DBDatapoint) -> str | None:
    """Extract unit tests from a datapoint's overlapping unit tests.

    Attempts to extract concrete unit tests from the actual unit test code
    (not the PBT code) using AST analysis.
    If successful, generates LSpec test suite code that can be used for evaluation.

    Args:
        dp: The datapoint containing the overlapping unit tests

    Returns:
        Generated LSpec code string if tests were extracted, None otherwise

    Note:
        Unit tests are for EVALUATION only - they should NOT be shown to the model.
        They validate model implementations after spec generation.
    """
    # Handle DB datapoints differently - fetch overlaps from DB
    if isinstance(dp, DBDatapoint):
        # For now, return None - we'll implement this when we need it
        # TODO: Use get_overlapping_unit_tests(session, dp.id)
        return None

    # JSONL datapoint - use existing logic
    if not dp.overlapping_tests:
        return None

    # Try each overlapping test group and each unit test within
    for overlap in dp.overlapping_tests:
        unit_tests = overlap.get("unit_tests", [])
        shared_functions = overlap.get("shared_functions", [])

        if not unit_tests or not shared_functions:
            continue

        # Try extraction on each unit test with each shared function
        for unit_test in unit_tests:
            unit_test_code = unit_test.get("code", "")
            if not unit_test_code:
                continue

            for func_name in shared_functions:
                # Extract unit tests using AST analysis
                test_suite = extract_unit_tests(unit_test_code, func_name=func_name)

                if test_suite is not None and (
                    test_suite.exact_tests or test_suite.float_tests
                ):
                    # Successfully extracted tests, generate LSpec code
                    return generate_test_suite(test_suite)

    # No tests could be extracted from any unit test
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
    return initial_template.render(pbt=prompt.pbt, deps=prompt.deps)


# ============================================================================
# DB-based interface (preferred for new code)
# ============================================================================


def mk_dataset_from_db(
    db_path: Path,
    date_time: datetime,
    variant: str | None = None,
    sample_size: int = 100,
    ranseed: int | None = 0,
) -> MemoryDataset:
    """Create an inspect_ai dataset from pbts_full.db (NEW DB-based interface).

    Args:
        db_path: Path to the pbts_full.db SQLite database
        date_time: Timestamp for organizing output artifacts
        variant: Prompt variant name. If None, uses registry default.
        sample_size: Number of datapoints to sample from the dataset
        ranseed: Random seed used for sampling datapoints (Note: SQLite RANDOM() limitations)

    Returns:
        MemoryDataset with randomly sampled datapoints
    """
    # Get the actual variant name (resolve default if needed)
    registry = VariantRegistry()
    actual_variant = variant or registry.default_variant()

    # Sample datapoints from DB
    with get_session(db_path) as session:
        datapoints = _db_sample(session, n=sample_size, ranseed=ranseed)

    console = Console()
    if len(datapoints) < sample_size:
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
                    "unit_tests_lspec": unit_tests_lspec,  # For evaluation only
                },
                id=f"{dp.id:05d}_{dp.name}",
            )
        )

    return MemoryDataset(samples)


def load_datapoints_by_id_from_db(
    db_path: Path,
    datapoint_ids: list[int],
) -> dict[int, DBDatapoint]:
    """Load specific datapoints by ID from pbts_full.db (NEW DB-based interface).

    Args:
        db_path: Path to the pbts_full.db SQLite database
        datapoint_ids: List of datapoint IDs to load

    Returns:
        Dictionary mapping datapoint ID to DBDatapoint object
    """
    with get_session(db_path) as session:
        return _db_load_by_id(session, datapoint_ids)


# ============================================================================
# Legacy JSONL interface (backward compatibility)
# ============================================================================


def mk_dataset(
    path: Path,
    date_time: datetime,
    variant: str | None = None,
    sample_size: int = 100,
    ranseed: int | None = 0,
    skip_index: bool = False,
) -> MemoryDataset:
    """Create an inspect_ai dataset from scraped datapoints (LEGACY JSONL interface).

    For new code, prefer mk_dataset_from_db() which uses the SQLite database.

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

    samples = []
    for datapoint in sample_datapoints(
        path, n=sample_size, ranseed=ranseed, skip_index=skip_index
    ):
        # Extract unit tests for evaluation (NOT shown to model)
        unit_tests_lspec = extract_datapoint_unit_tests(datapoint)

        samples.append(
            Sample(
                input=mk_initial_prompt(
                    datapoint_to_prompt(datapoint), variant=actual_variant
                ),
                metadata={
                    "datapoint": datapoint,
                    "date_time": date_time.strftime("%Y-%m-%dT%H-%M-%S"),
                    "variant": actual_variant,
                    "unit_tests_lspec": unit_tests_lspec,  # For evaluation only
                },
                id=f"{datapoint.id:05d}_{datapoint.pbt_name}",
            )
        )

    return MemoryDataset(samples)
