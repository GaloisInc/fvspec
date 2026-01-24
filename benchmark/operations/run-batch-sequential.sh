#!/usr/bin/env bash
# Sequential batch runner - process chunks one at a time in tmux sessions
# Usage: ./run-batch-sequential.sh --variant control-functional --total 1000 --chunk-size 50

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCHMARK_DIR="$(dirname "$SCRIPT_DIR")"
LOGS_DIR="$SCRIPT_DIR/logs"

# Error trap to debug unexpected exits (ERR only, not EXIT to avoid false positives)
trap 'echo "ERROR: Command failed at line $LINENO with exit code $?" >&2' ERR

# Source library functions
source "$SCRIPT_DIR/lib/done-filter.sh"
source "$SCRIPT_DIR/lib/memory-limit.sh"

# Default values
VARIANT="control-functional"
TOTAL_SAMPLES=53408  # Full eligible dataset (54,345 total - 937 filtered)
CHUNK_SIZE=100
PARALLELISM=10
DRY_RUN=false
START_IDX=""  # Optional: starting index (0-indexed, inclusive)
END_IDX=""    # Optional: ending index (0-indexed, exclusive)
DONE_FILE="./operations/done.txt"  # Manifest of completed ranges
MEMORY_HIGH="25G"  # Soft memory limit (throttling)
POLL_INTERVAL=5  # Seconds to wait between checking if session finished

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
        --memory-high)
            MEMORY_HIGH="$2"
            shift 2
            ;;
        --poll-interval)
            POLL_INTERVAL="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 --variant <variant> [--total <n>] [--start-idx <n>] [--end-idx <n>] [--chunk-size <n>] [--parallelism <n>] [--dry-run] [--done-file <path>] [--skip-done-check] [--memory-high <size>] [--poll-interval <seconds>]"
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
echo "Sequential Batch Run Configuration"
echo "================================================"
echo "Variant:       $VARIANT"
if [[ -n "$START_IDX" ]] || [[ -n "$END_IDX" ]]; then
    echo "Index range:   [$RANGE_START, $RANGE_END) ($RANGE_SIZE samples)"
else
    echo "Total:         $TOTAL_SAMPLES samples"
fi
echo "Chunk size:    $CHUNK_SIZE samples"
echo "Chunks:        $NUM_CHUNKS"
echo "Parallelism:   $PARALLELISM per chunk (inspect internal)"
echo "Memory High:   $MEMORY_HIGH (soft limit, throttling)"
echo "Poll interval: ${POLL_INTERVAL}s"
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
Sequential Batch Run Started: $(date)
Variant: $VARIANT
Range: [$RANGE_START, $RANGE_END)
Range Size: $RANGE_SIZE
Chunk Size: $CHUNK_SIZE
Parallelism: $PARALLELISM
Memory High: $MEMORY_HIGH
Poll Interval: ${POLL_INTERVAL}s
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

if [[ "$DRY_RUN" == "true" ]]; then
    echo "DRY RUN: Would process the following chunks:"
    chunk_num=1
    for chunk_spec in "${CHUNK_QUEUE[@]}"; do
        chunk_start="${chunk_spec%:*}"
        chunk_end="${chunk_spec#*:}"
        SESSION_NAME="fvspec_${chunk_start}-${chunk_end}"
        echo "  Chunk $chunk_num/$NUM_CHUNKS: [$chunk_start, $chunk_end) -> tmux: $SESSION_NAME"
        ((chunk_num++))
    done
    exit 0
fi

# Track success/failure counts
SUCCESS_COUNT=0
FAILURE_COUNT=0

