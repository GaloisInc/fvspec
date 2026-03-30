"""Post-production: Merge multiple benchmark runs into a unified JSONL dataset.

This CLI tool merges sample data from multiple runs listed in runs.txt
into a single JSONL file where each line contains all data for one sample:
- datapoint.json fields
- qa.json fields
- Lean code (spec, impl)
- Run provenance

The output is automatically deduplicated by sample_id, keeping the highest
quality sample when duplicates are found across runs.

Usage (from benchmark/ directory):
    uv run merge runs.txt
    uv run merge --runs-file src/scripts/postproduction/merge/runs.txt
    uv run merge --output artifacts/dataset-out/my-dataset.jsonl
"""

import json
import subprocess
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.progress import track

from scripts.postproduction.merge.deduplicate import deduplicate_samples
from scripts.postproduction.merge.prune import prune_samples

app = typer.Typer(help="Merge multiple benchmark runs into a unified JSONL dataset")
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


def process_sample(sample_dir: Path, run_name: str) -> dict[str, Any] | None:
    """Process a single sample directory into a combined JSON object.

    Args:
        sample_dir: Path to sample directory (e.g., 341_test_foo/)
        run_name: Name of the run this sample came from

    Returns:
        Combined dictionary with all sample data, or None if files missing
    """
    # Load JSON files
    datapoint_file = sample_dir / "datapoint.json"
    qa_file = sample_dir / "qa.json"

    if not datapoint_file.exists() or not qa_file.exists():
        console.print(
            f"[yellow]Skipping {sample_dir.name}: missing datapoint.json or qa.json[/yellow]"
        )
        return None

    with open(datapoint_file) as f:
        datapoint = json.load(f)

    with open(qa_file) as f:
        qa = json.load(f)

    # Read Lean code files
    spec_file = sample_dir / "Spec.lean"
    impl_file = sample_dir / "Impl.lean"

    spec_code = spec_file.read_text() if spec_file.exists() else None
    impl_code = impl_file.read_text() if impl_file.exists() else None

    # Build provenance from sample metadata and run name
    model = qa.get("model") or datapoint.get("model")
    # Run names look like "2025-12-18T14-48-17__idx43000-43500__control-functional"
    # Extract the timestamp prefix (everything before the first "__")
    run_timestamp = run_name.split("__")[0] if "__" in run_name else None
    provenance = {
        "git_commit": _get_git_commit(),
        "model": model,
        "run_timestamp": run_timestamp,
        "lean_toolchain": _get_lean_toolchain(),
    }

    # Combine all data
    combined = {
        **datapoint,  # All fields from datapoint.json
        **qa,  # All fields from qa.json
        "spec": spec_code,
        "impl": impl_code,
        "run_provenance": run_name,  # Which run this sample came from
        "provenance": provenance,
    }

    return combined


_cached_git_commit: str | None = None


def _get_git_commit() -> str | None:
    """Get the current git commit hash, cached for the process lifetime."""
    global _cached_git_commit
    if _cached_git_commit is None:
        try:
            _cached_git_commit = (
                subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
                )
                .decode()
                .strip()
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            _cached_git_commit = ""
    return _cached_git_commit or None


_cached_lean_toolchain: str | None = None


def _get_lean_toolchain() -> str | None:
    """Read lean-toolchain from lake-template, cached for the process lifetime."""
    global _cached_lean_toolchain
    if _cached_lean_toolchain is None:
        toolchain_file = (
            Path(__file__).resolve().parents[4] / "lake-template" / "lean-toolchain"
        )
        try:
            _cached_lean_toolchain = toolchain_file.read_text().strip()
        except FileNotFoundError:
            _cached_lean_toolchain = ""
    return _cached_lean_toolchain or None


