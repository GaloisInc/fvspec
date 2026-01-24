#!/usr/bin/env bash
# Wrapper to run run-batch-queued.sh in the background using tmux
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
echo "Starting queued batch orchestration in tmux..."
echo "Log file: $LOG_FILE"
echo ""
echo "This will run a limited number of chunks at once,"
echo "launching new chunks as old ones complete."
echo "You can safely close your SSH session."
echo ""

# Create tmux session name with timestamp
SESSION_NAME="fvspec_queued_orchestrator_${TIMESTAMP}"

# Check if session already exists
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "ERROR: Session $SESSION_NAME already exists"
    echo "Attach with: tmux attach -t $SESSION_NAME"
    exit 1
fi

# Run run-batch-queued.sh in a tmux session with logging
# Create a temporary wrapper script to avoid quoting issues
WRAPPER_SCRIPT="$LOGS_DIR/.wrapper__${TIMESTAMP}.sh"
cat > "$WRAPPER_SCRIPT" <<'WRAPPER_EOF'
#!/usr/bin/env bash
set -euo pipefail
WRAPPER_EOF

echo "exec '$SCRIPT_DIR/run-batch-queued.sh' \\" >> "$WRAPPER_SCRIPT"
for arg in "$@"; do
    printf '  %q \\\n' "$arg" >> "$WRAPPER_SCRIPT"
done
echo "  2>&1 | tee '$LOG_FILE'" >> "$WRAPPER_SCRIPT"

chmod +x "$WRAPPER_SCRIPT"

# Run the wrapper in tmux
tmux new-session -d -s "$SESSION_NAME" "$WRAPPER_SCRIPT"

echo "✓ Orchestrator started in tmux session: $SESSION_NAME"
echo ""
echo "Commands:"
echo "  Attach:        tmux attach -t $SESSION_NAME"
echo "  Watch log:     tail -f $LOG_FILE"
echo "  Monitor:       ./operations/monitor.sh --watch"
echo "  Find crashes:  ./operations/find-crashes.sh"
echo "  Kill session:  tmux kill-session -t $SESSION_NAME"
echo ""
echo "The orchestrator will:"
echo "  - Launch chunks gradually as resources become available"
echo "  - Keep RAM usage bounded"
echo "  - Continue running until all chunks complete"
echo "  - You can disconnect and reconnect anytime"
echo ""
