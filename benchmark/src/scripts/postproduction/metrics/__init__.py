"""Post-production: Compute Lean code metrics for benchmark samples.

This CLI tool analyzes Lean code in merged JSONL files and augments each sample
with structure and complexity metrics.

Usage (from benchmark/ directory):
    uv run metrics artifacts/dataset-out/fvspec.jsonl
    uv run metrics input.jsonl --output metrics.jsonl --limit 10
    uv run metrics input.metrics.jsonl --retry-failed  # Retry errors
"""

from pathlib import Path

import typer
from rich.console import Console

from scripts.postproduction.metrics.processor import process_jsonl

app = typer.Typer(help="Compute Lean code metrics for benchmark samples")
console = Console()


@app.command()
def main(
    input_file: Path = typer.Argument(
        ...,
        help="Path to input JSONL file (merged benchmark data)",
        exists=True,
    ),
    output: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output JSONL file path (default: <input>.metrics.jsonl)",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        "-n",
        help="Compute metrics for only first N missing samples (mutually exclusive with --start-idx/--stop-idx)",
    ),
    start_idx: int | None = typer.Option(
        None,
        "--start-idx",
        help="Start computing from this index (0-based, inclusive)",
    ),
    stop_idx: int | None = typer.Option(
        None,
        "--stop-idx",
        help="Stop computing at this index (0-based, exclusive)",
    ),
    retry_failed: bool = typer.Option(
        False,
        "--retry-failed",
        help="Also retry samples with metrics_error (default: only compute missing samples)",
    ),
) -> None:
    """Compute Lean code metrics for benchmark samples.

    Reads a merged JSONL file and computes structure and complexity metrics
    for Lean code (Spec.lean, Impl.lean, Tests.lean).

    **Default behavior**: Automatically computes metrics for samples missing them (resume-safe).
    Already-computed samples are skipped. Use --retry-failed to also retry samples with errors.

    **Output behavior**: The output is a COMPLETE COPY of the input file.
    All samples are written to output. Successfully computed samples include:
    - lean_metrics: Structure and complexity metrics
    - metrics_metadata: Computation metadata (version, time, availability)
    - metrics_error: Error message (if computation failed)

    Examples (from benchmark/ directory):
        uv run metrics artifacts/dataset-out/fvspec.jsonl  # Compute missing metrics
        uv run metrics input.jsonl --output metrics.jsonl --limit 10
        uv run metrics input.jsonl --start-idx 100 --stop-idx 200  # Compute range
        uv run metrics input.metrics.jsonl  # Resume: compute only missing
        uv run metrics input.metrics.jsonl --retry-failed  # Also retry errors
    """
    console.print("[bold]Post-production: Computing Lean code metrics[/bold]\n")

    # Validate arguments
    if limit and (start_idx is not None or stop_idx is not None):
        console.print(
            "[red]Error: Cannot use --limit with --start-idx/--stop-idx[/red]"
        )
        raise typer.Exit(1)

    if start_idx is not None and stop_idx is not None and start_idx >= stop_idx:
        console.print("[red]Error: --start-idx must be less than --stop-idx[/red]")
        raise typer.Exit(1)

    # Setup paths
    if output is None:
        output_path = input_file.with_suffix(".metrics.jsonl")
    else:
        output_path = Path(output)

    console.print(f"Input file: {input_file}")
    console.print(f"Output file: {output_path}")

    if limit:
        console.print(f"Sample limit: {limit}")
    if start_idx is not None or stop_idx is not None:
        start_str = str(start_idx) if start_idx is not None else "0"
        stop_str = str(stop_idx) if stop_idx is not None else "end"
        console.print(f"Index range: [{start_str}, {stop_str})")
    if retry_failed:
        console.print("[cyan]Retry mode: also retrying samples with errors[/cyan]")

    # Process JSONL
    console.print("\n[bold]Starting metrics computation...[/bold]\n")

    stats = process_jsonl(
        input_file=input_file,
        output_file=output_path,
        limit=limit,
        start_idx=start_idx,
        stop_idx=stop_idx,
        retry_failed=retry_failed,
    )

    # Display summary
    console.print("\n[bold]Metrics Summary:[/bold]\n")
    console.print(f"  Total samples in input: {stats['total_read']}")
    console.print(f"  Metrics computed: {stats['total_computed']}")
    console.print(f"  Samples passed through: {stats['skipped']}")
    console.print(f"  Computation errors: {stats['errors']}")
    console.print(f"  Total samples in output: {stats['total_read']}")

    console.print(
        f"\n[green]✓[/green] Metrics computation complete! Data saved to: {output_path}"
    )
    console.print(
        f"[dim]File size: {output_path.stat().st_size / 1024 / 1024:.2f} MB[/dim]"
    )


if __name__ == "__main__":
    app()
