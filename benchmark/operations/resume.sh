#!/usr/bin/env bash
# Resume failed chunks from a batch run

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS_DIR="$SCRIPT_DIR/logs"

# Parse arguments
BATCH_ID=""
PARALLELISM=10
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --batch-id)
            BATCH_ID="$2"
            shift 2
            ;;
        --parallelism)
            PARALLELISM="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 --batch-id <id> [--parallelism <n>] [--dry-run]"
            exit 1
            ;;
    esac
done

# Validate required arguments
if [[ -z "$BATCH_ID" ]]; then
    echo "Error: --batch-id is required"
    echo "Usage: $0 --batch-id <id> [--parallelism <n>] [--dry-run]"
    exit 1
fi

echo "================================================"
echo "Resume Failed Chunks"
echo "================================================"
echo "Batch ID:     $BATCH_ID"
echo "Parallelism:  $PARALLELISM"
echo "Dry run:      $DRY_RUN"
echo "================================================"
echo ""

# Find failed chunks
STATUS_FILES=("$LOGS_DIR"/chunk__${BATCH_ID}__*.status)

if [[ ! -e "${STATUS_FILES[0]}" ]]; then
    echo "No chunks found for batch: $BATCH_ID"
    exit 1
fi

FAILED_CHUNKS=()
for status_file in "${STATUS_FILES[@]}"; do
    if [[ ! -f "$status_file" ]]; then
        continue
    fi

    # Parse status file
    source "$status_file"

    if [[ "$status" == "FAILED" ]]; then
        FAILED_CHUNKS+=("$status_file")
        echo "Found failed chunk: [$start_idx, $end_idx)"
    fi
done

if [[ ${#FAILED_CHUNKS[@]} -eq 0 ]]; then
    echo ""
    echo "✓ No failed chunks to resume"
    exit 0
fi

echo ""
echo "Total failed chunks: ${#FAILED_CHUNKS[@]}"
echo ""

if [[ "$DRY_RUN" == "true" ]]; then
    echo "Dry run - would resume these chunks"
    exit 0
fi

read -p "Resume these failed chunks? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled"
    exit 0
fi

echo ""
echo "Resuming failed chunks..."
echo ""

# Resume each failed chunk
for status_file in "${FAILED_CHUNKS[@]}"; do
    # Parse status file to get parameters
    source "$status_file"

    # Create new session name (add retry suffix)
    RETRY_TIMESTAMP=$(date +%Y%m%d-%H%M%S)
    SESSION_NAME="fvspec_${variant}_${start_idx}-${end_idx}_retry_${RETRY_TIMESTAMP}"

    echo "Resuming chunk [$start_idx, $end_idx) -> $SESSION_NAME"

    # Check if session already exists
    if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
        echo "  WARNING: Session $SESSION_NAME already exists, skipping..."
        continue
    fi

    # Archive old status file
    mv "$status_file" "${status_file}.failed"

    # Create new tmux session
    tmux new-session -d -s "$SESSION_NAME" \
        "bash '$SCRIPT_DIR/run-chunk.sh' \
            --variant '$variant' \
            --start-idx $start_idx \
            --end-idx $end_idx \
            --parallelism $PARALLELISM \
            --batch-id '${BATCH_ID}_retry'"

    echo "  ✓ Session created: $SESSION_NAME"
done

echo ""
echo "================================================"
echo "Resume complete!"
echo "================================================"
echo ""
echo "Monitor with: ./operations/monitor.sh --batch-id ${BATCH_ID}_retry"
