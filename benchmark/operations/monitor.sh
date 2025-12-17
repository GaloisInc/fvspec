#!/usr/bin/env bash
# Monitor the status of all chunks in a batch run

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS_DIR="$SCRIPT_DIR/logs"

# Parse arguments
BATCH_ID=""
WATCH_MODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --batch-id)
            BATCH_ID="$2"
            shift 2
            ;;
        --watch)
            WATCH_MODE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--batch-id <id>] [--watch]"
            exit 1
            ;;
    esac
done

# Function to display status
show_status() {
    echo "================================================"
    echo "Batch Run Monitor"
    echo "================================================"
    echo "Time: $(date)"
    echo ""

    # If batch-id specified, filter for that batch
    if [[ -n "$BATCH_ID" ]]; then
        echo "Batch ID: $BATCH_ID"
        echo ""
        STATUS_FILES=("$LOGS_DIR"/chunk__${BATCH_ID}__*.status)
    else
        echo "All batches"
        echo ""
        STATUS_FILES=("$LOGS_DIR"/chunk__*.status)
    fi

    # Check if any status files exist
    if [[ ! -e "${STATUS_FILES[0]}" ]]; then
        echo "No chunks found"
        if [[ -n "$BATCH_ID" ]]; then
            echo "Batch ID: $BATCH_ID"
        fi
        return
    fi

    # Count chunks by status
    TOTAL=0
    RUNNING=0
    SUCCESS=0
    FAILED=0

    # Display individual chunks
    echo "Chunk Status:"
    echo "─────────────────────────────────────────────────"
    printf "%-20s %-15s %-20s %s\n" "RANGE" "STATUS" "STARTED" "DURATION"
    echo "─────────────────────────────────────────────────"

    for status_file in "${STATUS_FILES[@]}"; do
        if [[ ! -f "$status_file" ]]; then
            continue
        fi

        TOTAL=$((TOTAL + 1))

        # Parse status file
        source "$status_file"

        # Count by status
        case $status in
            RUNNING) RUNNING=$((RUNNING + 1)) ;;
            SUCCESS) SUCCESS=$((SUCCESS + 1)) ;;
            FAILED) FAILED=$((FAILED + 1)) ;;
        esac

        # Calculate duration
        STARTED_EPOCH=$(date -d "$started" +%s 2>/dev/null || echo "0")
        if [[ -n "${finished:-}" ]]; then
            FINISHED_EPOCH=$(date -d "$finished" +%s 2>/dev/null || echo "0")
            DURATION=$((FINISHED_EPOCH - STARTED_EPOCH))
        else
            NOW_EPOCH=$(date +%s)
            DURATION=$((NOW_EPOCH - STARTED_EPOCH))
        fi

        # Format duration
        if [[ $DURATION -ge 3600 ]]; then
            DURATION_STR="${DURATION}s (~$((DURATION/3600))h)"
        elif [[ $DURATION -ge 60 ]]; then
            DURATION_STR="${DURATION}s (~$((DURATION/60))m)"
        else
            DURATION_STR="${DURATION}s"
        fi

        # Format status with color codes for terminal
        case $status in
            RUNNING)
                STATUS_COLOR="\033[1;33mRUNNING\033[0m"
                ;;
            SUCCESS)
                STATUS_COLOR="\033[1;32mSUCCESS\033[0m"
                ;;
            FAILED)
                STATUS_COLOR="\033[1;31mFAILED\033[0m"
                ;;
            *)
                STATUS_COLOR="$status"
                ;;
        esac

        RANGE="[${start_idx}, ${end_idx})"
        STARTED_SHORT=$(date -d "$started" +"%m-%d %H:%M" 2>/dev/null || echo "$started")

        printf "%-20s %-24b %-20s %s\n" "$RANGE" "$STATUS_COLOR" "$STARTED_SHORT" "$DURATION_STR"
    done

    echo ""
    echo "─────────────────────────────────────────────────"
    echo "Summary:"
    echo "  Total:   $TOTAL chunks"
    echo "  Running: $RUNNING"
    echo "  Success: $SUCCESS"
    echo "  Failed:  $FAILED"
    echo "─────────────────────────────────────────────────"
    echo ""

    # Show crash logs if any
    if [[ $FAILED -gt 0 ]]; then
        echo "###################################################"
        echo "###  ⚠️  FAILED CHUNKS DETECTED  ⚠️             ###"
        echo "###################################################"
        echo ""
        echo "Failed chunks:"
        for status_file in "${STATUS_FILES[@]}"; do
            if [[ ! -f "$status_file" ]]; then
                continue
            fi
            source "$status_file"
            if [[ "$status" == "FAILED" ]]; then
                echo ""
                echo "  ✗ Range: [$start_idx, $end_idx)"
                echo "    Exit code: ${exit_code:-unknown}"
                if [[ -n "${crash_start_idx:-}" ]]; then
                    echo "    Crashed at: [$crash_start_idx, $crash_end_idx)"
                fi
                if [[ -n "${resume_command:-}" ]]; then
                    echo ""
                    echo "    TO RESUME, RUN:"
                    echo "      $resume_command"
                fi
                echo ""
                echo "    Full log: ${status_file%.status}.log"
            fi
        done
        echo ""
        echo "---------------------------------------------------"
        echo "To see all crashes with resume commands, run:"
        echo "  ./operations/find-crashes.sh"
        if [[ -n "$BATCH_ID" ]]; then
            echo "  ./operations/find-crashes.sh --batch-id $BATCH_ID"
        fi
        echo "---------------------------------------------------"
        echo ""
    fi

    # Show active tmux sessions
    if command -v tmux &> /dev/null; then
        echo "Active tmux sessions:"
        ACTIVE_SESSIONS=$(tmux ls 2>/dev/null | grep "fvspec_" || echo "")
        if [[ -n "$ACTIVE_SESSIONS" ]]; then
            echo "$ACTIVE_SESSIONS"
        else
            echo "  (none)"
        fi
    fi

    echo ""
    echo "Logs directory: $LOGS_DIR"
}

# Watch mode or single display
if [[ "$WATCH_MODE" == "true" ]]; then
    while true; do
        clear
        show_status
        echo ""
        echo "Press Ctrl+C to exit watch mode"
        sleep 5
    done
else
    show_status
fi
