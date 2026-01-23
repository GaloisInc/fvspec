#!/bin/bash

# Configuration
RUN_TIME=600  # 5 minutes: Better for 1-3 hour jobs
GAP_TIME=20    # 5 seconds: Let the kernel breathe

# Cleanup: Wake everyone up if we stop the script
trap 'echo "Terminating: Waking all jobs..."; pgrep -f fvspec | xargs kill -CONT 2>/dev/null; exit' SIGINT SIGTERM

echo "------------------------------------------------"
echo "fvspec Long-Job Rotator Started"
echo "Mode: Single-Process Throughput"
echo "------------------------------------------------"

while true; do
    # Only find the PIDs of the actual Python scripts, ignoring the internal Lean workers
    PIDS=($(pgrep "fvspec"))
    COUNT=${#PIDS[@]}

    if [ $COUNT -eq 0 ]; then
        echo "[$(date +%T)] No active fvspec jobs. Checking again in 30s..."
        sleep 30
        continue
    fi

    echo "[$(date +%T)] $COUNT jobs in queue. Rotating..."

    for pid in "${PIDS[@]}"; do
        # Verify PID still exists
        if kill -0 "$pid" 2>/dev/null; then

            # 1. Stop everyone else
            pgrep -f fvspec | grep -v -e "$$" -e "$pid" | xargs kill -STOP 2>/dev/null

            # 2. Start the chosen one
            echo "[$(date +%T)] --> RUNNING: PID $pid ($COUNT jobs total)"
            kill -CONT "$pid" 2>/dev/null

            # 3. Wait for the long stretch
            sleep "$RUN_TIME"

            # 4. Pause it
            echo "[$(date +%T)] ||| PAUSING: PID $pid"
            kill -STOP "$pid" 2>/dev/null
            sleep "$GAP_TIME"
        fi

        # Break to re-scan pgrep in case your queue script added/removed jobs
        break
    done
done
