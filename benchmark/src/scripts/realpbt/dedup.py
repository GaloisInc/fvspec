"""Deduplicate the RealPBT dataset by collapsing forked repositories.

Repos are grouped by the base repository name extracted from their GitHub URL
(e.g. "SunsetMkt/pytorch" and "njzjz/pytorch" both have base name "pytorch").
Within each group, a canonical repo is chosen (highest star count, then most
PBTs, then lowest repo id as tiebreaker). PBTs from non-canonical repos are
dropped unless they have unique code not present in the canonical repo's PBTs.

Input:  Benchify/realpbt HuggingFace dataset (downloaded automatically)
Output: A new SQLite database matching the pbts_full.db schema

Usage:
    uv run dedup-realpbt                         # default output
    uv run dedup-realpbt --output path/to/out.db # custom output
    uv run dedup-realpbt --dry-run               # just print stats
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

import typer
from datasets import Dataset, load_dataset
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Deduplicate RealPBT by collapsing forked repos.")
console = Console()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_repo_name(github_url: str) -> str:
    """Extract the base repository name from a GitHub URL.

    >>> _base_repo_name("https://github.com/SunsetMkt/pytorch.git")
    'pytorch'
    >>> _base_repo_name("https://github.com/PortablePy/3.10.8.0.git")
    '3.10.8.0'
    """
    m = re.search(r"github\.com/[^/]+/([^/.]+)", github_url)
    if m:
        return m.group(1).lower()
    # Fallback: last path segment
    return github_url.rstrip("/").rsplit("/", 1)[-1].lower().removesuffix(".git")


def _code_fingerprint(code: str) -> str:
    """Content-hash for PBT dedup within a fork group.

    We normalize whitespace so trivially reformatted forks still dedup.
    """
    normalized = " ".join(code.split())
    return hashlib.sha256(normalized.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _load_pbts() -> list[dict]:
    """Load PBTs from HuggingFace into a list of dicts."""
    console.print("[bold]Loading PBTs from HuggingFace...[/bold]")
    ds = load_dataset("Benchify/realpbt", data_files="pbts.jsonl", split="train")
    assert isinstance(ds, Dataset)
    rows = list(ds)
    console.print(f"  Loaded {len(rows):,} PBTs")
    return rows


def _group_repos(rows: list[dict]) -> dict[str, list[dict]]:
    """Group repos by base name. Returns {base_name: [repo_info_dicts]}."""
    # Collect unique repos
    repos: dict[str, dict] = {}  # repo_name -> repo info + pbt_count
    for row in rows:
        rname = row["repo"]["name"]
        if rname not in repos:
            repos[rname] = {
                "name": rname,
                "url": row["repo"]["url"],
                "license": row["repo"]["license"],
                "stars": row["repo"]["stars"] or 0,
                "forks": row["repo"]["forks"] or 0,
                "pbt_count": 0,
            }
        repos[rname]["pbt_count"] += 1

    # Group by base name
    groups: dict[str, list[dict]] = defaultdict(list)
    for repo_info in repos.values():
        base = _base_repo_name(repo_info["url"])
        groups[base].append(repo_info)

    return dict(groups)


def _pick_canonical(group: list[dict]) -> str:
    """Pick the canonical repo from a fork group.

    Priority: most stars > most PBTs > alphabetically first name.
    """
    group.sort(key=lambda r: (-r["stars"], -r["pbt_count"], r["name"]))
    return group[0]["name"]


def _dedup(rows: list[dict]) -> tuple[list[dict], dict]:
    """Deduplicate PBTs. Returns (kept_rows, stats)."""
    groups = _group_repos(rows)

    # Determine canonical repo per group
    canonical_map: dict[str, str] = {}  # repo_name -> canonical_name
    canonical_repos: set[str] = set()
    for _base, group in groups.items():
        canon = _pick_canonical(group)
        canonical_repos.add(canon)
        for repo_info in group:
            canonical_map[repo_info["name"]] = canon

    # Pass 1: collect fingerprints from canonical repos
    canonical_fingerprints: dict[str, set[str]] = defaultdict(
        set
    )  # base -> set of hashes
    for row in rows:
        rname = row["repo"]["name"]
        if rname in canonical_repos:
            base = _base_repo_name(row["repo"]["url"])
            fp = _code_fingerprint(row["code"])
            canonical_fingerprints[base].add(fp)

    # Pass 2: keep canonical PBTs + unique non-canonical PBTs
    kept: list[dict] = []
    stats = {
        "total_input": len(rows),
        "total_repos_input": len({r["repo"]["name"] for r in rows}),
        "fork_groups": sum(1 for g in groups.values() if len(g) > 1),
        "singleton_groups": sum(1 for g in groups.values() if len(g) == 1),
        "dropped_duplicate": 0,
        "kept_canonical": 0,
        "kept_unique_from_fork": 0,
    }

    for row in rows:
        rname = row["repo"]["name"]
        if rname in canonical_repos:
            kept.append(row)
            stats["kept_canonical"] += 1
        else:
            # Non-canonical: keep only if code is unique to this fork
            base = _base_repo_name(row["repo"]["url"])
            fp = _code_fingerprint(row["code"])
            if fp not in canonical_fingerprints[base]:
                kept.append(row)
                canonical_fingerprints[base].add(fp)  # don't keep further dupes
                stats["kept_unique_from_fork"] += 1
            else:
                stats["dropped_duplicate"] += 1

    stats["total_output"] = len(kept)
    stats["total_repos_output"] = len({r["repo"]["name"] for r in kept})
    return kept, stats


# ---------------------------------------------------------------------------
# SQLite output
# ---------------------------------------------------------------------------


def _write_sqlite(rows: list[dict], db_path: Path) -> None:
    """Write deduped PBTs to a SQLite database matching pbts_full.db schema."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    # Create tables matching the existing schema exactly
    cur.executescript("""
        CREATE TABLE repos (
            id INTEGER PRIMARY KEY,
            source TEXT,
            name TEXT,
            url TEXT,
            license TEXT,
            license_status TEXT,
            stars INTEGER,
            forks INTEGER,
            parsed_at TEXT,
            hash TEXT
        );

        CREATE TABLE pbts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_id INTEGER,
            name TEXT,
            code TEXT,
            source_file TEXT,
            start_line INTEGER,
            end_line INTEGER,
            original_id INTEGER,
            dep_names TEXT,
            deps TEXT,
            source TEXT,
            summary TEXT,
            hash TEXT,
            summary_vector TEXT,
            mode TEXT,
            summaryversion INTEGER,
            summaryconfidence REAL,
            FOREIGN KEY (repo_id) REFERENCES repos(id)
        );

        CREATE TABLE unit_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_id INTEGER,
            name TEXT,
            code TEXT,
            source_file TEXT,
            start_line INTEGER,
            end_line INTEGER,
            FOREIGN KEY (repo_id) REFERENCES repos(id)
        );

        CREATE TABLE functions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_id INTEGER,
            name TEXT,
            code TEXT,
            source_file TEXT,
            start_line INTEGER,
            end_line INTEGER,
            FOREIGN KEY (repo_id) REFERENCES repos(id)
        );

        CREATE TABLE pbt_functions (
            pbt_id INTEGER,
            function_name TEXT,
            FOREIGN KEY (pbt_id) REFERENCES pbts(id),
            PRIMARY KEY (pbt_id, function_name)
        );

        CREATE TABLE unit_test_functions (
            unit_test_id INTEGER,
            function_name TEXT,
            FOREIGN KEY (unit_test_id) REFERENCES unit_tests(id),
            PRIMARY KEY (unit_test_id, function_name)
        );

        CREATE TABLE processing_status (
            repo_id INTEGER PRIMARY KEY,
            status TEXT,
            last_attempt TEXT,
            error_message TEXT,
            FOREIGN KEY (repo_id) REFERENCES repos(id)
        );

        CREATE TABLE radon_metrics (
            pbt_id INTEGER NOT NULL PRIMARY KEY,
            loc INTEGER NOT NULL,
            sloc INTEGER NOT NULL,
            lloc INTEGER NOT NULL,
            comments INTEGER NOT NULL,
            blank INTEGER NOT NULL,
            multi INTEGER NOT NULL,
            single_comments INTEGER NOT NULL,
            num_functions INTEGER NOT NULL,
            avg_complexity FLOAT NOT NULL,
            max_complexity INTEGER NOT NULL,
            total_complexity INTEGER NOT NULL,
            complexity_rank VARCHAR NOT NULL,
            maintainability_index FLOAT NOT NULL,
            maintainability_rank VARCHAR NOT NULL,
            halstead_vocabulary INTEGER NOT NULL,
            halstead_length INTEGER NOT NULL,
            halstead_volume FLOAT NOT NULL,
            halstead_difficulty FLOAT NOT NULL,
            halstead_effort FLOAT NOT NULL,
            halstead_time FLOAT NOT NULL,
            halstead_bugs FLOAT NOT NULL,
            FOREIGN KEY(pbt_id) REFERENCES pbts(id)
        );

        CREATE INDEX idx_pbts_repo ON pbts(repo_id);
        CREATE INDEX idx_unit_tests_repo ON unit_tests(repo_id);
        CREATE INDEX idx_functions_repo ON functions(repo_id);
        CREATE INDEX idx_pbt_functions_pbt ON pbt_functions(pbt_id);
        CREATE INDEX idx_pbt_functions_name ON pbt_functions(function_name);
        CREATE INDEX idx_unit_test_functions_test ON unit_test_functions(unit_test_id);
        CREATE INDEX idx_unit_test_functions_name ON unit_test_functions(function_name);
    """)

    # Insert repos (assign new sequential ids)
    seen_repos: dict[str, int] = {}  # repo_name -> new repo_id
    repo_id_seq = 0
    for row in rows:
        rname = row["repo"]["name"]
        if rname not in seen_repos:
            repo_id_seq += 1
            seen_repos[rname] = repo_id_seq
            r = row["repo"]
            cur.execute(
                "INSERT INTO repos (id, name, url, license, stars, forks) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (repo_id_seq, rname, r["url"], r["license"], r["stars"], r["forks"]),
            )

    # Insert PBTs (new sequential ids, mapped repo_id)
    # The HF dataset has: id, name, code, language, source_file, start_line,
    # end_line, dependencies, repo, metrics, summary
    # The DB schema expects: repo_id, name, code, source_file, start_line,
    # end_line, original_id, dep_names, deps, source, summary
    for row in rows:
        repo_id = seen_repos[row["repo"]["name"]]
        # The HF 'dependencies' field is a JSON string of dep *names*.
        # In the DB schema, dep_names holds names and deps holds code.
        # HF only has names; deps code is not available in the HF export.
        dep_names = row.get("dependencies", "[]")
        cur.execute(
            "INSERT INTO pbts "
            "(repo_id, name, code, source_file, start_line, end_line, "
            "original_id, dep_names, deps, summary) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                repo_id,
                row["name"],
                row["code"],
                row.get("source_file"),
                row.get("start_line"),
                row.get("end_line"),
                row["id"],  # preserve original HF id
                dep_names,
                "[]",  # deps code not in HF export
                row.get("summary"),
            ),
        )

    # Insert radon metrics where available
    # Re-query to get new pbt ids mapped to original ids
    cur.execute("SELECT id, original_id FROM pbts")
    orig_to_new: dict[int, int] = {}
    for new_id, orig_id in cur.fetchall():
        if orig_id is not None:
            orig_to_new[orig_id] = new_id

    for row in rows:
        m = row.get("metrics")
        if not m or row["id"] not in orig_to_new:
            continue
        new_id = orig_to_new[row["id"]]
        cur.execute(
            "INSERT OR IGNORE INTO radon_metrics "
            "(pbt_id, loc, sloc, lloc, comments, blank, multi, "
            "single_comments, num_functions, avg_complexity, max_complexity, "
            "total_complexity, complexity_rank, maintainability_index, "
            "maintainability_rank, halstead_vocabulary, halstead_length, "
            "halstead_volume, halstead_difficulty, halstead_effort, "
            "halstead_time, halstead_bugs) "
            "VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0, ?, ?, 0, '', ?, '', "
            "0, 0, 0, ?, ?, 0, 0)",
            (
                new_id,
                m.get("loc", 0),
                m.get("sloc", 0),
                m.get("lloc", 0),
                m.get("comments", 0),
                m.get("avg_complexity", 0),
                int(m.get("max_complexity", 0)),
                m.get("maintainability_index", 0),
                m.get("halstead_difficulty", 0),
                m.get("halstead_effort", 0),
            ),
        )

    conn.commit()

    # Summary counts
    pbt_count = cur.execute("SELECT COUNT(*) FROM pbts").fetchone()[0]
    repo_count = cur.execute("SELECT COUNT(*) FROM repos").fetchone()[0]
    conn.close()

    console.print(
        f"[green]Wrote {pbt_count:,} PBTs across {repo_count:,} repos "
        f"to {db_path}[/green]"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print_stats(stats: dict) -> None:
    """Pretty-print dedup statistics."""
    table = Table(title="Deduplication Results")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Input PBTs", f"{stats['total_input']:,}")
    table.add_row("Input repos", f"{stats['total_repos_input']:,}")
    table.add_row("Fork clusters (>1 repo)", f"{stats['fork_groups']:,}")
    table.add_row("Singleton repos", f"{stats['singleton_groups']:,}")
    table.add_row("", "")
    table.add_row("Kept (canonical repos)", f"{stats['kept_canonical']:,}")
    table.add_row("Kept (unique from forks)", f"{stats['kept_unique_from_fork']:,}")
    table.add_row("Dropped (duplicate)", f"{stats['dropped_duplicate']:,}")
    table.add_row("", "")
    table.add_row("[bold]Output PBTs[/bold]", f"[bold]{stats['total_output']:,}[/bold]")
    table.add_row(
        "[bold]Output repos[/bold]", f"[bold]{stats['total_repos_output']:,}[/bold]"
    )
    table.add_row(
        "Reduction",
        f"{100 * (1 - stats['total_output'] / stats['total_input']):.1f}%",
    )

    console.print(table)


@app.command()
def main(
    output: Path = typer.Option(
        Path("benchmark/data/realpbt_deduped.db"),
        help="Output SQLite path.",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print stats without writing DB."
    ),
) -> None:
    """Deduplicate RealPBT by collapsing forked repositories."""
    rows = _load_pbts()
    kept, stats = _dedup(rows)
    _print_stats(stats)

    if not dry_run:
        _write_sqlite(kept, output)


if __name__ == "__main__":
    app()
