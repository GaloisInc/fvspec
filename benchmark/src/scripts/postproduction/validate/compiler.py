"""Core validation logic: compile samples with lake build."""

import json
import random
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel
from rich.console import Console
from rich.progress import Progress

console = Console()

# Resolve lake-template relative to the benchmark root
BENCHMARK_ROOT = Path(__file__).resolve().parents[4]
LAKE_TEMPLATE = BENCHMARK_ROOT / "lake-template"
REPORT_DIR = BENCHMARK_ROOT / "docs" / "postproduction"

# Error categories checked in priority order; first match wins
CATEGORY_PATTERNS: list[tuple[str, list[str]]] = [
    ("timeout (nontermination)", []),  # special: checked via r.timeout
    (
        "termination / well-founded",
        [
            "fail to show termination",
            "well-founded recursion",
            "structural recursion",
        ],
    ),
    (
        "unknown identifier / namespace",
        ["unknown identifier", "unknown namespace", "does not contain"],
    ),
    (
        "failed to synthesize",
        ["failed to synthesize", "don't know how to synthesize"],
    ),
    ("type mismatch", ["type mismatch"]),
    ("syntax error", ["unexpected token", "expected", "unknown command"]),
    ("function expected", ["function expected"]),
    ("application error", ["application type mismatch", "invalid field"]),
    ("declaration error", ["failed to infer", "declaration type"]),
]

TURN_BUCKETS = [(0, 10), (11, 15), (16, 20), (21, 30), (31, 50), (51, 999)]


class ValidationResult(BaseModel):
    """Result of compiling a single sample with lake build."""

    sample_id: int
    sample_name: str
    compiles: bool
    exit_code: int
    errors: str
    warnings: str
    timeout: bool
    # From dataset for correlation analysis
    turn_counts_total: int | None = None
    turn_counts_impl_turns: int | None = None
    turn_counts_spec_turns: int | None = None
    impl_autoform_success: float | None = None
    num_theorems: int | None = None


