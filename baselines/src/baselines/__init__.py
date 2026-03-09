"""Baselines evaluation for fvspec benchmark."""

import logging

import typer

app = typer.Typer(help="fvspec baselines evaluation CLI")


@app.command()
def run(
    model: str = typer.Option(
        ..., help="Model identifier (e.g. anthropic/claude-sonnet-4-20250514)"
    ),
    ranseed: int = typer.Option(42, help="Random seed for stratified sampling"),
    parallelism: int = typer.Option(10, help="Number of parallel samples"),
) -> None:
    """Run the baselines evaluation for a given model."""
    from inspect_ai import eval as inspect_eval

    from baselines.solver import fvspec_baselines

    logging.basicConfig(level=logging.INFO)

    task = fvspec_baselines(ranseed=ranseed)
    inspect_eval(
        task,
        model=model,
        max_tasks=parallelism,
        log_dir="artifacts",
    )


@app.command()
def stats(
    log_dir: str = typer.Option("artifacts", help="Directory containing .eval logs"),
    ranseed: int = typer.Option(42, help="Random seed used in the run"),
) -> None:
    """Aggregate eval logs into results.toml."""
    from baselines.stats import aggregate_logs, write_results_toml

    logging.basicConfig(level=logging.INFO)

    results = aggregate_logs(log_dir=log_dir)
    if not results:
        typer.echo("No results found.")
        raise typer.Exit(1)

    out = write_results_toml(results, ranseed=ranseed)
    typer.echo(f"Wrote {out}")


@app.command(name="sample-info")
def sample_info(
    ranseed: int = typer.Option(42, help="Random seed for stratified sampling"),
) -> None:
    """Print bucket sizes and sample IDs for the given seed."""
    from baselines.dataset import load_and_sample

    logging.basicConfig(level=logging.INFO)

    samples = load_and_sample(ranseed=ranseed)

    buckets: dict[str, list[str]] = {"easy": [], "medium": [], "hard": []}
    for s in samples:
        bucket = s.difficulty_bucket
        if bucket in buckets:
            buckets[bucket].append(s.sample_id)

    for bucket_name in ["easy", "medium", "hard"]:
        ids = buckets[bucket_name]
        typer.echo(f"{bucket_name}: {len(ids)} samples")
        if len(ids) <= 10:
            typer.echo(f"  IDs: {ids}")


def main() -> None:
    app()
