#!/usr/bin/env bash
# Orchestrate large batch runs across multiple tmux sessions
# Usage: ./run-batch.sh --variant control-functional --total 1000 --chunk-size 50

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCHMARK_DIR="$(dirname "$SCRIPT_DIR")"
LOGS_DIR="$SCRIPT_DIR/logs"

# Source done.txt filtering library
source "$SCRIPT_DIR/lib/done-filter.sh"

# Default values
VARIANT="control-functional"
TOTAL_SAMPLES=53408  # Full eligible dataset (54,345 total - 937 filtered)
CHUNK_SIZE=250
PARALLELISM=10
LAUNCH_DELAY=2  # Seconds to wait between launching tmux sessions
DRY_RUN=false
START_IDX=""  # Optional: starting index (0-indexed, inclusive)
END_IDX=""    # Optional: ending index (0-indexed, exclusive)
DONE_FILE="./operations/done.txt"  # Manifest of completed ranges

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
        --start-idx)
            START_IDX="$2"
            shift 2
            ;;
        --end-idx)
            END_IDX="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --done-file)
            DONE_FILE="$2"
            shift 2
            ;;
        --skip-done-check)
            DONE_FILE=""
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 --variant <variant> [--total <n>] [--start-idx <n>] [--end-idx <n>] [--chunk-size <n>] [--parallelism <n>] [--launch-delay <seconds>] [--dry-run] [--done-file <path>] [--skip-done-check]"
            exit 1
            ;;
    esac
done

# Validate chunk size
if [[ $CHUNK_SIZE -le 0 ]]; then
    echo "Error: --chunk-size must be positive"
    exit 1
fi

# Handle start/end indices
# If START_IDX is provided, use it; otherwise default to 0
# If END_IDX is provided, use it; otherwise use TOTAL_SAMPLES
RANGE_START=${START_IDX:-0}
RANGE_END=${END_IDX:-$TOTAL_SAMPLES}

# Validate range
if [[ $RANGE_START -lt 0 ]]; then
    echo "Error: --start-idx must be non-negative"
    exit 1
fi

if [[ $RANGE_END -le $RANGE_START ]]; then
    echo "Error: --end-idx must be greater than --start-idx"
    exit 1
fi

# Calculate range size and number of chunks
RANGE_SIZE=$((RANGE_END - RANGE_START))
NUM_CHUNKS=$(( (RANGE_SIZE + CHUNK_SIZE - 1) / CHUNK_SIZE ))

echo "================================================"
echo "Batch Run Configuration"
echo "================================================"
echo "Variant:       $VARIANT"
if [[ -n "$START_IDX" ]] || [[ -n "$END_IDX" ]]; then
    echo "Index range:   [$RANGE_START, $RANGE_END) ($RANGE_SIZE samples)"
else
    echo "Total:         $TOTAL_SAMPLES samples"
fi
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
if [[ -n "$START_IDX" ]] || [[ -n "$END_IDX" ]]; then
    BATCH_ID="${TIMESTAMP}__${VARIANT}__range-${RANGE_START}-${RANGE_END}"
else
    BATCH_ID="${TIMESTAMP}__${VARIANT}__total-${TOTAL_SAMPLES}"
fi
BATCH_LOG="$LOGS_DIR/batch__${BATCH_ID}.log"

cat > "$BATCH_LOG" <<EOF
Batch Run Started: $(date)
Variant: $VARIANT
Range: [$RANGE_START, $RANGE_END)
Range Size: $RANGE_SIZE
Chunk Size: $CHUNK_SIZE
Parallelism: $PARALLELISM
Launch Delay: ${LAUNCH_DELAY}s
Num Chunks: $NUM_CHUNKS
Done File: ${DONE_FILE:-none}
EOF

echo "Batch log: $BATCH_LOG"
echo ""

# Build chunk list
declare -a CHUNK_QUEUE=()
for (( i=0; i<NUM_CHUNKS; i++ )); do
    chunk_start=$((RANGE_START + i * CHUNK_SIZE))
    chunk_end=$(( chunk_start + CHUNK_SIZE ))

    # Don't exceed range end
    if [[ $chunk_end -gt $RANGE_END ]]; then
        chunk_end=$RANGE_END
    fi

    CHUNK_QUEUE+=("$chunk_start:$chunk_end")
done

UNFILTERED_CHUNK_COUNT=${#CHUNK_QUEUE[@]}
echo "Built queue with $UNFILTERED_CHUNK_COUNT chunks"
echo ""

# Filter against done.txt
COMPLETED_COUNT=0
if [[ -n "$DONE_FILE" ]] && [[ -f "$DONE_FILE" ]]; then
    echo "Filtering completed chunks from done.txt..."
    load_and_filter_done_ranges "$DONE_FILE" "$VARIANT" CHUNK_QUEUE COMPLETED_COUNT

    # Update NUM_CHUNKS after filtering
    NUM_CHUNKS=${#CHUNK_QUEUE[@]}

    if [[ $NUM_CHUNKS -eq 0 ]]; then
        echo "All chunks already completed! Nothing to do."
        exit 0
    fi

    echo "Remaining chunks to process: $NUM_CHUNKS"
    echo ""
fi

# Launch tmux sessions for each chunk
chunk_num=1
for chunk_spec in "${CHUNK_QUEUE[@]}"; do
    chunk_start="${chunk_spec%:*}"
    chunk_end="${chunk_spec#*:}"

    # Create unique session name
    SESSION_NAME="fvspec_${VARIANT}_${chunk_start}-${chunk_end}"

    # Log chunk info
    echo "Chunk $chunk_num/$NUM_CHUNKS: samples [$chunk_start, $chunk_end) -> tmux session: $SESSION_NAME"
    echo "Chunk $chunk_num/$NUM_CHUNKS: [$chunk_start, $chunk_end) -> $SESSION_NAME" >> "$BATCH_LOG"

    if [[ "$DRY_RUN" == "true" ]]; then
        ((chunk_num++))
        continue
    fi

    # Check if session already exists
    if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
        echo "  WARNING: Session $SESSION_NAME already exists, skipping..."
        ((chunk_num++))
        continue
    fi

    # Create new tmux session running the chunk worker script
    tmux new-session -d -s "$SESSION_NAME" \
        "DONE_FILE='$DONE_FILE' bash '$SCRIPT_DIR/run-chunk.sh' \
            --variant '$VARIANT' \
            --start-idx $chunk_start \
            --end-idx $chunk_end \
            --parallelism $PARALLELISM \
            --batch-id '$BATCH_ID'"

    echo "  ✓ Session created: $SESSION_NAME"

    # Rate limit: wait before launching next session (except for last chunk)
    if [[ $chunk_num -lt $NUM_CHUNKS ]] && [[ $LAUNCH_DELAY -gt 0 ]]; then
        sleep "$LAUNCH_DELAY"
    fi

    ((chunk_num++))
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
