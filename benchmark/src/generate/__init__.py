"""Generate the benchmark"""

from collections import defaultdict
from datetime import datetime
from pathlib import Path
import random

from inspect_ai import eval, eval_set

from generate.config import load_config
from generate.scaffold.task import fvspec, DATA_DIR
from generate.scaffold.dataset import load_datapoints, Datapoint
from generate.scaffold.depmock import (
    DependencyBatchError,
    DependencyExecutionRequest,
    DependencyResult,
    DependencySampleSpec,
    build_dependency_dataset,
    clear_cache,
    load_cached_dependency,
    persist_generated_dependency,
    record_cache_hit,
    run_dependency_autoformalizer,
    scan_dependencies,
)
from generate.scaffold.depmock.cache import CacheProvenance, read_manifest
from generate.scaffold.depmock.runner import _aggregate_lean, _order_modules  # type: ignore[attr-defined]
from generate.scaffold.tools import utilio
from generate.templates.spec import VariantRegistry
from typer import Typer, Option
import typer

cfg = load_config()
# if cfg.meta.logging:
#     setup_logfire()

app = Typer(no_args_is_help=False, invoke_without_command=True)
deps_app = Typer(help="Dependency management utilities")
app.add_typer(deps_app, name="deps")


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

    use_parallelism = parallelism if parallelism is not None else cfg.meta.parallelism

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
    use_parallelism = parallelism if parallelism is not None else cfg.meta.parallelism

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


@deps_app.command(name="autoformalize")
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
    skip_cached: bool = Option(
        True,
        "--skip-cached/--no-skip-cached",
        help="Skip dependencies already present in the cache (still copies them into the run directory).",
    ),
    max_attempts: int = Option(
        3, help="Maximum attempts for recoverable Lean errors per dependency."
    ),
    dry_run: bool = Option(
        False,
        "--dry-run",
        help="Emit Lean stubs without invoking the autoformalizer agent.",
    ),
    batch_size: int = Option(
        None,
        help="Logical batch size recorded for dependency dataset metadata.",
    ),
) -> None:
    """Autoformalize dependencies for selected datapoints without running the full generate."""

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
    path_variant = f"{base_variant}-deps"
    base_dir = Path("artifacts") / f"{timestamp}__variant_{path_variant}"
    base_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"Autoformalizing {len(selected)} dependency set(s) using variant '{base_variant}'."
    )
    print(f"Artifacts will be written to {base_dir}\n")

    specs = scan_dependencies(
        selected,
        skip_cached=False,
        dedupe=True,
    )

    if not specs:
        print("No dependencies discovered for the selected datapoints.")
        return

    for spec in specs:
        sample_output_dir = utilio.get_sample_output_dir(
            timestamp, spec.sample_id, path_variant
        )
        deps_dir = sample_output_dir / "deps"
        deps_dir.mkdir(parents=True, exist_ok=True)
        if skip_cached and spec.cached:
            cached_record = load_cached_dependency(spec.payload)
            if cached_record is not None:
                record_cache_hit(cached_record, sample_output_dir, source="cache")

    dependency_dataset = build_dependency_dataset(
        specs,
        date_time=datetime.strptime(timestamp, "%Y-%m-%dT%H-%M-%S"),
        variant=base_variant,
        batch_size=batch_size,
    )
    print(f"Prepared dependency dataset with {len(dependency_dataset)} samples.\n")

    def make_stub_result(payload) -> DependencyResult:
        module_name = payload.lean_module_name
        original = payload.python_source.strip()
        lean_code = (
            f"/-- Autoformalization stub for `{payload.dep_name}`.\n"
            "TODO: replace with generated Lean code. -/\n"
            "-- Original Python:\n/-\n"
            f"{original}\n"
            "-/\n\n"
            f"def {module_name}_stub : Unit := ()\n"
        )
        diagnostics = "dry-run" if dry_run else "autoformalizer not yet implemented"
        return DependencyResult(
            lean_module=module_name,
            lean_code=lean_code,
            variant=base_variant,
            status="stub",
            diagnostics=diagnostics,
        )

    def executor(request: DependencyExecutionRequest) -> DependencyResult:
        payload = request.spec.payload
        # Placeholder: emit stub Lean code until the agent integration is implemented.
        return make_stub_result(payload)

    metadata = {"timestamp": timestamp, "variant": base_variant}

    fatal_encountered = False
    try:
        report = run_dependency_autoformalizer(
            specs,
            executor=executor,
            variant=base_variant,
            max_attempts=max_attempts,
            skip_cached=skip_cached,
            dataset_batch_size=batch_size,
            metadata=metadata,
        )
    except DependencyBatchError as err:
        report = err.report
        fatal_encountered = True

    for outcome in report.outcomes:
        spec = outcome.spec
        sample_output_dir = utilio.get_sample_output_dir(
            timestamp, spec.sample_id, path_variant
        )
        if outcome.status == "success" and outcome.result is not None:
            provenance = CacheProvenance(
                model=cfg.agent.model,
                attempts=outcome.attempts,
                diagnostics=outcome.diagnostics,
            )
            persist_generated_dependency(
                spec.payload,
                outcome.result,
                sample_output_dir,
                provenance=provenance,
            )
        elif outcome.status == "skipped" and skip_cached:
            continue
        elif outcome.status in {"failed", "fatal"}:
            print(
                f"! Dependency {spec.dependency_name} failed after {outcome.attempts} attempt(s)."
            )

    sample_groups: dict[str, list[DependencySampleSpec]] = defaultdict(list)
    for spec in specs:
        sample_groups[spec.sample_id].append(spec)

    for sample_id, _ in sample_groups.items():
        sample_output_dir = utilio.get_sample_output_dir(
            timestamp, sample_id, path_variant
        )
        deps_dir = sample_output_dir / "deps"
        if not deps_dir.exists():
            continue
        manifest = read_manifest(deps_dir)
        aggregated = _aggregate_lean(deps_dir, manifest)
        ordered = _order_modules(aggregated)
        body = "\n\n".join(item["code"] for item in ordered if item["code"])
        lean_text = (
            f"namespace Fvspec.Deps\n\n{body}\n\nend Fvspec.Deps\n" if body else ""
        )
        (deps_dir / "Deps.lean").write_text(lean_text)

    succeeded = len(report.succeeded)
    skipped = len(report.skipped)
    failed = len(report.failed)
    fatal = len(report.fatal)

    print("Run summary:")
    print(f"  Successful: {succeeded}")
    print(f"  Skipped (cached): {skipped}")
    print(f"  Failed: {failed}")
    print(f"  Fatal: {fatal}")

    if fatal_encountered or fatal:
        raise typer.Exit(code=1)

    print(
        "\nDone. You can inspect the generated Lean modules and cache metadata under the directory above."
    )


@deps_app.command(name="cache-flush")
def deps_cache_flush_command() -> None:
    """Clear all dependency autoformalization cache artifacts."""

    root = clear_cache()
    print(f"Cleared dependency cache at {root}")


def main() -> None:
    app()
