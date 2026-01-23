#!/bin/bash

# --- Configuration ---
RUN_TIME=300  # 5 minutes per job
GAP_TIME=5    # Cooldown for kernel memory reclaim
# Pattern to identify your specific orchestrators
ANCHOR_PATTERN="python.*fvspec"
# Pattern for all memory-heavy workers (Regex: fvspec OR lean OR lake)
WORKER_PATTERN="fvspec|lean|lake"

# --- Cleanup Trap ---
trap 'echo -e "\n[!] Signal received. Waking all processes..."; pgrep -f "$WORKER_PATTERN" | xargs kill -CONT 2>/dev/null; exit' SIGINT SIGTERM

echo "------------------------------------------------"
echo "fvspec Broad-Net Rotator Started"
echo "Targeting Orchestrators: $ANCHOR_PATTERN"
echo "Managing Workers: $WORKER_PATTERN"
echo "------------------------------------------------"

while true; do
    # 1. Identify the stable Python 'Anchors'
    # Exclude bash, the script ($$), and the parent shell ($PPID)
    ANCHORS=($(pgrep -f "$ANCHOR_PATTERN" | grep -v -e "bash" -e "sh" -e "$$" -e "$PPID"))

    if [ ${#ANCHORS[@]} -eq 0 ]; then
        echo "[$(date +%T)] No active jobs found. Sleeping 10s..."
        sleep 10
        continue
    fi

    echo "[$(date +%T)] Queue: ${ANCHORS[*]} (${#ANCHORS[@]} jobs)"

    for active_pid in "${ANCHORS[@]}"; do
        # 2. THE GLOBAL FREEZE
        # Use the pipe-separated string for pgrep
        pgrep -f "$WORKER_PATTERN" | grep -v -e "$$" -e "$PPID" | xargs kill -STOP 2>/dev/null

        # 3. THE TARGETED THAW
        echo "[$(date +%T)] --> ACTIVE: Anchor $active_pid"

        # Wake the specific Python orchestrator
        kill -CONT "$active_pid" 2>/dev/null

        # Wake all lean/lake workers
        pgrep -f "lean|lake" | xargs kill -CONT 2>/dev/null

        # 4. RUN PERIOD
        sleep "$RUN_TIME"

        # 5. TRANSITION PAUSE
        echo "[$(date +%T)] ||| PAUSING: Anchor $active_pid"
        pgrep -f "$WORKER_PATTERN" | grep -v -e "$$" -e "$PPID" | xargs kill -STOP 2>/dev/null
        sleep "$GAP_TIME"

        # Break to re-scan for new/finished jobs
        break
    done
done
