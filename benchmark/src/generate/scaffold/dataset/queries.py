"""Query functions for pbts_full.db using SQLModel.

All data access should go through these functions for consistency and testability.
"""

from typing import Any

from sqlmodel import Session, func, select

from generate.scaffold.dataset.models import (
    Datapoint,
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


def sample_datapoints(
    session: Session,
    n: int,
    ranseed: int | None = 0,
) -> list[Datapoint]:
    """Sample n random datapoints, filtering by dependency count.

    Args:
        session: SQLModel database session
        n: Number of samples to draw
        ranseed: Random seed for reproducibility (Note: SQLite RANDOM() doesn't support seeding directly)

    Returns:
        List of randomly sampled Datapoint objects (may be fewer than n if many samples filtered)

    Note:
        SQLite's RANDOM() function doesn't support seeding. For deterministic sampling,
        consider implementing custom seeded random selection in Python after fetching.
    """
    # Use json_array_length to filter by dependency count
    # SQLite stores JSON as TEXT, so we parse with json_array_length()
    statement = (
        select(Datapoint)
        .where(func.json_array_length(Datapoint.deps) <= MAX_DEPENDENCIES)
        .order_by(func.random())
        .limit(n)
    )

    results = session.exec(statement)
    return list(results)


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
    unit_test_ids_stmt = select(UnitTestFunction.unit_test_id).where(
        UnitTestFunction.function_name.in_(shared_functions)  # type: ignore[attr-defined]
    )
    unit_test_ids = list(set(session.exec(unit_test_ids_stmt)))

    if not unit_test_ids:
        return []

    # Fetch the actual unit tests
    unit_tests_stmt = select(UnitTest).where(
        UnitTest.id.in_(unit_test_ids)  # type: ignore[attr-defined]
    )
    unit_tests = list(session.exec(unit_tests_stmt))

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
