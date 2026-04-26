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

_BUCKET_ORDER = {"easy": 0, "hard": 1}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_eval(eval_path: Path) -> dict[str, Any]:
    """Load an inspect_ai .eval zip into a dict with 'eval' header, 'samples',
    and (if present) 'reductions' from reductions.json (multi-epoch pass@k runs)."""
    with zipfile.ZipFile(eval_path) as zf:
        names = zf.namelist()
        # Prefer full header.json when available — it contains final results/stats.
        header_file = (
            "header.json"
            if "header.json" in names
            else "_journal/start.json"
            if "_journal/start.json" in names
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

        if "reductions.json" in names:
            header["reductions"] = json.loads(zf.read("reductions.json"))
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


def process_epoch(sample: dict[str, Any]) -> dict[str, Any]:
    """Process one raw (id, epoch) sample into display-ready per-epoch data."""
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
        "id": str(sample.get("id", "?")),
        "epoch": sample.get("epoch", 1),
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
        "num_theorems": sample_meta.get("num_theorems", 0),
        "total_time": round(sample.get("total_time", 0), 1),
        "working_time": round(sample.get("working_time", 0), 1),
        "message_count": len(sample.get("messages", [])),
        "total_tokens": total_tokens,
        "output_tokens": output_tokens,
        "messages": messages,
    }


def _index_reductions(
    reductions: list[dict[str, Any]] | None,
) -> dict[str, dict[str, dict[str, Any]]]:
    """Index reductions.json as {reducer -> {sample_id -> entry}}."""
    out: dict[str, dict[str, dict[str, Any]]] = {}
    if not reductions:
        return out
    for r in reductions:
        reducer = r.get("reducer", "")
        entries: dict[str, dict[str, Any]] = {}
        for s in r.get("samples", []):
            sid = str(s.get("sample_id", ""))
            entries[sid] = s
        out[reducer] = entries
    return out


