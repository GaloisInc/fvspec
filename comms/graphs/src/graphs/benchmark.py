"""FVSpec benchmark dataset characterization plots.

Loads the quinn-dougherty/fvspec HuggingFace dataset and produces figures
covering difficulty distribution, structural faithfulness, Lean output
complexity, Python source metrics, pipeline cost, and cross-cutting views.

Also calls graphs.realpbt for the upstream RealPBT corpus characterization.

Usage:
    uv run graphs benchmark           # via the main entrypoint
    python -m graphs.benchmark        # direct invocation
"""

from __future__ import annotations

from pathlib import Path

from datasets import load_dataset
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd
import seaborn as sns

HF_REPO = "quinn-dougherty/fvspec"
OUT_DIR = Path(__file__).resolve().parents[2] / "out"

SF_KEYS = [
    "parameter_coverage",
    "type_correspondence",
    "strategy_coverage",
    "assertion_coverage",
    "dependency_coverage",
    "overall",
]


def _flatten(d: dict) -> dict:
    sf = d.get("structural_faithfulness") or {}
    lm = d.get("lean_metrics") or {}
    spec_s = lm.get("spec_structure") or {}
    spec_c = lm.get("spec_complexity") or {}
    radon = d.get("realpbt_radon") or {}
    tc = d.get("turn_counts") or {}

    flat: dict = {
        "sample_id": d["sample_id"],
        "difficulty": d["difficulty_binary"],
        "difficulty_confidence": d["difficulty_binary_confidence"],
        "implementation_level": d["implementation_level"],
        "num_theorems": d["num_theorems"],
        "actually_invokes_given": d["actually_invokes_given"],
        "impl_autoform_success": d["impl_autoform_success"],
        "realpbt_lines_pbt": d["realpbt_lines_pbt"],
        "time": d["time"],
        "token_usage": d["token_usage"],
        "total_lean_lines": lm.get("total_lean_lines", 0),
        "total_sorries": lm.get("total_sorries", 0),
        "total_axioms": lm.get("total_axioms", 0),
        "spec_theorems": spec_s.get("num_theorems", 0),
        "spec_defs": spec_s.get("num_defs", 0),
        "spec_halstead_volume": spec_c.get("halstead_volume", 0),
        "spec_halstead_difficulty": spec_c.get("halstead_difficulty", 0),
        "py_complexity": radon.get("avg_complexity"),
        "py_maintainability": radon.get("maintainability_index"),
        "py_loc": radon.get("loc"),
        "total_turns": tc.get("total_turns", 0),
        "total_tool_calls": tc.get("total_tool_calls", 0),
    }
    for k in SF_KEYS:
        flat[f"sf_{k}"] = sf.get(k)
    return flat


def load() -> pd.DataFrame:
    try:
        ds = load_dataset(HF_REPO, split="train")
    except Exception as e:
        print(f"  HF load failed ({e.__class__.__name__}), trying local symlink...")
        local = Path(__file__).resolve().parents[2] / "data" / "fvspec.jsonl"
        ds = load_dataset("json", data_files=str(local.resolve()), split="train")
    print(f"  {len(ds)} samples loaded")
    return pd.DataFrame([_flatten(row) for row in ds])


def _save(fig: plt.Figure, name: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_DIR / f"{name}.png", dpi=200, bbox_inches="tight")
    fig.savefig(OUT_DIR / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


def plot_difficulty_distribution(df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), width_ratios=[1, 1.4])

    counts = df["difficulty"].value_counts()
    colors = {"easy": "#5ba3cf", "hard": "#e07b54"}
    axes[0].bar(counts.index, counts.values, color=[colors[x] for x in counts.index])
    axes[0].set_ylabel("Count")
    axes[0].set_title("Difficulty: easy vs. hard")
    for i, val in enumerate(counts.values):
        axes[0].text(i, val + 50, str(val), ha="center", fontsize=9)

    axes[1].hist(
        df["difficulty_confidence"], bins=20, color="#7a7a7a", edgecolor="white"
    )
    axes[1].set_xlabel("Grader confidence")
    axes[1].set_ylabel("Count")
    axes[1].set_title("Difficulty grader confidence distribution")

    fig.suptitle("Difficulty distribution (n={:,})".format(len(df)), fontsize=13)
    fig.tight_layout()
    _save(fig, "difficulty_distribution")


