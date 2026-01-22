#!/usr/bin/env bash
# Worker script that runs a single chunk in a tmux session
# This script is called by run-batch.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCHMARK_DIR="$(dirname "$SCRIPT_DIR")"
LOGS_DIR="$SCRIPT_DIR/logs"

# Parse arguments
VARIANT=""
START_IDX=""
END_IDX=""
PARALLELISM=10
BATCH_ID=""
NO_WAIT=false  # If true, exit immediately on failure (for queued runner)
DONE_FILE="${DONE_FILE:-}"  # Optional done.txt path from environment
MEMORY_LIMIT="4G"  # Default memory limit per chunk (override with --memory-limit)

while [[ $# -gt 0 ]]; do
    case $1 in
        --variant)
            VARIANT="$2"
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
        --parallelism)
            PARALLELISM="$2"
            shift 2
            ;;
        --batch-id)
            BATCH_ID="$2"
            shift 2
            ;;
        --no-wait)
            NO_WAIT=true
            shift
            ;;
        --memory-limit)
            MEMORY_LIMIT="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate required arguments
if [[ -z "$VARIANT" ]] || [[ -z "$START_IDX" ]] || [[ -z "$END_IDX" ]]; then
    echo "Error: Missing required arguments"
    exit 1
fi

# Create chunk log file
CHUNK_LOG="$LOGS_DIR/chunk__${BATCH_ID}__${START_IDX}-${END_IDX}.log"
CHUNK_STATUS="$LOGS_DIR/chunk__${BATCH_ID}__${START_IDX}-${END_IDX}.status"

# Initialize status file
cat > "$CHUNK_STATUS" <<EOF
status=RUNNING
start_idx=$START_IDX
end_idx=$END_IDX
variant=$VARIANT
started=$(date -Iseconds)
pid=$$
EOF

echo "================================================" | tee "$CHUNK_LOG"
echo "Chunk Worker: [$START_IDX, $END_IDX)" | tee -a "$CHUNK_LOG"
echo "================================================" | tee -a "$CHUNK_LOG"
echo "Variant:      $VARIANT" | tee -a "$CHUNK_LOG"
echo "Start Index:  $START_IDX" | tee -a "$CHUNK_LOG"
echo "End Index:    $END_IDX" | tee -a "$CHUNK_LOG"
echo "Parallelism:  $PARALLELISM" | tee -a "$CHUNK_LOG"
echo "Batch ID:     $BATCH_ID" | tee -a "$CHUNK_LOG"
echo "Memory Limit: ${MEMORY_LIMIT:-unlimited}" | tee -a "$CHUNK_LOG"
echo "Log:          $CHUNK_LOG" | tee -a "$CHUNK_LOG"
echo "Started:      $(date)" | tee -a "$CHUNK_LOG"
echo "================================================" | tee -a "$CHUNK_LOG"
echo "" | tee -a "$CHUNK_LOG"

# Change to benchmark directory
cd "$BENCHMARK_DIR"

# Source memory limiting library and build command prefix
source "$SCRIPT_DIR/lib/memory-limit.sh"
MEMORY_CMD=$(build_memory_cmd "$MEMORY_LIMIT")

# Run the benchmark with error handling
# Use nice and ionice to reduce system priority (prevents system slowdown)
# Optional memory limiting via systemd-run or prlimit
EXIT_CODE=0
echo "Running: ${MEMORY_CMD:+$MEMORY_CMD }nice -n 19 ionice -c 3 uv run fvspec --variant $VARIANT --start-idx $START_IDX --end-idx $END_IDX --parallelism $PARALLELISM" | tee -a "$CHUNK_LOG"
echo "" | tee -a "$CHUNK_LOG"

# shellcheck disable=SC2086  # Word splitting is intentional for MEMORY_CMD
if $MEMORY_CMD nice -n 19 ionice -c 3 uv run fvspec \
    --variant "$VARIANT" \
    --start-idx "$START_IDX" \
    --end-idx "$END_IDX" \
    --parallelism "$PARALLELISM" \
    2>&1 | tee -a "$CHUNK_LOG"; then

    # Success
    EXIT_CODE=0
    echo "" | tee -a "$CHUNK_LOG"
    echo "================================================" | tee -a "$CHUNK_LOG"
    echo "✓ Chunk completed successfully" | tee -a "$CHUNK_LOG"
    echo "================================================" | tee -a "$CHUNK_LOG"

    # Update status file
    cat >> "$CHUNK_STATUS" <<EOF
