"""Generate the benchmark"""

from datetime import datetime
from pathlib import Path
import random
from inspect_ai import eval, eval_set
from benchmark.config import load_config
from benchmark.scaffold.task import fvspec, DATA_DIR
from benchmark.scaffold.dataset import load_datapoints, Datapoint
from benchmark.scaffold.depmock.runner import run_depmock_for_sample
from benchmark.templates.spec import VariantRegistry
from typer import Typer, Option
import typer

cfg = load_config()
# if cfg.meta.logging:
#     setup_logfire()

app = Typer(no_args_is_help=False, invoke_without_command=True)


@app.callback()
def main_callback(
    ctx: typer.Context,
    datafile: str = Option("scrapedtests.json", help="Path to test data JSON file"),
    no_mcp: bool = Option(False, help="Disable Lean LSP MCP tools"),
    variant: str = Option(
        None,
        help="Prompt variant name from registry.toml (e.g., 'control-functional', 'terse-functional'). If not specified, uses default from registry or config.toml.",
    ),
    sample_size: int = Option(
        None,
        help="Number of samples to draw from dataset. If not specified, uses value from config.toml (default: 100).",
    ),
    ranseed: int = Option(
        None,
        help="Random seed used for dataset sampling. Overrides config.toml (default: 0).",
    ),
    list_variants: bool = Option(
        False, "--list-variants", help="List all available prompt variants and exit"
    ),
    display: str = Option(
        None,
        help="Display mode: full, conversation, rich, plain, log, none. Overrides config.toml.",
    ),
    parallelism: int = Option(
        None,
        help="Number of samples to evaluate in parallel. Overrides config.toml.",
    ),
) -> None:
    """Run the fvspec benchmark with a single variant.

    This is the default command. For A/B testing, use the compare-variants subcommand.

    Args:
        ctx: Typer context
        datafile: Path to the JSON file containing test data
        no_mcp: Disable Lean LSP MCP tools
        variant: Prompt variant name (overrides config.toml)
        sample_size: Number of samples to draw (overrides config.toml)
        ranseed: Random seed used when sampling datapoints (overrides config.toml)
        list_variants: List available variants and exit
    """
    # If a subcommand was invoked, don't run the default behavior
    if ctx.invoked_subcommand is not None:
        return

    # Handle --list-variants flag
    if list_variants:
        registry = VariantRegistry()
        print("Available prompt variants:\n")
        for name in registry.list_variants():
            info = registry.get_variant_info(name)
            print(f"  {name}")
            print(f"    Style: {info['style']}")
            print(f"    Description: {info['description']}")
            print(f"    Tags: {', '.join(info.get('tags', []))}")
            print()
        return

    # Determine variant: CLI arg > config > registry default
    use_variant = variant or cfg.prompt.variant
    # Determine sample_size: CLI arg > config
    use_sample_size = (
        sample_size if sample_size is not None else cfg.dataset.sample_size
    )
    use_ranseed = ranseed if ranseed is not None else cfg.dataset.ranseed

    use_parallelism = (
        parallelism if parallelism is not None else cfg.meta.parallelism
    )

    # Create log directory in artifacts
    now = datetime.now()
    log_dir_name = (
        f"{now.strftime('%Y-%m-%dT%H-%M-%S')}__variant_{use_variant or 'default'}"
    )
    log_dir = Path("artifacts") / log_dir_name
    log_dir.mkdir(parents=True, exist_ok=True)

    eval(
        fvspec(
            datafile,
            use_mcp=not no_mcp,
            variant=use_variant,
            sample_size=use_sample_size,
            ranseed=use_ranseed,
        ),
        model=cfg.agent.model,
        log_dir=str(log_dir),
        max_samples=use_parallelism,
        max_connections=use_parallelism,
    )


