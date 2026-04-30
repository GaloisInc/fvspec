"""Baseline evaluation charts from inspect_ai .eval files.

Reads all .eval symlinks from comms/graphs/data/ and produces per-model,
per-bucket comparison plots for the fvspec baselines evaluation.

Handles inspect's native multi-epoch pass@k runs: when an .eval has
`epochs > 1` and a `reductions.json`, per-sample trajectories are grouped
by sample_id and reducer values (pass_at_1, pass_at_5, mean) are surfaced.

Usage:
    uv run graphs baselines           # via the main entrypoint
    python -m graphs.baselines        # direct invocation
"""

from __future__ import annotations

import json
import math
import re
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
OUT_DIR = Path(__file__).resolve().parents[2] / "out"

_PALETTE = ["#5ba3cf", "#e07b54", "#7a7a7a", "#a67ac4", "#4db88c"]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


_PRETTY_MODEL = {
    "snt46": "Sonnet 4.6",
    "ops47": "Opus 4.7",
    "gpt54": "GPT-5.4",
    "gpt54mini": "GPT-5.4 mini",
}


def _pretty(label: str) -> str:
    """Map an internal run label like `snt46_n-200_k-5` to `Sonnet 4.6`.

    Falls back to the original label if no model code is recognized.
    """
    head = label.split("_", 1)[0]
    return _PRETTY_MODEL.get(head, label)


def _label_from_path(path: Path) -> str:
    """Build a display label from a symlink filename.

    Strips only the trailing YYYYMMDD date so that runs of the same model
    with different (n, k) are kept as distinct labels. Examples:
      snt46_n-20_20260420         -> snt46_n-20
      snt46_n-200_k-5_20260422    -> snt46_n-200_k-5
    """
    stem = path.stem
    parts = stem.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit() and len(parts[1]) == 8:
        return parts[0]
    return stem


