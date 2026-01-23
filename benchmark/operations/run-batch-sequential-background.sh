#!/usr/bin/env bash
# Background wrapper for sequential batch runner
# Usage: ./run-batch-sequential-background.sh --variant control-functional --total 1000

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS_DIR="$SCRIPT_DIR/logs"

# Create logs directory
mkdir -p "$LOGS_DIR"

# Generate timestamp for log file
TIMESTAMP=$(date +%Y-%m-%dT%H-%M-%S)
LOG_FILE="$LOGS_DIR/run-batch-sequential-background__${TIMESTAMP}.log"

echo "================================================"
echo "Sequential Batch Runner (Background Mode)"
echo "================================================"
echo "Starting sequential batch processing in background..."
echo "Log file: $LOG_FILE"
echo ""
echo "All arguments will be forwarded to run-batch-sequential.sh"
echo "================================================"
echo ""

# Start the sequential runner in background with nohup
nohup "$SCRIPT_DIR/run-batch-sequential.sh" "$@" > "$LOG_FILE" 2>&1 &

BACKGROUND_PID=$!

echo "✓ Background process started: PID $BACKGROUND_PID"
echo ""
echo "Commands:"
echo "  Watch log:     tail -f $LOG_FILE"
echo "  Check status:  ps -p $BACKGROUND_PID"
echo "  Kill process:  kill $BACKGROUND_PID"
echo ""
echo "Process will continue running even if you disconnect from SSH."
echo "All output is being written to: $LOG_FILE"
echo ""