@app.command(name="compare-variants")
def compare_variants(
    datafile: str = Option("scrapedtests.json", help="Path to test data JSON file"),
    no_mcp: bool = Option(False, help="Disable Lean LSP MCP tools"),
    variant: list[str] = Option(
        None,
        "--variant",
        help="Variant names to compare (can be specified multiple times). If not specified, uses all control and treatment variants.",
    ),
    sample_size: int = Option(
        None,
        help="Number of samples to draw from dataset. If not specified, uses value from config.toml (default: 100).",
    ),
    ranseed: int = Option(
        None,
        help="Random seed used for dataset sampling. Overrides config.toml (default: 0).",
    ),
    parallelism: int = Option(
        None,
        help="Number of samples to evaluate in parallel. Overrides config.toml.",
    ),
) -> None:
    """Run A/B testing comparing multiple prompt variants using eval_set.

    Args:
        datafile: Path to the JSON file containing test data
        no_mcp: Disable Lean LSP MCP tools
        variant: List of variant names to compare
        sample_size: Number of samples to draw (overrides config.toml)
        ranseed: Random seed used when sampling datapoints (overrides config.toml)
    """
    registry = VariantRegistry()

    # If no variants specified, use all control and treatment variants
    if not variant:
        all_variants = registry.list_variants()
        variants_to_compare = []
        for v in all_variants:
            info = registry.get_variant_info(v)
            tags = info.get("tags", [])
            if "control" in tags or "treatment" in tags:
                variants_to_compare.append(v)
    else:
        variants_to_compare = list(variant)

    if len(variants_to_compare) < 2:
        print("Error: Need at least 2 variants to compare")
        print(f"Found: {variants_to_compare}")
        return

    print(f"Comparing variants: {', '.join(variants_to_compare)}\n")

    # Determine sample_size: CLI arg > config
    use_sample_size = (
        sample_size if sample_size is not None else cfg.dataset.sample_size
    )
    use_ranseed = ranseed if ranseed is not None else cfg.dataset.ranseed
    use_parallelism = (
        parallelism if parallelism is not None else cfg.meta.parallelism
    )

    # Create log directory for comparison results
    now = datetime.now()
    log_dir_name = f"comparison_{now.strftime('%Y-%m-%dT%H-%M-%S')}"
    log_dir = Path("artifacts") / log_dir_name
    log_dir.mkdir(parents=True, exist_ok=True)

    # Create task instances for each variant
    tasks = [
        fvspec(
            datafile,
            use_mcp=not no_mcp,
            variant=v,
            sample_size=use_sample_size,
            ranseed=use_ranseed,
        )
        for v in variants_to_compare
    ]

    # Run all tasks together with eval_set
    eval_set(
        tasks,
        log_dir=str(log_dir),
        model=cfg.agent.model,
        max_samples=use_parallelism,
        max_connections=use_parallelism,
    )


@app.command(name="deps-autoformalize")
def deps_autoformalize_command(
    datafile: str = Option("scrapedtests.json", help="Path to test data JSON file"),
    sample_id: list[int] = Option(
        None,
        "--sample-id",
        help="Specific datapoint id(s) to autoformalize (can be repeated).",
    ),
    sample_size: int = Option(
        1,
        help="If --sample-id is not provided, sample this many datapoints (default: 1).",
    ),
    ranseed: int = Option(
        0,
        help="Random seed used when sampling datapoints (only when --sample-id not supplied).",
    ),
    variant: str = Option(
        None,
        help="Variant name used for metadata (defaults to config.toml prompt variant).",
    ),
) -> None:
    """Autoformalize dependencies for selected datapoints without running the full benchmark."""

    dataset_path = (DATA_DIR / datafile).resolve()
    if not dataset_path.exists():
        print(f"Dataset not found at {dataset_path}")
        return

    datapoints = load_datapoints(dataset_path)
    if not datapoints:
        print("No datapoints available in dataset")
        return

    dp_by_id = {dp.id: dp for dp in datapoints}

    selected: list[Datapoint] = []
    if sample_id:
        for sid in sample_id:
            dp = dp_by_id.get(sid)
            if dp is None:
                print(f"Warning: sample id {sid} not found in dataset")
            else:
                selected.append(dp)
        if not selected:
            print("No valid sample ids provided; aborting.")
            return
    else:
        size = max(0, min(sample_size, len(datapoints)))
        if size == 0:
            print("Sample size is zero; nothing to do.")
            return
        rng = random.Random(ranseed)
        selected = rng.sample(datapoints, size)

    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    base_variant = variant or cfg.prompt.variant or "default"
    path_variant = f"{base_variant}-deps-auto"
    base_dir = Path("artifacts") / f"{timestamp}__variant_{path_variant}"
    base_dir.mkdir(parents=True, exist_ok=True)

    print(f"Autoformalizing {len(selected)} dependency set(s) using variant '{base_variant}'.")
    print(f"Artifacts will be written to {base_dir}\n")

    for dp in selected:
        sample_label = f"{dp.id:05d}_{dp.pbt_name}"
        meta = run_depmock_for_sample(
            dp,
            date_time=timestamp,
            variant=base_variant,
            sample_id=sample_label,
            path_variant=path_variant,
        )
        deps_dir = meta.get("deps_dir")
        manifest = meta.get("manifest")
        manifest_entries = manifest if isinstance(manifest, list) else []
        print(
            f"- {sample_label}: deps written to {deps_dir} ({len(manifest_entries)} entries)"
        )

    print("\nDone. You can inspect the generated Lean modules under the directory above.")


def main() -> None:
    app()
