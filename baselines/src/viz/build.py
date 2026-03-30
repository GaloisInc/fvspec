"""
Static site generator for fvspec baselines .eval trajectory viewer.

Reads multiple .eval files (one per model) and an optional results.json,
then builds a static HTML dashboard with cross-model comparison charts
and a per-sample trajectory viewer.

Usage:
    uv run doteval-dashboard artifacts/*.eval
    uv run doteval-dashboard artifacts/2026-03-27*.eval
    uv run doteval-dashboard --help
"""

from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

import typer
from jinja2 import Environment, FileSystemLoader, select_autoescape
from rich.console import Console

app = typer.Typer(add_completion=False)
console = Console()

HERE = Path(__file__).parent

_PALETTE = [
    "rgba(59,130,246,0.85)",
    "rgba(20,184,166,0.85)",
    "rgba(168,85,247,0.85)",
    "rgba(251,146,60,0.85)",
    "rgba(34,197,94,0.85)",
    "rgba(239,68,68,0.85)",
]

_BUCKET_ORDER = {"easy": 0, "medium": 1, "hard": 2}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_eval(eval_path: Path) -> dict[str, Any]:
    """Load an inspect_ai .eval zip into a dict with 'eval' header and 'samples'."""
    with zipfile.ZipFile(eval_path) as zf:
        names = zf.namelist()
        header_file = (
            "_journal/start.json"
            if "_journal/start.json" in names
            else "header.json"
            if "header.json" in names
            else None
        )
        if not header_file:
            msg = f"No header found in {eval_path}"
            raise ValueError(msg)

        header = json.loads(zf.read(header_file))
        samples = []
        for name in sorted(names):
            if name.startswith("samples/") and name.endswith(".json"):
                samples.append(json.loads(zf.read(name)))
        header["samples"] = samples
    return header


def find_results_json(eval_paths: list[Path]) -> dict[str, Any] | None:
    """Find a results.json matching any of the eval file timestamps."""
    for eval_path in eval_paths:
        match = re.match(
            r"(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}\+\d{2}-\d{2})", eval_path.name
        )
        if not match:
            continue
        ts = match.group(1)
        results_path = eval_path.parent / "results" / ts / "results.json"
        if results_path.exists():
            return json.loads(results_path.read_text())
    return None


def _short_model(model: str) -> str:
    if "/" in model:
        model = model.split("/", 1)[1]
    # Strip date suffixes: -20250514 or -2026-03-17
    model = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", model)
    return re.sub(r"-\d{8}$", "", model)


# ---------------------------------------------------------------------------
# Sample processing
# ---------------------------------------------------------------------------


