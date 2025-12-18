#!/usr/bin/env bash
# Orchestrate large batch runs with a queue system to limit concurrent chunks
# This prevents overwhelming the system by only running N chunks at a time
# Usage: ./run-batch-queued.sh --variant control-functional --total 1000 --chunk-size 50 --max-concurrent 5

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCHMARK_DIR="$(dirname "$SCRIPT_DIR")"
LOGS_DIR="$SCRIPT_DIR/logs"

# Default values
VARIANT="control-functional"
TOTAL_SAMPLES=53408  # Full eligible dataset (54,345 total - 937 filtered)
CHUNK_SIZE=1000
PARALLELISM=10
MAX_CONCURRENT=5  # Maximum number of chunks running at once
POLL_INTERVAL=60  # Seconds between checking for completed chunks
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
        --max-concurrent)
            MAX_CONCURRENT="$2"
            shift 2
            ;;
        --poll-interval)
            POLL_INTERVAL="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 --variant <variant> --total <n> [--chunk-size <n>] [--parallelism <n>] [--max-concurrent <n>] [--poll-interval <seconds>] [--dry-run]"
            exit 1
            ;;
    esac
done

# Validate inputs
if [[ $CHUNK_SIZE -le 0 ]]; then
    echo "Error: --chunk-size must be positive"
    exit 1
fi

if [[ $MAX_CONCURRENT -le 0 ]]; then
    echo "Error: --max-concurrent must be positive"
    exit 1
fi

# Calculate number of chunks
NUM_CHUNKS=$(( (TOTAL_SAMPLES + CHUNK_SIZE - 1) / CHUNK_SIZE ))

echo "================================================"
echo "Queued Batch Run Configuration"
echo "================================================"
echo "Variant:         $VARIANT"
echo "Total:           $TOTAL_SAMPLES samples"
echo "Chunk size:      $CHUNK_SIZE samples"
echo "Total chunks:    $NUM_CHUNKS"
echo "Max concurrent:  $MAX_CONCURRENT chunks"
echo "Parallelism:     $PARALLELISM per chunk"
echo "Poll interval:   ${POLL_INTERVAL}s"
echo "Dry run:         $DRY_RUN"
echo "================================================"
echo ""
echo "RAM-friendly: Only $MAX_CONCURRENT chunks will run at once"
echo "Estimated peak processes: $((MAX_CONCURRENT * PARALLELISM))"
echo "================================================"
echo ""

if [[ "$DRY_RUN" == "true" ]]; then
    echo "DRY RUN: Would launch $NUM_CHUNKS chunks with max $MAX_CONCURRENT concurrent"
    exit 0
fi

# Create logs directory
mkdir -p "$LOGS_DIR"

# Create batch metadata file
TIMESTAMP=$(date +%Y-%m-%dT%H-%M-%S)
BATCH_ID="${TIMESTAMP}__${VARIANT}__total-${TOTAL_SAMPLES}"
BATCH_LOG="$LOGS_DIR/batch__${BATCH_ID}.log"
QUEUE_STATE="$LOGS_DIR/queue__${BATCH_ID}.state"

cat > "$BATCH_LOG" <<EOF
Queued Batch Run Started: $(date)
Variant: $VARIANT
Total Samples: $TOTAL_SAMPLES
Chunk Size: $CHUNK_SIZE
Parallelism: $PARALLELISM
Max Concurrent: $MAX_CONCURRENT
Num Chunks: $NUM_CHUNKS
Poll Interval: ${POLL_INTERVAL}s
EOF

echo "Batch log: $BATCH_LOG"
echo "Queue state: $QUEUE_STATE"
echo ""

# Build chunk list
declare -a CHUNK_QUEUE=()
for (( i=0; i<NUM_CHUNKS; i++ )); do
    START_IDX=$((i * CHUNK_SIZE))
    END_IDX=$(( START_IDX + CHUNK_SIZE ))

    # Don't exceed total samples
    if [[ $END_IDX -gt $TOTAL_SAMPLES ]]; then
        END_IDX=$TOTAL_SAMPLES
    fi

    CHUNK_QUEUE+=("$START_IDX:$END_IDX")
done

echo "Built queue with ${#CHUNK_QUEUE[@]} chunks"
echo ""

# Track running chunks: session_name -> start_idx:end_idx
declare -A RUNNING_CHUNKS=()
NEXT_CHUNK_IDX=0
COMPLETED_COUNT=0
FAILED_COUNT=0