# Process chunks sequentially
chunk_num=1
for chunk_spec in "${CHUNK_QUEUE[@]}"; do
    chunk_start="${chunk_spec%:*}"
    chunk_end="${chunk_spec#*:}"

    # Create unique session name (removed variant name per user request)
    SESSION_NAME="fvspec_${chunk_start}-${chunk_end}"

    # Print chunk header
    echo "" | tee -a "$BATCH_LOG"
    echo "==========================================" | tee -a "$BATCH_LOG"
    echo "Chunk $chunk_num/$NUM_CHUNKS: [$chunk_start, $chunk_end)" | tee -a "$BATCH_LOG"
    echo "Started: $(date)" | tee -a "$BATCH_LOG"
    echo "Session: $SESSION_NAME" | tee -a "$BATCH_LOG"
    echo "==========================================" | tee -a "$BATCH_LOG"

    # Check if session already exists
    if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
        echo "WARNING: Session $SESSION_NAME already exists, skipping..." | tee -a "$BATCH_LOG"
        ((chunk_num++))
        continue
    fi

    # Build memory limiting command using library (MemoryHigh only, no MemoryMax)
    MEMORY_CMD=$(build_memory_cmd "$MEMORY_HIGH")

    # Create chunk log and status files
    CHUNK_LOG="$LOGS_DIR/chunk__${BATCH_ID}__${chunk_start}-${chunk_end}.log"
    CHUNK_STATUS="$LOGS_DIR/chunk__${BATCH_ID}__${chunk_start}-${chunk_end}.status"

    # Build comprehensive command for tmux session that handles logging, status, and done.txt
    read -r -d '' CHUNK_CMD <<'CMDEOF' || true
set -euo pipefail
CHUNK_START=%CHUNK_START%
CHUNK_END=%CHUNK_END%
VARIANT="%VARIANT%"
PARALLELISM=%PARALLELISM%
CHUNK_LOG="%CHUNK_LOG%"
CHUNK_STATUS="%CHUNK_STATUS%"
DONE_FILE="%DONE_FILE%"
MEMORY_CMD="%MEMORY_CMD%"
BENCHMARK_DIR="%BENCHMARK_DIR%"

# Initialize status file
cat > "$CHUNK_STATUS" <<EOF
status=RUNNING
start_idx=$CHUNK_START
end_idx=$CHUNK_END
variant=$VARIANT
started=$(date -Iseconds)
pid=$$
EOF

cd "$BENCHMARK_DIR"

# Run fvspec with memory limiting
EXIT_CODE=0
if $MEMORY_CMD nice -n 19 ionice -c 3 uv run fvspec \
    --variant "$VARIANT" \
    --start-idx "$CHUNK_START" \
    --end-idx "$CHUNK_END" \
    --parallelism "$PARALLELISM" \
    > "$CHUNK_LOG" 2>&1; then

    # Success
    EXIT_CODE=0
    cat >> "$CHUNK_STATUS" <<EOF
status=SUCCESS
finished=$(date -Iseconds)
exit_code=$EXIT_CODE
EOF

    # Append to done.txt (atomic with flock)
    if [[ -n "$DONE_FILE" ]]; then
        DONE_DIR="$(dirname "$DONE_FILE")"
        mkdir -p "$DONE_DIR"
        (
            flock -x 200
            echo "$CHUNK_START $CHUNK_END $VARIANT" >> "$DONE_FILE"
        ) 200>"${DONE_FILE}.lock"
    fi
else
    # Failure
    EXIT_CODE=$?
    cat >> "$CHUNK_STATUS" <<EOF
status=FAILED
finished=$(date -Iseconds)
exit_code=$EXIT_CODE
EOF

    # Create crash log
    CRASH_LOG="${CHUNK_LOG%.log}.CRASH.log"
    cp "$CHUNK_LOG" "$CRASH_LOG"
fi

