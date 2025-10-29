"""Test unit test extraction on the full dataset.

This script runs the AST-based unit test extractor on all unit tests
in the dataset to measure extraction success rates and identify common failure patterns.
"""

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)

from generate.scaffold.units import extract_unit_tests

DATADIR = Path(".") / "data"
TOTAL_PBTS = 60776  # Total lines in pbts.jsonl

app = typer.Typer()


@app.command()
def main(
    num_samples: Annotated[
        int | None, typer.Option(help="Number of PBT samples to process (default: all)")
    ] = None,
):
    """Run extraction test on full dataset."""
    print("Unit Test Extraction Success Analysis")
    print("=" * 60)
    print()

    pbts_jsonl = DATADIR / "pbts.jsonl"
    if not pbts_jsonl.exists():
        print(f"Error: {pbts_jsonl} not found")
        return

    # Track statistics
    stats = {
        "total_pbts": 0,
        "pbts_with_functions": 0,
        "pbts_with_existing_units": 0,
        "total_existing_unit_tests": 0,
        "extraction_attempts": 0,
        "extraction_successes": 0,
        "extraction_failures": 0,
        "total_tests_extracted": 0,
        "exact_tests": 0,
        "float_tests": 0,
    }

    # Track test counts per PBT
    tests_per_pbt: Counter[int] = Counter()
    existing_units_per_pbt: Counter[int] = Counter()
    failure_reasons: Counter[str] = Counter()

    total_to_process = num_samples if num_samples else TOTAL_PBTS

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
    ) as progress:
        task = progress.add_task(
            "[cyan]Processing PBT samples",
            total=total_to_process,
        )

        with open(pbts_jsonl) as f:
            for line_num, line in enumerate(f, 1):
                if num_samples and line_num > num_samples:
                    break

                stats["total_pbts"] += 1

                # Update progress every 100 lines
                if line_num % 100 == 0:
                    progress.update(
                        task,
                        completed=line_num,
                        description=f"[cyan]Processing PBT samples (successes: {stats['extraction_successes']})",
                    )

                # Parse JSON
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Count existing unit tests and try extraction on each
                overlapping_tests = data.get("overlapping_tests", [])
                if overlapping_tests:
                    num_existing_units = 0
                    for overlap in overlapping_tests:
                        unit_tests = overlap.get("unit_tests", [])
                        shared_functions = overlap.get("shared_functions", [])
                        num_existing_units += len(unit_tests)

                        # Try extraction on each unit test
                        for unit_test in unit_tests:
                            unit_test_code = unit_test.get("code", "")
                            if not unit_test_code:
                                continue

                            # Try each shared function
                            for func_name in shared_functions:
                                stats["extraction_attempts"] += 1

                                try:
                                    test_suite = extract_unit_tests(
                                        unit_test_code, func_name=func_name
                                    )

                                    if test_suite and (
                                        test_suite.exact_tests or test_suite.float_tests
                                    ):
                                        stats["extraction_successes"] += 1
                                        num_tests = len(test_suite.exact_tests) + len(
                                            test_suite.float_tests
                                        )
                                        stats["total_tests_extracted"] += num_tests
                                        stats["exact_tests"] += len(
                                            test_suite.exact_tests
                                        )
                                        stats["float_tests"] += len(
                                            test_suite.float_tests
                                        )
                                        tests_per_pbt[num_tests] += 1
                                    else:
                                        stats["extraction_failures"] += 1
                                        failure_reasons["no_tests_found"] += 1

                                except Exception as e:
                                    stats["extraction_failures"] += 1
                                    error_type = type(e).__name__
                                    failure_reasons[error_type] += 1

                    if num_existing_units > 0:
                        stats["pbts_with_existing_units"] += 1
                        stats["total_existing_unit_tests"] += num_existing_units
                        existing_units_per_pbt[num_existing_units] += 1

        # Final progress update
        progress.update(
            task,
            completed=total_to_process,
            description=f"[cyan]Processing PBT samples (successes: {stats['extraction_successes']})",
        )

    print()
    print("Processing complete!")
    print()

    # Generate report
    report_path = DATADIR / "unit_test_extraction_success.md"
    with open(report_path, "w") as f:
        f.write("# Unit Test Extraction Success Report\n\n")
        f.write(f"**Generated:** {datetime.now().isoformat()}\n\n")

        f.write("## Dataset Statistics\n\n")
        f.write(f"- **Total PBT samples processed:** {stats['total_pbts']:,}\n")
        f.write(
            f"- **PBTs with existing unit tests:** {stats['pbts_with_existing_units']:,} ({stats['pbts_with_existing_units'] / stats['total_pbts'] * 100:.1f}% of processed)\n"
        )
        f.write(
            f"- **Total existing unit tests:** {stats['total_existing_unit_tests']:,}\n"
        )

        if stats["pbts_with_existing_units"] > 0:
            avg_existing = (
                stats["total_existing_unit_tests"] / stats["pbts_with_existing_units"]
            )
            f.write(
                f"- **Average existing units per PBT (with units):** {avg_existing:.1f}\n"
            )

        f.write("\n## Extraction Results\n\n")
        f.write(f"- **Extraction attempts:** {stats['extraction_attempts']:,}\n")
        f.write(f"- **Successful extractions:** {stats['extraction_successes']:,}\n")
        f.write(f"- **Failed extractions:** {stats['extraction_failures']:,}\n")

        if stats["extraction_attempts"] > 0:
            success_rate = (
                stats["extraction_successes"] / stats["extraction_attempts"] * 100
            )
            f.write(f"- **Success rate:** {success_rate:.1f}%\n")

        f.write("\n## Extracted Tests\n\n")
        f.write(f"- **Total tests extracted:** {stats['total_tests_extracted']:,}\n")
        f.write(f"- **Exact tests:** {stats['exact_tests']:,}\n")
        f.write(f"- **Float tests:** {stats['float_tests']:,}\n")

        if stats["extraction_successes"] > 0:
            avg_tests = stats["total_tests_extracted"] / stats["extraction_successes"]
            f.write(f"- **Average tests per success:** {avg_tests:.1f}\n")

        f.write("\n## Tests Per PBT Distribution\n\n")
        f.write("| Tests Extracted | Count | Percentage |\n")
        f.write("|----------------|-------|------------|\n")
        for num_tests in sorted(tests_per_pbt.keys()):
            count = tests_per_pbt[num_tests]
            pct = (
                count / stats["extraction_successes"] * 100
                if stats["extraction_successes"] > 0
                else 0
            )
            f.write(f"| {num_tests} | {count:,} | {pct:.1f}% |\n")

        f.write("\n## Existing Unit Tests Distribution\n\n")
        f.write("| Unit Tests | PBT Count | Percentage |\n")
        f.write("|------------|-----------|------------|\n")
        for num_units in sorted(existing_units_per_pbt.keys()):
            count = existing_units_per_pbt[num_units]
            pct = (
                count / stats["pbts_with_existing_units"] * 100
                if stats["pbts_with_existing_units"] > 0
                else 0
            )
            f.write(f"| {num_units} | {count:,} | {pct:.1f}% |\n")

        if failure_reasons:
            f.write("\n## Failure Reasons\n\n")
            f.write("| Reason | Count | Percentage |\n")
            f.write("|--------|-------|------------|\n")
            for reason, count in failure_reasons.most_common():
                pct = (
                    count / stats["extraction_failures"] * 100
                    if stats["extraction_failures"] > 0
                    else 0
                )
                f.write(f"| {reason} | {count:,} | {pct:.1f}% |\n")

    print(f"Report written to: {report_path}")
    print()
    print(
        f"Success rate: {stats['extraction_successes'] / stats['extraction_attempts'] * 100:.1f}%"
    )
    print(f"Total tests extracted: {stats['total_tests_extracted']:,}")


if __name__ == "__main__":
    app()
