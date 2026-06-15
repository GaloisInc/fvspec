"""Post-production: Enrich samples with dedup metadata for HuggingFace delivery.

Groups samples by SHA-256 of ``pbt_code``, ranks formalizations within
each group by quality score, computes Pareto dominance on structural
faithfulness sub-metrics, and annotates every row with:

- ``code_hash`` — group key
- ``is_canonical`` — best sample in its group
- ``formalization_rank`` — 1-based rank (1 = canonical)
- ``num_formalizations`` — group size
- ``pareto_dominated`` — whether a strictly better sample exists on all SF axes

Usage (from benchmark/ directory):
    uv run postprod enrich artifacts/dataset-out/fvspec-merged.validated.jsonl
    uv run postprod enrich input.jsonl -o enriched.jsonl --dry-run
"""

import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from scripts.postproduction.dedup import _quality_score, code_hash

console = Console()

# Structural faithfulness sub-metrics used for Pareto comparison.
# Excludes 'overall' (composite) and 'assertion_theorem_difference' (signed delta).
SF_SUB_METRICS = [
    "parameter_coverage",
    "type_correspondence",
    "strategy_coverage",
    "assertion_coverage",
    "dependency_coverage",
]

# v1 grader fields to strip (inconsistent coverage across runs).
V1_GRADER_FIELDS = [
    "difficulty_subjective_haiku",
    "difficulty_subjective_haiku_takes",
]

# Ordered field groups for clean HF presentation.
FIELD_ORDER_PREFIX = [
    # Identity
    "sample_id",
    "code_hash",
    "pbt_sample_name",
    "pbt_id",
    "run",
    # Dedup metadata
    "is_canonical",
    "formalization_rank",
    "num_formalizations",
    "pareto_dominated",
    # Source PBT
    "pbt_code",
    "pbt_summary",
    "pbt_lines_pbt",
    "pbt_radon",
    "language",
    # Lean artifacts
    "spec",
    "impl",
    # Quality
    "success",
    "num_theorems",
    "structural_faithfulness",
    "impl_autoform_success",
    "actually_invokes_given",
    "implementation_level",
    "num_fns_impl",
    # Difficulty (v2 only)
    "difficulty_binary",
    "difficulty_binary_confidence",
    "difficulty_binary_reasoning",
    # Dependencies
    "dependencies",
    # Lean analysis
    "lean_metrics",
    "metrics_metadata",
]


def _sf_vector(sample: dict[str, Any]) -> list[float]:
    """Extract SF sub-metric vector, treating None/missing as 0."""
    sf = sample.get("structural_faithfulness") or {}
    return [float(sf.get(m, 0.0) or 0.0) for m in SF_SUB_METRICS]


def _dominates(a: list[float], b: list[float]) -> bool:
    """True if a >= b on all dimensions and strictly > on at least one."""
    at_least_one_strict = False
    for ai, bi in zip(a, b):
        if ai < bi:
            return False
        if ai > bi:
            at_least_one_strict = True
    return at_least_one_strict


def compute_pareto_dominated(group: list[dict[str, Any]]) -> dict[int, bool]:
    """For each sample index in the group, check if it's Pareto-dominated."""
    vectors = [_sf_vector(s) for s in group]
    dominated: dict[int, bool] = {}
    for i, vi in enumerate(vectors):
        dominated[i] = any(_dominates(vj, vi) for j, vj in enumerate(vectors) if j != i)
    return dominated


def reorder_fields(sample: dict[str, Any]) -> dict[str, Any]:
    """Reorder sample fields: prefix order first, then remaining alphabetically."""
    ordered: dict[str, Any] = {}
    for key in FIELD_ORDER_PREFIX:
        if key in sample:
            ordered[key] = sample[key]
    remaining = sorted(k for k in sample if k not in ordered)
    for key in remaining:
        ordered[key] = sample[key]
    return ordered


