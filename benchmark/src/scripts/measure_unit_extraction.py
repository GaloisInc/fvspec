"""Measure unit test extraction rate across the dataset.

This script samples datapoints, runs the extraction pipeline, and generates
detailed metrics on:
- Extraction success rate
- Tests extracted per PBT
- Failure reasons (categorized)
- Quality of generated LSpec code
"""

from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)
from rich.table import Table

from generate.scaffold.dataset import extract_datapoint_unit_tests
from generate.scaffold.dataset.connection import get_session
from generate.scaffold.dataset.queries import (
    get_overlapping_unit_tests,
    sample_datapoints,
)

DATADIR = Path(".") / "data"

app = typer.Typer()
console = Console()


def categorize_failure(dp, overlaps, target_func, extracted_lspec) -> tuple[str, str]:
    """Categorize why extraction failed.

    Returns:
        (category, detail) tuple
    """
    if not overlaps:
        return ("no_overlaps", "PBT has no overlapping unit tests")

    if not target_func:
        return ("no_target_func", "Could not infer target function name")

    # Check if any unit tests have assertions
    has_asserts = False
    for overlap in overlaps:
        for unit_test in overlap["unit_tests"]:
            if "assert" in unit_test["code"].lower():
                has_asserts = True
                break

    if not has_asserts:
        return ("no_assertions", "Unit tests contain no assert statements")

    if not extracted_lspec:
        return ("extraction_failed", "AST/tree-sitter extraction produced no tests")

    return ("unknown", "Extraction failed for unknown reason")


