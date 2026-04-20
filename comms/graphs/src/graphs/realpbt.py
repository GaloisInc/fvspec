"""Dataset characterization and comparison analysis for the RealPBT dataset.

Loads from comms/graphs/data/realpbt2.jsonl (local) and computes:
  - Repository distribution (PBTs per repo, stars, forks)
  - License breakdown
  - PBT complexity metrics
  - Comparison table vs. Liam DeVoe's Hypothesis Corpus (hypothesis.works/articles/hypothesis-corpus/)

Outputs figures to comms/graphs/out/ and prints a LaTeX comparison table.

Usage:
    uv run graphs realpbt           # via the main entrypoint
    python -m graphs.realpbt        # direct invocation
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

OUT_DIR = Path(__file__).resolve().parents[2] / "out"
_PBTS_PATH = Path(__file__).resolve().parents[2] / "data" / "realpbt2.jsonl"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def _load_local_pbts() -> list[dict]:
    """Load PBTs from the local artifacts directory."""
    if not _PBTS_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found at {_PBTS_PATH}. "
            "Run 'uv run realpbt-pipeline' from benchmark/ first."
        )
    rows = []
    with open(_PBTS_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _build_dataframes(rows: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build per-PBT and per-repo DataFrames."""
    pbt_records = []
    for r in rows:
        m = r.get("metrics") or {}
        pbt_records.append(
            {
                "id": r["id"],
                "name": r["name"],
                "repo": r["repo"]["name"],
                "stars": r["repo"]["stars"] or 0,
                "forks": r["repo"]["forks"] or 0,
                "license": r["repo"].get("license") or "unknown",
                "loc": m.get("loc"),
                "sloc": m.get("sloc"),
                "avg_complexity": m.get("avg_complexity"),
                "maintainability_index": m.get("maintainability_index"),
                "halstead_effort": m.get("halstead_effort"),
            }
        )

    pbt_df = pd.DataFrame(pbt_records)

    # Per-repo aggregation
    repo_df = (
        pbt_df.groupby("repo")
        .agg(
            pbt_count=("id", "count"),
            stars=("stars", "first"),
            forks=("forks", "first"),
            license=("license", "first"),
        )
        .reset_index()
    )
    return pbt_df, repo_df


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------


def _save(fig: plt.Figure, name: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_DIR / f"{name}.png", dpi=200, bbox_inches="tight")
    fig.savefig(OUT_DIR / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


def plot_pbts_per_repo(repo_df: pd.DataFrame) -> None:
    """Histogram of PBT count per repository."""
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))

    # Full distribution (log scale y)
    axes[0].hist(repo_df["pbt_count"], bins=50, color="#5ba3cf", edgecolor="white")
    axes[0].set_yscale("log")
    axes[0].set_xlabel("PBTs per repository")
    axes[0].set_ylabel("Number of repositories (log scale)")
    axes[0].set_title("PBT count per repository (all repos)")

    # Zoom: repos with <= 50 PBTs (majority)
    small = repo_df[repo_df["pbt_count"] <= 50]["pbt_count"]
    axes[1].hist(small, bins=range(1, 52), color="#5ba3cf", edgecolor="white")
    axes[1].set_xlabel("PBTs per repository")
    axes[1].set_ylabel("Number of repositories")
    axes[1].set_title("PBT count per repository (≤50 PBTs shown)")
    axes[1].axvline(
        repo_df["pbt_count"].median(),
        color="#c44",
        ls="--",
        label=f"median={repo_df['pbt_count'].median():.0f}",
    )
    axes[1].legend()

    n_repos = len(repo_df)
    n_pbts = repo_df["pbt_count"].sum()
    fig.suptitle(
        f"Repository distribution: {n_repos:,} repos, {n_pbts:,} PBTs total",
        fontsize=13,
    )
    fig.tight_layout()
    _save(fig, "realpbt_pbts_per_repo")


def plot_stars_forks(repo_df: pd.DataFrame) -> None:
    """Stars and forks distributions."""
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))

    nonzero_stars = repo_df[repo_df["stars"] > 0]["stars"]
    if len(nonzero_stars) > 0:
        axes[0].hist(
            np.log10(nonzero_stars + 1),
            bins=30,
            color="#5ba3cf",
            edgecolor="white",
        )
        axes[0].set_xlabel("log10(stars + 1)")
    else:
        axes[0].text(
            0.5, 0.5, "No repos with stars", ha="center", transform=axes[0].transAxes
        )
    axes[0].set_ylabel("Number of repositories")
    axes[0].set_title(
        f"Stars distribution\n({sum(repo_df['stars'] == 0):,} repos with 0 stars omitted)"
    )

    nonzero_forks = repo_df[repo_df["forks"] > 0]["forks"]
    if len(nonzero_forks) > 0:
        axes[1].hist(
            np.log10(nonzero_forks + 1),
            bins=30,
            color="#e07b54",
            edgecolor="white",
        )
        axes[1].set_xlabel("log10(forks + 1)")
    else:
        axes[1].text(
            0.5, 0.5, "No repos with forks", ha="center", transform=axes[1].transAxes
        )
    axes[1].set_ylabel("Number of repositories")
    axes[1].set_title(
        f"Forks distribution\n({sum(repo_df['forks'] == 0):,} repos with 0 forks omitted)"
    )

    fig.suptitle("Repository popularity (stars and forks)", fontsize=13)
    fig.tight_layout()
    _save(fig, "realpbt_stars_forks")