def enrich_samples(
    samples: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Group by code hash, rank, annotate, strip v1 fields, reorder.

    Returns:
        (enriched_samples, stats_dict)
    """
    # Group
    groups: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for i, s in enumerate(samples):
        h = code_hash(s)
        groups.setdefault(h, []).append((i, s))

    enriched: list[dict[str, Any]] = []
    canonical_count = 0
    pareto_nontrivial = 0

    for h, indexed_group in groups.items():
        group = [s for _, s in indexed_group]

        # Rank by quality score (descending)
        ranked = sorted(
            range(len(group)), key=lambda i: _quality_score(group[i]), reverse=True
        )

        # Pareto dominance
        dominated = compute_pareto_dominated(group)
        pareto_front_size = sum(1 for d in dominated.values() if not d)
        if pareto_front_size > 1:
            pareto_nontrivial += 1

        for rank_idx, group_idx in enumerate(ranked):
            s = dict(group[group_idx])  # shallow copy

            # Strip v1 grader fields
            for field in V1_GRADER_FIELDS:
                s.pop(field, None)

            # Add enrichment fields
            s["code_hash"] = h
            s["is_canonical"] = rank_idx == 0
            s["formalization_rank"] = rank_idx + 1
            s["num_formalizations"] = len(group)
            s["pareto_dominated"] = dominated[group_idx]

            enriched.append(reorder_fields(s))
            if rank_idx == 0:
                canonical_count += 1

    # Sort by sample_id for stable output
    enriched.sort(key=lambda s: s.get("sample_id", 0))

    stats = {
        "input_samples": len(samples),
        "unique_pbts": len(groups),
        "canonical_count": canonical_count,
        "pareto_nontrivial_groups": pareto_nontrivial,
        "v1_fields_stripped": V1_GRADER_FIELDS,
    }
    return enriched, stats


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
        help="Output path (default: <input>.enriched.jsonl)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print stats without writing output",
    ),
) -> None:
    """Enrich samples with dedup metadata for HuggingFace delivery.

    Groups samples by SHA-256 of pbt_code, ranks formalizations by
    quality score, computes Pareto dominance on structural faithfulness
    sub-metrics, strips v1 grader fields, and reorders columns.
    """
    console.print("[bold]Post-production: Enrich for HuggingFace[/bold]\n")

    console.print(f"Loading {input_jsonl.name}...")
    samples = []
    with open(input_jsonl) as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))
    console.print(f"  Loaded {len(samples)} samples")

    from collections import Counter

    run_counts = Counter(s.get("run", "unknown") for s in samples)
    for run, count in sorted(run_counts.items()):
        console.print(f"  {run}: {count}")

    enriched, stats = enrich_samples(samples)

    console.print("\n[bold]Enrichment Results[/bold]")
    console.print(f"  Input samples:             {stats['input_samples']}")
    console.print(f"  Unique PBTs:               {stats['unique_pbts']}")
    console.print(f"  Canonical samples:         {stats['canonical_count']}")
    console.print(f"  Pareto-nontrivial groups:  {stats['pareto_nontrivial_groups']}")
    console.print(f"  v1 fields stripped:        {stats['v1_fields_stripped']}")

    # Verify invariants
    canonical = [s for s in enriched if s["is_canonical"]]
    assert len(canonical) == stats["unique_pbts"], (
        f"Canonical count mismatch: {len(canonical)} != {stats['unique_pbts']}"
    )

    # Show composition
    enriched_runs = Counter(s.get("run", "unknown") for s in canonical)
    console.print("\n[bold]Canonical composition[/bold]")
    for run, count in sorted(enriched_runs.items()):
        console.print(f"  {run}: {count}")

    # Pareto stats
    not_dominated = sum(1 for s in enriched if not s["pareto_dominated"])
    console.print(f"\n  Pareto non-dominated samples: {not_dominated}/{len(enriched)}")

    if dry_run:
        console.print("\n[yellow]Dry run — no output written[/yellow]")
        return

    if output is None:
        output = input_jsonl.with_suffix(".enriched.jsonl")

    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        for s in enriched:
            f.write(json.dumps(s) + "\n")

    console.print(
        f"\n[green]Wrote {len(enriched)} samples to {output}[/green]"
        f" [dim]({output.stat().st_size / 1024 / 1024:.1f} MB)[/dim]"
    )