def aggregate_sample(
    sid: str,
    epochs: list[dict[str, Any]],
    reductions_by_sid: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    """Collapse N per-epoch records for one sample_id into one display-ready record.
    Keeps per-epoch details under `epochs` and picks the best epoch as the default
    view so templates that read `proved`, `messages`, etc. still work."""
    epochs_sorted = sorted(epochs, key=lambda e: e["epoch"])
    best = max(epochs_sorted, key=lambda e: (e["score_value"], e["partial_credit"]))

    n = len(epochs_sorted)
    any_proved = any(e["proved"] for e in epochs_sorted)
    all_proved = all(e["proved"] for e in epochs_sorted)
    proved_count = sum(1 for e in epochs_sorted if e["proved"])

    # Prefer inspect's reducer values when available.
    pass_at_1_r = reductions_by_sid.get("pass_at_1", {}).get(sid)
    pass_at_5_r = reductions_by_sid.get("pass_at_5", {}).get(sid)
    mean_r = reductions_by_sid.get("mean", {}).get(sid)

    pass_at_1 = (
        pass_at_1_r["value"]
        if pass_at_1_r is not None
        else sum(e["score_value"] for e in epochs_sorted) / n
    )
    pass_at_5 = (
        pass_at_5_r["value"]
        if pass_at_5_r is not None
        else (1.0 if any_proved else 0.0)
    )
    mean_value = (
        mean_r["value"]
        if mean_r is not None
        else sum(e["score_value"] for e in epochs_sorted) / n
    )
    mean_partial = sum(e["partial_credit"] for e in epochs_sorted) / n

    return {
        "id": sid,
        "num_epochs": n,
        "epochs": epochs_sorted,
        # Best-epoch defaults (templates treat this as the "primary" view)
        "proved": best["proved"],
        "compiles": best["compiles"],
        "score_value": best["score_value"],
        "explanation": best["explanation"],
        "sorries_original": best["sorries_original"],
        "sorries_remaining": best["sorries_remaining"],
        "sorries_removed": best["sorries_removed"],
        "partial_credit": best["partial_credit"],
        "messages": best["messages"],
        "message_count": best["message_count"],
        "difficulty_bucket": best["difficulty_bucket"],
        "difficulty_score": None,
        "num_theorems": best["num_theorems"],
        # Aggregates across epochs
        "any_proved": any_proved,
        "all_proved": all_proved,
        "proved_count": proved_count,
        "pass_at_1": pass_at_1,
        "pass_at_5": pass_at_5,
        "mean_value": mean_value,
        "mean_partial_credit": mean_partial,
        "total_time": round(sum(e["total_time"] for e in epochs_sorted), 1),
        "working_time": round(sum(e["working_time"] for e in epochs_sorted), 1),
        "total_tokens": sum(e["total_tokens"] for e in epochs_sorted),
        "output_tokens": sum(e["output_tokens"] for e in epochs_sorted),
    }


# ---------------------------------------------------------------------------
# Per-model stats
# ---------------------------------------------------------------------------


def _model_stats(model_name: str, samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute summary stats for one model's aggregated samples.

    `proved` / `prove_rate` reflect best-epoch proved (== any_proved == pass@k).
    For multi-epoch runs, `pass_at_1_rate` is the mean per-sample pass@1 value
    (equivalent to the mean scorer) and `pass_at_5_rate` is the fraction of
    samples where at least one of k epochs fully proved."""
    n = len(samples)
    compiles = sum(1 for s in samples if s["compiles"])
    total_time = sum(s["total_time"] for s in samples)
    total_tokens = sum(s["total_tokens"] for s in samples)

    k = max((s.get("num_epochs", 1) for s in samples), default=1)
    multi_epoch = k > 1

    # "proved" = best epoch proved (= any_proved). For single-epoch this is the
    # classic pass@1; for k>1 this is pass@k (equivalent when score is binary).
    proved = sum(1 for s in samples if s.get("any_proved", s["proved"]))

    mean_partial = (
        round(
            sum(s.get("mean_partial_credit", s["partial_credit"]) for s in samples) / n,
            4,
        )
        if n > 0
        else 0
    )

    # pass@k aggregates (fraction across samples)
    if multi_epoch:
        pass_at_1_rate = sum(s["pass_at_1"] for s in samples) / n if n > 0 else 0
        pass_at_5_rate = sum(s["pass_at_5"] for s in samples) / n if n > 0 else 0
    else:
        pass_at_1_rate = proved / n if n > 0 else 0
        pass_at_5_rate = pass_at_1_rate

    # Per-bucket stats
    bucket_stats: dict[str, dict[str, Any]] = {}
    for bucket in ["easy", "hard"]:
        bs = [s for s in samples if s["difficulty_bucket"] == bucket]
        bn = len(bs)
        bp = sum(1 for s in bs if s.get("any_proved", s["proved"]))
        bpc = sum(s.get("mean_partial_credit", s["partial_credit"]) for s in bs)
        if multi_epoch:
            b_p1 = sum(s["pass_at_1"] for s in bs) / bn if bn > 0 else 0
            b_p5 = sum(s["pass_at_5"] for s in bs) / bn if bn > 0 else 0
        else:
            b_p1 = bp / bn if bn > 0 else 0
            b_p5 = b_p1
        bucket_stats[bucket] = {
            "n": bn,
            "proved": bp,
            "rate": round(bp / bn * 100, 1) if bn > 0 else 0,
            "partial_credit": round(bpc / bn * 100, 1) if bn > 0 else 0,
            "pass_at_1": round(b_p1 * 100, 1),
            "pass_at_5": round(b_p5 * 100, 1),
        }

    return {
        "model": model_name,
        "n_samples": n,
        "num_epochs": k,
        "multi_epoch": multi_epoch,
        "proved": proved,
        "compiles": compiles,
        "prove_rate": round(proved / n * 100, 1) if n > 0 else 0,
        "compile_rate": round(compiles / n * 100, 1) if n > 0 else 0,
        "pass_at_1_rate": round(pass_at_1_rate * 100, 1),
        "pass_at_5_rate": round(pass_at_5_rate * 100, 1),
        "mean_partial_credit": mean_partial,
        "total_time": round(total_time, 1),
        "mean_time": round(total_time / n, 1) if n > 0 else 0,
        "total_tokens": total_tokens,
        "buckets": bucket_stats,
    }


# ---------------------------------------------------------------------------
# Chart builders (cross-model)
# ---------------------------------------------------------------------------


def _build_pass_at_k_chart(
    models: list[str], model_data: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Grouped bar: pass@1 vs pass@5 per model."""
    labels = ["pass@1", "pass@k"]
    datasets = []
    for i, m in enumerate(models):
        ms = model_data[m]
        datasets.append(
            {
                "label": f"{m} (k={ms['num_epochs']})",
                "data": [ms["pass_at_1_rate"], ms["pass_at_5_rate"]],
                "backgroundColor": _PALETTE[i % len(_PALETTE)],
            }
        )
    return {"labels": labels, "datasets": datasets}


def _build_prove_rate_chart(
    models: list[str], model_data: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Grouped bar: prove rate by bucket, one dataset per model."""
    labels = ["Easy", "Hard", "Total"]
    datasets = []
    for i, m in enumerate(models):
        ms = model_data[m]
        data = [
            ms["buckets"]["easy"]["rate"],
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
    labels = ["Easy", "Hard", "Total"]
    datasets = []
    for i, m in enumerate(models):
        ms = model_data[m]
        data = [
            ms["buckets"]["easy"]["partial_credit"],
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
    for bucket in ["easy", "hard"]:
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
    sample_ids_by_bucket: dict[str, list[str]] = {"easy": [], "hard": []}
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
        "any_multi_epoch": any(md["multi_epoch"] for md in model_data.values()),
        "max_k": max((md["num_epochs"] for md in model_data.values()), default=1),
        # Charts
        "pass_at_k_chart": _build_pass_at_k_chart(models, model_data),
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
        epochs_cfg = eval_data.get("eval", {}).get("config", {}).get("epochs", 1) or 1
        reductions_by_sid = _index_reductions(eval_data.get("reductions"))

        per_epoch = [process_epoch(s) for s in raw_samples]
        grouped: dict[str, list[dict[str, Any]]] = {}
        for ep in per_epoch:
            grouped.setdefault(ep["id"], []).append(ep)

        processed = [
            aggregate_sample(sid, eps, reductions_by_sid)
            for sid, eps in grouped.items()
        ]
        processed.sort(
            key=lambda s: (_BUCKET_ORDER.get(s["difficulty_bucket"], 9), s["id"])
        )
        console.print(
            f"  {model} — {len(raw_samples)} rows → {len(processed)} samples "
            f"(k={epochs_cfg})"
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