def plot_license_breakdown(repo_df: pd.DataFrame) -> None:
    """Bar chart of license distribution across repos."""
    counts = repo_df["license"].value_counts().head(10)
    fig, ax = plt.subplots(figsize=(9, 4))
    bars = ax.barh(counts.index[::-1], counts.values[::-1], color="#5ba3cf")
    ax.set_xlabel("Number of repositories")
    ax.set_title(f"License distribution (top 10, {len(repo_df):,} repos total)")
    for bar, val in zip(bars, counts.values[::-1]):
        ax.text(
            val + 0.3,
            bar.get_y() + bar.get_height() / 2,
            str(val),
            va="center",
            fontsize=8,
        )
    fig.tight_layout()
    _save(fig, "realpbt_licenses")


def plot_pbt_complexity(pbt_df: pd.DataFrame) -> None:
    """PBT code complexity metrics."""
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))

    loc_data = pbt_df["loc"].dropna()
    axes[0].hist(loc_data.clip(upper=80), bins=40, color="#5ba3cf", edgecolor="white")
    axes[0].axvline(
        loc_data.median(),
        color="#c44",
        ls="--",
        label=f"median={loc_data.median():.0f}",
    )
    axes[0].set_xlabel("Lines of code (clipped at 80)")
    axes[0].set_ylabel("Count")
    axes[0].set_title("PBT size (LOC)")
    axes[0].legend()

    cc_data = pbt_df["avg_complexity"].dropna()
    axes[1].hist(cc_data.clip(upper=15), bins=30, color="#e07b54", edgecolor="white")
    axes[1].axvline(
        cc_data.median(), color="#c44", ls="--", label=f"median={cc_data.median():.1f}"
    )
    axes[1].set_xlabel("Avg cyclomatic complexity (clipped at 15)")
    axes[1].set_ylabel("Count")
    axes[1].set_title("Cyclomatic complexity")
    axes[1].legend()

    mi_data = pbt_df["maintainability_index"].dropna()
    axes[2].hist(mi_data, bins=30, color="#7a7a7a", edgecolor="white")
    axes[2].axvline(
        mi_data.median(), color="#c44", ls="--", label=f"median={mi_data.median():.0f}"
    )
    axes[2].set_xlabel("Maintainability index")
    axes[2].set_ylabel("Count")
    axes[2].set_title("Python maintainability index")
    axes[2].legend()

    fig.suptitle(f"PBT complexity metrics (n={len(pbt_df):,})", fontsize=13)
    fig.tight_layout()
    _save(fig, "realpbt_complexity")


def print_comparison_table() -> None:
    """Print a LaTeX table comparing our dataset to Liam's hypothesis-corpus."""
    # Our dataset statistics (from pbts.jsonl + HF Benchify/realpbt)
    our_pre_dedup = 54_345  # Benchify/realpbt HuggingFace total
    # realpbt2/pbts.jsonl is post-dedup
    rows = _load_local_pbts()
    _, repo_df = _build_dataframes(rows)
    our_post_dedup = len(rows)
    our_repos = len(repo_df)

    print("% --- LaTeX comparison table ---")
    print(r"\begin{table}[t]")
    print(r"  \centering")
    print(
        r"  \caption{Comparison of \FVSpec's RealPBT corpus with the Hypothesis Corpus~\cite{devoe2026hypothesis}.}"
    )
    print(r"  \label{tab:dataset-comparison}")
    print(r"  \begin{tabular}{lrr}")
    print(r"    \toprule")
    print(r"    & \textbf{Ours (RealPBT)} & \textbf{Hypothesis Corpus} \\")
    print(r"    \midrule")
    print(f"    PBTs (pre-dedup)  & {our_pre_dedup:,} & 28,928 \\\\")
    print(f"    PBTs (post-dedup) & {our_post_dedup:,} & n/a \\\\")
    print(f"    Repositories (post-dedup) & {our_repos:,} & 1,529 \\\\")
    print(r"    \midrule")
    print(r"    Dependency source code & \checkmark & \texttimes \\")
    print(r"    Radon code metrics      & \checkmark & \texttimes \\")
    print(r"    NL summary              & \checkmark & \texttimes \\")
    print(r"    @settings configuration & \texttimes & \checkmark \\")
    print(r"    Runtime/entropy info    & \texttimes & \checkmark \\")
    print(r"    Line coverage           & \texttimes & \checkmark \\")
    print(r"    Filter: permissive license only & \checkmark & \texttimes \\")
    print(r"    \midrule")
    print(
        r"    Repo overlap            & \multicolumn{2}{c}{not computed (corpus gated)} \\"
    )
    print(r"    \bottomrule")
    print(r"  \end{tabular}")
    print(r"\end{table}")


def main() -> None:
    """Run all RealPBT dataset analysis plots."""
    sns.set_theme(style="whitegrid", font_scale=0.95)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading RealPBT dataset from local artifacts...")
    rows = _load_local_pbts()
    print(f"  {len(rows):,} PBTs loaded")

    pbt_df, repo_df = _build_dataframes(rows)
    print(f"  {len(repo_df):,} unique repositories")

    plots = [
        ("realpbt_pbts_per_repo", lambda: plot_pbts_per_repo(repo_df)),
        ("realpbt_stars_forks", lambda: plot_stars_forks(repo_df)),
        ("realpbt_licenses", lambda: plot_license_breakdown(repo_df)),
        ("realpbt_complexity", lambda: plot_pbt_complexity(pbt_df)),
    ]

    for name, fn in plots:
        print(f"  Plotting {name}...")
        fn()

    print(f"Done. {len(plots)} figures saved to {OUT_DIR}/")
    print()
    print_comparison_table()


if __name__ == "__main__":
    main()
