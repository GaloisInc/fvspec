"""Compute and export radon metrics for Python PBTs in the database.

This script analyzes Python code in pbts_full.db using radon to compute:
- Cyclomatic complexity
- Maintainability index
- Raw metrics (LOC, SLOC, comments)
- Halstead complexity metrics

Results are exported to JSON/CSV for analysis.
"""

import json
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import track
from rich.table import Table

from generate.scaffold.dataset.connection import get_session
from generate.scaffold.dataset.models import Datapoint
from generate.scaffold.quality_assessment.radon_metrics import (
    compute_metrics_for_datapoint,
)
from generate.scaffold.task import DATA_DIR

app = typer.Typer()
console = Console()


@app.command()
def compute(
    datafile: str = typer.Option(
        "pbts_full.db", help="Path to the SQLite database file"
    ),
    sample_size: int = typer.Option(
        None,
        "--sample-size",
        "-n",
        help="Number of datapoints to analyze (default: all)",
    ),
    sample_ids: list[int] = typer.Option(
        None, "--sample-id", help="Specific sample IDs to analyze (can be repeated)"
    ),
    ranseed: int = typer.Option(
        0, help="Random seed for sampling (when sample-size is specified)"
    ),
    output_dir: str = typer.Option(
        "artifacts/radon_metrics", help="Output directory for results"
    ),
    output_format: str = typer.Option("json", help="Output format: json, csv, or both"),
    show_failures: bool = typer.Option(
        False, "--show-failures", help="Show datapoints that failed analysis"
    ),
) -> None:
    """Compute radon code metrics for Python PBTs in the database.

    Examples:
        # Analyze all datapoints
        uv run compute-radon-metrics

        # Analyze a sample of 100 datapoints
        uv run compute-radon-metrics --sample-size 100

        # Analyze specific datapoints
        uv run compute-radon-metrics --sample-id 1 --sample-id 42 --sample-id 100

        # Export to CSV
        uv run compute-radon-metrics --sample-size 1000 --output-format csv
    """
    dataset_path = (DATA_DIR / datafile).resolve()
    if not dataset_path.exists():
        console.print(f"[red]Error:[/red] Database not found at {dataset_path}")
        raise typer.Exit(code=1)

    console.print(f"[bold]Computing radon metrics from {datafile}[/bold]\n")

    # Load datapoints
    with get_session(dataset_path) as session:
        if sample_ids:
            # Load specific IDs
            from generate.scaffold.dataset.queries import load_datapoints_by_id

            dp_dict = load_datapoints_by_id(session, sample_ids)
            datapoints = list(dp_dict.values())
            console.print(f"Loaded {len(datapoints)} specific datapoint(s)")
        elif sample_size:
            # Sample random datapoints
            from generate.scaffold.dataset.queries import sample_datapoints

            datapoints = sample_datapoints(session, n=sample_size, ranseed=ranseed)
            console.print(f"Sampled {len(datapoints)} datapoint(s) (seed={ranseed})")
        else:
            # Load all datapoints
            from sqlmodel import select

            result = session.exec(select(Datapoint))
            datapoints = list(result.all())
            console.print(f"Loaded all {len(datapoints)} datapoints")

    if not datapoints:
        console.print("[yellow]No datapoints to analyze[/yellow]")
        return

    # Compute metrics
    console.print(f"\n[bold]Analyzing {len(datapoints)} datapoint(s)...[/bold]\n")

    results = []
    failed = []

    for dp in track(datapoints, description="Computing metrics"):
        metrics = compute_metrics_for_datapoint(dp.code)

        if metrics:
            results.append(
                {
                    "id": dp.id,
                    "name": dp.name,
                    "repo_id": dp.repo_id,
                    # Raw metrics
                    "loc": metrics.loc,
                    "sloc": metrics.sloc,
                    "lloc": metrics.lloc,
                    "comments": metrics.comments,
                    "blank": metrics.blank,
                    "multi": metrics.multi,
                    "single_comments": metrics.single_comments,
                    # Cyclomatic complexity
                    "num_functions": metrics.num_functions,
                    "avg_complexity": round(metrics.average_complexity, 2),
                    "max_complexity": metrics.max_complexity,
                    "total_complexity": metrics.total_complexity,
                    "complexity_rank": metrics.complexity_rank(),
                    # Maintainability
                    "maintainability_index": round(metrics.maintainability_index, 2),
                    "maintainability_rank": metrics.maintainability_rank(),
                    # Halstead
                    "halstead_vocabulary": metrics.halstead_vocabulary,
                    "halstead_length": metrics.halstead_length,
                    "halstead_volume": round(metrics.halstead_volume, 2),
                    "halstead_difficulty": round(metrics.halstead_difficulty, 2),
                    "halstead_effort": round(metrics.halstead_effort, 2),
                    "halstead_time": round(metrics.halstead_time, 2),
                    "halstead_bugs": round(metrics.halstead_bugs, 4),
                }
            )
        else:
            failed.append({"id": dp.id, "name": dp.name})

    # Summary statistics
    console.print("\n[bold green]✓ Analysis complete[/bold green]")
    console.print(f"  Successful: {len(results)}/{len(datapoints)}")
    console.print(f"  Failed: {len(failed)}/{len(datapoints)}")

    if show_failures and failed:
        console.print("\n[yellow]Failed datapoints:[/yellow]")
        for item in failed[:10]:  # Show first 10
            console.print(f"  - ID {item['id']}: {item['name']}")
        if len(failed) > 10:
            console.print(f"  ... and {len(failed) - 10} more")

    # Display sample results
    if results:
        console.print("\n[bold]Sample results:[/bold]")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("ID", style="dim", width=6)
        table.add_column("Name", width=30)
        table.add_column("LOC", justify="right", width=6)
        table.add_column("CC", justify="right", width=4)
        table.add_column("MI", justify="right", width=6)
        table.add_column("Rank", width=6)

        for result in results[:10]:  # Show first 10
            table.add_row(
                str(result["id"]),
                result["name"][:28],
                str(result["loc"]),
                str(result["avg_complexity"]),
                str(result["maintainability_index"]),
                f"{result['complexity_rank']}/{result['maintainability_rank']}",
            )

        console.print(table)

        if len(results) > 10:
            console.print(f"\n... and {len(results) - 10} more results")

    # Export results
    if results:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")

        if output_format in ["json", "both"]:
            json_file = output_path / f"radon_metrics_{timestamp}.json"
            json_file.write_text(json.dumps(results, indent=2))
            console.print(f"\n[green]✓[/green] JSON exported to: {json_file}")

        if output_format in ["csv", "both"]:
            import csv

            csv_file = output_path / f"radon_metrics_{timestamp}.csv"
            if results:
                with open(csv_file, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=results[0].keys())
                    writer.writeheader()
                    writer.writerows(results)
                console.print(f"[green]✓[/green] CSV exported to: {csv_file}")

        # Also export failure list if any
        if failed:
            failed_file = output_path / f"radon_metrics_failed_{timestamp}.json"
            failed_file.write_text(json.dumps(failed, indent=2))
            console.print(
                f"[yellow]⚠[/yellow] Failed datapoints logged to: {failed_file}"
            )


