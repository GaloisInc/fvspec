#!/bin/bash

# --- Configuration ---
RUN_TIME=300  # 5 minutes per job
GAP_TIME=5    # Cooldown for kernel memory reclaim
# Pattern to identify your specific orchestrators
ANCHOR_PATTERN="python.*fvspec"
# Patterns for all memory-heavy workers
WORKER_PATTERN="-e fvspec -e lean -e lake"

# --- Cleanup Trap ---
# If you Ctrl+C, wake up EVERY fvspec/lean/lake process on the box
trap 'echo -e "\n[!] Signal received. Waking all processes..."; pgrep -f $WORKER_PATTERN | xargs kill -CONT 2>/dev/null; exit' SIGINT SIGTERM

echo "------------------------------------------------"
echo "fvspec Broad-Net Rotator Started"
echo "Targeting Orchestrators: $ANCHOR_PATTERN"
echo "Managing Workers: $WORKER_PATTERN"
echo "------------------------------------------------"

while true; do
    # 1. Identify the 4 stable Python 'Anchors'
    # We exclude bash shells and the script itself to avoid TTY freezes
    ANCHORS=($(pgrep -f "$ANCHOR_PATTERN" | grep -v -e "bash" -e "sh" -e "$$"))

    if [ ${#ANCHORS[@]} -eq 0 ]; then
        echo "[$(date +%T)] No active jobs found. Sleeping 10s..."
        sleep 10
        continue
    fi

    echo "[$(date +%T)] Queue: ${ANCHORS[*]} (${#ANCHORS[@]} jobs)"

    for active_pid in "${ANCHORS[@]}"; do
        # 2. THE GLOBAL FREEZE
        # Immediately stop every process that looks like fvspec, lean, or lake.
        # This clears the path for the one we are about to wake up.
        pgrep -f $WORKER_PATTERN | grep -v -e "$$" -e "$PPID" | xargs kill -STOP 2>/dev/null

        # 3. THE TARGETED THAW
        # We wake the specific Python orchestrator.
        # Then we wake all Lean/Lake workers.
        # Note: Workers of 'Paused' parents will stay idle because their pipes are blocked.
        echo "[$(date +%T)] --> ACTIVE: Anchor $active_pid"
        kill -CONT "$active_pid" 2>/dev/null
        pgrep -f -e lean -e lake | xargs kill -CONT 2>/dev/null

        # 4. RUN PERIOD
        sleep "$RUN_TIME"

        # 5. TRANSITION PAUSE
        # Freeze everyone again before moving the turn to the next anchor.
        echo "[$(date +%T)] ||| PAUSING: Anchor $active_pid"
        pgrep -f $WORKER_PATTERN | grep -v -e "$$" -e "$PPID" | xargs kill -STOP 2>/dev/null
        sleep "$GAP_TIME"

        # We break the inner loop to re-scan pgrep in case jobs finished/started
        break
    done
done
