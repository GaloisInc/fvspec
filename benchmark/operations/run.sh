#!/usr/bin/env bash
# Run fvspec and automatically retry on crash until all samples complete.
#
# Usage:
#   ./operations/run.sh                          # defaults: -n 250 -s 100
#   ./operations/run.sh -n 10000 -s 100          # 10k samples
#   ./operations/run.sh -n 10000 -s 100 -p 16    # custom parallelism
#
# All arguments are forwarded to `uv run fvspec`.
# On crash, finds the .eval file and retries incomplete samples in a loop.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

ARGS=("$@")
if [ ${#ARGS[@]} -eq 0 ]; then
    ARGS=(-n 250 -s 100)
fi

MAX_RETRIES=50
attempt=0

echo "=== fvspec run started at $(date) ==="
echo "Args: ${ARGS[*]}"
echo "Max retries: $MAX_RETRIES"
echo ""

# Initial run
echo "--- Attempt $((attempt + 1)): fresh run ---"
if uv run fvspec "${ARGS[@]}"; then
    echo "=== Run completed successfully at $(date) ==="
    exit 0
fi

echo "Run crashed at $(date). Looking for .eval file to retry..."

# Find the most recent .eval file
while [ $attempt -lt $MAX_RETRIES ]; do
    attempt=$((attempt + 1))

    eval_file=$(find artifacts/runs -name "*.eval" -printf "%T@ %p\n" 2>/dev/null \
        | sort -rn | head -1 | cut -d' ' -f2-)

    if [ -z "$eval_file" ]; then
        echo "No .eval file found. Cannot retry."
        exit 1
    fi

    echo ""
    echo "--- Attempt $((attempt + 1)): retrying $eval_file ---"
    if uv run fvspec retry "$eval_file"; then
        echo "=== Retry completed successfully at $(date) ==="
        exit 0
    fi

    echo "Retry crashed at $(date). Will retry again..."
    sleep 5
done

echo "=== Exhausted $MAX_RETRIES retries. Giving up. ==="
exit 1