status=SUCCESS
finished=$(date -Iseconds)
exit_code=$EXIT_CODE
EOF

    # Append to done.txt manifest if provided
    if [[ -n "$DONE_FILE" ]]; then
        # Ensure directory exists
        DONE_DIR="$(dirname "$DONE_FILE")"
        mkdir -p "$DONE_DIR"

        # Atomic append with flock to prevent concurrent write issues
        (
            flock -x 200
            echo "$START_IDX $END_IDX $VARIANT" >> "$DONE_FILE"
        ) 200>"${DONE_FILE}.lock"

        echo "Recorded completion in done.txt: [$START_IDX, $END_IDX) for $VARIANT" | tee -a "$CHUNK_LOG"
    fi

else
    # Failure
    EXIT_CODE=$?
    echo "" | tee -a "$CHUNK_LOG"
    echo "###################################################" | tee -a "$CHUNK_LOG"
    echo "###                                             ###" | tee -a "$CHUNK_LOG"
    echo "###        ✗✗✗ CHUNK CRASHED ✗✗✗              ###" | tee -a "$CHUNK_LOG"
    echo "###                                             ###" | tee -a "$CHUNK_LOG"
    echo "###################################################" | tee -a "$CHUNK_LOG"
    echo "" | tee -a "$CHUNK_LOG"
    echo "CRASH SUMMARY:" | tee -a "$CHUNK_LOG"
    echo "  Variant:      $VARIANT" | tee -a "$CHUNK_LOG"
    echo "  Start Index:  $START_IDX" | tee -a "$CHUNK_LOG"
    echo "  End Index:    $END_IDX" | tee -a "$CHUNK_LOG"
    echo "  Samples:      [$START_IDX, $END_IDX)" | tee -a "$CHUNK_LOG"
    echo "  Exit Code:    $EXIT_CODE" | tee -a "$CHUNK_LOG"
    echo "  Memory Limit: ${MEMORY_LIMIT:-unlimited}" | tee -a "$CHUNK_LOG"
    echo "  Crashed at:   $(date)" | tee -a "$CHUNK_LOG"

    # Check for likely OOM kill (exit 137 = SIGKILL)
    if is_oom_exit "$EXIT_CODE"; then
        echo "" | tee -a "$CHUNK_LOG"
        echo "  ⚠️  LIKELY OOM KILL (exit $EXIT_CODE)" | tee -a "$CHUNK_LOG"
        echo "  Try: --memory-limit <larger> or --parallelism <lower>" | tee -a "$CHUNK_LOG"
    fi

    echo "" | tee -a "$CHUNK_LOG"
    echo "---------------------------------------------------" | tee -a "$CHUNK_LOG"
    echo "TO RESUME THIS CHUNK, RUN:" | tee -a "$CHUNK_LOG"
    echo "" | tee -a "$CHUNK_LOG"
    echo "  nice -n 19 ionice -c 3 uv run fvspec \\" | tee -a "$CHUNK_LOG"
    echo "    --variant $VARIANT \\" | tee -a "$CHUNK_LOG"
    echo "    --start-idx $START_IDX \\" | tee -a "$CHUNK_LOG"
    echo "    --end-idx $END_IDX \\" | tee -a "$CHUNK_LOG"
    echo "    --parallelism $PARALLELISM" | tee -a "$CHUNK_LOG"
    echo "" | tee -a "$CHUNK_LOG"
    echo "---------------------------------------------------" | tee -a "$CHUNK_LOG"
    echo "" | tee -a "$CHUNK_LOG"

    # Update status file with failure info
    cat >> "$CHUNK_STATUS" <<EOF
status=FAILED
finished=$(date -Iseconds)
exit_code=$EXIT_CODE
crash_start_idx=$START_IDX
crash_end_idx=$END_IDX
resume_command=nice -n 19 ionice -c 3 uv run fvspec --variant $VARIANT --start-idx $START_IDX --end-idx $END_IDX --parallelism $PARALLELISM
EOF

    # Create a prominent crash marker file
    CRASH_LOG="$LOGS_DIR/CRASH__${BATCH_ID}__${START_IDX}-${END_IDX}.log"
    cp "$CHUNK_LOG" "$CRASH_LOG"
    echo "" | tee -a "$CHUNK_LOG"
    echo "###################################################" | tee -a "$CHUNK_LOG"
    echo "CRASH LOG SAVED TO:" | tee -a "$CHUNK_LOG"
    echo "  $CRASH_LOG" | tee -a "$CHUNK_LOG"
    echo "###################################################" | tee -a "$CHUNK_LOG"
fi

echo "" | tee -a "$CHUNK_LOG"
echo "Chunk log: $CHUNK_LOG" | tee -a "$CHUNK_LOG"
echo "Status:    $CHUNK_STATUS" | tee -a "$CHUNK_LOG"
echo "" | tee -a "$CHUNK_LOG"

# Keep tmux session open for inspection (unless --no-wait)
if [[ $EXIT_CODE -ne 0 ]] && [[ "$NO_WAIT" != "true" ]]; then
    echo "Press Enter to close this tmux session..."
    read
fi

exit $EXIT_CODE
