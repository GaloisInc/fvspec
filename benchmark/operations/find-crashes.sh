#!/usr/bin/env bash
# Find all crashed chunks and generate one-button resume script
# Usage: ./find-crashes.sh [--batch-id <batch_id>]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS_DIR="$SCRIPT_DIR/logs"

BATCH_ID=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --batch-id)
            BATCH_ID="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--batch-id <batch_id>]"
            exit 1
            ;;
    esac
done

echo "================================================"
echo "Searching for crashed chunks..."
echo "================================================"
echo ""

# Find all .status files with FAILED status
if [[ -n "$BATCH_ID" ]]; then
    STATUS_FILES=$(find "$LOGS_DIR" -name "chunk__${BATCH_ID}__*.status" 2>/dev/null | sort || true)
else
    STATUS_FILES=$(find "$LOGS_DIR" -name "chunk__*.status" 2>/dev/null | sort || true)
fi

if [[ -z "$STATUS_FILES" ]]; then
    echo "✓ No status files found. Run a batch first!"
    exit 0
fi

# Parse status files and collect failed chunks
declare -a FAILED_CHUNKS=()
CRASH_NUM=1

for status_file in $STATUS_FILES; do
    # Read status file line by line (can't source because resume_command has spaces)
    unset status start_idx end_idx variant crash_start_idx crash_end_idx resume_command

    while IFS='=' read -r key value; do
        case "$key" in
            status) status="$value" ;;
            start_idx) start_idx="$value" ;;
            end_idx) end_idx="$value" ;;
            variant) variant="$value" ;;
            crash_start_idx) crash_start_idx="$value" ;;
            crash_end_idx) crash_end_idx="$value" ;;
            resume_command) resume_command="$value" ;;
        esac
    done < "$status_file"

    # Skip if not failed
    if [[ "${status:-}" != "FAILED" ]]; then
        continue
    fi

    # Display crash info
    echo "================================================"
    echo "CRASH #$CRASH_NUM"
    echo "================================================"
    echo "  Range:        [${crash_start_idx:-$start_idx}, ${crash_end_idx:-$end_idx})"
    echo "  Variant:      ${variant:-unknown}"
    echo "  Status file:  $status_file"

    # Extract parallelism from resume_command
    PARALLELISM=10
    if [[ -n "${resume_command:-}" ]]; then
        # Parse --parallelism N from resume_command
        if [[ "$resume_command" =~ --parallelism[[:space:]]+([0-9]+) ]]; then
            PARALLELISM="${BASH_REMATCH[1]}"
        fi
        echo "  Resume cmd:   $resume_command"
    fi
    echo ""

    # Add to failed chunks array
    CHUNK_SPEC="${crash_start_idx:-$start_idx}:${crash_end_idx:-$end_idx}:${variant:-unknown}:$PARALLELISM"
    FAILED_CHUNKS+=("$CHUNK_SPEC")

    CRASH_NUM=$((CRASH_NUM + 1))
done

