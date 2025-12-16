#!/usr/bin/env bash
# Wrapper to run run-batch.sh in the background with nohup
# Safe to disconnect SSH after running this

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS_DIR="$SCRIPT_DIR/logs"

# Create logs directory
mkdir -p "$LOGS_DIR"

# Generate timestamp for log file
TIMESTAMP=$(date +%Y-%m-%dT%H-%M-%S)
LOG_FILE="$LOGS_DIR/run-batch-background__${TIMESTAMP}.log"

echo "================================================"
echo "Background Batch Run"
echo "================================================"
echo "Starting batch orchestration in background..."
echo "Log file: $LOG_FILE"
echo ""
echo "This will create all tmux sessions and then exit."
echo "You can safely close your SSH session."
echo ""

# Run run-batch.sh with nohup, passing all arguments
nohup "$SCRIPT_DIR/run-batch.sh" "$@" > "$LOG_FILE" 2>&1 &

BATCH_PID=$!

echo "Background process started: PID $BATCH_PID"
echo ""
echo "Commands:"
echo "  Watch log:    tail -f $LOG_FILE"
echo "  Check PID:    ps -p $BATCH_PID"
echo "  Monitor:      ./operations/monitor.sh --watch"
echo ""
echo "Once tmux sessions are created (1-2 minutes), you can:"
echo "  - Close your SSH session"
echo "  - Sessions will continue running"
echo "  - Reconnect later and use: ./operations/monitor.sh"
echo ""
