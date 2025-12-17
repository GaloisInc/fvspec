#!/usr/bin/env bash
# Wrapper to run run-batch-queued.sh in the background with nohup
# Safe to disconnect SSH after running this
# RAM-friendly: Only runs N chunks at a time

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS_DIR="$SCRIPT_DIR/logs"

# Create logs directory
mkdir -p "$LOGS_DIR"

# Generate timestamp for log file
TIMESTAMP=$(date +%Y-%m-%dT%H-%M-%S)
LOG_FILE="$LOGS_DIR/run-batch-queued-background__${TIMESTAMP}.log"

echo "================================================"
echo "Background Queued Batch Run (RAM-Friendly)"
echo "================================================"
echo "Starting queued batch orchestration in background..."
echo "Log file: $LOG_FILE"
echo ""
echo "This will run a limited number of chunks at once,"
echo "launching new chunks as old ones complete."
echo "You can safely close your SSH session."
echo ""

# Run run-batch-queued.sh with nohup, passing all arguments
nohup "$SCRIPT_DIR/run-batch-queued.sh" "$@" > "$LOG_FILE" 2>&1 &

BATCH_PID=$!

echo "Background process started: PID $BATCH_PID"
echo ""
echo "Commands:"
echo "  Watch log:     tail -f $LOG_FILE"
echo "  Check PID:     ps -p $BATCH_PID"
echo "  Monitor:       ./operations/monitor.sh --watch"
echo "  Find crashes:  ./operations/find-crashes.sh"
echo ""
echo "The orchestrator will:"
echo "  - Launch chunks gradually as resources become available"
echo "  - Keep RAM usage bounded"
echo "  - Continue running until all chunks complete"
echo "  - You can disconnect and reconnect anytime"
echo ""