exit $EXIT_CODE
CMDEOF

    # Substitute variables in command
    CHUNK_CMD="${CHUNK_CMD//%CHUNK_START%/$chunk_start}"
    CHUNK_CMD="${CHUNK_CMD//%CHUNK_END%/$chunk_end}"
    CHUNK_CMD="${CHUNK_CMD//%VARIANT%/$VARIANT}"
    CHUNK_CMD="${CHUNK_CMD//%PARALLELISM%/$PARALLELISM}"
    CHUNK_CMD="${CHUNK_CMD//%CHUNK_LOG%/$CHUNK_LOG}"
    CHUNK_CMD="${CHUNK_CMD//%CHUNK_STATUS%/$CHUNK_STATUS}"
    CHUNK_CMD="${CHUNK_CMD//%DONE_FILE%/$DONE_FILE}"
    CHUNK_CMD="${CHUNK_CMD//%MEMORY_CMD%/$MEMORY_CMD}"
    CHUNK_CMD="${CHUNK_CMD//%BENCHMARK_DIR%/$BENCHMARK_DIR}"

    # Launch tmux session with inline command
    tmux new-session -d -s "$SESSION_NAME" "$CHUNK_CMD"

    echo "✓ Session launched: $SESSION_NAME" | tee -a "$BATCH_LOG"

    # Wait for session to complete (poll until session no longer exists)
    echo "Waiting for chunk to complete (polling every ${POLL_INTERVAL}s)..." | tee -a "$BATCH_LOG"
    POLL_COUNT=0
    while tmux has-session -t "$SESSION_NAME" 2>/dev/null; do
        sleep "$POLL_INTERVAL"
        ((POLL_COUNT++))
        if (( POLL_COUNT % 12 == 0 )); then
            echo "Still waiting... ($(( POLL_COUNT * POLL_INTERVAL ))s elapsed)" | tee -a "$BATCH_LOG"
        fi
    done
    echo "Chunk session completed after $(( POLL_COUNT * POLL_INTERVAL ))s" | tee -a "$BATCH_LOG"

    # Check status file to determine success/failure
    CHUNK_STATUS="$LOGS_DIR/chunk__${BATCH_ID}__${chunk_start}-${chunk_end}.status"
    echo "Checking status file: $CHUNK_STATUS" | tee -a "$BATCH_LOG"
    if [[ -f "$CHUNK_STATUS" ]]; then
        # Parse status from file (use tail -1 to get final status, not initial RUNNING)
        # Use || true to prevent grep failure from exiting with set -e
        STATUS=$(grep "^status=" "$CHUNK_STATUS" 2>/dev/null | tail -1 | cut -d= -f2 || echo "UNKNOWN")
        EXIT_CODE=$(grep "^exit_code=" "$CHUNK_STATUS" 2>/dev/null | tail -1 | cut -d= -f2 || echo "unknown")

        echo "  Status: $STATUS, Exit code: $EXIT_CODE" | tee -a "$BATCH_LOG"

        if [[ "$STATUS" == "SUCCESS" ]]; then
            ((SUCCESS_COUNT++))
            echo "✓ Chunk [$chunk_start, $chunk_end) completed successfully" | tee -a "$BATCH_LOG"
        else
            ((FAILURE_COUNT++))
            echo "✗ Chunk [$chunk_start, $chunk_end) FAILED (status: $STATUS, exit code: $EXIT_CODE)" | tee -a "$BATCH_LOG"
        fi
    else
        # Status file doesn't exist - assume failure
        ((FAILURE_COUNT++))
        echo "✗ Chunk [$chunk_start, $chunk_end) FAILED (no status file found)" | tee -a "$BATCH_LOG"
    fi

    echo "Chunk $chunk_num/$NUM_CHUNKS done" | tee -a "$BATCH_LOG"
    ((chunk_num++))
done

# Print final summary
echo "" | tee -a "$BATCH_LOG"
echo "================================================" | tee -a "$BATCH_LOG"
echo "Sequential Batch Run Complete" | tee -a "$BATCH_LOG"
echo "================================================" | tee -a "$BATCH_LOG"
echo "Finished:      $(date)" | tee -a "$BATCH_LOG"
echo "Total chunks:  $NUM_CHUNKS" | tee -a "$BATCH_LOG"
echo "Successful:    $SUCCESS_COUNT" | tee -a "$BATCH_LOG"
echo "Failed:        $FAILURE_COUNT" | tee -a "$BATCH_LOG"
echo "Batch log:     $BATCH_LOG" | tee -a "$BATCH_LOG"
echo "================================================" | tee -a "$BATCH_LOG"

echo ""
echo "Commands:"
echo "  Find crashes:  ./operations/find-crashes.sh --batch-id $BATCH_ID"
echo "  View logs:     ls -lh $LOGS_DIR/*${BATCH_ID}*"
echo ""

# Exit with failure if any chunks failed
if [[ $FAILURE_COUNT -gt 0 ]]; then
    echo "WARNING: $FAILURE_COUNT chunk(s) failed. Check CRASH logs in $LOGS_DIR/"
    exit 1
fi

exit 0