def _load_eval(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        hf = "header.json" if "header.json" in names else "_journal/start.json"
        header = json.loads(zf.read(hf))
        samples = [
            json.loads(zf.read(n))
            for n in sorted(names)
            if n.startswith("samples/") and n.endswith(".json")
        ]
        header["samples"] = samples
        if "reductions.json" in names:
            header["reductions"] = json.loads(zf.read("reductions.json"))
    return header


# Strong "I refuse to write a proof" signals: instruction-following phrases the
# system prompt asks the model to invoke when it judges the spec unprovable.
# Tuned to be conservative — these phrases rarely appear outside an explicit
# refusal to fill in a `sorry`.
_REFUSAL_PATTERNS = (
    re.compile(r"leav(?:e|ing)[^.\n]{0,80}sorry[^.\n]{0,40}place", re.I),
    re.compile(r"rather than[^.\n]{0,80}incorrect", re.I),
)


def _assistant_text(messages: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for m in messages:
        if m.get("role") != "assistant":
            continue
        c = m.get("content")
        if isinstance(c, str):
            parts.append(c)
        elif isinstance(c, list):
            for item in c:
                if not isinstance(item, dict):
                    continue
                if item.get("type") in ("text", "thinking", "reasoning"):
                    parts.append(item.get("text", item.get("thinking", "")))
    return "\n".join(parts)


def _detect_refusal(sample: dict[str, Any]) -> bool:
    text = _assistant_text(sample.get("messages", []))
    return any(p.search(text) for p in _REFUSAL_PATTERNS)


def _process_epoch(sample: dict[str, Any]) -> dict[str, Any]:
    """Flatten one (sample_id, epoch) record."""
    scores = sample.get("scores", {})
    scorer = scores.get("lake_build_scorer", {}) or next(iter(scores.values()), {})
    meta = scorer.get("metadata", {})
    sample_meta = sample.get("metadata", {})

    total_tokens = sum(
        u.get("total_tokens", 0) for u in sample.get("model_usage", {}).values()
    )

    return {
        "id": str(sample.get("id", "?")),
        "epoch": sample.get("epoch", 1),
        "proved": meta.get("proved", False),
        "compiles": meta.get("compiles", False),
        "score_value": scorer.get("value", 0.0),
        "sorries_original": meta.get("sorries_original", 0),
        "sorries_remaining": meta.get("sorries_remaining", 0),
        "sorries_removed": meta.get("sorries_removed", 0),
        "partial_credit": meta.get("partial_credit", 0.0),
        "difficulty_bucket": meta.get(
            "difficulty_bucket", sample_meta.get("difficulty_bucket", "unknown")
        ),
        "num_theorems": sample_meta.get("num_theorems", 0),
        "total_time": sample.get("total_time", 0.0),
        "message_count": len(sample.get("messages", [])),
        "total_tokens": total_tokens,
        "refused": _detect_refusal(sample),
    }


def _aggregate(sid: str, epochs: list[dict[str, Any]]) -> dict[str, Any]:
    """Collapse N per-epoch records for one sample_id into one aggregated
    record. Keeps the per-epoch list under `epochs`."""
    epochs_sorted = sorted(epochs, key=lambda e: e["epoch"])
    best = max(epochs_sorted, key=lambda e: (e["score_value"], e["partial_credit"]))
    n_eps = len(epochs_sorted)
    proved_count = sum(1 for e in epochs_sorted if e["proved"])
    refused_count = sum(1 for e in epochs_sorted if e.get("refused"))
    mean_partial = sum(e["partial_credit"] for e in epochs_sorted) / n_eps

    return {
        "id": sid,
        "num_epochs": n_eps,
        "epochs": epochs_sorted,
        # Best-epoch view (preserves semantics for legacy plots)
        "proved": best["proved"],
        "compiles": best["compiles"],
        "score_value": best["score_value"],
        "sorries_original": best["sorries_original"],
        "sorries_remaining": best["sorries_remaining"],
        "sorries_removed": best["sorries_removed"],
        "partial_credit": best["partial_credit"],
        "difficulty_bucket": best["difficulty_bucket"],
        "num_theorems": best["num_theorems"],
        # Aggregates
        "proved_count": proved_count,
        "any_proved": proved_count > 0,
        "all_proved": proved_count == n_eps,
        "refused_count": refused_count,
        "any_refused": refused_count > 0,
        "all_refused": refused_count == n_eps,
        "mean_partial_credit": mean_partial,
        "total_time": sum(e["total_time"] for e in epochs_sorted),
        "total_tokens": sum(e["total_tokens"] for e in epochs_sorted),
        "message_count": best["message_count"],
    }


def load_evals(data_dir: Path = DATA_DIR) -> dict[str, dict[str, Any]]:
    """Load all .eval files from `data_dir`.

    Returns {model_label: {"samples": [...], "num_epochs": k}}.
    `samples` are per-sample_id aggregates (collapsed over epochs).
    """
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(data_dir.glob("*.eval")):
        label = _label_from_path(path)
        eval_data = _load_eval(path)
        k = eval_data.get("eval", {}).get("config", {}).get("epochs", 1) or 1
        raw = eval_data.get("samples", [])
        per_epoch = [_process_epoch(s) for s in raw]
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for ep in per_epoch:
            grouped[ep["id"]].append(ep)
        samples = [_aggregate(sid, eps) for sid, eps in grouped.items()]
        result[label] = {"samples": samples, "num_epochs": k}
        print(
            f"  {label}: {len(raw)} rows → {len(samples)} samples (k={k})"
        )
    return result


# ---------------------------------------------------------------------------
# pass@k estimator (Codex paper, Chen et al. 2021)
# ---------------------------------------------------------------------------


def _pass_at_k(n: int, c: int, k: int) -> float:
    """Unbiased estimator of pass@k: 1 - C(n-c, k) / C(n, k).

    n: total attempts per problem, c: correct attempts, k: attempts considered.
    Returns 0 if k > n (requested k exceeds what we have data for).
    """
    if k > n:
        return float("nan")
    if n - c < k:
        return 1.0
    # Numerically stable form using logs
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def _pass_at_k_for_model(samples: list[dict[str, Any]], k: int) -> float:
    """Mean pass@k across all samples for a model."""
    vals = []
    for s in samples:
        n = s["num_epochs"]
        c = s["proved_count"]
        v = _pass_at_k(n, c, k)
        if not math.isnan(v):
            vals.append(v)
    return float(np.mean(vals)) if vals else float("nan")


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------


def _save(fig: plt.Figure, name: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_DIR / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


def _iter_models(
    model_data: dict[str, dict[str, Any]],
) -> list[tuple[str, list[dict[str, Any]], int]]:
    """Yield (model, samples, num_epochs) tuples in insertion order."""
    return [(m, d["samples"], d["num_epochs"]) for m, d in model_data.items()]


# ---------------------------------------------------------------------------
# Legacy plots (use best-epoch = any_proved semantics so k>1 evals work)
# ---------------------------------------------------------------------------


def plot_prove_rate(model_data: dict[str, dict[str, Any]]) -> None:
    """Grouped bar: proved-ever rate by bucket and overall, per model.

    Restricted to the n=200, pass@5 runs so the headline number reflects
    the full benchmark with multi-epoch coverage.
    """
    filtered = {m: d for m, d in model_data.items() if "n-200_k-5" in m}
    if not filtered:
        print("    skip baselines_prove_rate: no n-200_k-5 runs found")
        return
    models_list = _iter_models(filtered)
    buckets = ["easy", "hard", "overall"]
    x = np.arange(len(buckets))
    width = 0.8 / max(len(models_list), 1)

    fig, ax = plt.subplots(figsize=(8, 2.5))
    for i, ((model, samples, k), color) in enumerate(zip(models_list, _PALETTE)):
        rates = []
        for bucket in buckets:
            sub = (
                samples
                if bucket == "overall"
                else [s for s in samples if s["difficulty_bucket"] == bucket]
            )
            rates.append(
                sum(s["any_proved"] for s in sub) / len(sub) * 100 if sub else 0
            )

        label = f"{_pretty(model)}" + (f" (k={k})" if k > 1 else "")
        offset = (i - (len(models_list) - 1) / 2) * width
        bars = ax.bar(x + offset, rates, width * 0.9, label=label, color=color)
        for bar, rate in zip(bars, rates):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1,
                f"{rate:.0f}%",
                ha="center",
                va="bottom",
                fontsize=8,
            )

    ax.set_xticks(x)
    ax.set_xticklabels([b.capitalize() for b in buckets])
    ax.set_ylabel("Proved rate (%)  [pass@k]")
    ax.set_ylim(0, 100)
    ax.set_title("Proved-ever rate by difficulty (best-of-k)")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), borderaxespad=0)
    fig.tight_layout()
    _save(fig, "baselines_prove_rate")


