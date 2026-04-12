"""Baselines evaluation for fvspec benchmark."""

import logging

import typer

app = typer.Typer(help="fvspec baselines evaluation CLI")


@app.command()
def run(
    model: str = typer.Option(
        ..., "-m", help="Model human_name, model_pin, or provider/model_pin"
    ),
    num_samples: int | None = typer.Option(
        None, "-n", "--num-samples", help="Override config num_samples"
    ),
    ranseed: int | None = typer.Option(None, "-s", help="Override config ranseed"),
    parallelism: int | None = typer.Option(None, help="Override config parallelism"),
    data_source: str | None = typer.Option(
        None, "--data-source", help="Path to JSONL or 'huggingface'"
    ),
) -> None:
    """Run the baselines evaluation for a given model."""
    from inspect_ai import eval as inspect_eval

    from baselines.config import load_config
    from baselines.solver import fvspec_baselines

    logging.basicConfig(level=logging.INFO)

    cfg = load_config()
    seed = ranseed if ranseed is not None else cfg.ranseed
    par = parallelism if parallelism is not None else cfg.parallelism
    n = num_samples if num_samples is not None else cfg.num_samples
    ds = data_source if data_source is not None else cfg.data_source

    model_cfg = cfg.get_model(model)
    task = fvspec_baselines(ranseed=seed, num_samples=n, data_source=ds)
    inspect_eval(
        task,
        model=model_cfg.inspect_model,
        max_tasks=par,
        log_dir="artifacts",
    )


@app.command()
def stats(
    log_dir: str = typer.Option("artifacts", help="Directory containing .eval logs"),
    num_samples: int | None = typer.Option(
        None, "-n", "--num-samples", help="Override config num_samples"
    ),
    ranseed: int | None = typer.Option(None, "-s", help="Override config ranseed"),
) -> None:
    """Aggregate eval logs into results TOML and JSON."""
    from baselines.config import load_config
    from baselines.stats import aggregate_logs, write_results_toml

    logging.basicConfig(level=logging.INFO)

    cfg = load_config()
    seed = ranseed if ranseed is not None else cfg.ranseed
    n = num_samples if num_samples is not None else cfg.num_samples

    results, eval_ts = aggregate_logs(log_dir=log_dir)
    if not results:
        typer.echo("No results found.")
        raise typer.Exit(1)

    out = write_results_toml(
        results, ranseed=seed, num_samples=n, eval_timestamp=eval_ts
    )
    typer.echo(f"Wrote {out}")


@app.command(name="sample-info")
def sample_info(
    num_samples: int | None = typer.Option(
        None, "-n", "--num-samples", help="Override config num_samples"
    ),
    ranseed: int | None = typer.Option(None, "-s", help="Override config ranseed"),
    data_source: str | None = typer.Option(
        None, "--data-source", help="Path to JSONL or 'huggingface'"
    ),
) -> None:
    """Print bucket sizes and sample IDs for the given seed."""
    from baselines.config import load_config
    from baselines.dataset import load_and_sample

    logging.basicConfig(level=logging.INFO)

    cfg = load_config()
    seed = ranseed if ranseed is not None else cfg.ranseed
    n = num_samples if num_samples is not None else cfg.num_samples
    ds = data_source if data_source is not None else cfg.data_source

    samples = load_and_sample(ranseed=seed, num_samples=n, data_source=ds)

    buckets: dict[str, list[str]] = {"easy": [], "hard": []}
    for s in samples:
        bucket = s.difficulty_bucket
        if bucket in buckets:
            buckets[bucket].append(s.sample_id)

    for bucket_name in ["easy", "hard"]:
        ids = buckets[bucket_name]
        typer.echo(f"{bucket_name}: {len(ids)} samples")
        if len(ids) <= 10:
            typer.echo(f"  IDs: {ids}")


def main() -> None:
    app()
