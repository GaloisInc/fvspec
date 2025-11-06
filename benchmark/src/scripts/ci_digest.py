"""Run nightly CI benchmark and generate digest reports.

This script runs the fvspec evaluation on the CI dataset and generates
markdown or JSONL reports for tracking nightly benchmark performance.
"""

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from inspect_ai import eval as inspect_eval

from generate.scaffold.orchestration import fvspec


def run_ci_eval(
    datafile: str,
    model: str,
    variant: str,
    sample_size: int,
) -> Path:
    """Run the fvspec evaluation and return path to results.

    Args:
        datafile: Path to CI database (e.g., "pbts_ci.db")
        model: Model identifier (e.g., "anthropic/claude-haiku-4-5-20251001")
        variant: Prompt variant (e.g., "control-functional")
        sample_size: Number of samples to evaluate

    Returns:
        Path to the eval log directory
    """
    # Create log directory
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%dT%H-%M-%S")
    log_dir_name = f"ci_{timestamp}__{variant}"
    log_dir = Path("artifacts") / "ci" / log_dir_name
    log_dir.mkdir(parents=True, exist_ok=True)

    print("Running CI evaluation...")
    print(f"  Model: {model}")
    print(f"  Dataset: {datafile}")
    print(f"  Variant: {variant}")
    print(f"  Sample size: {sample_size}")
    print(f"  Log dir: {log_dir}")
    print()

    # Run evaluation with hardcoded settings for CI
    inspect_eval(
        fvspec(
            datafile,
            variant=variant,
            sample_size=sample_size,
            ranseed=0,  # Fixed seed for reproducibility
            timestamp=now,
        ),
        model=model,
        log_dir=str(log_dir),
        max_samples=4,  # Parallelism for CI
        display="none",  # Quiet output for CI
    )

    print(f"\nEvaluation complete. Logs saved to {log_dir}")
    return log_dir


def parse_qa_files(log_dir: Path) -> dict[str, Any]:
    """Parse quality assessment files from eval output.

    Args:
        log_dir: Path to eval log directory

    Returns:
        Dictionary containing extracted metrics
    """
    # Find all qa.json files in the log directory
    qa_files = list(log_dir.rglob("qa.json"))

    if not qa_files:
        print(f"Warning: No qa.json files found in {log_dir}")
        return {
            "total_samples": 0,
            "success_count": 0,
            "success_rate": 0,
            "functional_success": 0,
            "mvcgen_success": 0,
            "error_types": {},
            "avg_quality": None,
            "quality_scores": [],
        }

    total_samples = len(qa_files)
    success_count = 0
    functional_success = 0
    mvcgen_success = 0
    error_types: Counter[str] = Counter()
    quality_scores = []

    for qa_file in qa_files:
        try:
            with open(qa_file) as f:
                qa = json.load(f)

            # Check if sample succeeded (has theorems and no errors)
            theorem_count = qa.get("code", {}).get("theorem_count", 0)
            has_errors = qa.get("errors", [])

            if theorem_count > 0 and not has_errors:
                success_count += 1

                # Track by variant if available
                variant = qa.get("variant", "unknown")
                if "functional" in variant:
                    functional_success += 1
                elif "mvcgen" in variant:
                    mvcgen_success += 1

            # Collect error types
            for error in has_errors:
                error_type = error.get("type", "unknown")
                error_types[error_type] += 1

            # Collect quality metrics
            structural = qa.get("structural", {})
            if "faithfulness_score" in structural:
                quality_scores.append(structural["faithfulness_score"])

        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: Failed to parse {qa_file}: {e}")
            continue

    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else None

    return {
        "total_samples": total_samples,
        "success_count": success_count,
        "success_rate": success_count / total_samples if total_samples > 0 else 0,
        "functional_success": functional_success,
        "mvcgen_success": mvcgen_success,
        "error_types": dict(error_types.most_common(5)),
        "avg_quality": avg_quality,
        "quality_scores": quality_scores,
    }


def load_previous_results(branch: str = "ci-results") -> dict[str, Any] | None:
    """Load the most recent result from ci-results branch.

    Args:
        branch: Name of the orphan branch containing results

    Returns:
        Most recent result dict, or None if not available
    """
    results_file = Path("results.jsonl")
    if not results_file.exists():
        return None

    # Read last line
    with open(results_file) as f:
        lines = f.readlines()
        if not lines:
            return None
        return json.loads(lines[-1])


