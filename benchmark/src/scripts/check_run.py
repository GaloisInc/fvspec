"""Check Lean compilation for benchmark run samples.

This script tests whether generated Lean code compiles by:
1. Finding the latest run (or using --run-path)
2. Testing all samples (or specific --sample-id)
3. Copying files to a temporary Lake workspace
4. Running `lake build` with timeout
5. Reporting compilation success/failure

Usage:
    uv run check-run                    # Check latest run, all samples
    uv run check-run 307                # Check specific sample in latest run
    uv run check-run --run-path benchmark/artifacts/runs/2025-10-29T21-14-12__control-functional
"""

import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import typer
from pydantic import BaseModel, Field
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

app = typer.Typer(help="Check Lean compilation for benchmark samples")
console = Console()


def extract_sample_id(dir_name: str) -> str:
    """Extract sample ID from directory name.

    Directory names follow the pattern: <id>_<pbt_name>
    e.g., 10104_test_versioned_div_scalar -> 10104

    Args:
        dir_name: Directory name containing sample ID and test name

    Returns:
        Sample ID portion of the directory name
    """
    return dir_name.split("_", 1)[0]


class CompilationResult(BaseModel, frozen=True):
    """Result of compiling a single sample."""

    sample_id: str = Field(description="Sample identifier")
    sample_path: Path = Field(description="Path to sample directory")
    success: bool = Field(description="Whether compilation succeeded")
    duration_seconds: float = Field(description="Time taken to compile in seconds")
    error_message: str | None = Field(
        None, description="Error message if compilation failed"
    )
    missing_files: list[str] | None = Field(
        None, description="List of missing required files"
    )


def find_latest_run(
    artifacts_dir: Path = Path("artifacts/runs"),
) -> Path | None:
    """Find the most recent run directory by timestamp.

    Args:
        artifacts_dir: Path to artifacts/runs directory

    Returns:
        Path to the latest run directory, or None if no runs found
    """
    if not artifacts_dir.exists():
        return None

    # Get all run directories (format: YYYY-MM-DDTHH-MM-SS__variant)
    run_dirs = [d for d in artifacts_dir.iterdir() if d.is_dir()]
    if not run_dirs:
        return None

    # Sort by directory name (timestamp prefix sorts chronologically)
    run_dirs.sort(reverse=True)
    return run_dirs[0]


def find_sample_dirs(run_path: Path, sample_ids: list[str] | None = None) -> list[Path]:
    """Find sample directories within a run.

    Args:
        run_path: Path to the run directory
        sample_ids: Optional list of specific sample IDs to find

    Returns:
        List of sample directory paths
    """
    if not run_path.exists():
        return []

    sample_dirs = []
    for item in run_path.iterdir():
        if not item.is_dir():
            continue

        # Sample directories are named: <id>_<pbt_name>
        # e.g., 10104_test_versioned_div_scalar
        if "_" in item.name:
            sample_id = extract_sample_id(item.name)
            if sample_id.isdigit() and (sample_ids is None or sample_id in sample_ids):
                sample_dirs.append(item)

    # Sort by sample ID for consistent ordering
    sample_dirs.sort(key=lambda p: p.name)
    return sample_dirs