def compile_sample(
    sample: dict,
    lake_template: Path,
    timeout: int,
) -> ValidationResult:
    """Compile a single sample by copying lake-template and running lake build."""
    sample_id = sample["sample_id"]
    sample_name = sample.get(
        "realpbt_sample_name", sample.get("sample_name", "unknown")
    )
    spec = sample.get("spec", "")
    impl = sample.get("impl", "")

    # Extract turn counts for correlation
    tc = sample.get("turn_counts") or {}
    tc_impl = tc.get("impl") or {}
    tc_spec = tc.get("spec") or {}

    turn_counts_total = tc.get("total_turns")
    turn_counts_impl_turns = tc_impl.get("turns")
    turn_counts_spec_turns = tc_spec.get("turns")
    impl_autoform_success = sample.get("impl_autoform_success")
    num_theorems = sample.get("num_theorems")

    def _make_result(
        *,
        compiles: bool,
        exit_code: int,
        errors: str,
        warnings: str,
        is_timeout: bool,
    ) -> ValidationResult:
        return ValidationResult(
            sample_id=sample_id,
            sample_name=sample_name,
            compiles=compiles,
            exit_code=exit_code,
            errors=errors,
            warnings=warnings,
            timeout=is_timeout,
            turn_counts_total=turn_counts_total,
            turn_counts_impl_turns=turn_counts_impl_turns,
            turn_counts_spec_turns=turn_counts_spec_turns,
            impl_autoform_success=impl_autoform_success,
            num_theorems=num_theorems,
        )

    with tempfile.TemporaryDirectory(prefix=f"fvspec_validate_{sample_id}_") as tmpdir:
        work = Path(tmpdir)

        # Copy template structure (without .lake and Fvspec — we set those up separately)
        for item in lake_template.iterdir():
            if item.name in (".lake", "Fvspec"):
                continue
            dest = work / item.name
            if item.is_dir():
                shutil.copytree(item, dest, symlinks=True)
            else:
                shutil.copy2(item, dest)

        # Set up .lake: symlink packages (read-only deps), own build dir (avoids races)
        lake_dir = work / ".lake"
        lake_dir.mkdir()
        (lake_dir / "packages").symlink_to(lake_template / ".lake" / "packages")
        (lake_dir / "build").mkdir()

        # Resolve lean-toolchain symlink to absolute
        toolchain_link = work / "lean-toolchain"
        if toolchain_link.is_symlink():
            target = toolchain_link.resolve()
            toolchain_link.unlink()
            shutil.copy2(target, toolchain_link)

        # Write generated Lean files
        fvspec_dir = work / "Fvspec"
        fvspec_dir.mkdir(exist_ok=True)

        (fvspec_dir / "Impl.lean").write_text(
            impl if impl else "-- No implementation\n"
        )
        (fvspec_dir / "Spec.lean").write_text(spec if spec else "-- No specification\n")

        try:
            result = subprocess.run(
                ["lake", "build"],
                cwd=work,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            # lake puts Lean compiler errors in stdout, build status in stderr
            combined = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()

            return _make_result(
                compiles=result.returncode == 0,
                exit_code=result.returncode,
                errors=combined if result.returncode != 0 else "",
                warnings=combined if result.returncode == 0 else "",
                is_timeout=False,
            )
        except subprocess.TimeoutExpired:
            return _make_result(
                compiles=False,
                exit_code=-1,
                errors=f"Timeout after {timeout}s",
                warnings="",
                is_timeout=True,
            )
        except Exception as e:
            return _make_result(
                compiles=False,
                exit_code=-1,
                errors=str(e),
                warnings="",
                is_timeout=False,
            )


def _compile_worker(args: tuple) -> dict:
    """Wrapper for ProcessPoolExecutor (must be top-level picklable)."""
    sample, lake_template_str, timeout = args
    result = compile_sample(sample, Path(lake_template_str), timeout)
    return result.model_dump()


def _classify_error(r: ValidationResult) -> str:
    """Classify a failed result into an error category."""
    if r.timeout:
        return "timeout (nontermination)"
    errors = r.errors.lower()
    for cat_name, patterns in CATEGORY_PATTERNS:
        if not patterns:
            continue
        if any(p in errors for p in patterns):
            return cat_name
    return "other"


def _bucket_label(lo: int, hi: int) -> str:
    return f"{lo}-{hi}" if hi < 999 else f"{lo}+"


def _bucket_stats(
    results: list[ValidationResult],
    buckets: list[tuple[int, int]],
    key_fn: Callable[[ValidationResult], int | None],
) -> list[tuple[str, int, int]]:
    """Return (label, fails, total) for each bucket."""
    rows = []
    for lo, hi in buckets:
        bucket = [r for r in results if (v := key_fn(r)) is not None and lo <= v <= hi]
        if not bucket:
            continue
        fails = sum(1 for r in bucket if not r.compiles)
        rows.append((_bucket_label(lo, hi), fails, len(bucket)))
    return rows


def _extract_error_patterns(
    results: list[ValidationResult], top_n: int = 10
) -> list[tuple[str, int]]:
    """Extract normalized error line frequencies."""
    error_patterns: dict[str, int] = {}
    for r in results:
        if r.compiles or not r.errors:
            continue
        for line in r.errors.split("\n"):
            line = line.strip()
            if not line or line.startswith("warning:"):
                continue
            if "error:" in line.lower():
                parts = line.split("error:")
                if len(parts) > 1:
                    key = "error:" + parts[-1].strip()[:120]
                else:
                    key = line[:120]
                error_patterns[key] = error_patterns.get(key, 0) + 1
    return sorted(error_patterns.items(), key=lambda x: -x[1])[:top_n]


def _wilson_ci(failures: int, total: int) -> tuple[float, float]:
    """Wilson score 95% CI. Returns (center, margin) as fractions."""
    p = failures / total
    z = 1.96
    denom = 1 + z**2 / total
    center = (p + z**2 / (2 * total)) / denom
    margin = z * (p * (1 - p) / total + z**2 / (4 * total**2)) ** 0.5 / denom
    return center, margin


def run_validation(
    input_jsonl: Path,
    sample_size: int,
    all_samples: bool,
    parallelism: int,
    seed: int,
    output: Path | None,
    timeout: int,
    filter_impl_autoform: bool,
) -> None:
    """Main validation pipeline."""
    console.print("[bold]Post-production: Compilation Validation[/bold]\n")

    # Load dataset
    console.print(f"Loading {input_jsonl.name}...")
    samples = []
    with open(input_jsonl) as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))
    total_loaded = len(samples)
    console.print(f"  Loaded {total_loaded} total samples")

    # Filter
    if filter_impl_autoform:
        samples = [s for s in samples if s.get("impl_autoform_success", 0) >= 1.0]
        console.print(f"  After impl_autoform filter: {len(samples)} samples")

    samples = [s for s in samples if s.get("spec") and s.get("impl")]
    eligible = len(samples)
    console.print(f"  With spec+impl: {eligible} samples")

    # Sample
    actual_sample_size = eligible
    if not all_samples and len(samples) > sample_size:
        rng = random.Random(seed)
        samples = rng.sample(samples, sample_size)
        actual_sample_size = len(samples)
        console.print(f"  Sampled {actual_sample_size} (seed={seed})")
    else:
        console.print(f"  Using all {actual_sample_size} samples")

    # Verify template
    if not LAKE_TEMPLATE.exists():
        console.print(f"[red]lake-template not found at {LAKE_TEMPLATE}[/red]")
        raise SystemExit(1)
    if not (LAKE_TEMPLATE / ".lake").exists():
        console.print(
            "[yellow]Warning: .lake directory missing. "
            "Run `lake build` in lake-template/ first.[/yellow]"
        )

    # Output path
    if output is None:
        output = input_jsonl.with_suffix(".validated.jsonl")

    console.print(f"\nValidating with parallelism={parallelism}, timeout={timeout}s")
    console.print(f"Output: {output}\n")

    # Run compilations
    results: list[ValidationResult] = []
    args_list = [(sample, str(LAKE_TEMPLATE), timeout) for sample in samples]

    with Progress(console=console) as progress:
        task = progress.add_task("Compiling...", total=len(samples))

        with ProcessPoolExecutor(max_workers=parallelism) as executor:
            futures = {
                executor.submit(_compile_worker, args): i
                for i, args in enumerate(args_list)
            }

            for future in as_completed(futures):
                try:
                    result_dict = future.result()
                    results.append(ValidationResult(**result_dict))
                except Exception as e:
                    idx = futures[future]
                    console.print(f"[red]Worker error for index {idx}: {e}[/red]")
                progress.advance(task)

    # Write filtered dataset: only samples that successfully compiled, in their
    # original full form (datapoint+qa+spec+impl+provenance). Per-sample failure
    # details are still summarized in the markdown report and console analysis
    # below — they just don't live in the JSONL anymore.
    samples_by_id = {s["sample_id"]: s for s in samples}
    passing_samples = [
        samples_by_id[r.sample_id]
        for r in sorted(results, key=lambda x: x.sample_id)
        if r.compiles and r.sample_id in samples_by_id
    ]
    with open(output, "w") as f:
        for sample in passing_samples:
            f.write(json.dumps(sample) + "\n")

    console.print(
        f"\n[green]Wrote {len(passing_samples)} passing samples to {output}[/green]"
        f" [dim](dropped {len(results) - len(passing_samples)} failures)[/dim]\n"
    )

    # Analyze and print to console
    print_analysis(results)

    # Write markdown report
    report_path = write_report(
        results=results,
        input_jsonl=input_jsonl,
        total_loaded=total_loaded,
        eligible=eligible,
        sample_size=actual_sample_size,
        seed=seed,
        parallelism=parallelism,
        timeout=timeout,
        filter_impl_autoform=filter_impl_autoform,
        output_jsonl=output,
    )
    console.print(f"[green]Report written to {report_path}[/green]")