def format_markdown_report(
    metrics: dict[str, Any],
    model: str,
    commit: str,
    previous: dict[str, Any] | None = None,
) -> str:
    """Format metrics as a markdown report.

    Args:
        metrics: Current run metrics
        model: Model identifier
        commit: Git commit SHA
        previous: Previous run metrics for comparison

    Returns:
        Markdown formatted report
    """
    date = datetime.now().strftime("%Y-%m-%d")
    success_rate = metrics["success_rate"] * 100

    # Calculate deltas if previous data available
    delta_str = ""
    if previous:
        prev_rate = previous.get("success_rate", 0) * 100
        delta = success_rate - prev_rate
        emoji = "🔴" if delta < 0 else "🟢" if delta > 0 else "⚪"
        delta_str = f" ({emoji} {delta:+.1f}% vs previous)"

    report = f"""### Nightly Run: {date} (commit: `{commit[:7]}`)

**Model:** {model} | **Samples:** {metrics["total_samples"]}

| Metric | Value | Notes |
|--------|-------|-------|
| Success Rate | {success_rate:.1f}%{delta_str} | {metrics["success_count"]}/{metrics["total_samples"]} |
"""

    if metrics["functional_success"] or metrics["mvcgen_success"]:
        report += f"| Functional Success | {metrics['functional_success']} | (if variant tracked) |\n"
        report += (
            f"| Mvcgen Success | {metrics['mvcgen_success']} | (if variant tracked) |\n"
        )

    if metrics["avg_quality"] is not None:
        report += f"| Avg Quality Score | {metrics['avg_quality']:.2f} | Structural faithfulness |\n"

    # Error breakdown
    if metrics["error_types"]:
        report += "\n**Error Types:**\n"
        for error_type, count in metrics["error_types"].items():
            report += f"- `{error_type}`: {count} occurrences\n"

    report += (
        f"\n[View full commit →](https://github.com/fvspec/fvspec/commit/{commit})\n"
    )

    return report


def format_jsonl_output(
    metrics: dict[str, Any],
    model: str,
    commit: str,
) -> str:
    """Format metrics as a single JSONL line for the ci-results branch.

    Args:
        metrics: Current run metrics
        model: Model identifier
        commit: Git commit SHA

    Returns:
        JSON string (single line)
    """
    output = {
        "schema_version": "v1",  # Allows for future schema migrations
        "date": datetime.now().isoformat(),
        "commit": commit,
        "model": model,
        # Core metrics - use .get() for forward compatibility
        "total_samples": metrics.get("total_samples", 0),
        "success_rate": metrics.get("success_rate", 0.0),
        "functional_success": metrics.get("functional_success", 0),
        "mvcgen_success": metrics.get("mvcgen_success", 0),
        "avg_quality": metrics.get("avg_quality"),
        "error_types": metrics.get("error_types", {}),
        # Include all other metrics for extensibility
        "extended_metrics": {
            k: v
            for k, v in metrics.items()
            if k
            not in {
                "total_samples",
                "success_rate",
                "functional_success",
                "mvcgen_success",
                "avg_quality",
                "error_types",
                "quality_scores",  # Exclude large arrays
            }
        },
    }
    return json.dumps(output)


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run nightly CI benchmark and generate digest"
    )
    parser.add_argument(
        "--datafile",
        type=str,
        default=".github/pbts_ci.db",
        help="Path to CI database",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="anthropic/claude-haiku-4-5-20251001",
        help="Model identifier",
    )
    parser.add_argument(
        "--variant",
        type=str,
        default="control-functional",
        help="Prompt variant",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=64,
        help="Number of samples to evaluate",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        help="Parse existing log directory instead of running eval",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file path (stdout if not specified)",
    )
    parser.add_argument(
        "--output-format",
        choices=["markdown", "jsonl"],
        default="markdown",
        help="Output format",
    )
    parser.add_argument(
        "--commit",
        type=str,
        required=True,
        help="Git commit SHA",
    )
    parser.add_argument(
        "--compare-previous",
        action="store_true",
        help="Load and compare with previous results",
    )

    args = parser.parse_args()

    # Either run eval or use existing log directory
    if args.log_dir:
        log_dir = args.log_dir
        print(f"Using existing log directory: {log_dir}")
    else:
        # Run the evaluation
        log_dir = run_ci_eval(
            args.datafile,
            args.model,
            args.variant,
            args.sample_size,
        )

    # Parse results from qa.json files
    metrics = parse_qa_files(log_dir)

    # Optionally load previous results
    previous = None
    if args.compare_previous:
        previous = load_previous_results()

    # Generate output
    if args.output_format == "markdown":
        output = format_markdown_report(metrics, args.model, args.commit, previous)
    else:
        output = format_jsonl_output(metrics, args.model, args.commit)

    # Write output
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output)
    else:
        print(output)


if __name__ == "__main__":
    main()