def plot_refusal_rate(model_data: dict[str, dict[str, Any]]) -> None:
    """Grouped bar: per-epoch refusal rate by bucket and overall, per model.

    A "refusal" is an epoch whose final assistant text invokes the system
    prompt's leave-sorry-rather-than-write-incorrect-proofs clause. Per-epoch
    is the natural unit (each epoch = one independent ask).
    """
    models_list = _iter_models(model_data)
    if not models_list:
        print("    skip baselines_refusal_rate: no runs found")
        return
    buckets = ["easy", "hard", "overall"]
    x = np.arange(len(buckets))
    width = 0.8 / max(len(models_list), 1)

    fig, ax = plt.subplots(figsize=(8, 2.5))
    for i, ((model, samples, k), color) in enumerate(zip(models_list, _PALETTE)):
        rates = []
        for bucket in buckets:
            sub = (
                samples
                if bucket == "overall"
                else [s for s in samples if s["difficulty_bucket"] == bucket]
            )
            n_epochs = sum(s["num_epochs"] for s in sub)
            n_refused = sum(s["refused_count"] for s in sub)
            rates.append(n_refused / n_epochs * 100 if n_epochs else 0)

        label = f"{_pretty(model)}" + (f" (k={k})" if k > 1 else "")
        offset = (i - (len(models_list) - 1) / 2) * width
        bars = ax.bar(x + offset, rates, width * 0.9, label=label, color=color)
        for bar, rate in zip(bars, rates):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.5,
                f"{rate:.0f}%",
                ha="center",
                va="bottom",
                fontsize=8,
            )

    ax.set_xticks(x)
    ax.set_xticklabels([b.capitalize() for b in buckets])
    ax.set_ylabel("Refusal rate (%)  [per epoch]")
    ax.set_ylim(0, 100)
    ax.set_title("Refusal rate by difficulty (left sorry per system instruction)")
    ax.legend()
    fig.tight_layout()
    _save(fig, "baselines_refusal_rate")