def plot_structural_faithfulness(df: pd.DataFrame) -> None:
    sf_cols = [c for c in df.columns if c.startswith("sf_")]
    nice = [c.replace("sf_", "").replace("_", " ").title() for c in sf_cols]

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))

    axes[0].hist(df["sf_overall"].dropna(), bins=30, color="#5ba3cf", edgecolor="white")
    axes[0].set_xlabel("Overall faithfulness score")
    axes[0].set_ylabel("Count")
    axes[0].set_title("Structural faithfulness: overall")
    axes[0].axvline(
        df["sf_overall"].median(),
        color="#c44",
        ls="--",
        label=f"median={df['sf_overall'].median():.2f}",
    )
    axes[0].legend()

    sub_means = [df[c].mean() for c in sf_cols]
    bars = axes[1].barh(nice, sub_means, color="#5ba3cf")
    axes[1].set_xlim(0, 1)
    axes[1].set_xlabel("Mean score")
    axes[1].set_title("Faithfulness sub-scores (mean)")
    for bar, val in zip(bars, sub_means):
        axes[1].text(
            val + 0.01,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.2f}",
            va="center",
            fontsize=8,
        )

    fig.suptitle("Structural faithfulness", fontsize=13)
    fig.tight_layout()
    _save(fig, "structural_faithfulness")


def _tail_note(series: pd.Series, clip: int) -> str:
    """Return '(N values above X not shown; max=M)' for annotating clip axes."""
    n = int((series > clip).sum())
    if n == 0:
        return ""
    m = int(series.max())
    return f"({n:,} values >{clip} not shown; max={m:,})"


def plot_lean_complexity(df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))

    clip_lines = 500
    axes[0].hist(
        df["total_lean_lines"][df["total_lean_lines"] <= clip_lines],
        bins=40,
        color="#5ba3cf",
        edgecolor="white",
    )
    axes[0].set_xlabel(f"Total Lean lines  {_tail_note(df['total_lean_lines'], clip_lines)}")
    axes[0].set_ylabel("Count")
    axes[0].set_title("Lean output size")

    clip_thm = 20
    axes[1].hist(
        df["num_theorems"][df["num_theorems"] <= clip_thm],
        bins=range(0, clip_thm + 2),
        color="#e07b54",
        edgecolor="white",
    )
    axes[1].set_xlabel(f"Theorems per sample  {_tail_note(df['num_theorems'], clip_thm)}")
    axes[1].set_ylabel("Count")
    axes[1].set_title("Theorems per sample")

    clip_sorry = 20
    axes[2].hist(
        df["total_sorries"][df["total_sorries"] <= clip_sorry],
        bins=range(0, clip_sorry + 2),
        color="#7a7a7a",
        edgecolor="white",
    )
    axes[2].set_xlabel(f"sorry count per sample  {_tail_note(df['total_sorries'], clip_sorry)}")
    axes[2].set_ylabel("Count")
    axes[2].set_title("Sorry placeholders per sample")

    fig.suptitle("Lean output complexity", fontsize=13)
    fig.tight_layout()
    _save(fig, "lean_complexity")


def plot_python_source(df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))

    axes[0].hist(
        df["realpbt_lines_pbt"].clip(upper=100),
        bins=40,
        color="#5ba3cf",
        edgecolor="white",
    )
    axes[0].set_xlabel("Lines of PBT code (clipped at 100)")
    axes[0].set_ylabel("Count")
    axes[0].set_title("Source PBT size")

    cc = df["py_complexity"].dropna()
    axes[1].hist(cc.clip(upper=15), bins=30, color="#e07b54", edgecolor="white")
    axes[1].set_xlabel("Avg cyclomatic complexity")
    axes[1].set_ylabel("Count")
    axes[1].set_title("Python source complexity")

    mi = df["py_maintainability"].dropna()
    axes[2].hist(mi, bins=30, color="#7a7a7a", edgecolor="white")
    axes[2].set_xlabel("Maintainability index")
    axes[2].set_ylabel("Count")
    axes[2].set_title("Python maintainability index")

    fig.suptitle("Python source characteristics", fontsize=13)
    fig.tight_layout()
    _save(fig, "python_source")


