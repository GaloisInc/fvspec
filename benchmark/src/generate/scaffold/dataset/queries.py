"""Query functions for pbts_full.db using SQLModel.

All data access should go through these functions for consistency and testability.
"""

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

# Maximum number of dependencies allowed per sample before filtering
# Rationale: Samples with >100 dependencies are extreme outliers that:
# 1. Generate excessively large prompts (degraded model performance)
# 2. Take disproportionately long to autoformalize (hurt parallelism)
# 3. Are often synthetic/generated code rather than real-world tests
# 4. Exceed practical limits for meaningful specification generation
MAX_DEPENDENCIES = 100

# Utility function filtering for unit test extraction
# Rationale: Shared utility functions create false positives in PBT-unit test linking.
# For example, a PBT testing "Tile" operation and a unit test testing "TypeRegistry"
# may both use "np.random.rand" and "st.integers", but they test completely different
# functionality. By filtering out common utility prefixes and modules, we reduce
# false positives from ~96% to a more meaningful semantic matching.
UTILITY_PREFIXES = [
    "np.",
    "st.",
    "torch.",
    "tf.",
    "pytest.",
    "unittest.",
    "core.",
    "hypothesis.",
    "random.",
    "math.",
    "os.",
    "sys.",
    "json.",
    "pickle.",
    "itertools.",
    "functools.",
    "collections.",
]

UTILITY_MODULES = {
    "np",
    "st",
    "pytest",
    "unittest",
    "torch",
    "tf",
    "core",
    "hypothesis",
    "random",
    "math",
    "os",
    "sys",
    "json",
    "pickle",
    "itertools",
    "functools",
    "collections",
    "astype",  # numpy method
    "append",  # common list method
    "extend",  # common list method
    "assertEqual",  # unittest method
    "assertTrue",  # unittest method
    "assertFalse",  # unittest method
}


def filter_utility_functions(functions: list[str]) -> list[str]:
    """Remove common utility functions from shared function list.

    This reduces false positives in PBT-unit test linking by removing functions
    that are utilities (numpy, hypothesis, testing frameworks) rather than the
    actual functions being tested.

    Args:
        functions: List of function names (e.g., ["np.random.rand", "tile", "st.integers"])

    Returns:
        Filtered list with utility functions removed (e.g., ["tile"])

    Examples:
        >>> filter_utility_functions(["np.random.rand", "tile", "st.integers"])
        ["tile"]
        >>> filter_utility_functions(["pytest.mark", "test_foo"])
        ["test_foo"]
        >>> filter_utility_functions(["np.tile", "core.CreateOperator"])
        []  # Both are utilities
    """
    filtered = []
    for func_name in functions:
        # Skip if starts with utility prefix
        if any(func_name.startswith(prefix) for prefix in UTILITY_PREFIXES):
            continue

        # Skip if the base module/function is a utility
        base = func_name.split(".")[0] if "." in func_name else func_name
        if base in UTILITY_MODULES:
            continue

        filtered.append(func_name)

    return filtered


def sample_datapoints(
    session: Session,
    n: int,
    ranseed: int | None = 0,
) -> list[Datapoint]:
    """Sample n random datapoints, filtering by dependency count.

    Implements memory-efficient deterministic sampling by:
    1. Fetching only IDs of eligible datapoints (deps <= MAX_DEPENDENCIES)
    2. Shuffling IDs using seeded Python RNG
    3. Taking first n IDs and fetching full datapoints

    Args:
        session: SQLModel database session
        n: Number of samples to draw
        ranseed: Random seed for reproducibility (default: 0)

    Returns:
        List of randomly sampled Datapoint objects (may be fewer than n if insufficient eligible samples)

    Note:
        Uses Python's random.shuffle() for deterministic sampling since SQLite's RANDOM()
        does not support seeding. Only loads IDs into memory, not full datapoint objects.
    """
    # Use json_array_length to filter by dependency count
    # Fetch only IDs (lightweight) instead of full datapoint objects
    # ORDER BY id ensures deterministic ordering from database
    id_statement = (
        select(Datapoint.id)
        .where(func.json_array_length(Datapoint.deps) <= MAX_DEPENDENCIES)
        .order_by(Datapoint.id)  # type: ignore[attr-defined]
    )

    # Fetch all eligible IDs (deterministic order guaranteed by ORDER BY)
    results = session.exec(id_statement)
    all_ids = list(results)

    # Return empty list if no eligible datapoints
    if not all_ids:
        return []

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

    # Return in shuffled order (IN clause doesn't preserve order)
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


def get_overlapping_unit_tests(
    session: Session,
    pbt_id: int,
    filter_utilities: bool = True,
) -> list[dict[str, Any]]:
    """Get unit tests that share functions with a given PBT.

    This reconstructs the overlapping_tests data structure from the relational schema.

    Args:
        session: SQLModel database session
        pbt_id: ID of the PBT to find overlaps for
        filter_utilities: If True, filter out utility functions (numpy, hypothesis, etc.)
                         to reduce false positives. Default: True.

    Returns:
        List of overlap dictionaries with structure:
        [
            {
                "shared_functions": ["func1", "func2"],  # Non-utility functions only if filter_utilities=True
                "unit_tests": [
                    {"code": "...", "name": "test_foo", ...},
                    ...
                ]
            }
        ]

        Returns empty list if no non-utility functions are shared (when filter_utilities=True).

    Note:
        Batches queries to avoid SQLite's 999 variable limit on IN clauses.
    """
    # Get all function names shared by this PBT
    shared_funcs_stmt = select(PBTFunction.function_name).where(
        PBTFunction.pbt_id == pbt_id
    )
    shared_functions = list(session.exec(shared_funcs_stmt))

    if not shared_functions:
        return []

    # Filter out utility functions if requested
    if filter_utilities:
        shared_functions = filter_utility_functions(shared_functions)
        if not shared_functions:
            # All functions were utilities - no semantic overlap
            return []

    # Get all unit test IDs that use these functions
    unit_test_ids_stmt = select(UnitTestFunction.unit_test_id).where(
        UnitTestFunction.function_name.in_(shared_functions)  # type: ignore[attr-defined]
    )
    unit_test_ids = list(set(session.exec(unit_test_ids_stmt)))

    if not unit_test_ids:
        return []

    # Fetch the actual unit tests in batches (SQLite limit: 999 variables)
    BATCH_SIZE = 500  # Conservative batch size
    unit_tests = []

    for i in range(0, len(unit_test_ids), BATCH_SIZE):
        batch_ids = unit_test_ids[i : i + BATCH_SIZE]
        unit_tests_stmt = select(UnitTest).where(
            UnitTest.id.in_(batch_ids)  # type: ignore[attr-defined]
        )
        unit_tests.extend(session.exec(unit_tests_stmt))

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