def plot_partial_credit(model_data: dict[str, dict[str, Any]]) -> None:
    """Overlapping histograms of mean partial credit per model, by bucket."""
    models_list = _iter_models(model_data)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    for ax, bucket in zip(axes, ["easy", "hard"]):
        for (model, samples, k), color in zip(models_list, _PALETTE):
            sub = [
                s["mean_partial_credit"]
                for s in samples
                if s["difficulty_bucket"] == bucket
            ]
            if sub:
                label = f"{_pretty(model)}" + (f" (k={k})" if k > 1 else "")
                ax.hist(
                    sub,
                    bins=15,
                    alpha=0.6,
                    color=color,
                    label=label,
                    edgecolor="white",
                )
        ax.set_xlabel("Mean partial credit across epochs")
        ax.set_ylabel("Count")
        ax.set_title(f"Partial credit distribution — {bucket}")
        ax.legend()

    fig.suptitle("Partial credit (sorry removal ratio)", fontsize=13)
    fig.tight_layout()
    _save(fig, "baselines_partial_credit")


def plot_score_breakdown(model_data: dict[str, dict[str, Any]]) -> None:
    """Stacked bar: proved / compiles-only / failed per model (best-of-k)."""
    models_list = _iter_models(model_data)
    models = [m for m, _, _ in models_list]
    proved_counts, compiles_counts, failed_counts = [], [], []
    for _, samples, _ in models_list:
        n = len(samples)
        proved = sum(s["any_proved"] for s in samples)
        compiles_only = sum(
            s["compiles"] and not s["any_proved"] for s in samples
        )
        failed = n - proved - compiles_only
        proved_counts.append(proved / n * 100)
        compiles_counts.append(compiles_only / n * 100)
        failed_counts.append(failed / n * 100)

    x = np.arange(len(models))
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(x, proved_counts, color="#34d399", label="Proved")
    ax.bar(
        x,
        compiles_counts,
        bottom=proved_counts,
        color="#fbbf24",
        label="Compiles (not proved)",
    )
    bottom3 = [a + b for a, b in zip(proved_counts, compiles_counts)]
    ax.bar(x, failed_counts, bottom=bottom3, color="#f87171", label="Build failed")

    labels = [
        f"{m}" + (f"\n(k={k})" if k > 1 else "") for m, _, k in models_list
    ]
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("% of samples")
    ax.set_ylim(0, 100)
    ax.set_title("Score breakdown per model (best-of-k)")
    ax.legend(loc="upper right")
    fig.tight_layout()
    _save(fig, "baselines_score_breakdown")


def plot_time_and_tokens(model_data: dict[str, dict[str, Any]]) -> None:
    """Box plots of wall-clock time and token usage per model.

    For k>1 runs, time/tokens are summed across epochs per sample (full budget).
    """
    models_list = _iter_models(model_data)
    models = [m for m, _, _ in models_list]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))

    time_data = [[s["total_time"] for s in samples] for _, samples, _ in models_list]
    token_data = [[s["total_tokens"] for s in samples] for _, samples, _ in models_list]
    labels = [f"{m}" + (f"\n(k={k})" if k > 1 else "") for m, _, k in models_list]

    bp1 = axes[0].boxplot(time_data, labels=labels, patch_artist=True)
    for patch, color in zip(bp1["boxes"], _PALETTE):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    axes[0].set_ylabel("Wall-clock time (s)")
    axes[0].set_title("Time per sample (Σ over epochs)")
    plt.setp(axes[0].get_xticklabels(), rotation=45, ha="right")

    bp2 = axes[1].boxplot(token_data, labels=labels, patch_artist=True)
    for patch, color in zip(bp2["boxes"], _PALETTE):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    axes[1].set_ylabel("Total tokens")
    axes[1].set_title("Token usage per sample (Σ over epochs)")
    axes[1].yaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, _: f"{x / 1000:.0f}k")
    )
    plt.setp(axes[1].get_xticklabels(), rotation=45, ha="right")

    fig.suptitle("Compute cost per sample", fontsize=13)
    fig.tight_layout()
    _save(fig, "baselines_cost")


