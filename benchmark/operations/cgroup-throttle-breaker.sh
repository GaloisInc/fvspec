#!/bin/bash

# Configuration
RUN_TIME=300
GAP_TIME=5

# TRAP: Wake everyone on exit
trap 'echo "Exiting..."; pgrep "lean|lake|python|uv" | xargs kill -CONT 2>/dev/null; exit' SIGINT SIGTERM

while true; do
    # 1. Find ONLY the Python orchestrator PIDs
    # We remove -f and use -a to see the command, then grep for fvspec
    # This prevents matching the shell or the script's own path
    ANCHORS=($(pgrep python | xargs -r ps -o pid,args -p | grep "fvspec" | awk '{print $1}'))

    if [ ${#ANCHORS[@]} -eq 0 ]; then
        sleep 10 && continue
    fi

    for active_pid in "${ANCHORS[@]}"; do
        # 2. THE GLOBAL FREEZE (By process name, not full string)
        # This avoids freezing your bash shell or tmux
        pgrep "lean|lake|python|uv" | grep -v -e "$$" -e "$PPID" | xargs kill -STOP 2>/dev/null

        # 3. THE THAW
        echo "[$(date +%T)] --> ACTIVE: $active_pid"
        kill -CONT "$active_pid" 2>/dev/null
        # Wake all math workers globally
        pgrep "lean|lake" | xargs kill -CONT 2>/dev/null

        sleep "$RUN_TIME"

        # 4. PAUSE
        pgrep "lean|lake|python|uv" | grep -v -e "$$" -e "$PPID" | xargs kill -STOP 2>/dev/null
        sleep "$GAP_TIME"
        break
    done
done
