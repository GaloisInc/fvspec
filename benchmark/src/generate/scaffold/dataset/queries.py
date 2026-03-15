"""Query functions for pbts_full.db using SQLModel.

All data access should go through these functions for consistency and testability.
"""

import logging
import random
from typing import Any

from sqlmodel import Session, func, select

from generate.scaffold.dataset.models import (
    Datapoint,
    Function,
    PBTFunction,
    UnitTest,
    UnitTestFunction,
)

logger = logging.getLogger(__name__)

# Maximum number of dependencies allowed per sample before filtering
# Rationale: Samples with >100 dependencies are extreme outliers that:
# 1. Generate excessively large prompts (degraded model performance)
# 2. Take disproportionately long to autoformalize (hurt parallelism)
# 3. Are often synthetic/generated code rather than real-world tests
# 4. Exceed practical limits for meaningful specification generation
MAX_DEPENDENCIES = 100

# Maximum number of unit tests to sample per datapoint
# Rationale: Too many unit tests create excessively large prompts
# 10 unit tests provides sufficient coverage while keeping prompts manageable
MAX_UNIT_TESTS = 10

# SQLite parameter limit for query batching
# SQLite has a hard limit of 32766 parameters per query
# We use 32700 to stay safely under the limit
SQLITE_PARAM_BATCH_SIZE = 32700


def _batch_items(items: list, batch_size: int = SQLITE_PARAM_BATCH_SIZE):
    """Yield batches of items to avoid SQLite parameter limit.

    Args:
        items: List of items to batch
        batch_size: Size of each batch (default: SQLITE_PARAM_BATCH_SIZE)

    Yields:
        Batches of items
    """
    for i in range(0, len(items), batch_size):
        yield items[i : i + batch_size]


def sample_datapoints(
    session: Session,
    n: int,
    ranseed: int | None = 0,
    start_idx: int | None = None,
    end_idx: int | None = None,
    require_unit_tests: bool = False,
) -> list[Datapoint]:
    """Sample n random datapoints, filtering by dependency count.

    Implements memory-efficient deterministic sampling by:
    1. Fetching only IDs of eligible datapoints (deps <= MAX_DEPENDENCIES)
    2. Optionally filtering to only datapoints with unit tests
    3. Shuffling IDs using seeded Python RNG (if start_idx/end_idx not provided)
    4. Taking first n IDs and fetching full datapoints

    When start_idx and/or end_idx are provided, returns a sequential slice
    of datapoints instead of random sampling. This enables resumable large-scale
    runs by processing the dataset in chunks.

    Args:
        session: SQLModel database session
        n: Number of samples to draw (ignored if start_idx/end_idx provided)
        ranseed: Random seed for reproducibility (default: 0, ignored if start_idx/end_idx provided)
        start_idx: Starting index in the ordered dataset (0-indexed, inclusive)
        end_idx: Ending index in the ordered dataset (0-indexed, exclusive)
        require_unit_tests: If True, only sample datapoints that have unit tests (default: False)

    Returns:
        List of randomly sampled Datapoint objects (may be fewer than n if insufficient eligible samples)

    Note:
        Uses Python's random.shuffle() for deterministic sampling since SQLite's RANDOM()
        does not support seeding. Only loads IDs into memory, not full datapoint objects.

        Sequential mode (start_idx/end_idx): Returns datapoints[start_idx:end_idx] from
        the ordered, filtered dataset. Useful for splitting large runs across multiple jobs.

        When require_unit_tests=True, filters to PBTs that have at least one associated
        unit test via the pbt_functions and unit_test_functions junction tables.
    """
    # Use json_array_length to filter by dependency count
    # Fetch only IDs (lightweight) instead of full datapoint objects
    # ORDER BY id ensures deterministic ordering from database
    id_statement = (
        select(Datapoint.id)
        .where(func.json_array_length(Datapoint.deps) <= MAX_DEPENDENCIES)
        .order_by(Datapoint.id)  # type: ignore[attr-defined]
    )

    # Optionally filter to only datapoints with unit tests
    if require_unit_tests:
        # Join through pbt_functions to unit_test_functions to find PBTs with unit tests
        # Use EXISTS subquery for efficient filtering
        has_unit_tests_subquery = (
            select(PBTFunction.pbt_id)
            .join(
                UnitTestFunction,
                PBTFunction.function_name == UnitTestFunction.function_name,
            )
            .where(PBTFunction.pbt_id == Datapoint.id)
        )
        id_statement = id_statement.where(has_unit_tests_subquery.exists())

    # Fetch all eligible IDs (deterministic order guaranteed by ORDER BY)
    results = session.exec(id_statement)
    all_ids = list(results)

    # Return empty list if no eligible datapoints
    if not all_ids:
        return []

    # Sequential mode: slice by indices if provided
    if start_idx is not None or end_idx is not None:
        # Use Python's slice semantics (None = unbounded)
        selected_ids = all_ids[start_idx:end_idx]
        # Create RNG for unit test sampling (sequential mode still needs reproducibility)
        rng = random.Random(ranseed)
    else:
        # Random sampling mode: shuffle and take first n
        # Shuffle IDs using seeded RNG for deterministic sampling
        rng = random.Random(ranseed)
        rng.shuffle(all_ids)

        # Take first n IDs (or all if fewer than n available)
        sample_size = min(n, len(all_ids))
        selected_ids = all_ids[:sample_size]

    # Fetch full datapoints for selected IDs
    datapoints_statement = select(Datapoint).where(
        Datapoint.id.in_(selected_ids)  # type: ignore[attr-defined]
    )
    datapoints = list(session.exec(datapoints_statement))

    # Populate unit_tests field for all datapoints in a single batched query
    # (avoids N+1 query pattern: 1 batch query instead of ~3 queries per datapoint)
    all_unit_tests_by_pbt = get_all_overlapping_unit_tests(
        session, [dp.id for dp in datapoints]
    )
    for dp in datapoints:
        unit_tests = all_unit_tests_by_pbt.get(dp.id, [])
        # Sample up to MAX_UNIT_TESTS to keep prompts manageable
        original_count = len(unit_tests)
        if original_count > MAX_UNIT_TESTS:
            # Use the same seeded RNG for reproducible unit test sampling
            unit_tests = rng.sample(unit_tests, MAX_UNIT_TESTS)
            logger.debug(
                f"Sampled {MAX_UNIT_TESTS} of {original_count} unit tests for datapoint {dp.id}"
            )
        # Set the unit_tests field directly (now a proper field on the model)
        dp.unit_tests = unit_tests

    # Return in correct order
    # For sequential mode, preserve order from all_ids slice
    # For random mode, preserve shuffled order
    id_to_datapoint = {dp.id: dp for dp in datapoints}
    missing_ids = [dp_id for dp_id in selected_ids if dp_id not in id_to_datapoint]
    if missing_ids:
        raise KeyError(
            f"Datapoint(s) with ID(s) {missing_ids} not found in database. Data integrity issue."
        )
    return [id_to_datapoint[dp_id] for dp_id in selected_ids]