def merge_runs_to_jsonl(
    artifacts_dir: Path, run_names: list[str], output_file: Path
) -> dict[str, int]:
    """Merge all samples from all runs into a single deduplicated JSONL file.

    Automatically deduplicates by sample_id, keeping the highest quality sample
    when duplicates are found across runs.

    Args:
        artifacts_dir: Path to artifacts/ directory
        run_names: List of run directory names
        output_file: Path to output JSONL file

    Returns:
        Statistics about the merge operation
    """
    stats = {
        "total_samples_processed": 0,
        "skipped": 0,
        "runs_processed": 0,
    }

    # Collect all samples from all runs
    all_samples: list[dict[str, Any]] = []

    for run_name in track(run_names, description="Processing runs", console=console):
        run_dir = artifacts_dir / "runs" / run_name

        if not run_dir.exists():
            console.print(
                f"[yellow]Warning: Run directory not found: {run_dir}[/yellow]"
            )
            continue

        stats["runs_processed"] += 1

        # Process each sample directory in the run
        for sample_dir in sorted(run_dir.iterdir()):
            # Skip .eval files and other non-sample items
            if not sample_dir.is_dir() or sample_dir.name.startswith("."):
                continue

            combined = process_sample(sample_dir, run_name)
            if combined:
                stats["total_samples_processed"] += 1
                all_samples.append(combined)
            else:
                stats["skipped"] += 1

    # Deduplicate samples by sample_id
    best_by_id = deduplicate_samples(all_samples, console)

    # Apply schema pruning transformations
    console.print("\n[bold]Applying schema transformations...[/bold]")
    pruned_samples = prune_samples(best_by_id)

    # Write deduplicated and pruned samples to file
    console.print(f"[bold]Writing {len(pruned_samples)} samples...[/bold]")
    with open(output_file, "w") as outfile:
        for sample_id in sorted(pruned_samples.keys()):
            outfile.write(json.dumps(pruned_samples[sample_id]) + "\n")

    stats["unique_samples"] = len(pruned_samples)
    stats["duplicates_replaced"] = (
        stats["total_samples_processed"] - stats["unique_samples"]
    )
    return stats


@app.command()
def main(
    runs_file: Path = typer.Argument(
        ...,
        help="Path to runs.txt file (absolute or relative to benchmark/)",
    ),
    output: str = typer.Option(
        "artifacts/dataset-out/fvspec.jsonl",
        "--output",
        "-o",
        help="Output JSONL file path (relative to benchmark/)",
    ),
) -> None:
    """Merge multiple benchmark runs into a unified deduplicated JSONL dataset.

    Reads run directory names from runs_file (e.g., runs.txt) and creates
    a JSONL file where each line contains all data for one sample:
    - All fields from datapoint.json
    - All fields from qa.json
    - Lean code (spec, impl) as string fields
    - run_provenance field indicating which run it came from

    When duplicate sample_ids are found across runs, automatically keeps
    the highest quality sample based on success, structural faithfulness,
    theorem count, and other metrics.

    Examples (from benchmark/ directory):
        uv run merge src/scripts/postproduction/merge/runs.txt
        uv run merge runs.txt --output artifacts/dataset-out/my-dataset.jsonl
    """
    console.print("[bold]Post-production: Merging benchmark runs to JSONL[/bold]\n")

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
    output_path = Path(output)

    if not artifacts_dir.exists():
        console.print(
            f"[red]Error: Artifacts directory not found: {artifacts_dir}[/red]"
        )
        console.print("Make sure you're running from the benchmark/ directory")
        raise typer.Exit(1)

    # Create output directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)

    console.print(f"\nOutput file: {output_path}")

    # Merge runs to JSONL with deduplication
    stats = merge_runs_to_jsonl(artifacts_dir, run_names, output_path)

    # Display summary
    console.print("\n[bold]Merge Summary:[/bold]\n")
    console.print(f"  Runs processed: {stats['runs_processed']}")
    console.print(f"  Total samples processed: {stats['total_samples_processed']}")
    console.print(f"  Unique samples written: {stats['unique_samples']}")
    console.print(f"  Duplicates replaced: {stats['duplicates_replaced']}")
    console.print(f"  Skipped: {stats['skipped']}")

    console.print(
        f"\n[green]✓[/green] Merge complete! Deduplicated data saved to: {output_path}"
    )
    console.print(
        f"[dim]File size: {output_path.stat().st_size / 1024 / 1024:.2f} MB[/dim]"
    )


if __name__ == "__main__":
    app()