NUM_CRASHES=${#FAILED_CHUNKS[@]}

if [[ $NUM_CRASHES -eq 0 ]]; then
    echo "✓ No crashes found!"
    exit 0
fi

echo "================================================"
echo "SUMMARY"
echo "================================================"
echo "Total crashes: $NUM_CRASHES"
echo ""

# Generate resume script
TIMESTAMP=$(date +%Y-%m-%dT%H-%M-%S)
RESUME_SCRIPT="$LOGS_DIR/resume-failed__${TIMESTAMP}.sh"

cat > "$RESUME_SCRIPT" <<'SCRIPT_TEMPLATE'
#!/usr/bin/env bash
# Auto-generated resume script for failed chunks
SCRIPT_TEMPLATE

cat >> "$RESUME_SCRIPT" <<SCRIPT_HEADER
# Generated: $(date)
# Found $NUM_CRASHES failed chunk(s)
# Usage: ./$(basename "$RESUME_SCRIPT") [--max-concurrent N]

set -euo pipefail

SCRIPT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="\$(dirname "\$SCRIPT_DIR")"
MAX_CONCURRENT=5
POLL_INTERVAL=30

# Parse arguments
while [[ \$# -gt 0 ]]; do
    case \$1 in
        --max-concurrent)
            MAX_CONCURRENT="\$2"
            shift 2
            ;;
        *)
            echo "Unknown option: \$1"
            echo "Usage: \$0 [--max-concurrent N]"
            exit 1
            ;;
    esac
done

# Failed chunk ranges (embedded by generator)
declare -a FAILED_CHUNKS=(
SCRIPT_HEADER

# Add failed chunks array
for chunk_spec in "${FAILED_CHUNKS[@]}"; do
    echo "    \"$chunk_spec\"" >> "$RESUME_SCRIPT"
done

cat >> "$RESUME_SCRIPT" <<'SCRIPT_BODY'
)

echo "================================================"
echo "Resuming Failed Chunks"
echo "================================================"
echo "Total failed:    ${#FAILED_CHUNKS[@]}"
echo "Max concurrent:  $MAX_CONCURRENT"
echo "Poll interval:   ${POLL_INTERVAL}s"
echo "================================================"
echo ""

# Generate resume batch ID
RESUME_BATCH_ID="resume__$(date +%Y-%m-%dT%H-%M-%S)"

# Track running chunks
declare -A RUNNING_CHUNKS=()
NEXT_CHUNK_IDX=0
COMPLETED_COUNT=0

# Function to launch chunk
launch_chunk() {
    local chunk_spec="$1"
    IFS=':' read -r start_idx end_idx variant parallelism <<< "$chunk_spec"

    SESSION_NAME="fvspec_${variant}_${start_idx}-${end_idx}"

    # Skip if session already exists
    if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
        echo "$(date +%H:%M:%S) ⚠ Session $SESSION_NAME exists, skipping..."
        return 1
    fi

    # Launch chunk in tmux
    tmux new-session -d -s "$SESSION_NAME" \
        "bash '$PARENT_DIR/run-chunk.sh' \
            --variant '$variant' \
            --start-idx $start_idx \
            --end-idx $end_idx \
            --parallelism $parallelism \
            --batch-id '$RESUME_BATCH_ID' \
            --no-wait"

    RUNNING_CHUNKS["$SESSION_NAME"]="$chunk_spec"
    echo "$(date +%H:%M:%S) ✓ Launched [$start_idx, $end_idx) variant=$variant"
    return 0
}

# Function to check completed chunks
check_completed() {
    local completed_sessions=()

    for session_name in "${!RUNNING_CHUNKS[@]}"; do
        if ! tmux has-session -t "$session_name" 2>/dev/null; then
            local chunk_spec="${RUNNING_CHUNKS[$session_name]}"
            IFS=':' read -r start_idx end_idx variant parallelism <<< "$chunk_spec"

            echo "$(date +%H:%M:%S) ✓ Chunk [$start_idx, $end_idx) completed"
            completed_sessions+=("$session_name")
            COMPLETED_COUNT=$((COMPLETED_COUNT + 1))
        fi
    done

    # Remove completed from tracking
    for session_name in "${completed_sessions[@]}"; do
        unset RUNNING_CHUNKS["$session_name"]
    done
}

# Main orchestration loop
echo "Starting queued resume..."
echo ""

while true; do
    # Launch new chunks if we have capacity and chunks remaining
    while [[ ${#RUNNING_CHUNKS[@]} -lt $MAX_CONCURRENT ]] && \
          [[ $NEXT_CHUNK_IDX -lt ${#FAILED_CHUNKS[@]} ]]; do

        if launch_chunk "${FAILED_CHUNKS[$NEXT_CHUNK_IDX]}"; then
            # Small delay between launches
            sleep 2
        fi
        NEXT_CHUNK_IDX=$((NEXT_CHUNK_IDX + 1))
    done

    # Check if we're done
    if [[ $NEXT_CHUNK_IDX -ge ${#FAILED_CHUNKS[@]} ]] && \
       [[ ${#RUNNING_CHUNKS[@]} -eq 0 ]]; then
        echo ""
        echo "================================================"
        echo "All failed chunks resumed!"
        echo "================================================"
        echo "Total resumed: $COMPLETED_COUNT"
        echo "================================================"
        break
    fi

    # Show status
    QUEUED_REMAINING=$((${#FAILED_CHUNKS[@]} - NEXT_CHUNK_IDX))
    echo "$(date +%H:%M:%S) Status: Running=${#RUNNING_CHUNKS[@]}, Queued=$QUEUED_REMAINING, Completed=$COMPLETED_COUNT"

    # Wait before checking again
    sleep "$POLL_INTERVAL"

    # Check for completed chunks
    check_completed
done

echo ""
echo "Monitor results:"
echo "  ./operations/monitor.sh --batch-id $RESUME_BATCH_ID --watch"
echo "  ./operations/find-crashes.sh --batch-id $RESUME_BATCH_ID"
echo ""
SCRIPT_BODY

# Make script executable
chmod +x "$RESUME_SCRIPT"

echo "================================================"
echo "ONE-BUTTON RESUME SCRIPT GENERATED"
echo "================================================"
echo ""
echo "Found $NUM_CRASHES crashed chunk(s)."
echo ""
echo "To resume all failed chunks with ONE command:"
echo ""
echo "  $RESUME_SCRIPT"
echo ""
echo "Options:"
echo "  --max-concurrent N    Max chunks running at once (default: 5)"
echo ""
echo "Examples:"
echo "  # Run with default (5 concurrent)"
echo "  $RESUME_SCRIPT"
echo ""
echo "  # More aggressive (10 concurrent)"
echo "  $RESUME_SCRIPT --max-concurrent 10"
echo ""
echo "The script will:"
echo "  - Resume failed chunks with bounded concurrency"
echo "  - Launch new chunks as old ones complete"
echo "  - Display progress in real-time"
echo "  - Create new batch ID for tracking"
echo ""
echo "Monitor with: ./operations/monitor.sh --watch"
echo "================================================"
echo ""
