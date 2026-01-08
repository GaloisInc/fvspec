#!/usr/bin/env python3
"""Check and fix .eval file statuses to enable retry.

According to inspect docs, eval-retry works with partially complete evals.
We need to change status from "started" to "error" to trigger retry.
"""

import json
import shutil
import tempfile
import zipfile
from pathlib import Path


def check_eval_file(eval_path):
    """Check the status and progress of an eval file."""
    try:
        with zipfile.ZipFile(eval_path, "r") as z:
            if "header.json" not in z.namelist():
                return None, "CORRUPTED", 0, 0

            header = json.loads(z.read("header.json"))
            status = header.get("status", "unknown")

            # Count samples in the log
            eval_data = header.get("eval", {})
            dataset = eval_data.get("dataset", {})
            total = dataset.get("samples", 0)

            # Try to count completed samples from results
            results = header.get("results", {})
            scores = results.get("scores", [])
            completed = len([s for s in scores if s is not None])

            return header, status, completed, total
    except Exception as e:
        return None, f"ERROR: {e}", 0, 0


def fix_eval_status(eval_path, dry_run=True):
    """Change status from 'started' to 'error' to enable retry."""
    header, status, completed, total = check_eval_file(eval_path)

    if header is None:
        print(f"  ✗ Skipping {eval_path.name}: {status}")
        return False

    if status == "success":
        print(f"  ✓ Already complete: {eval_path.name}")
        return False

    if status in ["started", "cancelled"]:
        print(f"  ! Found {status}: {eval_path.name} ({completed}/{total} samples)")

        if not dry_run:
            # Extract to temp dir
            with tempfile.TemporaryDirectory() as tmpdir:
                tmppath = Path(tmpdir)

                # Extract all files
                with zipfile.ZipFile(eval_path, "r") as z:
                    z.extractall(tmppath)

                # Modify header
                header_path = tmppath / "header.json"
                with open(header_path) as f:
                    header_data = json.load(f)

                old_status = header_data["status"]
                header_data["status"] = "error"

                with open(header_path, "w") as f:
                    json.dump(header_data, f, indent=2)

                # Repack the zip
                backup_path = eval_path.with_suffix(".eval.bak")
                shutil.copy(eval_path, backup_path)

                with zipfile.ZipFile(eval_path, "w", zipfile.ZIP_DEFLATED) as z:
                    for file in tmppath.rglob("*"):
                        if file.is_file():
                            z.write(file, file.relative_to(tmppath))

                print(
                    f"    → Changed {old_status} → error (backup: {backup_path.name})"
                )
                return True
        else:
            print(f"    → Would change {status} → error")
            return True

    return False


def main():
    """CLI entry point for fixing .eval file statuses."""
    import argparse

    parser = argparse.ArgumentParser(description="Fix .eval file statuses for retry")
    parser.add_argument(
        "path", help="Path to artifacts directory or specific .eval file"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be changed"
    )
    parser.add_argument("--fix", action="store_true", help="Actually fix the files")
    args = parser.parse_args()

    path = Path(args.path)
    dry_run = not args.fix

    if dry_run:
        print("DRY RUN MODE - use --fix to actually modify files")
        print()

    # Find .eval files
    if path.is_file() and path.suffix == ".eval":
        eval_files = [path]
    else:
        eval_files = sorted(path.rglob("*.eval"))

    print(f"Found {len(eval_files)} .eval files")
    print()

    fixed_count = 0
    for eval_file in eval_files:
        if fix_eval_status(eval_file, dry_run=dry_run):
            fixed_count += 1

    print()
    print(f"Summary: {fixed_count} files {'would be' if dry_run else 'were'} fixed")

    if dry_run and fixed_count > 0:
        print()
        print("Run with --fix to apply changes:")
        print(f"  uv run fix_eval_status {args.path} --fix")


if __name__ == "__main__":
    main()
