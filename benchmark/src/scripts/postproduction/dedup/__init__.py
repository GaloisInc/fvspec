"""Post-production: Deduplicate samples by Python source code across runs.

Samples from different runs may formalize the same Python PBT. This step
groups samples by SHA-256 of ``realpbt_code`` and keeps the highest-quality
sample from each group (using the same quality scoring as the merge step).

Usage (from benchmark/ directory):
    uv run postprod dedup artifacts/dataset-out/fvspec-merged.validated.jsonl
    uv run postprod dedup input.jsonl -o deduped.jsonl --dry-run
"""

import hashlib
import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console


def _quality_score(sample: dict[str, Any]) -> tuple:
    """Quality score safe for None values (coerces to comparable types)."""
    structural = sample.get("structural_faithfulness")
    structural_overall = structural.get("overall", 0.0) if structural else 0.0

    return (
        bool(sample.get("success")),
        float(structural_overall or 0.0),
        int(sample.get("num_theorems") or 0),
        bool(sample.get("has_unit_tests")),
        float(sample.get("impl_autoform_success") or 0.0),
        bool(sample.get("spec_sig_success")),
    )


console = Console()


def code_hash(sample: dict[str, Any]) -> str:
    """SHA-256 of realpbt_code — canonical identity for the underlying PBT."""
    code = sample.get("realpbt_code", "")
    return hashlib.sha256(code.encode()).hexdigest()


def deduplicate_by_code(
    samples: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Group samples by code hash, keep the best from each group.

    Returns:
        (kept_samples, stats_dict)
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for s in samples:
        h = code_hash(s)
        groups.setdefault(h, []).append(s)

    kept: list[dict[str, Any]] = []
    cross_run_deduped = 0
    within_run_deduped = 0

    for h, group in groups.items():
        best = max(group, key=_quality_score)
        kept.append(best)

        if len(group) > 1:
            runs = {s.get("run") for s in group}
            extras = len(group) - 1
            if len(runs) > 1:
                cross_run_deduped += extras
            else:
                within_run_deduped += extras

    # Sort by sample_id for stable output
    kept.sort(key=lambda s: s.get("sample_id", 0))

    stats = {
        "input_samples": len(samples),
        "unique_code_hashes": len(groups),
        "output_samples": len(kept),
        "dropped_total": len(samples) - len(kept),
        "dropped_cross_run": cross_run_deduped,
        "dropped_within_run": within_run_deduped,
    }
    return kept, stats


def main(
    input_jsonl: Path = typer.Argument(
        ...,
        help="Path to JSONL dataset file",
        exists=True,
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path (default: <input>.deduped.jsonl)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print stats without writing output",
    ),
) -> None:
    """Deduplicate samples by Python PBT source code.

    Groups samples by SHA-256 of realpbt_code and keeps the highest-quality
    sample from each group. When the same PBT was formalized in multiple runs,
    the best formalization (by success, structural faithfulness, theorem count,
    etc.) is retained.
    """
    console.print("[bold]Post-production: Code-level Deduplication[/bold]\n")

    console.print(f"Loading {input_jsonl.name}...")
    samples = []
    with open(input_jsonl) as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))
    console.print(f"  Loaded {len(samples)} samples")

    # Run breakdown
    from collections import Counter

    run_counts = Counter(s.get("run", "unknown") for s in samples)
    for run, count in sorted(run_counts.items()):
        console.print(f"  {run}: {count}")

    kept, stats = deduplicate_by_code(samples)

    console.print("\n[bold]Dedup Results[/bold]")
    console.print(f"  Input samples:        {stats['input_samples']}")
    console.print(f"  Unique PBTs:          {stats['unique_code_hashes']}")
    console.print(f"  Output samples:       {stats['output_samples']}")
    console.print(f"  Dropped (total):      {stats['dropped_total']}")
    console.print(f"    Cross-run dups:     {stats['dropped_cross_run']}")
    console.print(f"    Within-run dups:    {stats['dropped_within_run']}")

    # Show run composition of output
    kept_runs = Counter(s.get("run", "unknown") for s in kept)
    console.print("\n[bold]Output composition[/bold]")
    for run, count in sorted(kept_runs.items()):
        console.print(f"  {run}: {count}")

    if dry_run:
        console.print("\n[yellow]Dry run — no output written[/yellow]")
        return

    if output is None:
        output = input_jsonl.with_suffix(".deduped.jsonl")

    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        for s in kept:
            f.write(json.dumps(s) + "\n")

    console.print(
        f"\n[green]Wrote {len(kept)} samples to {output}[/green]"
        f" [dim]({output.stat().st_size / 1024 / 1024:.1f} MB)[/dim]"
    )