def load_datapoints_by_id(
    session: Session,
    datapoint_ids: list[int],
) -> dict[int, Datapoint]:
    """Load specific datapoints by their IDs.

    Args:
        session: SQLModel database session
        datapoint_ids: List of datapoint IDs to load

    Returns:
        Dictionary mapping datapoint ID to Datapoint object (only IDs that were found)
    """
    statement = select(Datapoint).where(
        Datapoint.id.in_(datapoint_ids)  # type: ignore[attr-defined]
    )
    results = session.exec(statement)
    return {dp.id: dp for dp in results}


def count_total_datapoints(session: Session) -> int:
    """Get total count of datapoints in the database.

    Args:
        session: SQLModel database session

    Returns:
        Total number of datapoints
    """
    statement = select(func.count(Datapoint.id))
    return session.exec(statement).one()


def get_all_overlapping_unit_tests(
    session: Session,
    pbt_ids: list[int],
) -> dict[int, list[dict[str, Any]]]:
    """Get unit tests that share functions with given PBTs, in a single batched query.

    Replaces per-datapoint get_overlapping_unit_tests() calls with a single JOIN
    query across all PBT IDs, eliminating the N+1 query pattern.

    Args:
        session: SQLModel database session
        pbt_ids: List of PBT IDs to find overlapping unit tests for

    Returns:
        Dictionary mapping pbt_id to list of unit test dicts:
        {pbt_id: [{"code": "...", "name": "test_foo", ...}, ...]}
    """
    if not pbt_ids:
        return {}

    result: dict[int, list[dict[str, Any]]] = {}

    # Batch to stay under SQLite parameter limit
    for id_batch in _batch_items(pbt_ids):
        # Single JOIN query: pbt_functions → unit_test_functions → unit_tests
        stmt = (
            select(PBTFunction.pbt_id, UnitTest)
            .join(
                UnitTestFunction,
                PBTFunction.function_name == UnitTestFunction.function_name,
            )
            .join(UnitTest, UnitTestFunction.unit_test_id == UnitTest.id)
            .where(PBTFunction.pbt_id.in_(id_batch))  # type: ignore[attr-defined]
        )
        rows = session.exec(stmt).all()

        # Group by pbt_id, deduplicating unit tests
        for pbt_id, ut in rows:
            if pbt_id not in result:
                result[pbt_id] = []
            ut_dict = {
                "code": ut.code,
                "name": ut.name,
                "source_file": ut.source_file,
                "start_line": ut.start_line,
                "end_line": ut.end_line,
            }
            # Deduplicate by unit test id
            if not any(
                existing.get("name") == ut.name
                and existing.get("source_file") == ut.source_file
                for existing in result[pbt_id]
            ):
                result[pbt_id].append(ut_dict)

    return result


