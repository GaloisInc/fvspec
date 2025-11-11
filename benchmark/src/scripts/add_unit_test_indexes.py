"""Add database indexes for unit test extraction performance.

This script creates indexes on the junction tables and unit_tests table to
optimize the get_overlapping_unit_tests() query performance.

Expected speedup: 10-50x for queries involving overlapping unit tests.

Run this once on your local pbts_full.db:
    uv run add-unit-test-indexes

Indexes created:
- idx_pbt_functions_pbt_id: Speed up PBT → function lookups
- idx_unit_test_functions_function_name: Speed up function → unit test ID lookups
- idx_unit_tests_id: Speed up unit test ID → full unit test lookups
"""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from sqlmodel import text

from generate.scaffold.dataset.connection import get_session

DATADIR = Path(".") / "data"

app = typer.Typer()
console = Console()

INDEXES = [
    (
        "idx_pbt_functions_pbt_id",
        "CREATE INDEX IF NOT EXISTS idx_pbt_functions_pbt_id ON pbt_functions(pbt_id)",
        "PBT → functions lookup",
    ),
    (
        "idx_unit_test_functions_function_name",
        "CREATE INDEX IF NOT EXISTS idx_unit_test_functions_function_name ON unit_test_functions(function_name)",
        "function → unit test IDs lookup",
    ),
    (
        "idx_unit_tests_id",
        "CREATE INDEX IF NOT EXISTS idx_unit_tests_id ON unit_tests(id)",
        "unit test ID → full unit test lookup",
    ),
]


@app.command()
def main(
    db_path: Annotated[
        Path | None,
        typer.Option(help="Path to pbts_full.db (default: data/pbts_full.db)"),
    ] = None,
    check_only: Annotated[
        bool, typer.Option(help="Check if indexes exist without creating them")
    ] = False,
):
    """Add performance indexes for unit test extraction queries."""
    if db_path is None:
        db_path = DATADIR / "pbts_full.db"

    if not db_path.exists():
        console.print(f"[red]Error:[/red] Database not found at {db_path}")
        raise typer.Exit(1)

    console.print("\n[bold cyan]Unit Test Database Indexing[/bold cyan]")
    console.print("=" * 60)
    console.print(f"Database: {db_path}")
    console.print()

    with get_session(db_path) as session:
        # Check existing indexes
        result = session.exec(
            text(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
            )
        )
        existing_indexes = set(result)

        if check_only:
            console.print("[bold]Index Status:[/bold]")
            for idx_name, _, description in INDEXES:
                status = "✅ Exists" if idx_name in existing_indexes else "❌ Missing"
                console.print(f"  {status} {idx_name}: {description}")
            console.print()
            return

        # Create indexes
        console.print("[bold]Creating indexes...[/bold]")
        created = []
        skipped = []

        for idx_name, sql, description in INDEXES:
            if idx_name in existing_indexes:
                console.print(f"  ⏭️  Skipping {idx_name} (already exists)")
                skipped.append(idx_name)
            else:
                console.print(f"  🔨 Creating {idx_name}: {description}")
                session.exec(text(sql))
                created.append(idx_name)

        # Commit changes
        session.commit()

        console.print()
        console.print("[bold green]Results:[/bold green]")
        if created:
            console.print(f"  ✅ Created {len(created)} index(es):")
            for idx_name in created:
                console.print(f"     • {idx_name}")
        if skipped:
            console.print(f"  ⏭️  Skipped {len(skipped)} existing index(es)")

        if created:
            console.print()
            console.print(
                "[bold yellow]Note:[/bold yellow] Indexes are persistent. "
                "You only need to run this once per database."
            )

        console.print()
        console.print(
            "[bold green]✅ Done![/bold green] Unit test extraction queries "
            "should now be 10-50x faster."
        )


if __name__ == "__main__":
    app()