def _extract_message_content(content: Any) -> str:
    """Normalize message content to a string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block["text"])
            elif isinstance(block, dict):
                parts.append(json.dumps(block, indent=2))
            else:
                parts.append(str(block))
        return "\n".join(parts)
    return str(content)


def process_sample(sample: dict[str, Any]) -> dict[str, Any]:
    """Process a raw sample into display-ready data."""
    scores = sample.get("scores", {})
    scorer = scores.get("lake_build_scorer", {})
    meta = scorer.get("metadata", {})
    sample_meta = sample.get("metadata", {})

    messages = []
    for msg in sample.get("messages", []):
        display_msg: dict[str, Any] = {
            "role": msg.get("role", "unknown"),
            "content": _extract_message_content(msg.get("content", "")),
            "tool_calls": [
                {
                    "id": tc.get("id", ""),
                    "function": tc.get("function", ""),
                    "arguments": tc.get("arguments", {}),
                }
                for tc in msg.get("tool_calls", [])
            ],
        }
        if msg.get("tool_call_id"):
            display_msg["tool_call_id"] = msg["tool_call_id"]
        if msg.get("function"):
            display_msg["function"] = msg["function"]
        messages.append(display_msg)

    total_tokens = 0
    output_tokens = 0
    for model_usage in sample.get("model_usage", {}).values():
        total_tokens += model_usage.get("total_tokens", 0)
        output_tokens += model_usage.get("output_tokens", 0)

    return {
        "id": sample.get("id", "?"),
        "proved": meta.get("proved", False),
        "compiles": meta.get("compiles", False),
        "score_value": scorer.get("value", 0.0),
        "explanation": scorer.get("explanation", ""),
        "sorries_original": meta.get("sorries_original", 0),
        "sorries_remaining": meta.get("sorries_remaining", 0),
        "sorries_removed": meta.get("sorries_removed", 0),
        "partial_credit": meta.get("partial_credit", 0.0),
        "difficulty_bucket": meta.get(
            "difficulty_bucket", sample_meta.get("difficulty_bucket", "?")
        ),
        "difficulty_score": sample_meta.get("difficulty_subjective_haiku"),
        "num_theorems": sample_meta.get("num_theorems", 0),
        "total_time": round(sample.get("total_time", 0), 1),
        "working_time": round(sample.get("working_time", 0), 1),
        "message_count": len(sample.get("messages", [])),
        "total_tokens": total_tokens,
        "output_tokens": output_tokens,
        "messages": messages,
    }


# ---------------------------------------------------------------------------
# Per-model stats
# ---------------------------------------------------------------------------


def _model_stats(model_name: str, samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute summary stats for one model's samples."""
    n = len(samples)
    proved = sum(1 for s in samples if s["proved"])
    compiles = sum(1 for s in samples if s["compiles"])
    total_time = sum(s["total_time"] for s in samples)
    total_tokens = sum(s["total_tokens"] for s in samples)
    mean_partial = (
        round(sum(s["partial_credit"] for s in samples) / n, 4) if n > 0 else 0
    )

    # Per-bucket stats
    bucket_stats: dict[str, dict[str, Any]] = {}
    for bucket in ["easy", "medium", "hard"]:
        bs = [s for s in samples if s["difficulty_bucket"] == bucket]
        bn = len(bs)
        bp = sum(1 for s in bs if s["proved"])
        bpc = sum(s["partial_credit"] for s in bs)
        bucket_stats[bucket] = {
            "n": bn,
            "proved": bp,
            "rate": round(bp / bn * 100, 1) if bn > 0 else 0,
            "partial_credit": round(bpc / bn * 100, 1) if bn > 0 else 0,
        }

    return {
        "model": model_name,
        "n_samples": n,
        "proved": proved,
        "compiles": compiles,
        "prove_rate": round(proved / n * 100, 1) if n > 0 else 0,
        "compile_rate": round(compiles / n * 100, 1) if n > 0 else 0,
        "mean_partial_credit": mean_partial,
        "total_time": round(total_time, 1),
        "mean_time": round(total_time / n, 1) if n > 0 else 0,
        "total_tokens": total_tokens,
        "buckets": bucket_stats,
    }


# ---------------------------------------------------------------------------
# Chart builders (cross-model)
# ---------------------------------------------------------------------------