@app.command()
def stats(
    datafile: str = typer.Option(
        "pbts_full.db", help="Path to the SQLite database file"
    ),
    sample_size: int = typer.Option(
        1000, help="Number of datapoints to sample for statistics"
    ),
    ranseed: int = typer.Option(0, help="Random seed for sampling"),
) -> None:
    """Compute aggregate statistics for radon metrics across the dataset.

    This command samples datapoints and shows distribution of complexity metrics.
    """
    dataset_path = (DATA_DIR / datafile).resolve()
    if not dataset_path.exists():
        console.print(f"[red]Error:[/red] Database not found at {dataset_path}")
        raise typer.Exit(code=1)

    console.print(f"[bold]Computing statistics from {sample_size} datapoints[/bold]\n")

    # Load sample
    with get_session(dataset_path) as session:
        from generate.scaffold.dataset.queries import sample_datapoints

        datapoints = sample_datapoints(session, n=sample_size, ranseed=ranseed)

    # Compute metrics
    metrics_list = []
    for dp in track(datapoints, description="Analyzing"):
        metrics = compute_metrics_for_datapoint(dp.code)
        if metrics:
            metrics_list.append(metrics)

    if not metrics_list:
        console.print("[yellow]No metrics computed[/yellow]")
        return

    # Compute statistics
    import statistics

    def safe_mean(values):
        return statistics.mean(values) if values else 0

    def safe_median(values):
        return statistics.median(values) if values else 0

    def safe_stdev(values):
        return statistics.stdev(values) if len(values) > 1 else 0

    console.print(
        f"\n[bold green]Statistics from {len(metrics_list)} samples:[/bold green]\n"
    )

    # LOC statistics
    locs = [m.loc for m in metrics_list]
    slocs = [m.sloc for m in metrics_list]
    console.print("[bold]Lines of Code:[/bold]")
    console.print(
        f"  LOC  - Mean: {safe_mean(locs):.1f}, Median: {safe_median(locs)}, Std: {safe_stdev(locs):.1f}"
    )
    console.print(
        f"  SLOC - Mean: {safe_mean(slocs):.1f}, Median: {safe_median(slocs)}, Std: {safe_stdev(slocs):.1f}"
    )

    # Complexity statistics
    ccs = [m.average_complexity for m in metrics_list if m.num_functions > 0]
    console.print("\n[bold]Cyclomatic Complexity:[/bold]")
    console.print(
        f"  Average CC - Mean: {safe_mean(ccs):.2f}, Median: {safe_median(ccs):.2f}, Std: {safe_stdev(ccs):.2f}"
    )

    # Complexity ranks distribution
    ranks = [m.complexity_rank() for m in metrics_list]
    rank_counts = {r: ranks.count(r) for r in "ABCDF"}
    console.print("  Rank distribution:")
    for rank in "ABCDF":
        pct = (rank_counts[rank] / len(ranks) * 100) if ranks else 0
        console.print(f"    {rank}: {rank_counts[rank]} ({pct:.1f}%)")

    # Maintainability statistics
    mis = [m.maintainability_index for m in metrics_list]
    console.print("\n[bold]Maintainability Index:[/bold]")
    console.print(
        f"  Mean: {safe_mean(mis):.1f}, Median: {safe_median(mis):.1f}, Std: {safe_stdev(mis):.1f}"
    )

    # Halstead statistics
    volumes = [m.halstead_volume for m in metrics_list if m.halstead_volume > 0]
    console.print("\n[bold]Halstead Metrics:[/bold]")
    console.print(
        f"  Volume - Mean: {safe_mean(volumes):.1f}, Median: {safe_median(volumes):.1f}"
    )

    bugs = [m.halstead_bugs for m in metrics_list if m.halstead_bugs > 0]
    console.print(
        f"  Estimated bugs - Mean: {safe_mean(bugs):.4f}, Median: {safe_median(bugs):.4f}"
    )


def cli():
    """Entry point for the compute-radon-metrics CLI command."""
    app()


if __name__ == "__main__":
    cli()
