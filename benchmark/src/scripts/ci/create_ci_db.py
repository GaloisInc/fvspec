"""Create pbts_ci.db - a small subset of pbts_full.db for CI testing.

Randomly samples 64 PBTs that each have <32 associated functions,
including all related table entries.
"""

import random
import sqlite3
from pathlib import Path

import typer

from generate.config import DATA_DIR

DOT_GITHUB = Path.cwd() / ".." / ".github"

app = typer.Typer()


def get_pbts_with_function_counts(conn: sqlite3.Connection) -> list[tuple[int, int]]:
    """Get all PBT IDs with their associated function counts.

    Args:
        conn: Database connection to pbts_full.db

    Returns:
        List of (pbt_id, function_count) tuples
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, COUNT(pf.function_name) as func_count
        FROM pbts p
        LEFT JOIN pbt_functions pf ON p.id = pf.pbt_id
        GROUP BY p.id
        HAVING func_count < 32
        ORDER BY p.id
    """)
    return cursor.fetchall()


def create_ci_database(
    source_db: Path,
    target_db: Path,
    sample_size: int = 64,
    ranseed: int = 42,
) -> None:
    """Create CI subset database by sampling from full database.

    Args:
        source_db: Path to pbts_full.db
        target_db: Path to output pbts_ci.db
        sample_size: Number of PBTs to sample (default: 64)
        ranseed: Random seed for reproducibility (default: 42)
    """
    random.seed(ranseed)

    # Delete existing target database
    if target_db.exists():
        print(f"Removing existing {target_db}")
        target_db.unlink()

    # Create empty target database with schema
    print(f"Creating new database {target_db}")
    target_conn = sqlite3.connect(target_db)
    target_cursor = target_conn.cursor()

    # Create schema (get from source)
    source_conn = sqlite3.connect(source_db)
    source_cursor = source_conn.cursor()

    print("Creating schema...")
    source_cursor.execute(
        "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND type='table' AND name != 'sqlite_sequence'"
    )
    for (sql,) in source_cursor.fetchall():
        if sql:
            target_cursor.execute(sql)

    # Create indices
    source_cursor.execute(
        "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND type='index'"
    )
    for (sql,) in source_cursor.fetchall():
        if sql and not sql.startswith(
            "CREATE UNIQUE INDEX"
        ):  # Skip auto-generated indices
            try:
                target_cursor.execute(sql)
            except sqlite3.OperationalError:
                pass  # Index might already exist

    target_conn.commit()

    try:
        # Get PBTs with <32 functions
        print("Finding PBTs with <32 associated functions...")
        pbts_with_counts = get_pbts_with_function_counts(source_conn)
        print(f"Found {len(pbts_with_counts)} PBTs with <32 functions")

        if len(pbts_with_counts) < sample_size:
            print(f"WARNING: Only {len(pbts_with_counts)} PBTs available, sampling all")
            sample_size = len(pbts_with_counts)

        # Random sample
        sampled_pbts = random.sample(pbts_with_counts, sample_size)
        sampled_pbt_ids = [pbt_id for pbt_id, _ in sampled_pbts]
        print(f"Sampled {len(sampled_pbt_ids)} PBTs")

        # Get all associated repo_ids
        source_cursor = source_conn.cursor()
        placeholders = ",".join("?" * len(sampled_pbt_ids))
        source_cursor.execute(
            f"SELECT DISTINCT repo_id FROM pbts WHERE id IN ({placeholders})",
            sampled_pbt_ids,
        )
        repo_ids = [row[0] for row in source_cursor.fetchall()]
        print(f"Found {len(repo_ids)} associated repos")

        # Copy repos
        print("Copying repos...")
        repo_placeholders = ",".join("?" * len(repo_ids))
        source_cursor.execute(
            f"SELECT * FROM repos WHERE id IN ({repo_placeholders})", repo_ids
        )
        repos_data = source_cursor.fetchall()
        target_cursor.executemany(
            """INSERT INTO repos
               (id, source, name, url, license, license_status, stars, forks, parsed_at, hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            repos_data,
        )
        print(f"  Copied {len(repos_data)} repos")

        # Copy pbts
        print("Copying PBTs...")
        source_cursor.execute(
            f"SELECT * FROM pbts WHERE id IN ({placeholders})", sampled_pbt_ids
        )
        pbts_data = source_cursor.fetchall()
        target_cursor.executemany(
            """INSERT INTO pbts
               (id, repo_id, name, code, source_file, start_line, end_line,
                original_id, dep_names, deps, source, summary, hash, summary_vector,
                mode, summaryversion, summaryconfidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            pbts_data,
        )
        print(f"  Copied {len(pbts_data)} PBTs")

        # Get all associated function names
        source_cursor.execute(
            f"SELECT DISTINCT function_name FROM pbt_functions WHERE pbt_id IN ({placeholders})",
            sampled_pbt_ids,
        )
        function_names = [row[0] for row in source_cursor.fetchall()]
        print(f"Found {len(function_names)} associated function names")

        # Copy functions
        if function_names:
            print("Copying functions...")
            func_placeholders = ",".join("?" * len(function_names))
            source_cursor.execute(
                f"""SELECT DISTINCT * FROM functions
                    WHERE name IN ({func_placeholders}) AND repo_id IN ({repo_placeholders})""",
                function_names + repo_ids,
            )
            functions_data = source_cursor.fetchall()
            if functions_data:
                target_cursor.executemany(
                    """INSERT OR IGNORE INTO functions
                       (id, repo_id, name, code, source_file, start_line, end_line)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    functions_data,
                )
                print(f"  Copied {len(functions_data)} functions")

        # Copy pbt_functions
        print("Copying pbt_functions...")
        source_cursor.execute(
            f"SELECT * FROM pbt_functions WHERE pbt_id IN ({placeholders})",
            sampled_pbt_ids,
        )
        pbt_functions_data = source_cursor.fetchall()
        target_cursor.executemany(
            """INSERT INTO pbt_functions (pbt_id, function_name)
               VALUES (?, ?)""",
            pbt_functions_data,
        )
        print(f"  Copied {len(pbt_functions_data)} pbt_function associations")

        # Copy radon_metrics if they exist
        print("Copying radon_metrics...")
        source_cursor.execute(
            f"SELECT * FROM radon_metrics WHERE pbt_id IN ({placeholders})",
            sampled_pbt_ids,
        )
        radon_data = source_cursor.fetchall()
        if radon_data:
            target_cursor.executemany(
                """INSERT INTO radon_metrics
                   (pbt_id, loc, sloc, lloc, comments, blank, multi, single_comments,
                    num_functions, avg_complexity, max_complexity, total_complexity,
                    complexity_rank, maintainability_index, maintainability_rank,
                    halstead_vocabulary, halstead_length, halstead_volume,
                    halstead_difficulty, halstead_effort, halstead_time, halstead_bugs)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                radon_data,
            )
            print(f"  Copied {len(radon_data)} radon_metrics entries")
        else:
            print("  No radon_metrics entries found")

        # Copy processing_status if exists
        print("Copying processing_status...")
        source_cursor.execute(
            f"SELECT * FROM processing_status WHERE repo_id IN ({repo_placeholders})",
            repo_ids,
        )
        status_data = source_cursor.fetchall()
        if status_data:
            target_cursor.executemany(
                """INSERT INTO processing_status (repo_id, status, last_attempt, error_message)
                   VALUES (?, ?, ?, ?)""",
                status_data,
            )
            print(f"  Copied {len(status_data)} processing_status entries")
        else:
            print("  No processing_status entries found")

        # Commit all changes
        target_conn.commit()

        # Print summary statistics
        print("\n=== Summary ===")
        target_cursor.execute("SELECT COUNT(*) FROM repos")
        print(f"Repos: {target_cursor.fetchone()[0]}")
        target_cursor.execute("SELECT COUNT(*) FROM pbts")
        print(f"PBTs: {target_cursor.fetchone()[0]}")
        target_cursor.execute("SELECT COUNT(*) FROM functions")
        print(f"Functions: {target_cursor.fetchone()[0]}")
        target_cursor.execute("SELECT COUNT(*) FROM pbt_functions")
        print(f"PBT-Function associations: {target_cursor.fetchone()[0]}")
        target_cursor.execute("SELECT COUNT(*) FROM radon_metrics")
        print(f"Radon metrics: {target_cursor.fetchone()[0]}")

        print(f"\n✓ Successfully created {target_db}")

    finally:
        source_conn.close()
        target_conn.close()


@app.command()
def main(
    source: Path = typer.Option(DATA_DIR / "pbts_full.db", help="Source database path"),
    target: Path = typer.Option(DOT_GITHUB / "pbts_ci.db", help="Target database path"),
    sample_size: int = typer.Option(64, help="Number of PBTs to sample"),
    seed: int = typer.Option(42, help="Random seed for reproducibility"),
) -> None:
    """Create pbts_ci.db subset from pbts_full.db."""
    if not source.exists():
        print(f"ERROR: Source database not found: {source}")
        raise typer.Exit(code=1)

    create_ci_database(
        source_db=source,
        target_db=target,
        sample_size=sample_size,
        ranseed=seed,
    )


if __name__ == "__main__":
    app()
