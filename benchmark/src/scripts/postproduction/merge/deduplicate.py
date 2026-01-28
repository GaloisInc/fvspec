"""Deduplication logic for merging benchmark runs.

This module provides functions for deduplicating samples by sample_id,
keeping the highest quality sample when duplicates are found.
"""

from typing import Any

from rich.console import Console


def quality_score(sample: dict[str, Any]) -> tuple:
    """Calculate quality score tuple for sorting (higher is better).

    Returns tuple of:
    1. success (true > false)
    2. structural_faithfulness.overall (higher better)
    3. num_theorems (higher better)
    4. has_unit_tests (true > false)
    5. impl_autoform_success (true > false)
    6. spec_sig_success (true > false)
    """
    structural = sample.get("structural_faithfulness")
    structural_overall = structural.get("overall", 0.0) if structural else 0.0

    return (
        sample.get("success", False),
        structural_overall,
        sample.get("num_theorems", 0),
        sample.get("has_unit_tests", False),
        sample.get("impl_autoform_success", False),
        sample.get("spec_sig_success", False),
    )


def deduplicate_samples(
    samples: list[dict[str, Any]], console: Console
) -> dict[int, dict[str, Any]]:
    """Deduplicate samples by sample_id, keeping the highest quality sample.

    Args:
        samples: List of sample dictionaries to deduplicate
        console: Rich console for progress output

    Returns:
        Dictionary mapping sample_id to the best quality sample for that id
    """
    best_by_id: dict[int, dict[str, Any]] = {}
    duplicates_replaced = 0

    for sample in samples:
        sample_id = sample.get("sample_id")
        if sample_id is None:
            console.print(
                f"[yellow]Warning: Sample missing sample_id: {sample.get('id')}[/yellow]"
            )
            continue

        if sample_id not in best_by_id:
            best_by_id[sample_id] = sample
        else:
            # Compare quality and keep better one
            current_score = quality_score(best_by_id[sample_id])
            new_score = quality_score(sample)

            if new_score > current_score:
                old_prov = best_by_id[sample_id].get("run_provenance", "unknown")
                new_prov = sample.get("run_provenance", "unknown")
                console.print(
                    f"[dim]Sample {sample_id}: replacing {old_prov} with {new_prov}[/dim]"
                )
                best_by_id[sample_id] = sample
                duplicates_replaced += 1

    return best_by_id