def plot_sorry_removal(model_data: dict[str, dict[str, Any]]) -> None:
    """Scatter: sorries removed vs. original, colored by proved-ever."""
    models_list = _iter_models(model_data)
    fig, axes = plt.subplots(
        1, len(models_list), figsize=(6 * len(models_list), 4), squeeze=False
    )

    for ax, (model, samples, k) in zip(axes[0], models_list):
        orig = [s["sorries_original"] for s in samples]
        removed = [s["sorries_removed"] for s in samples]
        proved = [s["any_proved"] for s in samples]

        ax.scatter(
            [o for o, p in zip(orig, proved) if not p],
            [r for r, p in zip(removed, proved) if not p],
            alpha=0.5,
            color="#7a7a7a",
            label="not proved",
            s=40,
        )
        ax.scatter(
            [o for o, p in zip(orig, proved) if p],
            [r for r, p in zip(removed, proved) if p],
            alpha=0.8,
            color="#34d399",
            label="proved (best of k)",
            s=50,
            zorder=3,
        )
        lim = max(max(orig, default=1) + 1, 2)
        ax.plot(
            [0, lim], [0, lim], ls="--", color="#c44", alpha=0.4, label="all removed"
        )
        ax.set_xlabel("Sorries original")
        ax.set_ylabel("Sorries removed (best epoch)")
        ax.set_title(f"{_pretty(model)}" + (f" (k={k})" if k > 1 else ""))
        ax.legend(fontsize=8)

    fig.suptitle("Sorry removal per sample", fontsize=13)
    fig.tight_layout()
    _save(fig, "baselines_sorry_removal")


def plot_prove_rate_by_theorems(model_data: dict[str, dict[str, Any]]) -> None:
    """Scatter: proved-ever rate vs. number of theorems per sample."""
    models_list = _iter_models(model_data)
    fig, ax = plt.subplots(figsize=(8, 4))

    for (model, samples, k), color in zip(models_list, _PALETTE):
        by_n: dict[int, list[bool]] = {}
        for s in samples:
            by_n.setdefault(s["num_theorems"], []).append(s["any_proved"])
        xs = sorted(by_n)
        ys = [sum(by_n[x]) / len(by_n[x]) * 100 for x in xs]
        sizes = [len(by_n[x]) * 20 for x in xs]
        label = f"{_pretty(model)}" + (f" (k={k})" if k > 1 else "")
        ax.scatter(xs, ys, s=sizes, color=color, alpha=0.7, label=label)

    ax.set_xlabel("Number of theorems")
    ax.set_ylabel("Proved rate (%)  [pass@k]")
    ax.set_ylim(-5, 105)
    ax.set_title("Prove rate vs. theorem count\n(bubble size = sample count)")
    ax.legend()
    fig.tight_layout()
    _save(fig, "baselines_prove_vs_theorems")


# ---------------------------------------------------------------------------
# pass@k-specific plots
# ---------------------------------------------------------------------------


