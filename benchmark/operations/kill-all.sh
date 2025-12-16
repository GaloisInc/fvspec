#!/usr/bin/env bash
# Kill all tmux sessions for a specific variant or all fvspec sessions

set -euo pipefail

# Parse arguments
VARIANT=""
CONFIRM=true

while [[ $# -gt 0 ]]; do
    case $1 in
        --variant)
            VARIANT="$2"
            shift 2
            ;;
        --force)
            CONFIRM=false
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--variant <variant>] [--force]"
            exit 1
            ;;
    esac
done

# Build session pattern
if [[ -n "$VARIANT" ]]; then
    PATTERN="fvspec_${VARIANT}_"
    DESC="variant '$VARIANT'"
else
    PATTERN="fvspec_"
    DESC="all fvspec runs"
fi

# Find matching sessions
SESSIONS=$(tmux ls 2>/dev/null | grep "$PATTERN" | cut -d: -f1 || true)

if [[ -z "$SESSIONS" ]]; then
    echo "No tmux sessions found matching: $PATTERN"
    exit 0
fi

echo "Found sessions matching $DESC:"
echo "$SESSIONS"
echo ""

NUM_SESSIONS=$(echo "$SESSIONS" | wc -l)
echo "Total: $NUM_SESSIONS sessions"
echo ""

# Confirm before killing
if [[ "$CONFIRM" == "true" ]]; then
    read -p "Kill all these sessions? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled"
        exit 0
    fi
fi

# Kill each session
echo "Killing sessions..."
while IFS= read -r session; do
    echo "  Killing: $session"
    tmux kill-session -t "$session" 2>/dev/null || echo "    (already gone)"
done <<< "$SESSIONS"

echo ""
echo "✓ All sessions killed"
