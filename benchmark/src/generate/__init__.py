"""Generate the benchmark."""

from collections import defaultdict
import json
from datetime import datetime
from pathlib import Path
import random

from inspect_ai import eval, eval_set

from generate.config import load_config, WandbConfig
from generate.scaffold.task import fvspec, DATA_DIR
from generate.scaffold.wandb_logger import init_wandb_logger
from generate.scaffold.dataset import load_datapoints, Datapoint
from generate.scaffold.depmock import (
    DependencyPayload,
    DependencyBatchError,
    DependencyExecutionRequest,
    DependencyResult,
    DependencySampleSpec,
    run_dependency_agent,
    build_dependency_dataset,
    clear_cache,
    load_cached_dependency,
    persist_generated_dependency,
    record_cache_hit,
    run_dependency_autoformalizer,
    scan_dependencies,
)
from generate.scaffold.depmock.cache import CacheProvenance, read_manifest
from generate.scaffold.depmock.runner import (
    aggregate_dependency_modules,
    order_dependency_modules,
)  # type: ignore[attr-defined]
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
    datafile: str = Option("pbts.jsonl", help="Path to test data JSONL file"),
    no_mcp: bool = Option(False, help="Disable Lean LSP MCP tools"),
    skip_index: bool = Option(
        False, help="Skip using index file and use slower reservoir sampling"
    ),
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
    wandb_disable: bool = Option(
        False,
        "--wandb-disable",
        help="Disable Weights & Biases logging. Default is to enable wandb.",
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
    force_deps_regen: bool = Option(
        False,
        "--force-deps-regen",
        help="Ignore dependency cache and regenerate all dependencies. Overwrites existing cache entries on hash collision.",
    ),
) -> None:
    """Run the fvspec benchmark with a single variant.

    This is the default command. For A/B testing, use the compare-variants subcommand.

    Args:
        ctx: Typer context.
        datafile: Path to the JSONL file containing test data.
        no_mcp: Disable Lean LSP MCP tools.
        skip_index: Skip using index file and use reservoir sampling.
        variant: Prompt variant name (overrides config.toml).
        sample_size: Number of samples to draw (overrides config.toml).
        ranseed: Random seed used when sampling datapoints (overrides config.toml).
        list_variants: List available variants and exit.
        display: Display mode for eval logs (overrides config or CLI default).
        parallelism: Number of concurrent samples to evaluate.
        wandb_disable: Disable wandb logging (default is enabled).
        wandb_project: wandb project name (overrides config.toml).
        wandb_entity: wandb entity/team name (overrides config.toml).
        wandb_tags: Additional tags for wandb run.
        force_deps_regen: Ignore cache and regenerate all dependencies.
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

    # Configure wandb settings: CLI args > config
    # Default is enabled unless --wandb-disable flag is set
    wandb_cfg = WandbConfig(
        enabled=not wandb_disable,
        project=wandb_project or cfg.wandb.project,
        entity=wandb_entity or cfg.wandb.entity,
        tags=(wandb_tags or []) + cfg.wandb.tags,
        upload_samples=cfg.wandb.upload_samples,
        sync_dep_cache=cfg.wandb.sync_dep_cache,
    )

    # Create log directory in artifacts/runs
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%dT%H-%M-%S")
    log_dir_name = f"{timestamp}__{use_variant}"
    log_dir = Path("artifacts") / "runs" / log_dir_name
    log_dir.mkdir(parents=True, exist_ok=True)

    # Handle force_deps_regen: clear local cache before starting
    if force_deps_regen:
        print(
            "⚠️  Force regeneration enabled: clearing local cache, will overwrite existing entries"
        )
        clear_cache()

    # Initialize wandb logger if enabled
    wandb_logger = init_wandb_logger(wandb_cfg)
    if wandb_cfg.enabled:
        wandb_logger.init_run(
            variant=use_variant or "default",
            model=cfg.agent.model,
            sample_size=use_sample_size,
            ranseed=use_ranseed,
            timestamp=timestamp,
        )

        # Download dep cache at start of run (unless force_deps_regen is enabled)
        if wandb_cfg.sync_dep_cache and not force_deps_regen:
            print("Downloading dependency cache from wandb...")
            wandb_logger.download_dep_cache()

    try:
        eval(
            fvspec(
                datafile,
                use_mcp=not no_mcp,
                variant=use_variant,
                sample_size=use_sample_size,
                ranseed=use_ranseed,
                skip_index=skip_index,
                timestamp=now,
            ),
            model=cfg.agent.model,
            log_dir=str(log_dir),
            max_samples=use_parallelism,
            max_connections=use_parallelism,
        )
    finally:
        if wandb_cfg.enabled:
            # Upload dep cache at end of run
            if wandb_cfg.sync_dep_cache:
                print("Uploading dependency cache to wandb...")
                wandb_logger.upload_dep_cache()

            # Log summary metrics after eval completes
            # Note: We'll need to read QA files from disk since we don't have them in memory
            wandb_logger.finish()


@app.command(name="compare-variants")
def compare_variants(
    datafile: str = Option("pbts.jsonl", help="Path to test data JSONL file"),
    no_mcp: bool = Option(False, help="Disable Lean LSP MCP tools"),
    skip_index: bool = Option(
        False, help="Skip using index file and use slower reservoir sampling"
    ),
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
    wandb_disable: bool = Option(
        False,
        "--wandb-disable",
        help="Disable Weights & Biases logging. Default is to enable wandb.",
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
        no_mcp: Disable Lean LSP MCP tools.
        skip_index: Skip using index file and use reservoir sampling.
        variant: List of variant names to compare.
        sample_size: Number of samples to draw (overrides config.toml).
        ranseed: Random seed used when sampling datapoints (overrides config.toml).
        parallelism: Number of samples to evaluate concurrently.
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

    # Create log directory for comparison results
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%dT%H-%M-%S")
    log_dir_name = f"comparison_{timestamp}"
    log_dir = Path("artifacts") / "runs" / log_dir_name
    log_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Configure wandb settings: CLI args > config
        # Default is enabled unless --wandb-disable flag is set
        wandb_cfg = WandbConfig(
            enabled=not wandb_disable,
            project=wandb_project or cfg.wandb.project,
            entity=wandb_entity or cfg.wandb.entity,
            tags=(wandb_tags or []) + cfg.wandb.tags,
            upload_samples=cfg.wandb.upload_samples,
            sync_dep_cache=cfg.wandb.sync_dep_cache,
        )

        # Initialize wandb loggers for each variant if enabled
        # Use the comparison timestamp as the group name for wandb
        group_name = f"comparison_{timestamp}" if wandb_cfg.enabled else None

        wandb_loggers = {}
        if wandb_cfg.enabled:
            for v in variants_to_compare:
                variant_logger = init_wandb_logger(wandb_cfg)
                variant_logger.init_run(
                    variant=v,
                    model=cfg.agent.model,
                    sample_size=use_sample_size,
                    ranseed=use_ranseed,
                    timestamp=timestamp,
                    group=group_name,
                )
                wandb_loggers[v] = variant_logger

            # Download dep cache once before all variants run
            if wandb_cfg.sync_dep_cache and wandb_loggers:
                print("Downloading dependency cache from wandb...")
                first_logger = next(iter(wandb_loggers.values()))
                first_logger.download_dep_cache()

        # Create task instances for each variant (use same timestamp for all)
        tasks = [
            fvspec(
                datafile,
                use_mcp=not no_mcp,
                variant=v,
                sample_size=use_sample_size,
                ranseed=use_ranseed,
                skip_index=skip_index,
                timestamp=now,
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
                max_connections=use_parallelism,
            )
        finally:
            if wandb_cfg.enabled:
                # Upload dep cache once after all variants complete
                if wandb_cfg.sync_dep_cache and wandb_loggers:
                    print("Uploading dependency cache to wandb...")
                    first_logger = next(iter(wandb_loggers.values()))
                    first_logger.upload_dep_cache()

                for variant_logger in wandb_loggers.values():
                    variant_logger.finish()

            # Clean up empty log directory (handles both failures and mocked eval_set in tests)
            if log_dir.exists() and not any(log_dir.iterdir()):
                log_dir.rmdir()
    except (KeyboardInterrupt, Exception):
        # Re-raise to propagate the error
        raise


@deps_app.command(name="autoformalize")
def deps_autoformalize_command(
    datafile: str = Option("pbts.jsonl", help="Path to test data JSONL file"),
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
    validate: bool = Option(
        False,
        "--validate",
        help="Typecheck aggregated dependency modules after generation.",
    ),
    force_deps_regen: bool = Option(
        False,
        "--force-deps-regen",
        help="Ignore dependency cache and regenerate all dependencies. Overwrites existing cache entries on hash collision.",
    ),
) -> None:
    """Autoformalize dependencies for selected datapoints without running the full generate.

    Args:
        datafile: Path to the JSONL file containing test data.
        sample_id: Specific datapoint id(s) to autoformalize.
        sample_size: Number of datapoints to sample if --sample-id not provided.
        ranseed: Random seed for sampling.
        variant: Variant name for metadata.
        skip_cached: Skip dependencies already in cache (still copies to run directory).
        max_attempts: Maximum retry attempts per dependency.
        dry_run: Emit stubs without invoking autoformalizer.
        batch_size: Logical batch size for dataset metadata.
        validate: Typecheck aggregated modules after generation.
        force_deps_regen: Ignore cache and regenerate all dependencies.
    """
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
    base_dir = Path("artifacts") / "runs" / f"{timestamp}__variant_{path_variant}"
    base_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"Autoformalizing {len(selected)} dependency set(s) using variant '{base_variant}'."
    )
    print(f"Artifacts will be written to {base_dir}\n")

    # Force regeneration overrides skip_cached
    effective_skip_cached = False if force_deps_regen else skip_cached
    if force_deps_regen:
        print(
            "⚠️  Force regeneration enabled: ignoring cache, will overwrite existing entries\n"
        )

    specs = scan_dependencies(
        selected,
        skip_cached=False,  # Always scan to discover all dependencies; cache status adjusted below if force_deps_regen enabled
        dedupe=True,
    )

    if not specs:
        print("No dependencies discovered for the selected datapoints.")
        return

    # When force_deps_regen is enabled, mark all specs as uncached to force regeneration
    if force_deps_regen:
        specs = [
            DependencySampleSpec(
                payload=spec.payload,
                cache_key=spec.cache_key,
                datapoint_id=spec.datapoint_id,
                datapoint_repo_id=spec.datapoint_repo_id,
                datapoint_name=spec.datapoint_name,
                dependency_index=spec.dependency_index,
                sample_id=spec.sample_id,
                cached=False,  # Force regeneration
            )
            for spec in specs
        ]

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

    def make_stub_result(payload: DependencyPayload) -> DependencyResult:
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
        diagnostics = "dry-run"
        return DependencyResult(
            lean_module=module_name,
            lean_code=lean_code,
            variant=base_variant,
            status="stub",
            diagnostics=diagnostics,
        )

    agent_display = cfg.meta.display or "none"

    if dry_run:

        def executor(request: DependencyExecutionRequest) -> DependencyResult:
            return make_stub_result(request.spec.payload)

    else:

        def executor(request: DependencyExecutionRequest) -> DependencyResult:
            sample_output_dir = utilio.get_sample_output_dir(
                timestamp, request.spec.sample_id, path_variant
            )
            log_dir = sample_output_dir / "deps"
            return run_dependency_agent(
                request,
                variant=base_variant,
                model=cfg.agent.model,
                max_attempts=max_attempts,
                display=agent_display,
                log_dir=log_dir,
            )

    metadata = {
        "timestamp": timestamp,
        "variant": base_variant,
        "force_deps_regen": force_deps_regen,
    }

    fatal_encountered = False
    try:
        report = run_dependency_autoformalizer(
            specs,
            executor=executor,
            variant=base_variant,
            max_attempts=max_attempts,
            skip_cached=effective_skip_cached,
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

    validation_results: dict[str, dict[str, object]] = {}

    for sample_id, _ in sample_groups.items():
        sample_output_dir = utilio.get_sample_output_dir(
            timestamp, sample_id, path_variant
        )
        deps_dir = sample_output_dir / "deps"
        if not deps_dir.exists():
            continue
        manifest = read_manifest(deps_dir)
        aggregated = aggregate_dependency_modules(deps_dir, manifest)
        ordered = order_dependency_modules(aggregated)
        body = "\n\n".join(item["code"] for item in ordered if item["code"])
        lean_text = (
            f"namespace Fvspec.Deps\n\n{body}\n\nend Fvspec.Deps\n" if body else ""
        )
        (deps_dir / "Deps.lean").write_text(lean_text)
        if validate and lean_text.strip():
            stdout, stderr, exitcode = utilio.run_cmd(
                ["lean", str(deps_dir / "Deps.lean")], cwd=deps_dir
            )
            validation_results[sample_id] = {
                "exitcode": exitcode,
                "stdout": stdout,
                "stderr": stderr,
            }
            status = "ok" if exitcode == 0 else "error"
            print(f"  Validation ({sample_id}): {status} (exitcode={exitcode})")
        elif validate:
            validation_results[sample_id] = {
                "exitcode": 0,
                "stdout": "",
                "stderr": "",
            }
            print(f"  Validation ({sample_id}): skipped (no Lean content)")

    succeeded = len(report.succeeded)
    skipped = len(report.skipped)
    failed = len(report.failed)
    fatal = len(report.fatal)
    validation_failures = (
        sum(1 for res in validation_results.values() if res["exitcode"] != 0)
        if validate
        else 0
    )

    print("Run summary:")
    print(f"  Successful: {succeeded}")
    print(f"  Skipped (cached): {skipped}")
    print(f"  Failed: {failed}")
    print(f"  Fatal: {fatal}")
    if validate:
        print(f"  Validation failures: {validation_failures}")

    report_payload = {
        "timestamp": timestamp,
        "variant": base_variant,
        "dry_run": dry_run,
        "skip_cached": skip_cached,
        "max_attempts": max_attempts,
        "validate": validate,
        "dataset_size": len(dependency_dataset),
        "started_at": report.started_at.isoformat(),
        "completed_at": report.completed_at.isoformat(),
        "duration_seconds": (report.completed_at - report.started_at).total_seconds(),
        "totals": {
            "success": succeeded,
            "skipped": skipped,
            "failed": failed,
            "fatal": fatal,
            "total": report.total,
        },
        "outcomes": [
            {
                "cache_key": outcome.cache_key,
                "dependency": outcome.spec.dependency_name,
                "sample_id": outcome.spec.sample_id,
                "datapoint_id": outcome.spec.datapoint_id,
                "status": outcome.status,
                "attempts": outcome.attempts,
                "cached": outcome.spec.cached,
                "diagnostics": outcome.diagnostics,
                "result_status": outcome.result.status if outcome.result else None,
                "result_variant": outcome.result.variant if outcome.result else None,
                "error": str(outcome.error) if outcome.error else None,
            }
            for outcome in report.outcomes
        ],
        "metadata": report.metadata,
        "validation": validation_results,
    }

    report_path = base_dir / "dependency_report.json"
    report_path.write_text(json.dumps(report_payload, indent=2))
    print(f"  Report written to {report_path}")

    if fatal_encountered or fatal:
        raise typer.Exit(code=1)

    print(
        "\nDone. You can inspect the generated Lean modules and cache metadata under the directory above."
    )


@deps_app.command(name="cache-clear-local")
def deps_cache_clear_local_command() -> None:
    """Clear all local dependency autoformalization cache artifacts."""
    root = clear_cache()
    print(f"Cleared local dependency cache at {root}")


@deps_app.command(name="cache-clear-wandb")
def deps_cache_clear_wandb_command() -> None:
    """Delete the dependency cache artifact from wandb.

    This allows starting fresh with cache regeneration. The next run will
    create a new cache artifact from scratch.
    """
    import wandb
    from wandb.errors import CommError  # type: ignore[import-untyped]

    if not cfg.wandb.enabled:
        print("Error: wandb is disabled in config.toml")
        print("Enable wandb to manage remote cache artifacts")
        raise typer.Exit(code=1)

    # Initialize a temporary wandb run to access artifacts
    api = wandb.Api()

    try:
        artifact_path = f"{cfg.wandb.entity or api.default_entity}/{cfg.wandb.project}/dep-cache:latest"
        print(f"Attempting to delete artifact: {artifact_path}")

        artifact = api.artifact(artifact_path, type="dependency-cache")

        # First, delete the 'latest' alias to allow artifact deletion
        print("Removing 'latest' alias from artifact...")
        artifact.aliases.remove("latest")
        artifact.save()

        # Now delete all versions of the artifact
        print("Deleting artifact...")
        artifact.delete()

        print(f"✓ Successfully deleted dep-cache artifact from wandb")
        print(f"  Project: {cfg.wandb.project}")
        print(f"  Entity: {cfg.wandb.entity or api.default_entity}")
        print("\nNext run will create a fresh cache artifact.")

    except CommError as e:
        if "not found" in str(e).lower():
            print("Note: No dep-cache artifact found (may already be deleted)")
        else:
            print(f"Error communicating with wandb: {e}")
            raise typer.Exit(code=1)
    except Exception as e:
        print(f"Error deleting artifact: {e}")
        raise typer.Exit(code=1)


@app.command(name="index-data")
def index_data_command(
    datafile: str = Option("pbts.jsonl", help="Path to JSONL file to index"),
) -> None:
    """Build a byte-offset index for fast random sampling of the dataset.

    This is a one-time operation that creates an index file (datafile + ".index")
    mapping line numbers to byte positions. The index enables O(sample_size) sampling
    instead of O(total_lines) reservoir sampling.

    For the 116GB pbts.jsonl file:
    - Indexing takes: ~10-30 minutes (one-time cost)
    - Index file size: ~1-2 MB
    - Sampling speed: ~1 second for any sample size (vs ~10 minutes without index)

    The index is automatically used by all sampling operations once created.

    Args:
        datafile: JSONL file to index (default: pbts.jsonl)
    """
    from generate.scaffold.dataset import build_index

    dataset_path = (DATA_DIR / datafile).resolve()

    if not dataset_path.exists():
        print(f"Error: Dataset not found at {dataset_path}")
        raise typer.Exit(code=1)

    try:
        index_path = build_index(dataset_path)
        print(f"\n✓ Index successfully created at {index_path}")
        print(
            f"  All future sampling operations will automatically use this index for fast random access."
        )
    except Exception as e:
        print(f"Error building index: {e}")
        raise typer.Exit(code=1)


def main() -> None:
    """Entry point for the `uv run fvspec` CLI."""
    app()