def _build_prove_rate_chart(
    models: list[str], model_data: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Grouped bar: prove rate by bucket, one dataset per model."""
    labels = ["Easy", "Medium", "Hard", "Total"]
    datasets = []
    for i, m in enumerate(models):
        ms = model_data[m]
        data = [
            ms["buckets"]["easy"]["rate"],
            ms["buckets"]["medium"]["rate"],
            ms["buckets"]["hard"]["rate"],
            ms["prove_rate"],
        ]
        datasets.append(
            {
                "label": m,
                "data": data,
                "backgroundColor": _PALETTE[i % len(_PALETTE)],
            }
        )
    return {"labels": labels, "datasets": datasets}


def _build_partial_credit_chart(
    models: list[str], model_data: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Grouped bar: mean partial credit by bucket, one dataset per model."""
    labels = ["Easy", "Medium", "Hard", "Total"]
    datasets = []
    for i, m in enumerate(models):
        ms = model_data[m]
        data = [
            ms["buckets"]["easy"]["partial_credit"],
            ms["buckets"]["medium"]["partial_credit"],
            ms["buckets"]["hard"]["partial_credit"],
            round(ms["mean_partial_credit"] * 100, 1),
        ]
        datasets.append(
            {
                "label": m,
                "data": data,
                "backgroundColor": _PALETTE[i % len(_PALETTE)],
            }
        )
    return {"labels": labels, "datasets": datasets}


def _build_score_donut(
    models: list[str],
    model_samples: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Donut: proved vs compiled-only vs failed across all models combined."""
    all_samples = [s for ss in model_samples.values() for s in ss]
    proved = sum(1 for s in all_samples if s["proved"])
    compiled_only = sum(1 for s in all_samples if s["compiles"] and not s["proved"])
    failed = sum(1 for s in all_samples if not s["compiles"])
    return {
        "labels": ["Proved", "Compiles (not proved)", "Build failed"],
        "datasets": [
            {
                "data": [proved, compiled_only, failed],
                "backgroundColor": [
                    "rgba(52,211,153,0.85)",
                    "rgba(251,191,36,0.85)",
                    "rgba(248,113,113,0.85)",
                ],
                "borderWidth": 2,
                "borderColor": "#0b0f1a",
            }
        ],
    }


def _build_time_comparison_chart(
    models: list[str], model_data: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Bar: total and mean time per model."""
    return {
        "labels": models,
        "datasets": [
            {
                "label": "Mean time per sample (s)",
                "data": [model_data[m]["mean_time"] for m in models],
                "backgroundColor": [
                    _PALETTE[i % len(_PALETTE)] for i in range(len(models))
                ],
            }
        ],
    }


def _build_token_comparison_chart(
    models: list[str], model_data: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Bar: total tokens per model."""
    return {
        "labels": models,
        "datasets": [
            {
                "label": "Total tokens",
                "data": [model_data[m]["total_tokens"] for m in models],
                "backgroundColor": [
                    _PALETTE[i % len(_PALETTE)] for i in range(len(models))
                ],
            }
        ],
    }


def _build_head_to_head_charts(
    models: list[str],
    sample_ids_by_bucket: dict[str, list[str]],
    model_samples: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    """Per-bucket head-to-head charts: partial credit per model per sample."""
    lookup: dict[str, dict[str, dict[str, Any]]] = {}
    for m, samples in model_samples.items():
        lookup[m] = {s["id"]: s for s in samples}

    charts: dict[str, dict[str, Any]] = {}
    for bucket in ["easy", "medium", "hard"]:
        sids = sample_ids_by_bucket.get(bucket, [])
        if not sids:
            continue
        labels = [str(sid) for sid in sids]
        datasets = []
        for i, m in enumerate(models):
            data = [
                round(lookup[m].get(sid, {}).get("partial_credit", 0) * 100, 1)
                for sid in sids
            ]
            datasets.append(
                {
                    "label": m,
                    "data": data,
                    "backgroundColor": _PALETTE[i % len(_PALETTE)],
                }
            )
        charts[bucket] = {"labels": labels, "datasets": datasets}
    return charts


# ---------------------------------------------------------------------------
# Top-level compute
# ---------------------------------------------------------------------------


def compute_stats(
    models: list[str],
    model_evals: dict[str, dict[str, Any]],
    model_samples: dict[str, list[dict[str, Any]]],
    results_data: dict[str, Any] | None,
) -> dict[str, Any]:
    # Per-model stats
    model_data: dict[str, dict[str, Any]] = {}
    for m in models:
        model_data[m] = _model_stats(m, model_samples[m])

    # Collect all sample IDs (union), sorted by bucket then id
    all_ids: set[str] = set()
    for samples in model_samples.values():
        for s in samples:
            all_ids.add(s["id"])

    # Build bucket_map from all models' samples so every ID in the union is
    # covered (first-seen value wins to keep deterministic ordering).
    bucket_map: dict[str, str] = {}
    for m in models:
        for s in model_samples[m]:
            bucket_map.setdefault(s["id"], s["difficulty_bucket"])
    sample_ids = sorted(
        all_ids,
        key=lambda sid: (_BUCKET_ORDER.get(bucket_map.get(sid, ""), 9), sid),
    )

    # Group sample IDs by bucket
    sample_ids_by_bucket: dict[str, list[str]] = {"easy": [], "medium": [], "hard": []}
    for sid in sample_ids:
        b = bucket_map.get(sid, "unknown")
        if b in sample_ids_by_bucket:
            sample_ids_by_bucket[b].append(sid)

    # Pick representative metadata from first eval
    first_eval = model_evals[models[0]].get("eval", {})

    stats: dict[str, Any] = {
        "models": models,
        "model_data": model_data,
        "sample_ids": sample_ids,
        "sample_ids_by_bucket": sample_ids_by_bucket,
        "bucket_map": bucket_map,
        "n_samples": len(sample_ids),
        "created": first_eval.get("created", ""),
        "message_limit": first_eval.get("config", {}).get("message_limit"),
        "task_args": first_eval.get("task_args", {}),
        "revision": first_eval.get("revision", {}),
        # Charts
        "prove_rate_chart": _build_prove_rate_chart(models, model_data),
        "partial_credit_chart": _build_partial_credit_chart(models, model_data),
        "score_donut": _build_score_donut(models, model_samples),
        "time_chart": _build_time_comparison_chart(models, model_data),
        "token_chart": _build_token_comparison_chart(models, model_data),
        "head_to_head_charts": _build_head_to_head_charts(
            models, sample_ids_by_bucket, model_samples
        ),
    }

    if results_data:
        stats["results"] = results_data.get("results", {})
        stats["results_meta"] = results_data.get("meta", {})

    return stats


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def build_site(eval_paths: list[Path], output_dir: Path) -> None:
    models: list[str] = []
    model_evals: dict[str, dict[str, Any]] = {}
    model_samples: dict[str, list[dict[str, Any]]] = {}

    for eval_path in eval_paths:
        console.print(f"\n[bold]Loading eval:[/bold] {eval_path.name}")
        eval_data = load_eval(eval_path)
        model_full = eval_data.get("eval", {}).get("model", "unknown")
        model = _short_model(model_full)

        raw_samples = eval_data.get("samples", [])
        console.print(f"  {model} — {len(raw_samples)} samples")

        processed = [process_sample(s) for s in raw_samples]
        processed.sort(
            key=lambda s: (_BUCKET_ORDER.get(s["difficulty_bucket"], 9), s["id"])
        )

        models.append(model)
        model_evals[model] = eval_data
        model_samples[model] = processed

    results_data = find_results_json(eval_paths)
    if results_data:
        console.print("\n  [green]Found matching results.json[/green]")

    console.print("\n[bold]Computing statistics...[/bold]")
    stats = compute_stats(models, model_evals, model_samples, results_data)
    for m in models:
        md = stats["model_data"][m]
        console.print(
            f"  {m}: {md['proved']}/{md['n_samples']} proved ({md['prove_rate']}%)"
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(str(HERE / "templates")),
        autoescape=select_autoescape(["html", "j2"]),
    )

    ctx: dict[str, Any] = {
        "stats": stats,
        "models": models,
        "model_samples": model_samples,
        "pages": [
            {"id": "index", "title": "Overview", "href": "index.html"},
            {
                "id": "trajectories",
                "title": "Trajectories",
                "href": "trajectories.html",
            },
        ],
    }

    pages_to_render = [
        ("index.html.j2", "index.html"),
        ("trajectories.html.j2", "trajectories.html"),
    ]

    console.print("\n[bold]Rendering pages...[/bold]")
    for tpl_name, out_name in pages_to_render:
        tpl = env.get_template(tpl_name)
        out_path = output_dir / out_name
        out_path.write_text(
            tpl.render(**ctx, current_page=out_name.replace(".html", ""))
        )
        size_kb = round(out_path.stat().st_size / 1024, 1)
        console.print(f"  [green]+[/green] {out_name} ({size_kb} KB)")

    console.print(
        f"\n[bold green]Done![/bold green] Output -> [cyan]{output_dir}[/cyan]"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@app.command()
def main(
    eval_files: list[Path] = typer.Argument(
        ...,
        help="One or more .eval files to compare",
    ),
    output_dir: Path = typer.Option(
        None,
        "-o",
        "--output-dir",
        help="Output directory (default: artifacts/dashboard/<timestamp>)",
    ),
) -> None:
    """Build a cross-model comparison dashboard from .eval files."""
    existing = [f for f in eval_files if f.exists() and f.suffix == ".eval"]
    if not existing:
        console.print("[red]No valid .eval files found.[/red]")
        raise typer.Exit(1)

    if output_dir is None:
        # Use timestamp from first eval file
        match = re.match(
            r"(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}\+\d{2}-\d{2})",
            existing[0].name,
        )
        ts = match.group(1) if match else datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        output_dir = existing[0].parent / "dashboard" / ts

    build_site(existing, output_dir)


if __name__ == "__main__":
    app()
