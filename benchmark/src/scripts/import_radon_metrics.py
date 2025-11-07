"""Import radon metrics from JSON/CSV into pbts_full.db.

This script creates a new table for radon metrics and populates it from
the exported metrics files. The table is linked to the pbts table via
the datapoint ID.

Usage:
    uv run python src/scripts/import_radon_metrics.py --file artifacts/radon_metrics/radon_metrics_2025-11-05T10-50-42.json
"""

import json
from pathlib import Path

import typer
from generate.scaffold.task import DATA_DIR
from rich.console import Console
from rich.progress import track
from sqlalchemy import text
from sqlmodel import Field, Session, SQLModel, create_engine, select

app = typer.Typer()
console = Console()


class RadonMetricsDB(SQLModel, table=True):
    """Radon code metrics table for Python PBTs.

    This table stores objective code quality metrics computed by radon.
    Each row corresponds to a datapoint in the pbts table.
    """

    __tablename__ = "radon_metrics"

    # Link to pbts table
    pbt_id: int = Field(primary_key=True, foreign_key="pbts.id")

    # Raw metrics
    loc: int = Field(description="Total lines of code")
    sloc: int = Field(description="Source lines of code (no blanks/comments)")
    lloc: int = Field(description="Logical lines of code")
    comments: int = Field(description="Number of comment lines")
    blank: int = Field(description="Number of blank lines")
    multi: int = Field(description="Multi-line strings")
    single_comments: int = Field(description="Single-line comments")

    # Cyclomatic complexity
    num_functions: int = Field(description="Number of functions analyzed")
    avg_complexity: float = Field(description="Average cyclomatic complexity")
    max_complexity: int = Field(description="Maximum complexity of any function")
    total_complexity: int = Field(description="Sum of all function complexities")
    complexity_rank: str = Field(description="Complexity rank (A-F)")

    # Maintainability
    maintainability_index: float = Field(
        description="Maintainability index (0-100, higher is better)"
    )
    maintainability_rank: str = Field(description="Maintainability rank (A-C)")

    # Halstead metrics
    halstead_vocabulary: int = Field(
        description="Number of unique operators and operands"
    )
    halstead_length: int = Field(description="Total number of operators and operands")
    halstead_volume: float = Field(description="Program volume")
    halstead_difficulty: float = Field(description="Difficulty to understand/maintain")
    halstead_effort: float = Field(description="Effort required to implement")
    halstead_time: float = Field(description="Time to implement (seconds)")
    halstead_bugs: float = Field(description="Expected number of bugs")


