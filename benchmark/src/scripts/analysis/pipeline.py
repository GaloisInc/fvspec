"""Full pipeline: dedup → extract deps → JSONL dump for HuggingFace upload.

Produces two HuggingFace-idiomatic JSONL files matching the original
Benchify/realpbt schema:
  - pbts.jsonl:      same schema as original, with improved dependency names
  - functions.jsonl:  extracted functions with full source code

Processes the Benchify/realpbt dataset end-to-end:
1. Deduplicates by collapsing forked repositories
2. Drops repos that cannot be cloned (deleted, private, etc.)
3. Clones each repo (with timeout), builds a tree-sitter index
4. Extracts depth-bounded dependencies for each PBT (up to 8 in parallel per repo)
5. Writes pbts.jsonl + functions.jsonl matching the original HF schema

Usage:
    uv run realpbt-pipeline                                # full run
    uv run realpbt-pipeline --limit 10                     # test on 10 repos
    uv run realpbt-pipeline --outdir artifacts/realpbt2    # custom output dir
    uv run realpbt-pipeline --skip-dedup                   # skip deduplication
    uv run realpbt-pipeline --workers 4                    # parallel PBTs per repo
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
)

from scripts.analysis.dedup import _dedup, _load_pbts, _print_stats
from scripts.analysis.extract_deps import (
    build_repo_index,
    clone_repo,
    extract_dependencies,
)

app = typer.Typer(help="Full pipeline: dedup → extract deps → JSONL dump.")
console = Console()

SKIP_BASE_NAMES = frozenset(
    {
        "pytorch",
        "cpython",
        "tensorflow",
        "linux",
        "chromium",
        "gecko-dev",
        "mozilla-unified",
        "keystone",
    }
)


def _group_by_repo(rows: list[dict]) -> dict[str, list[dict]]:
    """Group PBT rows by repo name."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[row["repo"]["name"]].append(row)
    return dict(groups)


def _extract_one_pbt(
    row: dict,
    index: object,
    repo_root: Path,
) -> dict:
    """Extract deps for a single PBT. Returns the row with updated deps."""
    pbt_name = row["name"]
    pbt_code = row["code"]
    source_file = row.get("source_file", "")

    if source_file and source_file.startswith("/"):
        source_file = source_file[1:]

    result = dict(row)  # shallow copy

    if not source_file:
        result["_dep_status"] = "no_source_file"
        return result

    if not (repo_root / source_file).exists():
        # Try to find the file by searching for the PBT name
        try:
            candidates = [
                str(p.relative_to(repo_root))
                for p in repo_root.rglob("*.py")
                if pbt_name in p.read_text(errors="replace")
            ]
        except Exception:
            candidates = []
        if candidates:
            source_file = candidates[0]
        else:
            result["_dep_status"] = "file_not_found"
            return result

    try:
        deps = extract_dependencies(pbt_code, source_file, index, max_depth=2)
    except Exception as e:
        result["_dep_status"] = f"extraction_error: {e}"
        return result

    dep_list = []
    for d in deps:
        dep_list.append(
            {
                "name": d.name,
                "qualified_name": d.qualified_name,
                "code": d.code,
                "file_path": d.file_path,
                "depth": d.depth,
                "kind": d.kind,
                "resolution": d.resolution,
            }
        )

    result["_extracted_deps"] = dep_list
    result["_dep_status"] = "ok"
    return result


def _process_repo(
    repo_name: str,
    pbts: list[dict],
    workers: int,
    clone_timeout: int,
) -> list[dict]:
    """Clone a repo, index it, extract deps for all its PBTs."""
    repo_url = pbts[0]["repo"]["url"]
    clone_dir = Path(tempfile.mkdtemp(prefix="pipeline_"))
    repo_root = clone_dir / "repo"
    out: list[dict] = []

    try:
        success = clone_repo(repo_url, repo_root, timeout_seconds=clone_timeout)
        if not success:
            for row in pbts:
                r = dict(row)
                r["_dep_status"] = "clone_failed"
                out.append(r)
            return out

        index = build_repo_index(repo_root)

        if workers <= 1 or len(pbts) == 1:
            for row in pbts:
                out.append(_extract_one_pbt(row, index, repo_root))
        else:
            with ThreadPoolExecutor(max_workers=min(workers, len(pbts))) as pool:
                futures = {
                    pool.submit(_extract_one_pbt, row, index, repo_root): row
                    for row in pbts
                }
                for future in as_completed(futures):
                    try:
                        out.append(future.result())
                    except Exception:
                        row = futures[future]
                        r = dict(row)
                        r["_dep_status"] = "thread_error"
                        out.append(r)
    finally:
        shutil.rmtree(clone_dir, ignore_errors=True)

    return out