def print_analysis(results: list[ValidationResult]) -> None:
    """Print compilation stats and turn count correlation to console."""
    total = len(results)
    if total == 0:
        console.print("[yellow]No results to analyze[/yellow]")
        return

    compiles = sum(1 for r in results if r.compiles)
    fails = total - compiles
    timeouts = sum(1 for r in results if r.timeout)

    console.print("[bold]Compilation Results[/bold]")
    console.print(f"  Total:    {total}")
    console.print(f"  Compiles: {compiles} ({100 * compiles / total:.1f}%)")
    console.print(f"  Fails:    {fails} ({100 * fails / total:.1f}%)")
    console.print(f"  Timeouts: {timeouts}")

    if total > 0:
        center, margin = _wilson_ci(fails, total)
        console.print(
            f"  Failure rate 95% CI: {100 * center:.1f}% +/- {100 * margin:.1f}%"
        )

    with_turns = [r for r in results if r.turn_counts_total is not None]
    if not with_turns:
        console.print("\n  No turn count data available")
        return

    console.print("\n[bold]Turn Count Correlation[/bold]")
    pass_turns = [
        r.turn_counts_total
        for r in with_turns
        if r.compiles and r.turn_counts_total is not None
    ]
    fail_turns = [
        r.turn_counts_total
        for r in with_turns
        if not r.compiles and r.turn_counts_total is not None
    ]
    if pass_turns:
        console.print(
            f"  Compiling samples:     mean turns = "
            f"{sum(pass_turns) / len(pass_turns):.1f} (n={len(pass_turns)})"
        )
    if fail_turns:
        console.print(
            f"  Non-compiling samples: mean turns = "
            f"{sum(fail_turns) / len(fail_turns):.1f} (n={len(fail_turns)})"
        )

    console.print("\n[bold]Failure Rate by Turn Count Bucket[/bold]")
    for label, bucket_fails, bucket_total in _bucket_stats(
        with_turns, TURN_BUCKETS, lambda r: r.turn_counts_total
    ):
        console.print(
            f"  {label:>6s} turns: {bucket_fails}/{bucket_total} fail "
            f"({100 * bucket_fails / bucket_total:.0f}%)"
        )

    # Error categories
    console.print("\n[bold]Error Categories[/bold]")
    categories: dict[str, int] = {}
    for r in results:
        if r.compiles:
            continue
        cat = _classify_error(r)
        categories[cat] = categories.get(cat, 0) + 1
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        console.print(f"  {count:>4d}  {cat}")

    # Error patterns
    console.print("\n[bold]Common Error Patterns (top 10)[/bold]")
    for pattern, count in _extract_error_patterns(results):
        console.print(f"  {count:>4d}x  {pattern}")


