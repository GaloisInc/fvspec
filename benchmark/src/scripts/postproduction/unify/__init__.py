r"""Post-production: Unify two heterogeneous fvspec metrics JSONL files into one.

Specifically merges the legacy feb03 schema (`fvspec-feb03.graded.metrics.jsonl`)
with the apr08 schema (`fvspec-apr08.metrics.jsonl`). The two files were produced
by different generations of the pipeline and have several schema drifts:

- Renamed: feb03 `radon` -> apr08 `realpbt_radon` (same 21-key shape).
- Restructured deps: feb03 `realpbt_deps` + `realpbt_dep_names`
  (parallel JSON-stringified lists) -> apr08 `dependencies` (list of structured
  objects with name, code, qualified_name, source_file, depth, kind, resolution).
  We backfill the structured shape from the parallel lists with `null` for the
  fields feb03 didn't capture. We do NOT keep two parallel formats.
- Lost in translation: feb03 `realpbt_repo_id` (int) is dropped; apr08's richer
  `repo` object cannot be reconstructed from feb03 alone, so feb03 rows get
  `repo: null`.
- Dead fields removed: `lean_metrics.tests_structure`, `lean_metrics.tests_complexity`,
  and `metrics_metadata.tests_available` are 100%-null in feb03 and absent in
  apr08, so we drop them on both sides.
- Redundant apr08 fields removed: top-level `metrics` (strict subset of
  `realpbt_radon`) and top-level `git_commit` (already in `provenance.git_commit`).
- feb03 `sample_name` is dropped (duplicate of `realpbt_sample_name`).
- feb03 carries grader fields (`grader_metadata`, `difficulty_subjective_haiku`,
  `difficulty_subjective_haiku_takes`); apr08 hasn't been graded yet, so those
  are emitted as `null` for apr08 rows.
- feb03 doesn't track `success`; emitted as `null` (postprod validate will fill).
- apr08's `realpbt_id` is missing entirely from the file; we leave it `null`.
  (We considered backfilling from realpbt2.jsonl, but realpbt v1 vs v2 ids
  diverged too much to make the join meaningful.)

Sample IDs are reassigned freshly across the merged output (1..N), with feb03
rows first (preserving their original order), then apr08 rows. The pre-merge
`sample_id` collisions are spurious -- they're artifacts of rescraping/relabeling
between snapshots, not real duplicates.

A `run` field ("feb03" | "apr08") is added to every row so downstream analyses
can slice by source.

Usage (from benchmark/ directory):
    uv run postprod unify \\
        artifacts/dataset-out/fvspec-feb03.graded.metrics.jsonl \\
        artifacts/dataset-out/fvspec-apr08.metrics.jsonl
    uv run postprod unify FEB03 APR08 --output artifacts/dataset-out/fvspec-merged.jsonl
"""

import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

console = Console()

# Schema constants ---------------------------------------------------------

# The 21 keys radon emits. feb03's `radon` has all populated; apr08's
# `realpbt_radon` has the same key set but ~12 of them are null.
RADON_KEYS = [
    "loc",
    "sloc",
    "lloc",
    "comments",
    "blank",
    "multi",
    "single_comments",
    "num_functions",
    "avg_complexity",
    "max_complexity",
    "total_complexity",
    "complexity_rank",
    "maintainability_index",
    "maintainability_rank",
    "halstead_vocabulary",
    "halstead_length",
    "halstead_volume",
    "halstead_difficulty",
    "halstead_effort",
    "halstead_time",
    "halstead_bugs",
]

# Fields stripped from `lean_metrics` because they're 100% null in feb03
# and absent in apr08.
LEAN_METRICS_DROP = ("tests_structure", "tests_complexity")

# Fields stripped from `metrics_metadata` for the same reason.
METRICS_METADATA_DROP = ("tests_available",)


# Transformations ----------------------------------------------------------


def _strip_lean_metrics(lm: dict[str, Any] | None) -> dict[str, Any] | None:
    """Drop dead `tests_*` keys from a lean_metrics object."""
    if lm is None:
        return None
    return {k: v for k, v in lm.items() if k not in LEAN_METRICS_DROP}


def _strip_metrics_metadata(mm: dict[str, Any] | None) -> dict[str, Any] | None:
    """Drop dead `tests_available` key from a metrics_metadata object."""
    if mm is None:
        return None
    return {k: v for k, v in mm.items() if k not in METRICS_METADATA_DROP}


