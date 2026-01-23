"""Post-production: Grade benchmark samples for quality and difficulty using Claude Haiku.

This CLI tool uses Claude Haiku 4.5 to evaluate formalization quality and difficulty
for samples in merged JSONL files. Each sample is augmented with grading results.

Usage (from benchmark/ directory):
    uv run grader artifacts/dataset-out/fvspec.jsonl
    uv run grader input.jsonl --output graded.jsonl --limit 10
    uv run grader input.jsonl --skip-difficulty
    uv run grader input.graded.jsonl --retry-failed  # Input must be previously graded
"""

from pathlib import Path

import typer
from rich.console import Console

from .client import AnthropicGraderClient
from .grader import process_jsonl

app = typer.Typer(help="Grade benchmark samples for quality and difficulty")
console = Console()


@app.command()
def main(
    input_file: Path = typer.Argument(
        ...,
        help="Path to input JSONL file (merged benchmark data)",
        exists=True,
    ),
    output: str = typer.Option(
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
    limit: int = typer.Option(
        None,
        "--limit",
        "-n",
        help="Grade only first N samples (output contains all samples, only first N graded)",
    ),
    skip_quality: bool = typer.Option(
        False,
        "--skip-quality",
        help="Skip quality assessment (only grade difficulty)",
    ),
    skip_difficulty: bool = typer.Option(
        False,
        "--skip-difficulty",
        help="Skip difficulty assessment (only grade quality)",
    ),
    retry_failed: bool = typer.Option(
        False,
        "--retry-failed",
        help="Only re-grade samples with grader_error field (input must be a previously graded file)",
    ),
    parallel: int = typer.Option(
        1,
        "--parallel",
        "-p",
        help="Number of parallel workers (not yet implemented)",
    ),
) -> None:
    """Grade benchmark samples for quality and difficulty using Claude Haiku.

    Reads a merged JSONL file and uses Claude Haiku 4.5 to assess:
    - Quality: correctness, type safety, edge cases, Lean idioms
    - Difficulty: math complexity, type challenges, proof difficulty, domain knowledge

    **Output behavior**: The output is a COMPLETE COPY of the input file.
    All samples are written to output, but only specified samples are graded
    (based on --limit, --retry-failed, or all by default).
    Ungraded samples pass through unchanged.

    Each graded sample is augmented with:
    - grader_quality: Quality assessment (or None if skipped/failed)
    - grader_difficulty: Difficulty estimation (or None if skipped/failed)
    - grader_metadata: Grading metadata (model, tokens, time)
    - grader_error: Error message (if grading failed)

    Examples (from benchmark/ directory):
        uv run grader artifacts/dataset-out/fvspec.jsonl
        uv run grader input.jsonl --output graded.jsonl --limit 10
        uv run grader input.jsonl --skip-difficulty
        uv run grader input.graded.jsonl --retry-failed  # Retry with previously graded file
    """
    console.print("[bold]Post-production: Grading benchmark samples[/bold]\n")

    # Validate options
    if skip_quality and skip_difficulty:
        console.print(
            "[red]Error: Cannot skip both quality and difficulty assessment[/red]"
        )
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
    if skip_quality:
        console.print("[yellow]Skipping quality assessment[/yellow]")
    if skip_difficulty:
        console.print("[yellow]Skipping difficulty assessment[/yellow]")
    if retry_failed:
        console.print("[cyan]Retry mode: only processing samples with errors[/cyan]")

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
        skip_quality=skip_quality,
        skip_difficulty=skip_difficulty,
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