@app.command()
def import_metrics(
    file: str = typer.Argument(..., help="Path to radon metrics JSON or CSV file"),
    database: str = typer.Option(
        "pbts_full.db", help="Path to the SQLite database file"
    ),
    drop_existing: bool = typer.Option(
        False,
        "--drop-existing",
        help="Drop existing radon_metrics table if it exists",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be done without making changes"
    ),
) -> None:
    """Import radon metrics from JSON/CSV into the database.

    This creates a radon_metrics table and populates it with the computed metrics.

    Examples:
        # Import from JSON
        uv run python src/scripts/import_radon_metrics.py artifacts/radon_metrics/radon_metrics_2025-11-05T10-50-42.json

        # Import from CSV
        uv run python src/scripts/import_radon_metrics.py artifacts/radon_metrics/radon_metrics_2025-11-05T10-50-42.csv

        # Dry run to see what would happen
        uv run python src/scripts/import_radon_metrics.py --dry-run artifacts/radon_metrics/radon_metrics_2025-11-05T10-50-42.json
    """
    metrics_file = Path(file)
    if not metrics_file.exists():
        console.print(f"[red]Error:[/red] File not found: {file}")
        raise typer.Exit(code=1)

    # Load metrics data
    console.print(f"[bold]Loading metrics from {metrics_file.name}...[/bold]")

    if metrics_file.suffix == ".json":
        with open(metrics_file) as f:
            metrics_data = json.load(f)
    elif metrics_file.suffix == ".csv":
        import csv

        with open(metrics_file) as f:
            reader = csv.DictReader(f)
            metrics_data = list(reader)
    else:
        console.print(
            f"[red]Error:[/red] Unsupported file format: {metrics_file.suffix}"
        )
        raise typer.Exit(code=1)

    console.print(f"Loaded {len(metrics_data):,} metric records")

    if dry_run:
        console.print("\n[yellow]DRY RUN MODE - No changes will be made[/yellow]")
        console.print(
            f"\nWould create/update radon_metrics table with {len(metrics_data):,} rows"
        )
        console.print("\nSample record:")
        console.print(metrics_data[0])
        return

    # Connect to database
    dataset_path = (DATA_DIR / database).resolve()
    if not dataset_path.exists():
        console.print(f"[red]Error:[/red] Database not found: {dataset_path}")
        raise typer.Exit(code=1)

    console.print("\n[bold]Connecting to database...[/bold]")
    engine = create_engine(f"sqlite:///{dataset_path}")

    # Drop existing table if requested
    if drop_existing:
        console.print("[yellow]Dropping existing radon_metrics table...[/yellow]")
        with Session(engine) as session:
            session.exec(text("DROP TABLE IF EXISTS radon_metrics"))
            session.commit()

    # Create table
    console.print("[bold]Creating radon_metrics table...[/bold]")
    SQLModel.metadata.create_all(engine)

    # Insert data
    console.print(f"\n[bold]Inserting {len(metrics_data):,} records...[/bold]")

    batch_size = 1000
    inserted = 0
    skipped = 0
    errors = []

    with Session(engine) as session:
        batch = []
        for record in track(metrics_data, description="Importing"):
            try:
                # Convert types (CSV imports everything as strings)
                metrics_obj = RadonMetricsDB(
                    pbt_id=int(record["id"]),
                    loc=int(record["loc"]),
                    sloc=int(record["sloc"]),
                    lloc=int(record["lloc"]),
                    comments=int(record["comments"]),
                    blank=int(record["blank"]),
                    multi=int(record["multi"]),
                    single_comments=int(record["single_comments"]),
                    num_functions=int(record["num_functions"]),
                    avg_complexity=float(record["avg_complexity"]),
                    max_complexity=int(record["max_complexity"]),
                    total_complexity=int(record["total_complexity"]),
                    complexity_rank=str(record["complexity_rank"]),
                    maintainability_index=float(record["maintainability_index"]),
                    maintainability_rank=str(record["maintainability_rank"]),
                    halstead_vocabulary=int(record["halstead_vocabulary"]),
                    halstead_length=int(record["halstead_length"]),
                    halstead_volume=float(record["halstead_volume"]),
                    halstead_difficulty=float(record["halstead_difficulty"]),
                    halstead_effort=float(record["halstead_effort"]),
                    halstead_time=float(record["halstead_time"]),
                    halstead_bugs=float(record["halstead_bugs"]),
                )
                batch.append(metrics_obj)
                inserted += 1

                # Commit in batches
                if len(batch) >= batch_size:
                    session.add_all(batch)
                    session.commit()
                    batch = []

            except Exception as e:
                skipped += 1
                errors.append((record.get("id", "unknown"), str(e)))
                if len(errors) <= 5:  # Only store first 5 errors
                    pass

        # Commit remaining
        if batch:
            session.add_all(batch)
            session.commit()

    # Summary
    console.print("\n[bold green]✓ Import complete[/bold green]")
    console.print(f"  Inserted: {inserted:,}")
    console.print(f"  Skipped: {skipped:,}")

    if errors:
        console.print("\n[yellow]Errors encountered:[/yellow]")
        for pbt_id, error in errors[:5]:
            console.print(f"  - ID {pbt_id}: {error}")
        if len(errors) > 5:
            console.print(f"  ... and {len(errors) - 5} more")

    # Verify
    console.print("\n[bold]Verifying import...[/bold]")
    with Session(engine) as session:
        count = session.exec(select(RadonMetricsDB)).all()
        console.print(f"  Records in radon_metrics table: {len(count):,}")

    console.print("\n[green]✓ Successfully imported radon metrics to database[/green]")


@app.command()
def verify(
    database: str = typer.Option(
        "pbts_full.db", help="Path to the SQLite database file"
    ),
) -> None:
    """Verify the radon_metrics table and show sample data.

    Examples:
        uv run python src/scripts/import_radon_metrics.py verify
    """
    dataset_path = (DATA_DIR / database).resolve()
    if not dataset_path.exists():
        console.print(f"[red]Error:[/red] Database not found: {dataset_path}")
        raise typer.Exit(code=1)

    engine = create_engine(f"sqlite:///{dataset_path}")

    console.print("[bold]Verifying radon_metrics table...[/bold]\n")

    with Session(engine) as session:
        # Check if table exists
        result = session.exec(
            text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='radon_metrics'"
            )
        )
        if not result.first():
            console.print("[red]✗ radon_metrics table does not exist[/red]")
            return

        console.print("[green]✓ radon_metrics table exists[/green]")

        # Count records
        count_result = session.exec(select(RadonMetricsDB))
        count = len(list(count_result.all()))
        console.print(f"  Total records: {count:,}")

        # Show sample records
        sample = session.exec(select(RadonMetricsDB).limit(5)).all()
        if sample:
            console.print("\n[bold]Sample records:[/bold]")
            for metrics in sample:
                console.print(
                    f"  PBT ID {metrics.pbt_id}: "
                    f"LOC={metrics.loc}, CC={metrics.avg_complexity:.1f} ({metrics.complexity_rank}), "
                    f"MI={metrics.maintainability_index:.1f} ({metrics.maintainability_rank})"
                )


def cli():
    """Entry point for the import-radon-metrics CLI command."""
    app()


if __name__ == "__main__":
    cli()