def plot_pipeline_cost(df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))

    clip_time = 2000
    axes[0].hist(
        df["time"][df["time"] <= clip_time], bins=40, color="#5ba3cf", edgecolor="white"
    )
    axes[0].set_xlabel(f"Wall-clock time (s)  {_tail_note(df['time'], clip_time)}")
    axes[0].set_ylabel("Count")
    axes[0].set_title("Pipeline time per sample")

    clip_tok = 500_000
    axes[1].hist(
        df["token_usage"][df["token_usage"] <= clip_tok],
        bins=40,
        color="#e07b54",
        edgecolor="white",
    )
    axes[1].set_xlabel(f"Token usage  {_tail_note(df['token_usage'], clip_tok)}")
    axes[1].set_ylabel("Count")
    axes[1].set_title("Token cost per sample")
    axes[1].xaxis.set_major_formatter(
        ticker.FuncFormatter(lambda x, _: f"{x / 1000:.0f}k")
    )

    clip_turns = 30
    axes[2].hist(
        df["total_turns"][df["total_turns"] <= clip_turns],
        bins=range(0, clip_turns + 2),
        color="#7a7a7a",
        edgecolor="white",
    )
    axes[2].set_xlabel(f"Total agent turns  {_tail_note(df['total_turns'], clip_turns)}")
    axes[2].set_ylabel("Count")
    axes[2].set_title("Agent turns per sample")

    fig.suptitle("Pipeline cost", fontsize=13)
    fig.tight_layout()
    _save(fig, "pipeline_cost")


def plot_difficulty_vs_faithfulness(df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

    for diff, color in [("hard", "#e07b54"), ("easy", "#5ba3cf")]:
        subset = df[df["difficulty"] == diff]
        axes[0].hist(
            subset["sf_overall"].dropna(),
            bins=25,
            alpha=0.6,
            color=color,
            label=diff,
            edgecolor="white",
        )
    axes[0].set_xlabel("Overall faithfulness")
    axes[0].set_ylabel("Count")
    axes[0].set_title("Faithfulness by difficulty")
    axes[0].legend()

    for diff, color in [("hard", "#e07b54"), ("easy", "#5ba3cf")]:
        subset = df[df["difficulty"] == diff]
        axes[1].hist(
            subset["total_lean_lines"].clip(upper=500).dropna(),
            bins=30,
            alpha=0.6,
            color=color,
            label=diff,
            edgecolor="white",
        )
    axes[1].set_xlabel("Total Lean lines (clipped at 500)")
    axes[1].set_ylabel("Count")
    axes[1].set_title("Lean output size by difficulty")
    axes[1].legend()

    fig.suptitle("Difficulty vs. output characteristics", fontsize=13)
    fig.tight_layout()
    _save(fig, "difficulty_vs_faithfulness")


def plot_implementation_level(df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    counts = df["implementation_level"].value_counts()
    axes[0].bar(counts.index, counts.values, color=["#5ba3cf", "#e07b54"])
    axes[0].set_ylabel("Count")
    axes[0].set_title("Implementation level")
    for i, val in enumerate(counts.values):
        axes[0].text(i, val + 50, str(val), ha="center", fontsize=9)

    grouped = df.groupby("implementation_level")["sf_overall"].mean()
    axes[1].bar(grouped.index, grouped.values, color=["#5ba3cf", "#e07b54"])
    axes[1].set_ylabel("Mean faithfulness (overall)")
    axes[1].set_title("Faithfulness by implementation level")
    for i, val in enumerate(grouped.values):
        axes[1].text(i, val + 0.005, f"{val:.2f}", ha="center", fontsize=9)

    fig.suptitle("Implementation level breakdown", fontsize=13)
    fig.tight_layout()
    _save(fig, "implementation_level")


def main() -> None:
    sns.set_theme(style="whitegrid", font_scale=0.95)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Loading FVSpec data from HuggingFace ({HF_REPO})...")
    df = load()
    print(f"Loaded {len(df):,} samples.")

    plots = [
        ("difficulty_distribution", plot_difficulty_distribution),
        ("structural_faithfulness", plot_structural_faithfulness),
        ("lean_complexity", plot_lean_complexity),
        ("python_source", plot_python_source),
        ("pipeline_cost", plot_pipeline_cost),
        ("difficulty_vs_faithfulness", plot_difficulty_vs_faithfulness),
        ("implementation_level", plot_implementation_level),
    ]

    for name, fn in plots:
        print(f"  Plotting {name}...")
        fn(df)

    print(f"Done. {len(plots)} figures saved to {OUT_DIR}/")


if __name__ == "__main__":
    main()