def _parse_json_list(raw: Any) -> list[Any]:
    """Parse a JSON-stringified list, tolerating already-parsed lists and None."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        if not raw.strip():
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _feb03_dependencies(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Backfill the apr08-style `dependencies` list from feb03's parallel arrays.

    feb03 stores deps as two parallel JSON-stringified lists:
      - `realpbt_dep_names`: ["foo", "bar"]
      - `realpbt_deps`:      ["def foo(...): ...", "def bar(...): ..."]

    apr08 stores them as structured objects with extra fields we don't have
    in feb03 (qualified_name, source_file, depth, kind, resolution). We emit
    `null` for those, so the merged schema is uniform but lossy upward.
    """
    names = _parse_json_list(row.get("realpbt_dep_names"))
    codes = _parse_json_list(row.get("realpbt_deps"))
    n = max(len(names), len(codes))
    deps: list[dict[str, Any]] = []
    for i in range(n):
        name = names[i] if i < len(names) else None
        code = codes[i] if i < len(codes) else None
        deps.append(
            {
                "name": name,
                "code": code,
                "language": "python",
                "qualified_name": None,
                "source_file": None,
                "depth": None,
                "kind": None,
                "resolution": None,
            }
        )
    return deps


def transform_feb03(row: dict[str, Any]) -> dict[str, Any]:
    """Transform a feb03-schema row into the unified target schema.

    Caller is responsible for assigning the final `sample_id`.
    """
    return {
        # Identity / provenance
        "sample_id": None,  # assigned by caller
        "realpbt_id": row.get("realpbt_id"),
        "run": "feb03",
        # PBT metadata
        "realpbt_sample_name": row.get("realpbt_sample_name"),
        "realpbt_summary": row.get("realpbt_summary"),
        "realpbt_code": row.get("realpbt_code"),
        "realpbt_lines_pbt": row.get("realpbt_lines_pbt"),
        # Renamed: radon -> realpbt_radon (same 21-key shape, fully populated)
        "realpbt_radon": row.get("radon"),
        # Backfilled from parallel lists (lossy upward, null for missing fields)
        "dependencies": _feb03_dependencies(row),
        # feb03 has only an integer realpbt_repo_id; the structured `repo`
        # object cannot be reconstructed from feb03 alone (realpbt v1 vs v2
        # ids diverged), so leave null.
        "repo": None,
        # Lean artifacts
        "spec": row.get("spec"),
        "impl": row.get("impl"),
        # Sample-level metrics (unchanged)
        "num_theorems": row.get("num_theorems"),
        "actually_invokes_given": row.get("actually_invokes_given"),
        "impl_autoform_success": row.get("impl_autoform_success"),
        "implementation_level": row.get("implementation_level"),
        "num_fns_impl": row.get("num_fns_impl"),
        # apr08 carries an explicit language tag; feb03 was python-only
        "language": "python",
        "structural_faithfulness": row.get("structural_faithfulness"),
        "lean_metrics": _strip_lean_metrics(row.get("lean_metrics")),
        "metrics_metadata": _strip_metrics_metadata(row.get("metrics_metadata")),
        "provenance": row.get("provenance"),
        # Run-time stats
        "time": row.get("time"),
        "token_usage": row.get("token_usage"),
        "token_usage_breakdown": row.get("token_usage_breakdown"),
        "turn_counts": row.get("turn_counts"),
        # feb03 doesn't track `success`; postprod validate will populate later
        "success": None,
        # Grader fields (only feb03 has been graded so far)
        "grader_metadata": row.get("grader_metadata"),
        "difficulty_subjective_haiku": row.get("difficulty_subjective_haiku"),
        "difficulty_subjective_haiku_takes": row.get(
            "difficulty_subjective_haiku_takes"
        ),
    }


def transform_apr08(row: dict[str, Any]) -> dict[str, Any]:
    """Transform an apr08-schema row into the unified target schema.

    Caller is responsible for assigning the final `sample_id`.
    """
    return {
        # Identity / provenance
        "sample_id": None,  # assigned by caller
        # apr08 doesn't carry realpbt_id at all; backfill via realpbt2.jsonl
        # was considered and rejected (realpbt v1 vs v2 ids diverged too much).
        "realpbt_id": None,
        "run": "apr08",
        # PBT metadata
        "realpbt_sample_name": row.get("realpbt_sample_name"),
        "realpbt_summary": row.get("realpbt_summary"),
        "realpbt_code": row.get("realpbt_code"),
        "realpbt_lines_pbt": row.get("realpbt_lines_pbt"),
        # Already in target shape (with many nulls for the keys radon doesn't
        # bother computing on apr08; that's intentional).
        "realpbt_radon": row.get("realpbt_radon"),
        # Already structured.
        "dependencies": row.get("dependencies") or [],
        "repo": row.get("repo"),
        # Lean artifacts
        "spec": row.get("spec"),
        "impl": row.get("impl"),
        # Sample-level metrics
        "num_theorems": row.get("num_theorems"),
        "actually_invokes_given": row.get("actually_invokes_given"),
        "impl_autoform_success": row.get("impl_autoform_success"),
        "implementation_level": row.get("implementation_level"),
        "num_fns_impl": row.get("num_fns_impl"),
        "language": row.get("language", "python"),
        "structural_faithfulness": row.get("structural_faithfulness"),
        "lean_metrics": _strip_lean_metrics(row.get("lean_metrics")),
        "metrics_metadata": _strip_metrics_metadata(row.get("metrics_metadata")),
        # Note: apr08 also has a top-level `git_commit` that duplicates
        # provenance.git_commit; we drop it.
        "provenance": row.get("provenance"),
        # Run-time stats
        "time": row.get("time"),
        "token_usage": row.get("token_usage"),
        "token_usage_breakdown": row.get("token_usage_breakdown"),
        "turn_counts": row.get("turn_counts"),
        "success": row.get("success"),
        # apr08 hasn't been graded
        "grader_metadata": None,
        "difficulty_subjective_haiku": None,
        "difficulty_subjective_haiku_takes": None,
        # Note: apr08's top-level `metrics` is dropped (strict subset of
        # `realpbt_radon`).
    }