def write_report(
    results: list[ValidationResult],
    input_jsonl: Path,
    total_loaded: int,
    eligible: int,
    sample_size: int,
    seed: int,
    parallelism: int,
    timeout: int,
    filter_impl_autoform: bool,
    output_jsonl: Path,
) -> Path:
    """Write a markdown validation report."""
    total = len(results)
    compiles = sum(1 for r in results if r.compiles)
    fails = total - compiles
    timeouts = sum(1 for r in results if r.timeout)
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    lines: list[str] = []

    def w(s: str = "") -> None:
        lines.append(s)

    w("# Compilation Validation Report")
    w()
    w(f"> Generated {now} by `uv run postprod validate`")
    w()
    w("## Parameters")
    w()
    w(f"- **Input**: `{input_jsonl.name}`")
    w(f"- **Total records loaded**: {total_loaded}")
    w(f"- **Eligible after filtering**: {eligible}")
    w(f"  - `impl_autoform_success >= 1.0`: {'yes' if filter_impl_autoform else 'no'}")
    w("  - Has both `spec` and `impl`")
    w(f"- **Sample size**: {sample_size} (seed={seed})")
    w(f"- **Parallelism**: {parallelism}")
    w(f"- **Timeout**: {timeout}s per build")
    w(f"- **Results JSONL**: `{output_jsonl.name}`")
    w()

    # Compilation results
    w("## Compilation Results")
    w()
    w("| Metric | Value |")
    w("|--------|-------|")
    w(f"| Total validated | {total} |")
    if total > 0:
        w(f"| Compiles | {compiles} ({100 * compiles / total:.1f}%) |")
        w(f"| Fails | {fails} ({100 * fails / total:.1f}%) |")
    else:
        w(f"| Compiles | {compiles} |")
        w(f"| Fails | {fails} |")
    w(f"| Timeouts | {timeouts} |")

    if total > 0:
        center, margin = _wilson_ci(fails, total)
        w(f"| Failure rate 95% CI | {100 * center:.1f}% +/- {100 * margin:.1f}% |")
    w()

    # Turn count correlation
    with_turns = [r for r in results if r.turn_counts_total is not None]

    if with_turns:
        pass_turns = [
            r.turn_counts_total
            for r in with_turns
            if r.compiles and r.turn_counts_total is not None
        ]
        fail_turns = [
            r.turn_counts_total
            for r in with_turns
            if not r.compiles and r.turn_counts_total is not None
        ]

        w("## Turn Count Correlation")
        w()
        w("| Group | Mean turns | n |")
        w("|-------|-----------|---|")
        if pass_turns:
            w(
                f"| Compiling | "
                f"{sum(pass_turns) / len(pass_turns):.1f} | {len(pass_turns)} |"
            )
        if fail_turns:
            w(
                f"| Non-compiling | "
                f"{sum(fail_turns) / len(fail_turns):.1f} | {len(fail_turns)} |"
            )
        w()

        # Turn count buckets
        w("### Failure Rate by Turn Count")
        w()
        w("| Turns | Fails / Total | Rate |")
        w("|-------|--------------|------|")
        for label, bucket_fails, bucket_total in _bucket_stats(
            with_turns, TURN_BUCKETS, lambda r: r.turn_counts_total
        ):
            w(
                f"| {label} | "
                f"{bucket_fails}/{bucket_total} | "
                f"{100 * bucket_fails / bucket_total:.0f}% |"
            )
        w()

    # Error categories
    w("## Error Categories")
    w()
    categories: dict[str, int] = {}
    for r in results:
        if r.compiles:
            continue
        cat = _classify_error(r)
        categories[cat] = categories.get(cat, 0) + 1

    if not categories:
        w("_No compilation failures — 100% success._")
    else:
        w("| Category | Count | % of failures |")
        w("|----------|-------|--------------|")
        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            w(f"| {cat} | {count} | {100 * count / fails:.0f}% |")
    w()

    # Error patterns
    w("## Common Error Patterns")
    w()
    w("Top 10 normalized error lines:")
    w()
    w("| Count | Pattern |")
    w("|-------|---------|")
    for pattern, count in _extract_error_patterns(results):
        # Escape pipes in pattern for markdown table
        safe = pattern.replace("|", "\\|")
        w(f"| {count} | `{safe}` |")
    w()

    report_text = "\n".join(lines) + "\n"
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")
    report_path = REPORT_DIR / f"VALIDATION_REPORT_{timestamp}.md"
    report_path.write_text(report_text)
    return report_path
