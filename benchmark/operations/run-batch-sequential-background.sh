#!/usr/bin/env bash
# Background wrapper for sequential batch runner using tmux
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
echo "Starting sequential batch processing in tmux..."
echo "Log file: $LOG_FILE"
echo ""
echo "All arguments will be forwarded to run-batch-sequential.sh"
echo "================================================"
echo ""

# Create tmux session name with timestamp
SESSION_NAME="fvspec_orchestrator_${TIMESTAMP}"

# Check if session already exists
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "ERROR: Session $SESSION_NAME already exists"
    echo "Attach with: tmux attach -t $SESSION_NAME"
    exit 1
fi

# Start the sequential runner in a tmux session with logging
# Create a temporary wrapper script to avoid quoting issues
WRAPPER_SCRIPT="$LOGS_DIR/.wrapper__${TIMESTAMP}.sh"
cat > "$WRAPPER_SCRIPT" <<'WRAPPER_EOF'
#!/usr/bin/env bash
set -euo pipefail
WRAPPER_EOF

echo "exec '$SCRIPT_DIR/run-batch-sequential.sh' \\" >> "$WRAPPER_SCRIPT"
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
echo "  Kill session:  tmux kill-session -t $SESSION_NAME"
echo ""
echo "Session will continue running even if you disconnect from SSH."
echo "All output is being written to: $LOG_FILE"
echo ""