def plot_pass_at_k_curve(model_data: dict[str, dict[str, Any]]) -> None:
    """pass@k as a function of k for k=1..K, per model.

    Uses the unbiased estimator from Chen et al. 2021 (Codex paper) averaged
    across all samples. This is the canonical pass@k paper figure.
    """
    models_list = [
        (m, s, k) for m, s, k in _iter_models(model_data) if k > 1 and s
    ]
    if not models_list:
        print("  skipping pass_at_k_curve (no multi-epoch evals)")
        return

    k_max = max(k for _, _, k in models_list)
    ks = list(range(1, k_max + 1))

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))

    # Overall
    ax = axes[0]
    for (model, samples, k), color in zip(models_list, _PALETTE):
        ys = [_pass_at_k_for_model(samples, ki) * 100 for ki in ks if ki <= k]
        xs_plot = [ki for ki in ks if ki <= k]
        ax.plot(
            xs_plot, ys, marker="o", color=color,
            label=f"{_pretty(model)} (n_epochs={k})", linewidth=2, markersize=7,
        )
        for ki, y in zip(xs_plot, ys):
            if ki in (1, k):
                ax.annotate(
                    f"{y:.1f}%", (ki, y),
                    textcoords="offset points", xytext=(0, 8),
                    ha="center", fontsize=8, color=color,
                )
    ax.set_xticks(ks)
    ax.set_xlabel("k (attempts)")
    ax.set_ylabel("pass@k (%)")
    ax.set_ylim(0, 100)
    ax.set_title("pass@k — all samples")
    ax.grid(True, alpha=0.3)
    ax.legend()

    # By bucket
    ax = axes[1]
    linestyles = {"easy": "-", "hard": "--"}
    for (model, samples, k), color in zip(models_list, _PALETTE):
        for bucket in ("easy", "hard"):
            sub = [s for s in samples if s["difficulty_bucket"] == bucket]
            if not sub:
                continue
            ys = [_pass_at_k_for_model(sub, ki) * 100 for ki in ks if ki <= k]
            xs_plot = [ki for ki in ks if ki <= k]
            ax.plot(
                xs_plot, ys,
                linestyle=linestyles[bucket], marker="o",
                color=color, alpha=0.9,
                label=f"{_pretty(model)} · {bucket}",
                linewidth=1.8, markersize=5,
            )
    ax.set_xticks(ks)
    ax.set_xlabel("k (attempts)")
    ax.set_ylabel("pass@k (%)")
    ax.set_ylim(0, 100)
    ax.set_title("pass@k — by difficulty")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8, ncol=2)

    fig.suptitle(
        "pass@k unbiased estimator (Chen et al. 2021)", fontsize=13
    )
    fig.tight_layout()
    _save(fig, "baselines_pass_at_k_curve")


def plot_pass_at_k_bars(model_data: dict[str, dict[str, Any]]) -> None:
    """Grouped bar: pass@1 vs pass@K per model (the headline comparison)."""
    models_list = [
        (m, s, k) for m, s, k in _iter_models(model_data) if k > 1 and s
    ]
    if not models_list:
        print("  skipping pass_at_k_bars (no multi-epoch evals)")
        return

    models = [m for m, _, _ in models_list]
    ks = [k for _, _, k in models_list]
    p1 = [_pass_at_k_for_model(s, 1) * 100 for _, s, _ in models_list]
    pk = [_pass_at_k_for_model(s, k) * 100 for _, s, k in models_list]

    x = np.arange(len(models))
    width = 0.38
    fig, ax = plt.subplots(figsize=(max(6, 1.6 * len(models) + 3), 4))
    b1 = ax.bar(x - width / 2, p1, width, label="pass@1", color="#5ba3cf")
    b2 = ax.bar(
        x + width / 2, pk, width,
        label=f"pass@k (k={ks[0] if len(set(ks)) == 1 else 'max'})",
        color="#4db88c",
    )
    for bars, vals in ((b1, p1), (b2, pk)):
        for bar, v in zip(bars, vals):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1,
                f"{v:.1f}%", ha="center", va="bottom", fontsize=9,
            )

    labels = [f"{m}\n(n={len(s)}, k={k})" for m, s, k in models_list]
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("pass@k (%)")
    ax.set_ylim(0, min(100, max(max(p1), max(pk)) * 1.15 + 10))
    ax.set_title("pass@1 vs pass@k")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    _save(fig, "baselines_pass_at_k_bars")


