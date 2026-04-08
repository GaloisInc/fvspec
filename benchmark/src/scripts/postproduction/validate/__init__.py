"""Post-production: Validate that samples actually compile with `lake build`.

Usage (from benchmark/ directory):
    uv run postprod validate artifacts/dataset-out/fvspec-feb03.graded.metrics.jsonl
    uv run postprod validate fvspec.jsonl --sample-size 400 --parallelism 8
    uv run postprod validate fvspec.jsonl --all
"""

from pathlib import Path

import typer
from rich.console import Console

from scripts.postproduction.validate.compiler import run_validation

console = Console()


def main(
    input_jsonl: Path = typer.Argument(
        ...,
        help="Path to JSONL dataset file",
        exists=True,
    ),
    sample_size: int = typer.Option(
        400,
        "--sample-size",
        "-n",
        help="Number of samples to validate (default: 400 for ±5%% at 95%% CI)",
    ),
    all_samples: bool = typer.Option(
        False,
        "--all",
        help="Validate all samples (ignores --sample-size)",
    ),
    parallelism: int = typer.Option(
        8,
        "--parallelism",
        "-j",
        help="Number of parallel lake build processes",
    ),
    seed: int = typer.Option(
        42,
        "--seed",
        help="Random seed for sampling",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help=(
            "Output JSONL path (default: <input>.validated.jsonl). "
            "Contains only samples that successfully compiled, in their original form."
        ),
    ),
    timeout: int = typer.Option(
        60,
        "--timeout",
        help="Timeout per lake build in seconds",
    ),
    filter_impl_autoform: bool = typer.Option(
        True,
        "--filter-impl-autoform/--no-filter-impl-autoform",
        help="Only validate samples with impl_autoform_success >= 1.0",
    ),
) -> None:
    """Validate that dataset samples actually compile with `lake build`.

    Copies lake-template into temporary directories, writes Spec.lean and Impl.lean
    from the dataset, and runs `lake build`.

    Outputs a filtered JSONL containing only the samples that compiled successfully,
    in their original full form (drop-in replacement for the input dataset). Failures
    are dropped from the JSONL but still summarized in the markdown report and
    console analysis (compilation rate, turn count correlation, error categories).
    """
    run_validation(
        input_jsonl=input_jsonl,
        sample_size=sample_size,
        all_samples=all_samples,
        parallelism=parallelism,
        seed=seed,
        output=output,
        timeout=timeout,
        filter_impl_autoform=filter_impl_autoform,
    )
