"""Deduplicate JSONL dataset by keeping best quality sample per ID.

Usage:
    uv run python src/scripts/postproduction/deduplicate.py artifacts/dataset-out/fvspec-jan22.jsonl
"""

import json
import sys
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()


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


def deduplicate_jsonl(input_path: Path) -> dict[str, int]:
    """Deduplicate JSONL file by sample_id, keeping best quality entry.

    Args:
        input_path: Path to JSONL file (will be overwritten)

    Returns:
        Statistics about deduplication
    """
    console.print(f"[bold]Reading {input_path}...[/bold]")

    # Read all entries
    entries = []
    with open(input_path) as f:
        for line in f:
            entries.append(json.loads(line))

    console.print(f"Total entries: {len(entries)}")

    # Group by sample_id and keep best
    best_by_id: dict[int, dict[str, Any]] = {}
    duplicate_count = 0

    for entry in entries:
        sample_id = entry.get("sample_id")
        if sample_id is None:
            console.print(
                f"[yellow]Warning: Entry missing sample_id: {entry.get('id')}[/yellow]"
            )
            continue

        if sample_id not in best_by_id:
            best_by_id[sample_id] = entry
        else:
            duplicate_count += 1
            # Compare quality and keep better one
            current_score = quality_score(best_by_id[sample_id])
            new_score = quality_score(entry)

            if new_score > current_score:
                old_prov = best_by_id[sample_id].get("run_provenance", "unknown")
                new_prov = entry.get("run_provenance", "unknown")
                console.print(
                    f"[dim]Sample {sample_id}: replacing {old_prov} with {new_prov}[/dim]"
                )
                best_by_id[sample_id] = entry

    # Write deduplicated entries back
    console.print(f"\n[bold]Writing deduplicated data to {input_path}...[/bold]")

    with open(input_path, "w") as f:
        for sample_id in sorted(best_by_id.keys()):
            f.write(json.dumps(best_by_id[sample_id]) + "\n")

    stats = {
        "original_count": len(entries),
        "unique_count": len(best_by_id),
        "duplicates_removed": duplicate_count,
    }

    return stats


def main():
    """CLI entry point for deduplicating JSONL dataset files.

    Reads a JSONL file, removes duplicate sample_ids (keeping best quality),
    creates a backup, and overwrites the original with deduplicated data.

    Usage:
        uv run python deduplicate.py <jsonl-file>
    """
    if len(sys.argv) != 2:
        console.print("[red]Usage: uv run python deduplicate.py <jsonl-file>[/red]")
        sys.exit(1)

    input_path = Path(sys.argv[1])

    if not input_path.exists():
        console.print(f"[red]Error: File not found: {input_path}[/red]")
        sys.exit(1)

    # Backup original
    backup_path = input_path.with_suffix(".jsonl.backup")
    console.print(f"[dim]Creating backup: {backup_path}[/dim]")

    with open(input_path) as src, open(backup_path, "w") as dst:
        dst.write(src.read())

    # Deduplicate
    stats = deduplicate_jsonl(input_path)

    # Display summary
    console.print("\n[bold green]✓ Deduplication complete![/bold green]\n")
    console.print(f"  Original entries: {stats['original_count']}")
    console.print(f"  Unique samples: {stats['unique_count']}")
    console.print(f"  Duplicates removed: {stats['duplicates_removed']}")
    console.print(f"\n  File size: {input_path.stat().st_size / 1024 / 1024:.2f} MB")
    console.print(f"  Backup saved to: {backup_path}")


if __name__ == "__main__":
    main()
