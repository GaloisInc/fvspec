"""Generate the benchmark."""

import atexit
import os
import signal
import subprocess
from datetime import datetime
from pathlib import Path

import typer
from dotenv import load_dotenv
from inspect_ai import eval, eval_retry, eval_set
from inspect_ai._eval.eval import DisplayType
from typer import Option, Typer

from generate.config import WandbConfig, load_config

# Load .env from parent directory (monorepo root)
# This allows running `uv run fvspec` from ./benchmark while .env is at ./
_env_path = Path(__file__).parent.parent.parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
from generate.scaffold.orchestration import fvspec
from generate.scaffold.tools import utilio
from generate.scaffold.wandb_logger import init_wandb_logger
from generate.templates.formalize import FormalizationVariantRegistry as VariantRegistry

cfg = load_config()

# Set WANDB_MODE=disabled to prevent authentication when wandb is disabled
# This must happen before any wandb imports or operations
if not cfg.wandb.enabled:
    os.environ["WANDB_MODE"] = "disabled"

app = Typer(no_args_is_help=False, invoke_without_command=True)


@app.callback()
def main_callback(
    ctx: typer.Context,
    datafile: str = Option("realpbt2.jsonl", help="Path to test data JSONL file"),
    variant: str = Option(
        None,
        "-v",
        "--variant",
        help="Prompt variant name from registry.toml (e.g., 'control-functional', 'terse-functional'). If not specified, uses default from registry or config.toml.",
    ),
    sample_size: int = Option(
        None,
        "-n",
        "--sample-size",
        help="Number of samples to draw from dataset. If not specified, uses value from config.toml (default: 100).",
    ),
    ranseed: int = Option(
        None,
        "-s",
        "--ranseed",
        help="Random seed used for dataset sampling. Overrides config.toml (default: 0).",
    ),
    start_idx: int = Option(
        None,
        "--start-idx",
        help="Starting index for sequential sampling (0-indexed, inclusive). When provided with --end-idx, processes a sequential slice instead of random sampling. Useful for splitting large runs across multiple jobs.",
    ),
    end_idx: int = Option(
        None,
        "--end-idx",
        help="Ending index for sequential sampling (0-indexed, exclusive). When provided with --start-idx, processes a sequential slice instead of random sampling.",
    ),
    list_variants: bool = Option(
        False, "--list-variants", help="List all available prompt variants and exit"
    ),
    display: DisplayType | None = Option(
        None,
        help="Display mode: full, conversation, rich, plain, log, none. Overrides config.toml.",
    ),
    parallelism: int = Option(
        None,
        "-p",
        "--parallelism",
        help="Number of samples to evaluate in parallel. Overrides config.toml.",
    ),
    wandb_disable: bool = Option(
        False,
        "--wandb-disable",
        help="Disable Weights & Biases logging (overrides config.toml setting).",
    ),
    wandb_project: str = Option(
        None,
        help="wandb project name. Overrides config.toml (default: fvspec).",
    ),
    wandb_entity: str = Option(
        None,
        help="wandb entity/team name. Overrides config.toml.",
    ),
    wandb_tags: list[str] = Option(
        None,
        "--wandb-tag",
        help="Additional tags for wandb run (can be specified multiple times).",
    ),
    model: str = Option(
        None,
        "-m",
        "--model",
        help="Model identifier (e.g., 'anthropic/claude-sonnet-4-6'). Overrides config.toml.",
    ),
) -> None:
    """Run the fvspec benchmark with a single variant.

    This is the default command. For A/B testing, use the compare-variants subcommand.

    Args:
        ctx: Typer context.
        datafile: Path to the JSONL file containing test data.
        variant: Prompt variant name (overrides config.toml).
        sample_size: Number of samples to draw (overrides config.toml).
        ranseed: Random seed used when sampling datapoints (overrides config.toml).
        start_idx: Starting index for sequential sampling (0-indexed, inclusive).
        end_idx: Ending index for sequential sampling (0-indexed, exclusive).
        list_variants: List available variants and exit.
        display: Display mode for eval logs (overrides config or CLI default).
        parallelism: Number of concurrent samples to evaluate.
        wandb_disable: Disable wandb logging (default is enabled).
        wandb_project: wandb project name (overrides config.toml).
        wandb_entity: wandb entity/team name (overrides config.toml).
        wandb_tags: Additional tags for wandb run.
        model: Model identifier string (overrides config.toml).
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
    if use_variant is None:
        # Resolve default variant from registry so log_dir matches sample output dirs
        registry = VariantRegistry()
        use_variant = registry.default_variant()

    # Determine sample_size: CLI arg > config
    use_sample_size = (
        sample_size if sample_size is not None else cfg.dataset.sample_size
    )
    use_ranseed = ranseed if ranseed is not None else cfg.dataset.ranseed

    use_parallelism = parallelism if parallelism is not None else cfg.meta.parallelism
    use_display = display if display is not None else cfg.meta.display
    use_model = model if model is not None else cfg.agent.model

    # Capture git commit at generation time for artifact provenance
    try:
        git_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        git_commit = None

    # Configure wandb settings: CLI flag > config
    # --wandb-disable flag explicitly disables, otherwise use config.toml setting
    wandb_enabled = cfg.wandb.enabled if not wandb_disable else False
    wandb_cfg = WandbConfig(
        enabled=wandb_enabled,
        project=wandb_project or cfg.wandb.project,
        entity=wandb_entity or cfg.wandb.entity,
        tags=(wandb_tags or []) + cfg.wandb.tags,
        upload_samples=cfg.wandb.upload_samples,
    )

    # Create log directory in artifacts/runs
    # Use mk_run_path to include ranseed or indices in path (consistent with sample directories)
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%dT%H-%M-%S")
    log_dir_name = utilio.mk_run_path(
        timestamp, utilio.model_slug(use_model), use_ranseed, start_idx, end_idx
    )
    log_dir = Path("artifacts") / "runs" / log_dir_name
    log_dir.mkdir(parents=True, exist_ok=True)

    # Initialize wandb logger if enabled
    wandb_logger = init_wandb_logger(wandb_cfg)
    if wandb_cfg.enabled:
        # Register cleanup handler for both normal exit and signals
        def cleanup_wandb():
            wandb_logger.finish()

        atexit.register(cleanup_wandb)

        # Handle Ctrl+C and other termination signals
        def signal_handler(signum, frame):
            print("\n⚠️  Interrupted - finalizing wandb run...")
            cleanup_wandb()
            raise KeyboardInterrupt()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        wandb_logger.init_run(
            variant=use_variant or "default",
            model=use_model,
            sample_size=use_sample_size,
            ranseed=use_ranseed,
            timestamp=timestamp,
            start_idx=start_idx,
            end_idx=end_idx,
        )

    try:
        eval(
            fvspec(
                datafile,
                variant=use_variant,
                sample_size=use_sample_size,
                ranseed=use_ranseed,
                timestamp=now,
                start_idx=start_idx,
                end_idx=end_idx,
                git_commit=git_commit,
                model=utilio.model_slug(use_model),
            ),
            model=use_model,
            log_dir=str(log_dir),
            max_samples=use_parallelism,
            display=use_display,
        )
    finally:
        # Clean up empty sample directories (created by inspect_ai but unused)
        utilio.cleanup_empty_sample_dirs(log_dir)

        # Note: wandb cleanup handled by atexit/signal handlers
        # to ensure it runs even on interrupts


@app.command(name="compare-variants")
def compare_variants(
    datafile: str = Option("realpbt2.jsonl", help="Path to test data JSONL file"),
    variant: list[str] = Option(
        None,
        "-v",
        "--variant",
        help="Variant names to compare (can be specified multiple times). If not specified, uses all control and treatment variants.",
    ),
    sample_size: int = Option(
        None,
        "-n",
        "--sample-size",
        help="Number of samples to draw from dataset. If not specified, uses value from config.toml (default: 100).",
    ),
    ranseed: int = Option(
        None,
        "-s",
        "--ranseed",
        help="Random seed used for dataset sampling. Overrides config.toml (default: 0).",
    ),
    start_idx: int = Option(
        None,
        "--start-idx",
        help="Starting index for sequential sampling (0-indexed, inclusive). When provided with --end-idx, processes a sequential slice instead of random sampling.",
    ),
    end_idx: int = Option(
        None,
        "--end-idx",
        help="Ending index for sequential sampling (0-indexed, exclusive). When provided with --start-idx, processes a sequential slice instead of random sampling.",
    ),
    parallelism: int = Option(
        None,
        "-p",
        "--parallelism",
        help="Number of samples to evaluate in parallel. Overrides config.toml.",
    ),
    display: DisplayType | None = Option(
        None,
        help="Display mode: full, conversation, rich, plain, log, none. Overrides config.toml.",
    ),
    wandb_disable: bool = Option(
        False,
        "--wandb-disable",
        help="Disable Weights & Biases logging (overrides config.toml setting).",
    ),
    wandb_project: str = Option(
        None,
        help="wandb project name. Overrides config.toml (default: fvspec).",
    ),
    wandb_entity: str = Option(
        None,
        help="wandb entity/team name. Overrides config.toml.",
    ),
    wandb_tags: list[str] = Option(
        None,
        "--wandb-tag",
        help="Additional tags for wandb run (can be specified multiple times).",
    ),
) -> None:
    """Run A/B testing comparing multiple prompt variants using eval_set.

    Args:
        datafile: Path to the JSONL file containing test data.
        variant: List of variant names to compare.
        sample_size: Number of samples to draw (overrides config.toml).
        ranseed: Random seed used when sampling datapoints (overrides config.toml).
        start_idx: Starting index for sequential sampling (0-indexed, inclusive).
        end_idx: Ending index for sequential sampling (0-indexed, exclusive).
        parallelism: Number of samples to evaluate concurrently.
        display: Display mode for eval logs (overrides config.toml).
        wandb_disable: Disable wandb logging (default is enabled).
        wandb_project: wandb project name (overrides config.toml).
        wandb_entity: wandb entity/team name (overrides config.toml).
        wandb_tags: Additional tags for wandb run.
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
    use_parallelism = parallelism if parallelism is not None else cfg.meta.parallelism
    use_display = display if display is not None else cfg.meta.display

    # Create log directory for comparison results
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%dT%H-%M-%S")
    log_dir_name = f"comparison_{timestamp}"
    log_dir = Path("artifacts") / "runs" / log_dir_name
    log_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Configure wandb settings: CLI flag > config
        # --wandb-disable flag explicitly disables, otherwise use config.toml setting
        wandb_enabled = cfg.wandb.enabled if not wandb_disable else False
        wandb_cfg = WandbConfig(
            enabled=wandb_enabled,
            project=wandb_project or cfg.wandb.project,
            entity=wandb_entity or cfg.wandb.entity,
            tags=(wandb_tags or []) + cfg.wandb.tags,
            upload_samples=cfg.wandb.upload_samples,
        )

        # Initialize wandb loggers for each variant if enabled
        # Use the comparison timestamp as the group name for wandb
        group_name = f"comparison_{timestamp}" if wandb_cfg.enabled else None

        wandb_loggers = {}
        if wandb_cfg.enabled:
            # Register cleanup handlers for all wandb loggers
            def cleanup_all_wandb():
                for logger in wandb_loggers.values():
                    logger.finish()

            atexit.register(cleanup_all_wandb)

            # Handle Ctrl+C and other termination signals
            def signal_handler(signum, frame):
                print("\n⚠️  Interrupted - finalizing wandb runs...")
                cleanup_all_wandb()
                raise KeyboardInterrupt()

            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

            for v in variants_to_compare:
                variant_logger = init_wandb_logger(wandb_cfg)
                variant_logger.init_run(
                    variant=v,
                    model=cfg.agent.model,
                    sample_size=use_sample_size,
                    ranseed=use_ranseed,
                    timestamp=timestamp,
                    group=group_name,
                    start_idx=start_idx,
                    end_idx=end_idx,
                )
                wandb_loggers[v] = variant_logger

        # Create task instances for each variant (use same timestamp for all)
        tasks = [
            fvspec(
                datafile,
                variant=v,
                sample_size=use_sample_size,
                ranseed=use_ranseed,
                timestamp=now,
                start_idx=start_idx,
                end_idx=end_idx,
            )
            for v in variants_to_compare
        ]

        try:
            # Run all tasks together with eval_set
            eval_set(
                tasks,
                log_dir=str(log_dir),
                model=cfg.agent.model,
                max_samples=use_parallelism,
                display=use_display,
            )
        finally:
            # Clean up empty sample directories (created by inspect_ai but unused)
            utilio.cleanup_empty_sample_dirs(log_dir)

            # Note: wandb cleanup handled by atexit/signal handlers
            # to ensure it runs even on interrupts

            # Clean up empty log directory (handles both failures and mocked eval_set in tests)
            if log_dir.exists() and not any(log_dir.iterdir()):
                log_dir.rmdir()
    except (KeyboardInterrupt, Exception):
        # Re-raise to propagate the error
        raise