def _row_to_pbt(row: dict) -> dict:
    """Convert an internal row to the pbts.jsonl format (matches original HF schema)."""
    deps = row.get("_extracted_deps", [])
    dep_names = [d["name"] for d in deps]

    return {
        "id": row["id"],
        "name": row["name"],
        "code": row["code"],
        "language": row.get("language", "python"),
        "source_file": row.get("source_file"),
        "start_line": row.get("start_line"),
        "end_line": row.get("end_line"),
        "dependencies": json.dumps(dep_names),
        "repo": row["repo"],
        "metrics": row.get("metrics"),
        "summary": row.get("summary"),
    }


def _deps_to_functions(row: dict, func_id_counter: list[int]) -> list[dict]:
    """Convert extracted deps to functions.jsonl rows (matches original HF schema)."""
    deps = row.get("_extracted_deps", [])
    funcs = []
    for d in deps:
        func_id_counter[0] += 1
        funcs.append(
            {
                "id": func_id_counter[0],
                "name": d["name"],
                "code": d["code"],
                "language": row.get("language", "python"),
                "source_file": d["file_path"],
                "start_line": None,
                "end_line": None,
                "repo": row["repo"],
            }
        )
    return funcs


@app.command()
def main(
    outdir: Path = typer.Option(
        Path("artifacts/realpbt2"),
        help="Output directory (will contain pbts.jsonl + functions.jsonl).",
    ),
    limit: int | None = typer.Option(None, help="Limit to N repos (for testing)."),
    workers: int = typer.Option(8, help="Max parallel PBTs per repo."),
    clone_timeout: int = typer.Option(300, help="Clone timeout in seconds."),
    skip_dedup: bool = typer.Option(
        False, "--skip-dedup", help="Skip deduplication step."
    ),
    skip_large: bool = typer.Option(
        False,
        "--skip-large/--include-large",
        help="Skip notoriously large repos (pytorch, cpython, etc.).",
    ),
) -> None:
    """Full pipeline: dedup → extract deps → JSONL dump."""
    # Step 1: Load and dedup
    rows = _load_pbts()

    if not skip_dedup:
        console.print("\n[bold]Step 1: Deduplication[/bold]")
        rows, stats = _dedup(rows)
        _print_stats(stats)
    else:
        console.print("\n[bold]Step 1: Skipping dedup[/bold]")

    # Step 2: Filter large repos
    if skip_large:
        before = len(rows)
        filtered = []
        for row in rows:
            url = row["repo"]["url"]
            m = re.search(r"github\.com/[^/]+/([^/.]+)", url)
            base = m.group(1).lower() if m else ""
            if base not in SKIP_BASE_NAMES:
                filtered.append(row)
        rows = filtered
        dropped = before - len(rows)
        if dropped:
            console.print(f"  Skipped {dropped:,} PBTs from large repos")

    # Step 3: Group by repo
    groups = _group_by_repo(rows)
    repo_names = sorted(groups.keys())

    if limit:
        repo_names = repo_names[:limit]
        console.print(f"  Limited to {limit} repos")

    total_pbts = sum(len(groups[r]) for r in repo_names)
    console.print(
        f"\n[bold]Step 2: Extract deps for {total_pbts:,} PBTs "
        f"across {len(repo_names):,} repos[/bold]"
    )

    # Step 4: Process repos
    outdir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    ok_count = 0
    fail_count = 0

    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Repos", total=len(repo_names))

        for repo_name in repo_names:
            pbts = groups[repo_name]
            progress.update(task, description=f"{repo_name} ({len(pbts)} PBTs)")

            repo_results = _process_repo(repo_name, pbts, workers, clone_timeout)
            for result in repo_results:
                if result.get("_dep_status") == "ok":
                    results.append(result)
                    ok_count += 1
                else:
                    fail_count += 1

            progress.advance(task)

    # Step 5: Write JSONL files matching original HF schema
    console.print("\n[bold]Step 3: Writing JSONL[/bold]")

    pbts_path = outdir / "pbts.jsonl"
    funcs_path = outdir / "functions.jsonl"
    func_id_counter = [0]

    with open(pbts_path, "w") as pf, open(funcs_path, "w") as ff:
        for row in results:
            pf.write(json.dumps(_row_to_pbt(row)) + "\n")
            for func in _deps_to_functions(row, func_id_counter):
                ff.write(json.dumps(func) + "\n")

    console.print(f"  Wrote {len(results):,} PBTs to {pbts_path}")
    console.print(f"  Wrote {func_id_counter[0]:,} functions to {funcs_path}")
    console.print(
        f"  Dropped {fail_count:,} PBTs (clone failed / file not found / errors)"
    )

    # Stats summary
    dep_counts = [len(r.get("_extracted_deps", [])) for r in results]
    if dep_counts:
        avg = sum(dep_counts) / len(dep_counts)
        median = sorted(dep_counts)[len(dep_counts) // 2]
        console.print(
            f"  Avg deps: {avg:.1f}, Median: {median}, Max: {max(dep_counts)}"
        )


if __name__ == "__main__":
    app()
