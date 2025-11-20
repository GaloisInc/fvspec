"""Post-production analysis: Download and aggregate W&B runs for analysis.

This CLI tool downloads runs listed in manifest.toml from W&B and syncs
them to a local directory for analysis.

Usage (from benchmark/ directory):
    uv run python -m scripts.postproduction.accumulate sync
    uv run python -m scripts.postproduction.accumulate list-runs
    uv run python -m scripts.postproduction.accumulate status
"""

import json
import tomllib
from pathlib import Path
from typing import Any

import typer
import wandb
from pydantic import BaseModel
from rich.console import Console
from rich.progress import track

app = typer.Typer(help="Download and aggregate W&B runs for post-production analysis")
console = Console()


class ProjectConfig(BaseModel):
    """Project configuration from manifest.toml."""

    entity: str
    project: str
    output_dir: str


class Manifest(BaseModel):
    """Manifest schema for runs to download."""

    project: ProjectConfig
    run_names: list[str]


def load_manifest(manifest_path: Path) -> Manifest:
    """Load and validate manifest.toml."""
    with open(manifest_path, "rb") as f:
        data = tomllib.load(f)
    return Manifest(**data)


def download_run(
    api: wandb.Api,
    entity: str,
    project: str,
    run_id: str,
    output_dir: Path,
) -> dict[str, Any]:
    """Download a single run's data from W&B.

    Downloads:
    - Run metadata (config, summary, state)
    - Sample files (.lean, .json) if available
    - Metrics history

    Returns:
        Dictionary with run metadata and local paths
    """
    run = api.run(f"{entity}/{project}/{run_id}")

    # Create run directory
    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Download run metadata
    metadata = {
        "id": run.id,
        "name": run.name,
        "state": run.state,
        "created_at": run.created_at,
        "config": dict(run.config),
        "summary": dict(run.summary),
        "tags": run.tags,
        "group": run.group,
    }

    # Save metadata as JSON
    with open(run_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2, default=str)

    # Download metrics history
    history = run.history(samples=10000)  # Increased from default 500
    if not history.empty:
        history.to_csv(run_dir / "history.csv", index=False)

    # Download files
    files_dir = run_dir / "files"
    files_dir.mkdir(exist_ok=True)

    downloaded_files = []
    for file in run.files():
        # Download .lean, .json files (sample artifacts)
        if file.name.endswith((".lean", ".json")):
            try:
                file.download(root=str(files_dir), replace=True)
                downloaded_files.append(file.name)
            except Exception as e:
                console.print(
                    f"[yellow]Warning: Failed to download {file.name}: {e}[/yellow]"
                )

    return {
        "run_id": run_id,
        "run_name": run.name,
        "local_path": str(run_dir),
        "downloaded_files": len(downloaded_files),
        "state": run.state,
    }