# Function to launch a chunk
launch_chunk() {
    local chunk_spec="$1"
    local start_idx="${chunk_spec%:*}"
    local end_idx="${chunk_spec#*:}"

    SESSION_NAME="fvspec_${VARIANT}_${start_idx}-${end_idx}"

    # Check if session already exists (shouldn't happen, but be safe)
    if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
        echo "  WARNING: Session $SESSION_NAME already exists, skipping..."
        return 1
    fi

    # Create new tmux session running the chunk worker script
    # Use --no-wait so failed chunks exit immediately (no interactive prompt)
    tmux new-session -d -s "$SESSION_NAME" \
        "bash '$SCRIPT_DIR/run-chunk.sh' \
            --variant '$VARIANT' \
            --start-idx $start_idx \
            --end-idx $end_idx \
            --parallelism $PARALLELISM \
            --batch-id '$BATCH_ID' \
            --no-wait"

    RUNNING_CHUNKS["$SESSION_NAME"]="$chunk_spec"

    echo "$(date +%H:%M:%S) Launched chunk [$start_idx, $end_idx) in session: $SESSION_NAME"
    echo "Chunk $((NEXT_CHUNK_IDX+1))/$NUM_CHUNKS: [$start_idx, $end_idx) -> $SESSION_NAME" >> "$BATCH_LOG"

    return 0
}

# Function to check completed chunks
check_completed() {
    local completed_sessions=()

    for session_name in "${!RUNNING_CHUNKS[@]}"; do
        # Check if tmux session still exists
        if ! tmux has-session -t "$session_name" 2>/dev/null; then
            # Session is gone - check status file to determine success/failure
            local chunk_spec="${RUNNING_CHUNKS[$session_name]}"
            local start_idx="${chunk_spec%:*}"
            local end_idx="${chunk_spec#*:}"

            STATUS_FILE="$LOGS_DIR/chunk__${BATCH_ID}__${start_idx}-${end_idx}.status"

            if [[ -f "$STATUS_FILE" ]]; then
                source "$STATUS_FILE"
                if [[ "${status:-}" == "SUCCESS" ]]; then
                    echo "$(date +%H:%M:%S) ✓ Chunk [$start_idx, $end_idx) completed successfully"
                    COMPLETED_COUNT=$((COMPLETED_COUNT + 1))
                elif [[ "${status:-}" == "FAILED" ]]; then
                    echo "$(date +%H:%M:%S) ✗ Chunk [$start_idx, $end_idx) FAILED"
                    FAILED_COUNT=$((FAILED_COUNT + 1))
                else
                    echo "$(date +%H:%M:%S) ? Chunk [$start_idx, $end_idx) has unknown status: ${status:-UNKNOWN}"
                fi
            else
                echo "$(date +%H:%M:%S) ? Chunk [$start_idx, $end_idx) completed but no status file found"
            fi

            completed_sessions+=("$session_name")
        fi
    done

    # Remove completed sessions from tracking
    for session_name in "${completed_sessions[@]}"; do
        unset RUNNING_CHUNKS["$session_name"]
    done

    return ${#completed_sessions[@]}
}

# Function to save queue state
save_state() {
    cat > "$QUEUE_STATE" <<EOF
next_chunk_idx=$NEXT_CHUNK_IDX
completed_count=$COMPLETED_COUNT
failed_count=$FAILED_COUNT
running_count=${#RUNNING_CHUNKS[@]}
timestamp=$(date -Iseconds)
EOF
}

# Main orchestration loop
echo "Starting queued batch orchestration..."
echo ""

while true; do
    # Launch new chunks if we have capacity and chunks remaining
    while [[ ${#RUNNING_CHUNKS[@]} -lt $MAX_CONCURRENT ]] && [[ $NEXT_CHUNK_IDX -lt ${#CHUNK_QUEUE[@]} ]]; do
        chunk_spec="${CHUNK_QUEUE[$NEXT_CHUNK_IDX]}"

        if launch_chunk "$chunk_spec"; then
            NEXT_CHUNK_IDX=$((NEXT_CHUNK_IDX + 1))
            # Small delay between launches
            sleep 2
        else
            # Failed to launch, skip this chunk
            NEXT_CHUNK_IDX=$((NEXT_CHUNK_IDX + 1))
        fi
    done

    # Save current state
    save_state

    # Check if we're done
    if [[ $NEXT_CHUNK_IDX -ge ${#CHUNK_QUEUE[@]} ]] && [[ ${#RUNNING_CHUNKS[@]} -eq 0 ]]; then
        echo ""
        echo "================================================"
        echo "All chunks completed!"
        echo "================================================"
        echo "Total chunks:  $NUM_CHUNKS"
        echo "Completed:     $COMPLETED_COUNT"
        echo "Failed:        $FAILED_COUNT"
        echo "================================================"
        break
    fi

    # Show status
    QUEUED_REMAINING=$((${#CHUNK_QUEUE[@]} - NEXT_CHUNK_IDX))
    echo "$(date +%H:%M:%S) Status: Running=${#RUNNING_CHUNKS[@]}, Queued=$QUEUED_REMAINING, Completed=$COMPLETED_COUNT, Failed=$FAILED_COUNT"

    # Wait before checking again
    sleep "$POLL_INTERVAL"

    # Check for completed chunks
    check_completed
done

echo ""
echo "Batch log: $BATCH_LOG"
echo ""
echo "Commands:"
echo "  View results:  ./operations/monitor.sh --batch-id $BATCH_ID"
echo "  Find crashes:  ./operations/find-crashes.sh --batch-id $BATCH_ID"
echo ""

if [[ $FAILED_COUNT -gt 0 ]]; then
    echo "⚠️  Some chunks failed. Run find-crashes.sh to see details."
    exit 1
fi
