"""Post-production: Grade benchmark samples for difficulty using Claude Haiku.

This CLI tool uses Claude Haiku 4.5 to estimate formalization difficulty
for samples in merged JSONL files. Each sample is augmented with difficulty grading.

Usage (from benchmark/ directory):
    uv run grader artifacts/dataset-out/fvspec.jsonl
    uv run grader input.jsonl --output graded.jsonl --limit 10
    uv run grader input.graded.jsonl --retry-failed  # Input must be previously graded
"""

from pathlib import Path

import typer
from rich.console import Console

from scripts.postproduction.grader.client import AnthropicGraderClient
from scripts.postproduction.grader.grader import process_jsonl

app = typer.Typer(help="Grade benchmark samples for difficulty")
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
        help="Output JSONL file path (default: <input>.graded.jsonl)",
    ),
    model: str = typer.Option(
        "claude-haiku-4-5-20251001",
        "--model",
        "-m",
        help="Model to use for grading",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        "-n",
        help="Grade only first N samples (output contains all samples, only first N graded)",
    ),
    start_idx: int = typer.Option(
        None,
        "--start-idx",
        help="Start grading from this index (0-based, inclusive)",
    ),
    stop_idx: int = typer.Option(
        None,
        "--stop-idx",
        help="Stop grading at this index (0-based, exclusive)",
    ),
    retry_failed: bool = typer.Option(
        False,
        "--retry-failed",
        help="Also retry samples with grader_error (default: grades samples missing difficulty fields)",
    ),
    parallel: int = typer.Option(
        1,
        "--parallel",
        "-p",
        help="Number of parallel workers (not yet implemented)",
    ),
) -> None:
    """Grade benchmark samples for difficulty using Claude Haiku.

    Reads a merged JSONL file and uses Claude Haiku 4.5 to estimate formalization difficulty.

    **Default behavior**: Automatically grades samples missing difficulty fields (resume-safe).
    Already-graded samples are skipped. Use --retry-failed to also retry samples with errors.

    **Output behavior**: The output is a COMPLETE COPY of the input file.
    All samples are written to output. Successfully graded samples pass through unchanged.

    Each graded sample is augmented with:
    - difficulty_subjective_haiku: Difficulty score (0-10)
    - difficulty_subjective_haiku_takes: Prose justification
    - grader_metadata: Grading metadata (model, tokens, time)
    - grader_error: Error message (if grading failed)

    Examples (from benchmark/ directory):
        uv run grader artifacts/dataset-out/fvspec.jsonl  # Grade missing samples
        uv run grader input.jsonl --output graded.jsonl --limit 10
        uv run grader input.jsonl --start-idx 100 --stop-idx 200  # Grade range
        uv run grader input.graded.jsonl  # Resume: grades only missing samples
        uv run grader input.graded.jsonl --retry-failed  # Also retry errors
    """
    console.print(
        "[bold]Post-production: Grading benchmark samples for difficulty[/bold]\n"
    )

    # Validate arguments
    if limit and (start_idx is not None or stop_idx is not None):
        console.print(
            "[red]Error: Cannot use --limit with --start-idx/--stop-idx[/red]"
        )
        raise typer.Exit(1)

    if start_idx is not None and stop_idx is not None and start_idx >= stop_idx:
        console.print("[red]Error: --start-idx must be less than --stop-idx[/red]")
        raise typer.Exit(1)

    if parallel > 1:
        console.print(
            "[yellow]Warning: Parallel processing not yet implemented, using serial mode[/yellow]"
        )

    # Setup paths
    if output is None:
        output_path = input_file.with_suffix(".graded.jsonl")
    else:
        output_path = Path(output)

    console.print(f"Input file: {input_file}")
    console.print(f"Output file: {output_path}")
    console.print(f"Model: {model}")

    if limit:
        console.print(f"Sample limit: {limit}")
    if start_idx is not None or stop_idx is not None:
        start_str = str(start_idx) if start_idx is not None else "0"
        stop_str = str(stop_idx) if stop_idx is not None else "end"
        console.print(f"Index range: [{start_str}, {stop_str})")
    if retry_failed:
        console.print("[cyan]Retry mode: also retrying samples with errors[/cyan]")

    # Initialize client
    try:
        client = AnthropicGraderClient(model=model)
        console.print("[green]✓[/green] Anthropic client initialized\n")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print(
            "\nPlease set ANTHROPIC_API_KEY environment variable to your API key."
        )
        raise typer.Exit(1)

    # Process JSONL
    console.print("[bold]Starting grading process...[/bold]\n")

    stats = process_jsonl(
        input_file=input_file,
        output_file=output_path,
        client=client,
        limit=limit,
        start_idx=start_idx,
        stop_idx=stop_idx,
        retry_failed=retry_failed,
    )

    # Display summary
    console.print("\n[bold]Grading Summary:[/bold]\n")
    console.print(f"  Total samples in input: {stats['total_read']}")
    console.print(f"  Samples graded: {stats['total_graded']}")
    console.print(f"  Samples passed through: {stats['skipped']}")
    console.print(f"  Grading errors: {stats['errors']}")
    console.print(f"  Total samples in output: {stats['total_read']}")

    console.print(f"\n[green]✓[/green] Grading complete! Data saved to: {output_path}")
    console.print(
        f"[dim]File size: {output_path.stat().st_size / 1024 / 1024:.2f} MB[/dim]"
    )


if __name__ == "__main__":
    app()