@app.command()
def main(
    num_samples: Annotated[
        int, typer.Option(help="Number of PBT samples to measure")
    ] = 100,
    ranseed: Annotated[int, typer.Option(help="Random seed for sampling")] = 0,
    output: Annotated[
        Path | None, typer.Option(help="Output file for detailed results (JSON)")
    ] = None,
    phase2: Annotated[
        bool, typer.Option(help="Enable Phase 2 assertion-based filtering")
    ] = False,
):
    """Measure unit test extraction rate on sampled datapoints."""
    console.print("\n[bold cyan]Unit Test Extraction Measurement[/bold cyan]")
    console.print("=" * 60)
    console.print()

    pbts_db = DATADIR / "pbts_full.db"
    if not pbts_db.exists():
        console.print(f"[red]Error:[/red] {pbts_db} not found")
        raise typer.Exit(1)

    console.print(f"Database: {pbts_db}")
    console.print(f"Sample size: {num_samples}")
    console.print(f"Random seed: {ranseed}")
    console.print(f"Phase 2 filtering: {'enabled' if phase2 else 'disabled'}")
    console.print()

    # Statistics
    stats = {
        "total_samples": 0,
        "has_overlaps": 0,
        "has_target_func": 0,
        "extraction_success": 0,
        "total_tests_extracted": 0,
        "exact_tests": 0,
        "float_tests": 0,
    }

    # Detailed tracking
    tests_per_pbt: list[int] = []
    overlaps_per_pbt: list[int] = []
    failure_reasons: Counter[str] = Counter()
    failure_details: dict[str, list[str]] = defaultdict(list)
    success_samples: list[dict] = []

    # Sample datapoints
    with get_session(pbts_db) as session:
        datapoints = sample_datapoints(session, n=num_samples, ranseed=ranseed)

    console.print(f"Sampled {len(datapoints)} datapoints\n")

    # Process each datapoint with single DB session
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            "[cyan]Extracting unit tests...", total=len(datapoints)
        )

        # Open single DB session for all queries
        with get_session(pbts_db) as session:
            for dp in datapoints:
                stats["total_samples"] += 1

                # Query overlaps (reuse session)
                overlaps = get_overlapping_unit_tests(
                    session, dp.id, filter_by_assertions=phase2
                )

                # Count overlapping tests
                num_overlaps = sum(len(overlap["unit_tests"]) for overlap in overlaps)
                overlaps_per_pbt.append(num_overlaps)

                if overlaps:
                    stats["has_overlaps"] += 1

                # Try to infer target function
                from generate.scaffold.dataset import infer_target_function

                target_func = infer_target_function(dp)
                if target_func:
                    stats["has_target_func"] += 1

                # Try extraction (pass overlaps to avoid re-querying)
                try:
                    extracted_lspec = extract_datapoint_unit_tests(
                        dp, overlaps=overlaps
                    )
                except Exception as e:
                    extracted_lspec = None
                    failure_reasons["extraction_error"] += 1
                    failure_details["extraction_error"].append(
                        f"ID {dp.id}: {type(e).__name__}: {str(e)}"
                    )

                if extracted_lspec:
                    stats["extraction_success"] += 1

                    # Count tests in LSpec output
                    num_tests = extracted_lspec.count('test "')
                    num_eval = extracted_lspec.count("#eval")
                    tests_per_pbt.append(num_tests + num_eval)
                    stats["total_tests_extracted"] += num_tests + num_eval
                    stats["exact_tests"] += num_tests
                    stats["float_tests"] += num_eval

                    success_samples.append(
                        {
                            "id": dp.id,
                            "name": dp.name,
                            "target_func": target_func,
                            "num_tests": num_tests + num_eval,
                            "num_overlaps": num_overlaps,
                        }
                    )
                else:
                    tests_per_pbt.append(0)
                    # Categorize failure
                    category, detail = categorize_failure(
                        dp, overlaps, target_func, extracted_lspec
                    )
                    failure_reasons[category] += 1
                    failure_details[category].append(
                        f"ID {dp.id} ({dp.name}): {detail}"
                    )

                progress.update(task, advance=1)

    # Print results
    console.print("\n[bold green]Results[/bold green]")
    console.print("=" * 60)
    console.print()

    # Success rate
    success_rate = (
        stats["extraction_success"] / stats["total_samples"] * 100
        if stats["total_samples"] > 0
        else 0
    )
    console.print(f"[bold]Extraction Success Rate:[/bold] {success_rate:.1f}%")
    console.print(
        f"  • Successful: {stats['extraction_success']} / {stats['total_samples']}"
    )
    console.print(
        f"  • Has overlapping tests: {stats['has_overlaps']} ({stats['has_overlaps'] / stats['total_samples'] * 100:.1f}%)"
    )
    console.print()

    # Test counts
    avg_tests = sum(tests_per_pbt) / len(tests_per_pbt) if tests_per_pbt else 0
    console.print("[bold]Tests Extracted:[/bold]")
    console.print(f"  • Total: {stats['total_tests_extracted']}")
    console.print(f"  • Exact (LSpec): {stats['exact_tests']}")
    console.print(f"  • Float (#eval): {stats['float_tests']}")
    console.print(f"  • Average per PBT: {avg_tests:.1f}")
    console.print()

    # Failure analysis
    console.print("[bold]Failure Reasons:[/bold]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Category", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Percentage", justify="right")

    for category, count in failure_reasons.most_common():
        pct = count / stats["total_samples"] * 100
        table.add_row(category, str(count), f"{pct:.1f}%")

    console.print(table)
    console.print()

    # Distribution
    console.print("[bold]Distribution:[/bold]")
    if overlaps_per_pbt:
        console.print(
            f"  • Overlapping tests per PBT: min={min(overlaps_per_pbt)}, "
            f"max={max(overlaps_per_pbt)}, "
            f"avg={sum(overlaps_per_pbt) / len(overlaps_per_pbt):.1f}"
        )
    if tests_per_pbt:
        successful_tests = [t for t in tests_per_pbt if t > 0]
        if successful_tests:
            console.print(
                f"  • Tests extracted (when successful): min={min(successful_tests)}, "
                f"max={max(successful_tests)}, "
                f"avg={sum(successful_tests) / len(successful_tests):.1f}"
            )

    # Sample successes
    if success_samples:
        console.print()
        console.print("[bold]Sample Successes (first 5):[/bold]")
        for sample in success_samples[:5]:
            console.print(
                f"  • ID {sample['id']}: {sample['name']} → "
                f"{sample['num_tests']} tests extracted "
                f"({sample['num_overlaps']} overlaps)"
            )

    # Sample failures (detailed)
    if failure_details:
        console.print()
        console.print("[bold]Sample Failures (first 3 per category):[/bold]")
        for category, details in failure_details.items():
            console.print(f"\n  [cyan]{category}:[/cyan]")
            for detail in details[:3]:
                console.print(f"    {detail}")

    # Save detailed results
    if output:
        import json

        results = {
            "timestamp": datetime.now().isoformat(),
            "config": {
                "num_samples": num_samples,
                "ranseed": ranseed,
                "database": str(pbts_db),
            },
            "stats": stats,
            "success_rate": success_rate,
            "failure_reasons": dict(failure_reasons),
            "success_samples": success_samples,
            "failure_details": {k: v for k, v in failure_details.items()},
        }

        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w") as f:
            json.dump(results, f, indent=2)

        console.print(f"\n[green]Detailed results saved to {output}[/green]")

    # Decision guidance
    console.print()
    console.print("[bold yellow]Recommendation:[/bold yellow]")
    if success_rate >= 40:
        console.print(f"  ✅ {success_rate:.1f}% extraction rate meets 40-50% target")
        console.print("  → Ready to integrate into benchmark pipeline")
    elif success_rate >= 30:
        console.print(f"  ⚠️  {success_rate:.1f}% extraction rate is close to target")
        console.print("  → Consider analyzing failure patterns for quick wins")
    else:
        console.print(f"  ❌ {success_rate:.1f}% extraction rate below 30% threshold")
        console.print(
            "  → Investigate failure reasons and add support for common patterns"
        )

    console.print()


if __name__ == "__main__":
    app()