# IO -----------------------------------------------------------------------


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


# Entry point --------------------------------------------------------------


def main(
    feb03_input: Path = typer.Argument(
        ...,
        help="Path to legacy feb03 metrics JSONL (e.g. fvspec-feb03.graded.metrics.jsonl)",
        exists=True,
    ),
    apr08_input: Path = typer.Argument(
        ...,
        help="Path to apr08 metrics JSONL (e.g. fvspec-apr08.metrics.jsonl)",
        exists=True,
    ),
    output: Path = typer.Option(
        Path("artifacts/dataset-out/fvspec-merged.jsonl"),
        "--output",
        "-o",
        help="Output JSONL file path (relative to benchmark/)",
    ),
) -> None:
    """Unify feb03 + apr08 metrics JSONL files into a single merged dataset.

    Resolves schema drift between the two pipeline generations, assigns fresh
    `sample_id`s, tags each row with `run`, and concatenates feb03 then apr08
    in their original order. See module docstring for the full transformation
    rules.
    """
    console.print("[bold]Post-production: Unifying feb03 + apr08 datasets[/bold]\n")

    console.print(f"Reading feb03: {feb03_input}")
    feb03_rows = _read_jsonl(feb03_input)
    console.print(f"  {len(feb03_rows)} rows")

    console.print(f"Reading apr08: {apr08_input}")
    apr08_rows = _read_jsonl(apr08_input)
    console.print(f"  {len(apr08_rows)} rows")

    console.print("\n[bold]Transforming feb03 rows...[/bold]")
    feb03_transformed = [transform_feb03(r) for r in feb03_rows]

    console.print("[bold]Transforming apr08 rows...[/bold]")
    apr08_transformed = [transform_apr08(r) for r in apr08_rows]

    # Concatenate, preserving original within-source order: feb03 then apr08.
    merged = feb03_transformed + apr08_transformed

    # Assign fresh sample_ids 1..N.
    for i, row in enumerate(merged, start=1):
        row["sample_id"] = i

    console.print(f"\n[bold]Writing {len(merged)} rows to {output}[/bold]")
    _write_jsonl(output, merged)

    # Summary
    feb03_with_realpbt_id = sum(
        1 for r in feb03_transformed if r["realpbt_id"] is not None
    )
    feb03_with_deps = sum(1 for r in feb03_transformed if r["dependencies"])
    apr08_with_repo = sum(1 for r in apr08_transformed if r["repo"] is not None)
    apr08_with_deps = sum(1 for r in apr08_transformed if r["dependencies"])

    console.print("\n[bold]Unify Summary:[/bold]\n")
    console.print(f"  feb03 rows in:                  {len(feb03_rows)}")
    console.print(f"  apr08 rows in:                  {len(apr08_rows)}")
    console.print(f"  total rows out:                 {len(merged)}")
    console.print(f"  feb03 rows w/ realpbt_id:       {feb03_with_realpbt_id}")
    console.print(f"  feb03 rows w/ dependencies:     {feb03_with_deps}")
    console.print(f"  apr08 rows w/ repo:             {apr08_with_repo}")
    console.print(f"  apr08 rows w/ dependencies:     {apr08_with_deps}")
    console.print(
        "\n[dim]Note: apr08 rows have realpbt_id=null (no reliable backfill source); "
        "feb03 rows have repo=null and success=null.[/dim]"
    )

    console.print(
        f"\n[green]✓[/green] Unify complete! Merged dataset saved to: {output}"
    )
    console.print(f"[dim]File size: {output.stat().st_size / 1024 / 1024:.2f} MB[/dim]")