@app.command(name="retry-all")
def retry_all(
    artifacts_dir: str = Option(
        "artifacts",
        help="Directory to search for .eval files (default: artifacts/)",
    ),
    parallelism: int = Option(
        None,
        "-p",
        "--parallelism",
        help="Number of samples to evaluate in parallel. Overrides config.toml.",
    ),
    display: DisplayType | None = Option(
        None,
        help="Display mode: full, conversation, rich, plain, log, none. Overrides config.toml.",
    ),
) -> None:
    """Retry all .eval files found in artifacts directory.

    This command finds all .eval files and retries them using inspect eval-retry,
    automatically using the model and settings from config.toml.

    Args:
        artifacts_dir: Directory to search for .eval files.
        parallelism: Number of samples to evaluate in parallel (overrides config.toml).
        display: Display mode for eval logs (overrides config.toml).
    """
    # Find all .eval files
    artifacts_path = Path(artifacts_dir)
    if not artifacts_path.exists():
        print(f"Error: Directory {artifacts_dir} does not exist")
        return

    eval_files = sorted(artifacts_path.rglob("*.eval"))

    if not eval_files:
        print(f"No .eval files found in {artifacts_dir}")
        return

    print(f"Found {len(eval_files)} .eval files")
    print("Note: Will use the model stored in each .eval file")

    # Use config settings
    use_parallelism = parallelism if parallelism is not None else cfg.meta.parallelism
    use_display = display if display is not None else cfg.meta.display

    print(f"Parallelism: {use_parallelism}")
    print(f"Display: {use_display}")
    print()

    # Retry all files (model comes from .eval files, not config)
    eval_retry(
        [str(f) for f in eval_files],
        max_samples=use_parallelism,
        display=use_display,
    )


def main() -> None:
    """Entry point for the `uv run fvspec` CLI."""
    app()