@app.command()
def sync(
    manifest: Path = typer.Option(
        Path("src/scripts/postproduction/accumulate/manifest.toml"),
        "--manifest",
        "-m",
        help="Path to manifest.toml (relative to benchmark/)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Re-download even if already exists",
    ),
) -> None:
    """Download all runs listed in manifest.toml.

    Reads manifest.toml and downloads all listed W&B runs to the local
    output directory specified in the manifest.

    Example (from benchmark/ directory):
        uv run python -m scripts.postproduction.accumulate sync
        uv run python -m scripts.postproduction.accumulate sync --force
    """
    console.print("[bold]Post-production analysis: Syncing W&B runs[/bold]\n")

    # Load manifest
    if not manifest.exists():
        console.print(f"[red]Error: Manifest not found at {manifest}[/red]")
        raise typer.Exit(1)

    console.print(f"Loading manifest from: {manifest}")
    config = load_manifest(manifest)

    # Setup output directory (relative to benchmark/ root, not manifest location)
    # Go up from src/scripts/postproduction/accumulate/ to benchmark/
    benchmark_root = manifest.parent.parent.parent.parent
    output_dir = benchmark_root / config.project.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"Output directory: {output_dir}\n")

    # Initialize W&B API
    console.print("Initializing W&B API...")
    api = wandb.Api()

    # Lookup runs by name to get IDs
    console.print("Looking up runs by name...")
    run_lookup = {}
    for run_name in config.run_names:
        try:
            # Search for run by name
            runs = api.runs(
                f"{config.project.entity}/{config.project.project}",
                filters={"display_name": run_name},
            )
            matching_runs = list(runs)
            if matching_runs:
                run_lookup[run_name] = matching_runs[0].id
                console.print(f"  Found: {run_name} -> {matching_runs[0].id}")
            else:
                console.print(
                    f"  [yellow]Warning: No run found with name '{run_name}'[/yellow]"
                )
        except Exception as e:
            console.print(f"  [red]Error looking up '{run_name}': {e}[/red]")

    # Download runs
    console.print(f"\nDownloading {len(run_lookup)} runs:")
    results = []

    for run_name, run_id in track(
        run_lookup.items(), description="Downloading runs", console=console
    ):
        run_dir = output_dir / run_id

        # Skip if already exists (unless force)
        if run_dir.exists() and not force:
            console.print(
                f"  [dim]Skipping {run_name} ({run_id}) - already exists[/dim]"
            )
            continue

        console.print(f"  Downloading {run_name} ({run_id})...")
        try:
            result = download_run(
                api,
                config.project.entity,
                config.project.project,
                run_id,
                output_dir,
            )
            results.append(result)
            console.print(
                f"    [green]✓[/green] Downloaded {result['downloaded_files']} files"
            )
        except Exception as e:
            console.print(f"    [red]✗ Error: {e}[/red]")
            results.append({"run_id": run_id, "run_name": run_name, "error": str(e)})

    # Summary
    console.print("\n[bold]Summary:[/bold]")
    successful = [r for r in results if "error" not in r]
    failed = [r for r in results if "error" in r]
    console.print(f"  Successful: {len(successful)}")
    console.print(f"  Failed: {len(failed)}")
    console.print(f"  Total runs in manifest: {len(config.run_names)}")
    console.print(f"\nData saved to: {output_dir}")


@app.command()
def list_runs(
    manifest: Path = typer.Option(
        Path("src/scripts/postproduction/accumulate/manifest.toml"),
        "--manifest",
        "-m",
        help="Path to manifest.toml (relative to benchmark/)",
    ),
) -> None:
    """List all runs in manifest.toml.

    Example (from benchmark/ directory):
        uv run python -m scripts.postproduction.accumulate list-runs
    """
    config = load_manifest(manifest)

    console.print(f"[bold]Run names in {manifest}:[/bold]\n")
    for i, run_name in enumerate(config.run_names, 1):
        console.print(f"{i}. {run_name}")


@app.command()
def status(
    manifest: Path = typer.Option(
        Path("src/scripts/postproduction/accumulate/manifest.toml"),
        "--manifest",
        "-m",
        help="Path to manifest.toml (relative to benchmark/)",
    ),
) -> None:
    """Show download status for runs in manifest.toml.

    Example (from benchmark/ directory):
        uv run python -m scripts.postproduction.accumulate status
    """
    config = load_manifest(manifest)
    # Output directory is relative to benchmark/ root
    benchmark_root = manifest.parent.parent.parent.parent
    output_dir = benchmark_root / config.project.output_dir

    console.print("[bold]Download status:[/bold]\n")

    # Need to look up run IDs from names
    api = wandb.Api()
    for run_name in config.run_names:
        try:
            runs = api.runs(
                f"{config.project.entity}/{config.project.project}",
                filters={"display_name": run_name},
            )
            matching_runs = list(runs)
            if matching_runs:
                run_id = matching_runs[0].id
                run_dir = output_dir / run_id
                if run_dir.exists():
                    # Count files
                    files_dir = run_dir / "files"
                    file_count = (
                        len(list(files_dir.glob("**/*"))) if files_dir.exists() else 0
                    )
                    console.print(
                        f"[green]✓[/green] {run_name} ({run_id}) - {file_count} files"
                    )
                else:
                    console.print(
                        f"[red]✗[/red] {run_name} ({run_id}) - not downloaded"
                    )
            else:
                console.print(f"[yellow]?[/yellow] {run_name} - not found in W&B")
        except Exception as e:
            console.print(f"[red]✗[/red] {run_name} - error: {e}")


if __name__ == "__main__":
    app()
