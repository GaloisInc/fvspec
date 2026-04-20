"""Baseline evaluation charts from inspect_ai .eval files.

Reads all .eval symlinks from comms/graphs/data/ and produces per-model,
per-bucket comparison plots for the fvspec baselines evaluation.

Usage:
    uv run graphs baselines           # via the main entrypoint
    python -m graphs.baselines        # direct invocation
"""

from __future__ import annotations

import json
import zipfile
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


def _label_from_path(path: Path) -> str:
    """Extract the short model label from a symlink filename like snt46_n-20_20260420."""
    return path.stem.split("_n-")[0]


def _load_eval(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        hf = "_journal/start.json" if "_journal/start.json" in names else "header.json"
        header = json.loads(zf.read(hf))
        samples = [
            json.loads(zf.read(n))
            for n in sorted(names)
            if n.startswith("samples/") and n.endswith(".json")
        ]
        header["samples"] = samples
    return header


def _process_sample(sample: dict[str, Any]) -> dict[str, Any]:
    scores = sample.get("scores", {})
    scorer = scores.get("lake_build_scorer", {}) or next(iter(scores.values()), {})
    meta = scorer.get("metadata", {})
    sample_meta = sample.get("metadata", {})

    total_tokens = sum(
        u.get("total_tokens", 0) for u in sample.get("model_usage", {}).values()
    )

    return {
        "id": sample.get("id", "?"),
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
    }


def load_evals(data_dir: Path = DATA_DIR) -> dict[str, list[dict[str, Any]]]:
    """Load all .eval files from data_dir; returns {model_label: [samples]}."""
    result: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(data_dir.glob("*.eval")):
        label = _label_from_path(path)
        eval_data = _load_eval(path)
        result[label] = [_process_sample(s) for s in eval_data.get("samples", [])]
        print(f"  {label}: {len(result[label])} samples loaded")
    return result


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------


def _save(fig: plt.Figure, name: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_DIR / f"{name}.png", dpi=200, bbox_inches="tight")
    fig.savefig(OUT_DIR / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------


def plot_prove_rate(model_samples: dict[str, list[dict[str, Any]]]) -> None:
    """Grouped bar: prove rate by bucket and overall, one group per bucket."""
    models = list(model_samples.keys())
    buckets = ["easy", "hard", "overall"]
    x = np.arange(len(buckets))
    width = 0.8 / len(models)

    fig, ax = plt.subplots(figsize=(8, 4))
    for i, (model, color) in enumerate(zip(models, _PALETTE)):
        samples = model_samples[model]
        rates = []
        for bucket in buckets:
            if bucket == "overall":
                sub = samples
            else:
                sub = [s for s in samples if s["difficulty_bucket"] == bucket]
            rates.append(sum(s["proved"] for s in sub) / len(sub) * 100 if sub else 0)

        offset = (i - (len(models) - 1) / 2) * width
        bars = ax.bar(x + offset, rates, width * 0.9, label=model, color=color)
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
    ax.set_ylabel("Prove rate (%)")
    ax.set_ylim(0, 100)
    ax.set_title("Prove rate by difficulty bucket")
    ax.legend()
    fig.tight_layout()
    _save(fig, "baselines_prove_rate")


def plot_partial_credit(model_samples: dict[str, list[dict[str, Any]]]) -> None:
    """Overlapping histograms of partial credit per model."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    for ax, bucket in zip(axes, ["easy", "hard"]):
        for model, color in zip(model_samples, _PALETTE):
            sub = [
                s["partial_credit"]
                for s in model_samples[model]
                if s["difficulty_bucket"] == bucket
            ]
            if sub:
                ax.hist(
                    sub, bins=15, alpha=0.6, color=color, label=model, edgecolor="white"
                )
        ax.set_xlabel("Partial credit")
        ax.set_ylabel("Count")
        ax.set_title(f"Partial credit distribution — {bucket}")
        ax.legend()

    fig.suptitle("Partial credit (sorry removal ratio)", fontsize=13)
    fig.tight_layout()
    _save(fig, "baselines_partial_credit")


def plot_score_breakdown(model_samples: dict[str, list[dict[str, Any]]]) -> None:
    """Stacked bar: proved / compiles-only / failed per model."""
    models = list(model_samples.keys())
    proved_counts, compiles_counts, failed_counts = [], [], []
    for model in models:
        samples = model_samples[model]
        n = len(samples)
        proved = sum(s["proved"] for s in samples)
        compiles_only = sum(s["compiles"] and not s["proved"] for s in samples)
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

    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.set_ylabel("% of samples")
    ax.set_ylim(0, 100)
    ax.set_title("Score breakdown per model")
    ax.legend(loc="upper right")
    fig.tight_layout()
    _save(fig, "baselines_score_breakdown")


def plot_time_and_tokens(model_samples: dict[str, list[dict[str, Any]]]) -> None:
    """Box plots of wall-clock time and token usage per model."""
    models = list(model_samples.keys())
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))

    time_data = [[s["total_time"] for s in model_samples[m]] for m in models]
    token_data = [[s["total_tokens"] for s in model_samples[m]] for m in models]

    bp1 = axes[0].boxplot(time_data, labels=models, patch_artist=True)
    for patch, color in zip(bp1["boxes"], _PALETTE):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    axes[0].set_ylabel("Wall-clock time (s)")
    axes[0].set_title("Time per sample")

    bp2 = axes[1].boxplot(token_data, labels=models, patch_artist=True)
    for patch, color in zip(bp2["boxes"], _PALETTE):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    axes[1].set_ylabel("Total tokens")
    axes[1].set_title("Token usage per sample")
    axes[1].yaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, _: f"{x / 1000:.0f}k")
    )

    fig.suptitle("Compute cost per sample", fontsize=13)
    fig.tight_layout()
    _save(fig, "baselines_cost")


def plot_sorry_removal(model_samples: dict[str, list[dict[str, Any]]]) -> None:
    """Scatter: sorries removed vs. original, colored by proved."""
    models = list(model_samples.keys())
    fig, axes = plt.subplots(
        1, len(models), figsize=(6 * len(models), 4), squeeze=False
    )

    for ax, model in zip(axes[0], models):
        samples = model_samples[model]
        orig = [s["sorries_original"] for s in samples]
        removed = [s["sorries_removed"] for s in samples]
        proved = [s["proved"] for s in samples]

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
            label="proved",
            s=50,
            zorder=3,
        )
        lim = max(max(orig, default=1) + 1, 2)
        ax.plot(
            [0, lim], [0, lim], ls="--", color="#c44", alpha=0.4, label="all removed"
        )
        ax.set_xlabel("Sorries original")
        ax.set_ylabel("Sorries removed")
        ax.set_title(model)
        ax.legend(fontsize=8)

    fig.suptitle("Sorry removal per sample", fontsize=13)
    fig.tight_layout()
    _save(fig, "baselines_sorry_removal")


def plot_prove_rate_by_theorems(model_samples: dict[str, list[dict[str, Any]]]) -> None:
    """Scatter: prove rate vs. number of theorems per sample."""
    fig, ax = plt.subplots(figsize=(8, 4))

    for model, color in zip(model_samples, _PALETTE):
        samples = model_samples[model]
        by_n: dict[int, list[bool]] = {}
        for s in samples:
            by_n.setdefault(s["num_theorems"], []).append(s["proved"])
        xs = sorted(by_n)
        ys = [sum(by_n[x]) / len(by_n[x]) * 100 for x in xs]
        sizes = [len(by_n[x]) * 20 for x in xs]
        ax.scatter(xs, ys, s=sizes, color=color, alpha=0.7, label=model)

    ax.set_xlabel("Number of theorems")
    ax.set_ylabel("Prove rate (%)")
    ax.set_ylim(-5, 105)
    ax.set_title("Prove rate vs. theorem count\n(bubble size = sample count)")
    ax.legend()
    fig.tight_layout()
    _save(fig, "baselines_prove_vs_theorems")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    sns.set_theme(style="whitegrid", font_scale=0.95)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading .eval files from data/...")
    model_samples = load_evals()
    if not model_samples:
        print("No .eval files found in data/. Exiting.")
        return
    total = sum(len(v) for v in model_samples.values())
    print(f"  {len(model_samples)} models, {total} samples total")

    plots = [
        ("baselines_prove_rate", lambda: plot_prove_rate(model_samples)),
        ("baselines_partial_credit", lambda: plot_partial_credit(model_samples)),
        ("baselines_score_breakdown", lambda: plot_score_breakdown(model_samples)),
        ("baselines_cost", lambda: plot_time_and_tokens(model_samples)),
        ("baselines_sorry_removal", lambda: plot_sorry_removal(model_samples)),
        (
            "baselines_prove_vs_theorems",
            lambda: plot_prove_rate_by_theorems(model_samples),
        ),
    ]

    for name, fn in plots:
        print(f"  Plotting {name}...")
        fn()

    print(f"Done. {len(plots)} figures saved to {OUT_DIR}/")


if __name__ == "__main__":
    main()
