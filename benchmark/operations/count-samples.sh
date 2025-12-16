#!/usr/bin/env bash
# Quick script to count available samples in the database

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCHMARK_DIR="$(dirname "$SCRIPT_DIR")"

cd "$BENCHMARK_DIR"

echo "Counting samples in pbts_full.db..."
echo ""

uv run python -c "
from sqlmodel import Session, func, select
from generate.scaffold.dataset.connection import get_session
from generate.scaffold.dataset.models import Datapoint, PBTFunction, UnitTestFunction
from generate.config import DATA_DIR

with get_session(DATA_DIR / 'pbts_full.db') as session:
    # Total count
    total = session.exec(select(func.count(Datapoint.id))).one()

    # Eligible count (after filtering by MAX_DEPENDENCIES = 100)
    eligible = session.exec(
        select(func.count(Datapoint.id))
        .where(func.json_array_length(Datapoint.deps) <= 100)
    ).one()

    # With unit tests
    with_units_subquery = (
        select(PBTFunction.pbt_id)
        .join(UnitTestFunction, PBTFunction.function_name == UnitTestFunction.function_name)
        .where(PBTFunction.pbt_id == Datapoint.id)
    )
    eligible_with_units = session.exec(
        select(func.count(Datapoint.id))
        .where(func.json_array_length(Datapoint.deps) <= 100)
        .where(with_units_subquery.exists())
    ).one()

    filtered = total - eligible

    print('Database Sample Counts')
    print('=' * 50)
    print(f'Total datapoints in database:    {total:>8,}')
    print(f'Eligible for sampling:           {eligible:>8,}')
    print(f'  └─ with unit tests:            {eligible_with_units:>8,}')
    print(f'Filtered out (deps > 100):       {filtered:>8,}')
    print('=' * 50)
    print()
    print(f'Maximum batch size: {eligible:,}')
    print()
    print('Example batch runs:')
    print(f'  Full dataset:     ./operations/run-batch.sh')
    print(f'  Preview:          ./operations/run-batch.sh --dry-run')
    print(f'  Half:             ./operations/run-batch.sh --total {eligible // 2}')
    print(f'  Test (1000):      ./operations/run-batch.sh --total 1000')
    print(f'  Other variant:    ./operations/run-batch.sh --variant terse-functional')
" 2>&1 | grep -v "UnsupportedFieldAttributeWarning" | grep -v "warnings.warn"
