"""Generate the benchmark"""

from datetime import datetime
from pathlib import Path
from inspect_ai import eval, eval_set
from benchmark.config import load_config
from benchmark.scaffold.task import fvspec
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
    )


def main() -> None:
    app()
