#!/usr/bin/env bash
# Run fvspec generation pipeline comparing claude-opus-4-6 vs claude-sonnet-4-6
# on 500 samples with ranseed=0.
#
# Must be run from ./benchmark:  ./operations/46/run.sh

set -euo pipefail

BENCHMARK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$BENCHMARK_DIR"

SESSION="fvspec46"

# Kill existing session if present
tmux kill-session -t "$SESSION" 2>/dev/null || true

# Window 0: opus
tmux new-session -d -s "$SESSION" -n "opus" -x 220 -y 50
tmux send-keys -t "$SESSION:0" \
  "cd $BENCHMARK_DIR && uv run fvspec --model anthropic/claude-opus-4-6 --ranseed 0 --sample-size 500" \
  Enter

# Window 1: sonnet
tmux new-window -t "$SESSION" -n "sonnet"
tmux send-keys -t "$SESSION:1" \
  "cd $BENCHMARK_DIR && uv run fvspec --model anthropic/claude-sonnet-4-6 --ranseed 0 --sample-size 500" \
  Enter

echo "Both runs started in tmux session: $SESSION"
echo "  Window 0 (opus):   claude-opus-4-6,   500 samples, seed=0"
echo "  Window 1 (sonnet): claude-sonnet-4-6, 500 samples, seed=0"
echo ""
echo "Attach:          tmux attach -t $SESSION"
echo "Switch windows:  Ctrl-b 0  /  Ctrl-b 1"
