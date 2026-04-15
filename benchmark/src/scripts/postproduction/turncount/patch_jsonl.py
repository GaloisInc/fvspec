"""Patch turn_counts directly into a merged JSONL file from .eval files.

Use this when you can't re-run the full merge pipeline but need to backfill
turn_counts for samples whose qa.json files don't exist on disk.

Reads .eval zip files, extracts turn counts, and matches to JSONL rows
using (sample_name, token_usage) as the join key.

Usage (from benchmark/ directory):
    uv run python -m scripts.postproduction.turncount.patch_jsonl \
        artifacts/dataset-out/fvspec-merged.validated.jsonl \
        artifacts/runs/2026-03-30T14-10-09__idx0-2500__claude-sonnet-4-6 \
        artifacts/runs/2026-04-01T07-39-56__idx0-2500__claude-sonnet-4-6 \
        [... more run dirs ...]
"""

import json
import zipfile
from collections import Counter
from pathlib import Path

import typer
from rich.console import Console

from scripts.postproduction.turncount.extractor import (
    extract_sample_turn_counts,
    find_eval_files,
    sample_id_from_entry,
)

app = typer.Typer(help="Patch turn_counts directly into a merged JSONL file")
console = Console()


def build_tc_map_from_evals(
    run_dirs: list[Path],
) -> dict[tuple[str, int], dict]:
    """Build a (sample_name, token_usage) -> turn_counts dict from .eval files."""
    tc_map: dict[tuple[str, int], dict] = {}
    collisions = 0

    for run_dir in run_dirs:
        for eval_path in find_eval_files(run_dir):
            console.print(f"  Reading {eval_path.name}")
            try:
                with zipfile.ZipFile(eval_path, "r") as zf:
                    for entry in zf.namelist():
                        if not entry.startswith("samples/") or not entry.endswith(
                            ".json"
                        ):
                            continue

                        sample_data = json.loads(zf.read(entry))
                        eval_id = sample_id_from_entry(entry)

                        # Extract sample_name (strip numeric prefix)
                        parts = eval_id.split("_", 1)
                        sample_name = parts[1] if len(parts) > 1 else eval_id

                        # Sum total_tokens across all models in model_usage
                        model_usage = sample_data.get("model_usage", {})
                        token_usage = sum(
                            v.get("total_tokens", 0) for v in model_usage.values()
                        )

                        tc = extract_sample_turn_counts(sample_data)

                        key = (sample_name, token_usage)
                        if key in tc_map:
                            collisions += 1
                        tc_map[key] = tc.model_dump()

            except Exception as e:
                console.print(f"[red]Error reading {eval_path}: {e}[/red]")

    if collisions:
        console.print(
            f"[yellow]Warning: {collisions} key collisions (last write wins)[/yellow]"
        )
    return tc_map


@app.command()
def main(
    jsonl_file: Path = typer.Argument(
        ..., help="Path to the JSONL file to patch", exists=True
    ),
    run_dirs: list[Path] = typer.Argument(
        ..., help="Run directories containing .eval files"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be patched without writing"
    ),
) -> None:
    """Patch turn_counts into a merged JSONL file from .eval zip files.

    Matches JSONL rows to .eval samples using (realpbt_sample_name, token_usage)
    as the join key. Only patches rows where turn_counts is currently null.
    """
    console.print("[bold]Patching turn_counts into JSONL from .eval files[/bold]\n")

    # Validate run dirs
    valid_dirs = []
    for d in run_dirs:
        if not d.is_dir():
            console.print(f"[yellow]Warning: Not a directory: {d}[/yellow]")
            continue
        if not find_eval_files(d):
            console.print(f"[yellow]Warning: No .eval files in: {d}[/yellow]")
            continue
        valid_dirs.append(d)

    if not valid_dirs:
        console.print("[red]No valid run directories with .eval files found.[/red]")
        raise typer.Exit(1)

    console.print(f"Reading .eval files from {len(valid_dirs)} run(s)...")
    tc_map = build_tc_map_from_evals(valid_dirs)
    console.print(f"Built lookup with {len(tc_map)} entries\n")

    # Read JSONL, patch missing turn_counts, write back
    lines = jsonl_file.read_text().splitlines()
    stats: Counter[str] = Counter()
    patched_lines = []

    for line in lines:
        sample = json.loads(line)
        if sample.get("turn_counts") is not None:
            stats["already_has"] += 1
            patched_lines.append(line)
            continue

        name = sample.get("realpbt_sample_name")
        token_usage = sample.get("token_usage", 0)
        key = (name, token_usage)

        if key in tc_map:
            sample["turn_counts"] = tc_map[key]
            patched_lines.append(json.dumps(sample))
            stats["patched"] += 1
        else:
            stats["not_found"] += 1
            patched_lines.append(line)

    console.print("[bold]Results:[/bold]")
    console.print(f"  Already had turn_counts: {stats['already_has']}")
    console.print(f"  Patched:                 {stats['patched']}")
    console.print(f"  Not found in .eval:      {stats['not_found']}")

    if not dry_run and stats["patched"] > 0:
        jsonl_file.write_text("\n".join(patched_lines) + "\n")
        console.print(
            f"\n[green]✓[/green] Wrote {len(patched_lines)} lines to {jsonl_file}"
        )
    elif dry_run:
        console.print("\n[cyan]Dry run — no changes written.[/cyan]")
    else:
        console.print("\n[dim]Nothing to patch.[/dim]")


if __name__ == "__main__":
    app()
