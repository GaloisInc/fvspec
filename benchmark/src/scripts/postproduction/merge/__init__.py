"""Post-production: Merge multiple benchmark runs into a unified dataset.

This CLI tool merges sample directories from multiple runs listed in runs.txt
into a single dataset-out/ directory. Handles conflicts by prefixing duplicate
sample IDs with CONFLICT_N__.

Usage (from benchmark/ directory):
    uv run merge runs.txt
    uv run merge --runs-file src/scripts/postproduction/merge/runs.txt
    uv run merge --dry-run
"""

import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.progress import track
from rich.table import Table

app = typer.Typer(help="Merge multiple benchmark runs into a unified dataset")
console = Console()


def load_runs_file(runs_file: Path) -> list[str]:
    """Load run directory names from runs.txt.

    Args:
        runs_file: Path to runs.txt file

    Returns:
        List of run directory names (stripped of whitespace and empty lines)
    """
    with open(runs_file) as f:
        runs = [line.strip() for line in f if line.strip()]
    return runs


def find_samples_in_run(artifacts_dir: Path, run_name: str) -> dict[str, Path]:
    """Find all sample directories in a run.

    Args:
        artifacts_dir: Path to artifacts/ directory
        run_name: Name of the run directory

    Returns:
        Dictionary mapping sample_id to full path
    """
    run_dir = artifacts_dir / "runs" / run_name
    if not run_dir.exists():
        console.print(f"[yellow]Warning: Run directory not found: {run_dir}[/yellow]")
        return {}

    samples = {}
    for item in run_dir.iterdir():
        # Skip .eval files and other non-sample items
        if item.is_dir() and not item.name.startswith("."):
            sample_id = item.name
            samples[sample_id] = item

    return samples


def collect_all_samples(
    artifacts_dir: Path, run_names: list[str]
) -> dict[str, list[Path]]:
    """Collect all samples from all runs, tracking conflicts.

    Args:
        artifacts_dir: Path to artifacts/ directory
        run_names: List of run directory names

    Returns:
        Dictionary mapping sample_id to list of paths (multiple if conflicts)
    """
    all_samples: dict[str, list[Path]] = defaultdict(list)

    for run_name in run_names:
        samples = find_samples_in_run(artifacts_dir, run_name)
        for sample_id, path in samples.items():
            all_samples[sample_id].append(path)

    return dict(all_samples)


