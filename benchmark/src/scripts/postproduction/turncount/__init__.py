"""Post-production: Enrich qa.json files with true turn counts from .eval files.

Usage (from benchmark/ directory):
    uv run postprod turncount artifacts/runs/
    uv run postprod turncount artifacts/runs/<run-dir>/
    uv run postprod turncount artifacts/runs/ --force
"""

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress

from scripts.postproduction.turncount.extractor import (
    extract_turn_counts_from_eval,
    find_eval_files,
    patch_qa_json,
)

app = typer.Typer(help="Enrich qa.json files with true turn counts from .eval files")
console = Console()


@app.command()
def main(
    runs_dir: Path = typer.Argument(
        ...,
        help="Path to runs directory (or a specific run directory)",
        exists=True,
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Re-compute even if turn_counts already exists in qa.json",
    ),
) -> None:
    """Enrich qa.json files with true turn counts extracted from .eval zip files.

    Counts assistant messages (turns) and tool messages (tool calls) per subagent
    from the conversation arrays stored in .eval files.

    **Default behavior**: Skips qa.json files that already have a `turn_counts` key (resume-safe).
    Use --force to re-compute all.

    Examples (from benchmark/ directory):
        uv run postprod turncount artifacts/runs/                    # All runs
        uv run postprod turncount artifacts/runs/<specific-run>/     # Single run
        uv run postprod turncount artifacts/runs/ --force            # Re-compute all
    """
    console.print("[bold]Post-production: Enriching qa.json with turn counts[/bold]\n")

    # Determine if this is a single run dir or a parent of many
    eval_files = find_eval_files(runs_dir)
    if eval_files:
        # Single run directory
        run_dirs = [runs_dir]
    else:
        # Parent directory containing multiple runs
        run_dirs = sorted(
            d for d in runs_dir.iterdir() if d.is_dir() and find_eval_files(d)
        )

    if not run_dirs:
        console.print("[red]No .eval files found.[/red]")
        raise typer.Exit(1)

    console.print(f"Found {len(run_dirs)} run(s) with .eval files")
    if force:
        console.print("[cyan]Force mode: re-computing all turn counts[/cyan]")

    stats = {"patched": 0, "skipped": 0, "missing_qa": 0, "errors": 0}

    with Progress(console=console) as progress:
        task = progress.add_task("Processing runs...", total=len(run_dirs))

        for run_dir in run_dirs:
            eval_files = find_eval_files(run_dir)

            for eval_path in eval_files:
                try:
                    turn_counts_map = extract_turn_counts_from_eval(eval_path)
                except Exception as e:
                    console.print(f"[red]Error reading {eval_path.name}: {e}[/red]")
                    stats["errors"] += 1
                    continue

                for sample_id, turn_counts in turn_counts_map.items():
                    qa_path = run_dir / sample_id / "qa.json"

                    if not qa_path.exists():
                        stats["missing_qa"] += 1
                        continue

                    if not force:
                        try:
                            data = json.loads(qa_path.read_text())
                            if "turn_counts" in data:
                                stats["skipped"] += 1
                                continue
                        except json.JSONDecodeError as e:
                            console.print(
                                f"[red]Skipping corrupt JSON in {qa_path}: {e}[/red]"
                            )
                            stats["errors"] += 1
                            continue

                    try:
                        patch_qa_json(qa_path, turn_counts)
                        stats["patched"] += 1
                    except Exception as e:
                        console.print(f"[red]Error patching {qa_path}: {e}[/red]")
                        stats["errors"] += 1

            progress.advance(task)

    console.print("\n[bold]Summary:[/bold]\n")
    console.print(f"  Patched: {stats['patched']}")
    console.print(f"  Skipped (already enriched): {stats['skipped']}")
    console.print(f"  Missing qa.json: {stats['missing_qa']}")
    console.print(f"  Errors: {stats['errors']}")
    console.print(
        f"\n[green]✓[/green] Done. {stats['patched']} qa.json files enriched."
    )


if __name__ == "__main__":
    app()
