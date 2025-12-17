#!/usr/bin/env bash
# Orchestrate large batch runs across multiple tmux sessions
# Usage: ./run-batch.sh --variant control-functional --total 1000 --chunk-size 50

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCHMARK_DIR="$(dirname "$SCRIPT_DIR")"
LOGS_DIR="$SCRIPT_DIR/logs"

# Default values
VARIANT="control-functional"
TOTAL_SAMPLES=53408  # Full eligible dataset (54,345 total - 937 filtered)
CHUNK_SIZE=500
PARALLELISM=10
LAUNCH_DELAY=2  # Seconds to wait between launching tmux sessions
DRY_RUN=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --variant)
            VARIANT="$2"
            shift 2
            ;;
        --total)
            TOTAL_SAMPLES="$2"
            shift 2
            ;;
        --chunk-size)
            CHUNK_SIZE="$2"
            shift 2
            ;;
        --parallelism)
            PARALLELISM="$2"
            shift 2
            ;;
        --launch-delay)
            LAUNCH_DELAY="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 --variant <variant> --total <n> [--chunk-size <n>] [--parallelism <n>] [--launch-delay <seconds>] [--dry-run]"
            exit 1
            ;;
    esac
done

# Validate chunk size
if [[ $CHUNK_SIZE -le 0 ]]; then
    echo "Error: --chunk-size must be positive"
    exit 1
fi

# Calculate number of chunks
NUM_CHUNKS=$(( (TOTAL_SAMPLES + CHUNK_SIZE - 1) / CHUNK_SIZE ))

echo "================================================"
echo "Batch Run Configuration"
echo "================================================"
echo "Variant:       $VARIANT"
echo "Total:         $TOTAL_SAMPLES samples"
echo "Chunk size:    $CHUNK_SIZE samples"
echo "Chunks:        $NUM_CHUNKS"
echo "Parallelism:   $PARALLELISM per chunk"
echo "Launch delay:  ${LAUNCH_DELAY}s between sessions"
echo "Dry run:       $DRY_RUN"
echo "================================================"
echo ""

# Create logs directory
mkdir -p "$LOGS_DIR"

# Create batch metadata file
TIMESTAMP=$(date +%Y-%m-%dT%H-%M-%S)
BATCH_ID="${TIMESTAMP}__${VARIANT}__total-${TOTAL_SAMPLES}"
BATCH_LOG="$LOGS_DIR/batch__${BATCH_ID}.log"

cat > "$BATCH_LOG" <<EOF
Batch Run Started: $(date)
Variant: $VARIANT
Total Samples: $TOTAL_SAMPLES
Chunk Size: $CHUNK_SIZE
Parallelism: $PARALLELISM
Launch Delay: ${LAUNCH_DELAY}s
Num Chunks: $NUM_CHUNKS
EOF

echo "Batch log: $BATCH_LOG"
echo ""

# Launch tmux sessions for each chunk
for (( i=0; i<NUM_CHUNKS; i++ )); do
    START_IDX=$((i * CHUNK_SIZE))
    END_IDX=$(( START_IDX + CHUNK_SIZE ))

    # Don't exceed total samples
    if [[ $END_IDX -gt $TOTAL_SAMPLES ]]; then
        END_IDX=$TOTAL_SAMPLES
    fi

    # Create unique session name
    SESSION_NAME="fvspec_${VARIANT}_${START_IDX}-${END_IDX}"

    # Log chunk info
    echo "Chunk $((i+1))/$NUM_CHUNKS: samples [$START_IDX, $END_IDX) -> tmux session: $SESSION_NAME"
    echo "Chunk $((i+1))/$NUM_CHUNKS: [$START_IDX, $END_IDX) -> $SESSION_NAME" >> "$BATCH_LOG"

    if [[ "$DRY_RUN" == "true" ]]; then
        continue
    fi

    # Check if session already exists
    if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
        echo "  WARNING: Session $SESSION_NAME already exists, skipping..."
        continue
    fi

    # Create new tmux session running the chunk worker script
    tmux new-session -d -s "$SESSION_NAME" \
        "bash '$SCRIPT_DIR/run-chunk.sh' \
            --variant '$VARIANT' \
            --start-idx $START_IDX \
            --end-idx $END_IDX \
            --parallelism $PARALLELISM \
            --batch-id '$BATCH_ID'"

    echo "  ✓ Session created: $SESSION_NAME"

    # Rate limit: wait before launching next session (except for last chunk)
    if [[ $((i+1)) -lt $NUM_CHUNKS ]] && [[ $LAUNCH_DELAY -gt 0 ]]; then
        sleep "$LAUNCH_DELAY"
    fi
done

echo ""
echo "================================================"
echo "All chunks launched!"
echo "================================================"
echo ""
echo "Commands:"
echo "  Monitor:       ./operations/monitor.sh --batch-id $BATCH_ID --watch"
echo "  Find crashes:  ./operations/find-crashes.sh --batch-id $BATCH_ID"
echo "  List sessions: tmux ls | grep fvspec_${VARIANT}"
echo "  Attach:        tmux attach -t <session-name>"
echo "  Kill all:      ./operations/kill-all.sh --variant $VARIANT"
echo ""
echo "Logs stored in: $LOGS_DIR/"
echo "Batch log:      $BATCH_LOG"