def plot_success_count_histogram(model_data: dict[str, dict[str, Any]]) -> None:
    """Histogram of per-sample success count c (0..k) per model.

    Shows the "shape" of consistency: samples piled at c=0 or c=k indicate
    deterministic easy/hard; a spread distribution indicates stochastic
    problems where more samples would help.
    """
    models_list = [
        (m, s, k) for m, s, k in _iter_models(model_data) if k > 1 and s
    ]
    if not models_list:
        print("  skipping success_count_histogram (no multi-epoch evals)")
        return

    fig, axes = plt.subplots(
        1, len(models_list),
        figsize=(4.5 * len(models_list), 4),
        squeeze=False, sharey=True,
    )

    for ax, (model, samples, k) in zip(axes[0], models_list):
        counts_easy = [
            s["proved_count"] for s in samples if s["difficulty_bucket"] == "easy"
        ]
        counts_hard = [
            s["proved_count"] for s in samples if s["difficulty_bucket"] == "hard"
        ]
        bins = np.arange(-0.5, k + 1.5, 1)
        ax.hist(
            [counts_easy, counts_hard], bins=bins,
            label=["easy", "hard"], color=["#4db88c", "#e07b54"],
            alpha=0.85, edgecolor="white",
        )
        ax.set_xticks(range(k + 1))
        ax.set_xlabel(f"# epochs proved (0..{k})")
        ax.set_title(f"{_pretty(model)} (k={k})")
        ax.legend()

    axes[0][0].set_ylabel("# samples")
    fig.suptitle(
        "Per-sample success count distribution\n"
        "(c = number of epochs that fully proved a given sample)",
        fontsize=12,
    )
    fig.tight_layout()
    _save(fig, "baselines_success_count_hist")


def plot_coverage_vs_k(model_data: dict[str, dict[str, Any]]) -> None:
    """Fraction of samples with at least one success within the first k
    attempts, using the unbiased estimator. Parallel to the pass@k curve but
    emphasizes coverage gained per additional attempt.
    """
    models_list = [
        (m, s, k) for m, s, k in _iter_models(model_data) if k > 1 and s
    ]
    if not models_list:
        print("  skipping coverage_vs_k (no multi-epoch evals)")
        return

    fig, ax = plt.subplots(figsize=(8, 4.5))
    k_max = max(k for _, _, k in models_list)
    for (model, samples, k), color in zip(models_list, _PALETTE):
        ks = list(range(1, k + 1))
        # pass@k already is coverage when scored 0/1
        ys = [_pass_at_k_for_model(samples, ki) * 100 for ki in ks]
        ax.plot(
            ks, ys, marker="o", color=color,
            label=f"{_pretty(model)} (k={k})", linewidth=2,
        )
        # Marginal gain annotation
        if k >= 2:
            gain = ys[-1] - ys[0]
            ax.annotate(
                f"+{gain:.1f}% from k=1→{k}",
                xy=(k, ys[-1]),
                xytext=(10, -10),
                textcoords="offset points",
                fontsize=8, color=color,
                arrowprops=dict(arrowstyle="-", color=color, alpha=0.5),
            )

    ax.set_xticks(range(1, k_max + 1))
    ax.set_xlabel("Attempts budget k")
    ax.set_ylabel("Coverage — fraction proved (%)")
    ax.set_ylim(0, 100)
    ax.set_title("Coverage gained by additional attempts")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    _save(fig, "baselines_coverage_vs_k")


def plot_sample_success_heatmap(model_data: dict[str, dict[str, Any]]) -> None:
    """Per-sample, per-epoch binary success heatmap (one row per model).

    Samples are sorted by proved_count descending — highlights which samples
    are deterministically easy vs. stochastic vs. deterministically hard.
    """
    models_list = [
        (m, s, k) for m, s, k in _iter_models(model_data) if k > 1 and s
    ]
    if not models_list:
        print("  skipping sample_success_heatmap (no multi-epoch evals)")
        return

    fig, axes = plt.subplots(
        len(models_list), 1,
        figsize=(12, 2.2 * len(models_list) + 1),
        squeeze=False,
    )

    for ax, (model, samples, k) in zip(axes[:, 0], models_list):
        samples_sorted = sorted(
            samples,
            key=lambda s: (
                -s["proved_count"],
                0 if s["difficulty_bucket"] == "easy" else 1,
                s["id"],
            ),
        )
        matrix = np.zeros((k, len(samples_sorted)))
        for j, s in enumerate(samples_sorted):
            for e in s["epochs"]:
                matrix[e["epoch"] - 1, j] = 1 if e["proved"] else 0

        ax.imshow(
            matrix, aspect="auto",
            cmap="Greens", interpolation="nearest",
            vmin=0, vmax=1,
        )
        ax.set_yticks(range(k))
        ax.set_yticklabels([f"ep{i + 1}" for i in range(k)])
        ax.set_xlabel("samples (sorted by proved_count ↓)")
        ax.set_title(
            f"{_pretty(model)} — proved: "
            f"{sum(s['any_proved'] for s in samples)}/{len(samples)} "
            f"(pass@{k}), consistent: "
            f"{sum(s['all_proved'] for s in samples)}/{len(samples)}"
        )
        # Mark bucket boundary
        n_easy = sum(1 for s in samples_sorted if s["difficulty_bucket"] == "easy")
        ax.axvline(n_easy - 0.5, color="#c44", linestyle=":", linewidth=1, alpha=0.6)

    fig.suptitle(
        "Per-sample success matrix — green = proved in that epoch",
        fontsize=12,
    )
    fig.tight_layout()
    _save(fig, "baselines_sample_success_heatmap")