def compile_sample(
    sample_path: Path,
    lake_template: Path = Path("lake-template"),
    timeout: int = 120,
) -> CompilationResult:
    """Compile a single sample using a temporary Lake workspace.

    Args:
        sample_path: Path to the sample directory
        lake_template: Path to the lake-template directory
        timeout: Maximum seconds to wait for compilation

    Returns:
        CompilationResult with success status and details
    """
    # Extract sample ID from directory name
    sample_id = extract_sample_id(sample_path.name)
    start_time = datetime.now()

    # Check for required files
    required_files = ["Spec.lean"]
    optional_files = ["Impl.lean"]
    missing_files = [f for f in required_files if not (sample_path / f).exists()]

    if missing_files:
        duration = (datetime.now() - start_time).total_seconds()
        return CompilationResult(
            sample_id=sample_id,
            sample_path=sample_path,
            success=False,
            duration_seconds=duration,
            error_message=f"Missing required files: {', '.join(missing_files)}",
            missing_files=missing_files,
        )

    # Create temporary workspace
    with tempfile.TemporaryDirectory(prefix=f"fvspec_check_{sample_id}_") as tmpdir:
        workspace = Path(tmpdir)

        try:
            # Copy entire lake-template including .lake (but exclude .git to avoid conflicts)
            def ignore_git_dirs(directory: str, contents: list[str]) -> set[str]:
                """Ignore .git directories to avoid repository conflicts."""
                return {name for name in contents if name == ".git"}

            shutil.copytree(
                lake_template,
                workspace,
                dirs_exist_ok=True,
                ignore=ignore_git_dirs,
            )

            # Copy sample files to workspace
            fvspec_dir = workspace / "Fvspec"
            fvspec_dir.mkdir(exist_ok=True)

            # Copy Spec.lean
            shutil.copy2(sample_path / "Spec.lean", fvspec_dir / "Spec.lean")

            # Copy optional files if they exist
            for optional_file in optional_files:
                src = sample_path / optional_file
                if src.exists():
                    shutil.copy2(src, fvspec_dir / optional_file)

            # Run lake build (lake will fetch dependencies automatically)
            result = subprocess.run(
                ["lake", "build"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            duration = (datetime.now() - start_time).total_seconds()

            if result.returncode == 0:
                return CompilationResult(
                    sample_id=sample_id,
                    sample_path=sample_path,
                    success=True,
                    duration_seconds=duration,
                )
            else:
                # Capture full output (stdout + stderr) for error diagnosis
                full_output = []
                if result.stdout:
                    full_output.append("=== stdout ===")
                    full_output.append(result.stdout)
                if result.stderr:
                    full_output.append("=== stderr ===")
                    full_output.append(result.stderr)
                error_msg = "\n".join(full_output) if full_output else "Unknown error"

                return CompilationResult(
                    sample_id=sample_id,
                    sample_path=sample_path,
                    success=False,
                    duration_seconds=duration,
                    error_message=error_msg,
                )

        except subprocess.TimeoutExpired:
            duration = (datetime.now() - start_time).total_seconds()
            return CompilationResult(
                sample_id=sample_id,
                sample_path=sample_path,
                success=False,
                duration_seconds=duration,
                error_message=f"Compilation timed out after {timeout}s",
            )
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            return CompilationResult(
                sample_id=sample_id,
                sample_path=sample_path,
                success=False,
                duration_seconds=duration,
                error_message=f"Unexpected error: {e!s}",
            )


def print_results(results: list[CompilationResult], run_path: Path) -> None:
    """Print compilation results in a formatted table.

    Args:
        results: List of compilation results
        run_path: Path to the run directory
    """
    console.print(f"\n[bold]Run:[/bold] {run_path.name}")
    console.print(f"[dim]Path:[/dim] {run_path}\n")

    # Create results table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Sample ID", style="cyan", width=12)
    table.add_column("Status", width=10)
    table.add_column("Duration", justify="right", width=10)
    table.add_column("Notes", style="dim")

    success_count = 0
    failure_count = 0

    for result in results:
        if result.success:
            status = "[green]✓ PASS[/green]"
            success_count += 1
            notes = ""
        else:
            status = "[red]✗ FAIL[/red]"
            failure_count += 1
            if result.missing_files:
                notes = f"Missing: {', '.join(result.missing_files)}"
            elif result.error_message:
                # Show first line of error
                first_line = result.error_message.split("\n")[0]
                notes = first_line[:60] + "..." if len(first_line) > 60 else first_line
            else:
                notes = "Unknown error"

        duration_str = f"{result.duration_seconds:.1f}s"
        table.add_row(result.sample_id, status, duration_str, notes)

    console.print(table)

    # Summary
    total = len(results)
    console.print("\n[bold]Summary:[/bold]")
    console.print(f"  Total samples: {total}")
    console.print(f"  [green]Passed: {success_count}[/green]")
    console.print(f"  [red]Failed: {failure_count}[/red]")

    if total > 0:
        success_rate = (success_count / total) * 100
        console.print(f"  Success rate: {success_rate:.1f}%")


@app.command()
def main(
    sample_ids: list[str] = typer.Argument(
        None,
        help="Sample ID(s) to check. If not provided, checks all samples.",
    ),
    run_path: Path | None = typer.Option(
        None,
        "--run-path",
        help="Path to run directory (defaults to latest run)",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    timeout: int = typer.Option(
        120,
        "--timeout",
        help="Maximum seconds to wait for each compilation",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed error messages",
    ),
) -> None:
    """Check Lean compilation for benchmark run samples.

    By default, checks the latest run with all samples.
    Pass sample IDs as arguments: `check-run 37608` or `check-run 37608 12345`
    Use --run-path to specify a different run.

    Examples:
        check-run                  # Check all samples in latest run
        check-run 37608            # Check sample 37608 in latest run
        check-run 37608 12345      # Check multiple samples
        check-run --run-path ...   # Check all samples in specific run
    """
    # Determine run path
    if run_path is None:
        console.print("[dim]Finding latest run...[/dim]")
        run_path = find_latest_run()
        if run_path is None:
            console.print("[red]Error: No runs found in artifacts/runs[/red]")
            raise typer.Exit(code=1)
        console.print(f"[dim]Using latest run: {run_path.name}[/dim]\n")

    # Find sample directories
    sample_dirs = find_sample_dirs(run_path, sample_ids)

    if not sample_dirs:
        if sample_ids:
            console.print(
                f"[red]Error: No samples found matching IDs: {', '.join(sample_ids)}[/red]"
            )
        else:
            console.print(f"[red]Error: No samples found in {run_path}[/red]")
        raise typer.Exit(code=1)

    console.print(f"[bold]Checking {len(sample_dirs)} sample(s)...[/bold]\n")

    # Compile samples with progress indicator
    results: list[CompilationResult] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Compiling samples...", total=len(sample_dirs))

        for sample_dir in sample_dirs:
            sample_id_str = extract_sample_id(sample_dir.name)
            progress.update(task, description=f"Compiling {sample_id_str}...")

            result = compile_sample(sample_dir, timeout=timeout)
            results.append(result)

            progress.advance(task)

    # Print results
    print_results(results, run_path)

    # Show detailed errors if verbose
    if verbose:
        console.print("\n[bold]Detailed Errors:[/bold]")
        for result in results:
            if not result.success and result.error_message:
                console.print(f"\n[cyan]{result.sample_id}[/cyan]:")
                console.print(f"[dim]{result.error_message}[/dim]")

    # Exit with error code if any failures
    if any(not r.success for r in results):
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