def merge_samples(
    all_samples: dict[str, list[Path]],
    output_dir: Path,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Merge samples into output directory, handling conflicts.

    Args:
        all_samples: Dictionary mapping sample_id to list of source paths
        output_dir: Target directory for merged samples
        dry_run: If True, don't actually copy files

    Returns:
        Statistics about the merge operation
    """
    stats: dict[str, Any] = {
        "unique_samples": 0,
        "conflicted_samples": 0,
        "total_copies": 0,
        "conflicts": [],
    }

    for sample_id, source_paths in track(
        all_samples.items(),
        description="Merging samples",
        console=console,
    ):
        if len(source_paths) == 1:
            # No conflict - copy directly
            target = output_dir / sample_id
            if not dry_run:
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(source_paths[0], target)
            stats["unique_samples"] += 1
            stats["total_copies"] += 1

        else:
            # Conflict - copy all versions with CONFLICT_N__ prefix
            stats["conflicted_samples"] += 1
            stats["conflicts"].append(
                {"sample_id": sample_id, "num_versions": len(source_paths)}
            )

            for i, source_path in enumerate(source_paths):
                conflict_name = f"CONFLICT_{i}__{sample_id}"
                target = output_dir / conflict_name
                if not dry_run:
                    if target.exists():
                        shutil.rmtree(target)
                    shutil.copytree(source_path, target)
                stats["total_copies"] += 1

    return stats


@app.command()
def main(
    runs_file: Path = typer.Argument(
        ...,
        help="Path to runs.txt file (absolute or relative to benchmark/)",
    ),
    output_dir: str = typer.Option(
        "artifacts/dataset-out",
        "--output",
        "-o",
        help="Output directory for merged samples (relative to benchmark/)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be done without actually copying files",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Remove existing output directory if it exists",
    ),
) -> None:
    """Merge multiple benchmark runs into a unified dataset.

    Reads run directory names from runs_file (e.g., runs.txt) and merges all
    sample directories into a single output directory. Handles conflicts by
    prefixing duplicate sample IDs with CONFLICT_N__.

    Examples (from benchmark/ directory):
        uv run merge src/scripts/postproduction/merge/runs.txt
        uv run merge runs.txt --output artifacts/my-dataset
        uv run merge runs.txt --dry-run
    """
    console.print("[bold]Post-production: Merging benchmark runs[/bold]\n")

    # Load runs file
    if not runs_file.exists():
        console.print(f"[red]Error: Runs file not found: {runs_file}[/red]")
        raise typer.Exit(1)

    console.print(f"Loading runs from: {runs_file}")
    run_names = load_runs_file(runs_file)

    if not run_names:
        console.print("[red]Error: No runs found in runs file[/red]")
        raise typer.Exit(1)

    console.print(f"Found {len(run_names)} runs:\n")
    for run_name in run_names:
        console.print(f"  • {run_name}")

    # Setup paths
    artifacts_dir = Path("artifacts")
    output_path = Path(output_dir)

    if not artifacts_dir.exists():
        console.print(
            f"[red]Error: Artifacts directory not found: {artifacts_dir}[/red]"
        )
        console.print("Make sure you're running from the benchmark/ directory")
        raise typer.Exit(1)

    # Check output directory
    if output_path.exists():
        if force:
            console.print(
                f"\n[yellow]Removing existing output directory: {output_path}[/yellow]"
            )
            if not dry_run:
                shutil.rmtree(output_path)
        elif not dry_run:
            console.print(
                f"[red]Error: Output directory already exists: {output_path}[/red]"
            )
            console.print(
                "Use --force to remove it or choose a different output directory"
            )
            raise typer.Exit(1)

    # Create output directory
    if not dry_run:
        output_path.mkdir(parents=True, exist_ok=True)
    console.print(f"\nOutput directory: {output_path}")

    if dry_run:
        console.print("[yellow]DRY RUN MODE - No files will be copied[/yellow]")

    # Collect all samples
    console.print("\nCollecting samples from all runs...")
    all_samples = collect_all_samples(artifacts_dir, run_names)

    console.print(f"Found {len(all_samples)} unique sample IDs\n")

    # Merge samples
    stats = merge_samples(all_samples, output_path, dry_run=dry_run)

    # Display summary
    console.print("\n[bold]Merge Summary:[/bold]\n")

    summary_table = Table(show_header=True, header_style="bold")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Count", style="green", justify="right")

    summary_table.add_row("Unique samples", str(stats["unique_samples"]))
    summary_table.add_row("Conflicted samples", str(stats["conflicted_samples"]))
    summary_table.add_row("Total copies", str(stats["total_copies"]))

    console.print(summary_table)

    # Display conflicts if any
    if stats["conflicts"]:
        console.print("\n[bold]Conflicts detected:[/bold]\n")

        conflict_table = Table(show_header=True, header_style="bold")
        conflict_table.add_column("Sample ID", style="yellow")
        conflict_table.add_column("Versions", style="red", justify="right")

        for conflict in stats["conflicts"][:20]:  # Show first 20
            conflict_table.add_row(conflict["sample_id"], str(conflict["num_versions"]))

        if len(stats["conflicts"]) > 20:
            conflict_table.add_row(f"... and {len(stats['conflicts']) - 20} more", "")

        console.print(conflict_table)

        console.print(
            "\n[yellow]Note: Conflicted samples saved as CONFLICT_N__<sample_id>[/yellow]"
        )

    if not dry_run:
        console.print(
            f"\n[green]✓[/green] Merge complete! Data saved to: {output_path}"
        )
    else:
        console.print("\n[yellow]Dry run complete. No files were copied.[/yellow]")


if __name__ == "__main__":
    app()