def plot_pass_at_k_vs_compute(model_data: dict[str, dict[str, Any]]) -> None:
    """pass@k vs total token budget spent. Answers: does pass@k buy you
    success per token, compared to just using more tokens in one attempt?
    """
    models_list = [
        (m, s, k) for m, s, k in _iter_models(model_data) if k > 1 and s
    ]
    if not models_list:
        print("  skipping pass_at_k_vs_compute (no multi-epoch evals)")
        return

    fig, ax = plt.subplots(figsize=(8, 4.5))
    for (model, samples, k), color in zip(models_list, _PALETTE):
        mean_tokens_per_epoch = (
            sum(s["total_tokens"] for s in samples) / (len(samples) * k)
        )
        ks = list(range(1, k + 1))
        xs = [mean_tokens_per_epoch * ki / 1000 for ki in ks]
        ys = [_pass_at_k_for_model(samples, ki) * 100 for ki in ks]
        ax.plot(
            xs, ys, marker="o", color=color, linewidth=2,
            label=f"{_pretty(model)} (k={k})",
        )
        for ki, x, y in zip(ks, xs, ys):
            if ki in (1, k):
                ax.annotate(
                    f"k={ki}\n{y:.1f}%",
                    xy=(x, y), textcoords="offset points",
                    xytext=(6, -4), fontsize=7, color=color,
                )

    ax.set_xlabel("Mean tokens per sample (k × per-attempt avg) [×10³]")
    ax.set_ylabel("pass@k (%)")
    ax.set_title("pass@k vs compute budget")
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    _save(fig, "baselines_pass_at_k_vs_compute")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    sns.set_theme(style="whitegrid", font_scale=0.95)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading .eval files from data/...")
    model_data = load_evals()
    if not model_data:
        print("No .eval files found in data/. Exiting.")
        return
    total = sum(len(d["samples"]) for d in model_data.values())
    multi = sum(1 for d in model_data.values() if d["num_epochs"] > 1)
    print(
        f"  {len(model_data)} models, {total} samples total, "
        f"{multi} multi-epoch (pass@k) run(s)"
    )

    plots = [
        ("baselines_prove_rate", lambda: plot_prove_rate(model_data)),
        ("baselines_refusal_rate", lambda: plot_refusal_rate(model_data)),
        ("baselines_partial_credit", lambda: plot_partial_credit(model_data)),
        ("baselines_score_breakdown", lambda: plot_score_breakdown(model_data)),
        ("baselines_cost", lambda: plot_time_and_tokens(model_data)),
        ("baselines_sorry_removal", lambda: plot_sorry_removal(model_data)),
        ("baselines_prove_vs_theorems", lambda: plot_prove_rate_by_theorems(model_data)),
        # pass@k paper-style figures
        ("baselines_pass_at_k_bars", lambda: plot_pass_at_k_bars(model_data)),
        ("baselines_pass_at_k_curve", lambda: plot_pass_at_k_curve(model_data)),
        ("baselines_coverage_vs_k", lambda: plot_coverage_vs_k(model_data)),
        ("baselines_success_count_hist", lambda: plot_success_count_histogram(model_data)),
        ("baselines_sample_success_heatmap", lambda: plot_sample_success_heatmap(model_data)),
        ("baselines_pass_at_k_vs_compute", lambda: plot_pass_at_k_vs_compute(model_data)),
    ]

    for name, fn in plots:
        print(f"  Plotting {name}...")
        fn()

    print(f"Done. {len(plots)} figures saved to {OUT_DIR}/")


if __name__ == "__main__":
    main()