def get_overlapping_unit_tests(
    session: Session,
    pbt_id: int,
) -> list[dict[str, Any]]:
    """Get unit tests that share functions with a given PBT.

    This reconstructs the overlapping_tests data structure from the relational schema.

    Args:
        session: SQLModel database session
        pbt_id: ID of the PBT to find overlaps for

    Returns:
        List of overlap dictionaries with structure:
        [
            {
                "shared_functions": ["func1", "func2"],
                "unit_tests": [
                    {"code": "...", "name": "test_foo", ...},
                    ...
                ]
            }
        ]

    Note:
        This may be expensive for PBTs with many shared functions.
        Consider caching or materializing this data if needed frequently.
    """
    # Get all function names shared by this PBT
    shared_funcs_stmt = select(PBTFunction.function_name).where(
        PBTFunction.pbt_id == pbt_id
    )
    shared_functions = list(session.exec(shared_funcs_stmt))

    if not shared_functions:
        return []

    # Get all unit test IDs that use these functions
    # Batch the query if there are many shared functions to avoid SQLite parameter limit
    unit_test_ids = []
    for func_batch in _batch_items(shared_functions):
        unit_test_ids_stmt = select(UnitTestFunction.unit_test_id).where(
            UnitTestFunction.function_name.in_(func_batch)  # type: ignore[attr-defined]
        )
        batch_ids = list(session.exec(unit_test_ids_stmt))
        unit_test_ids.extend(batch_ids)

    # Deduplicate IDs
    unit_test_ids = list(set(unit_test_ids))

    if not unit_test_ids:
        return []

    # Fetch the actual unit tests
    # Batch the query if there are many unit test IDs to avoid SQLite parameter limit
    unit_tests = []
    for id_batch in _batch_items(unit_test_ids):
        unit_tests_stmt = select(UnitTest).where(
            UnitTest.id.in_(id_batch)  # type: ignore[attr-defined]
        )
        batch_tests = list(session.exec(unit_tests_stmt))
        unit_tests.extend(batch_tests)

    # Format as expected by existing code
    # Group by shared functions (simplified - just one group for now)
    return [
        {
            "shared_functions": shared_functions,
            "unit_tests": [
                {
                    "code": ut.code,
                    "name": ut.name,
                    "source_file": ut.source_file,
                    "start_line": ut.start_line,
                    "end_line": ut.end_line,
                }
                for ut in unit_tests
            ],
        }
    ]


def lookup_function_exact(
    session: Session,
    function_name: str,
    repo_id: int | None = None,
) -> Function | None:
    """Look up a function by exact name match.

    Args:
        session: SQLModel database session
        function_name: Exact function name to look up
        repo_id: Optional repository ID for scope-aware lookup (prefer same repo)

    Returns:
        Function object if found, None otherwise
        If repo_id provided and multiple matches, returns same-repo match first
    """
    statement = select(Function).where(Function.name == function_name)

    # If repo_id provided, try to get same-repo match first
    if repo_id is not None:
        same_repo_stmt = statement.where(Function.repo_id == repo_id)
        result = session.exec(same_repo_stmt).first()
        if result:
            return result

    # Fall back to any match
    return session.exec(statement).first()


def lookup_function_fuzzy(
    session: Session,
    function_name: str,
    repo_id: int | None = None,
    limit: int = 5,
) -> list[Function]:
    """Look up functions with fuzzy name matching.

    Args:
        session: SQLModel database session
        function_name: Function name pattern (supports SQL LIKE patterns)
        repo_id: Optional repository ID for scope-aware lookup (prefer same repo)
        limit: Maximum number of results to return

    Returns:
        List of matching Function objects, ordered by repo match and name similarity
    """
    # Use SQL LIKE for fuzzy matching
    # Try exact first, then prefix, then contains
    patterns = [
        function_name,  # exact
        f"{function_name}%",  # prefix
        f"%{function_name}%",  # contains
    ]

    results: list[Function] = []
    for pattern in patterns:
        statement = select(Function).where(Function.name.like(pattern)).limit(limit)  # type: ignore[attr-defined]

        # If repo_id provided, prioritize same-repo matches
        if repo_id is not None:
            same_repo_stmt = statement.where(Function.repo_id == repo_id)
            same_repo_results = list(session.exec(same_repo_stmt))
            if same_repo_results:
                return same_repo_results[:limit]

        matches = list(session.exec(statement))
        if matches:
            return matches[:limit]

    return results


def get_associated_function_names(
    session: Session,
    pbt_id: int,
) -> list[str]:
    """Get function names associated with a PBT from pbt_functions table.

    Args:
        session: SQLModel database session
        pbt_id: ID of the PBT

    Returns:
        List of function names associated with this PBT
    """
    statement = select(PBTFunction.function_name).where(PBTFunction.pbt_id == pbt_id)
    return list(session.exec(statement))
