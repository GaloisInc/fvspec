#!/usr/bin/env bash
# Diagnose fvspec hang by monitoring for stalls and capturing Python stack traces.
# Usage: ./scripts/diagnose_hang.sh
set -euo pipefail

ARTIFACTS_DIR="/home/q/projects/fvspec/benchmark/artifacts"
DIAG_DIR="/home/q/projects/fvspec/benchmark/artifacts/hang_diagnosis_$(date +%Y%m%dT%H%M%S)"
CHECK_INTERVAL=60  # seconds between checks
STALL_THRESHOLD=3  # consecutive checks with no new files before capturing
LOG="$DIAG_DIR/monitor.log"
STDERR_LOG="$DIAG_DIR/fvspec_stderr.log"

mkdir -p "$DIAG_DIR"

echo "=== Hang diagnosis started at $(date) ===" | tee "$LOG"
echo "Diagnosis output: $DIAG_DIR" | tee -a "$LOG"

# Start fvspec in background — stderr goes to separate file (faulthandler writes there)
cd /home/q/projects/fvspec/benchmark
uv run fvspec -n 250 -s 100 > "$DIAG_DIR/fvspec_stdout.log" 2>"$STDERR_LOG" &
FVSPEC_PID=$!
echo "Started fvspec PID=$FVSPEC_PID" | tee -a "$LOG"

# Wait for the python child process to appear
sleep 5
PYTHON_PID=$(ps aux | grep '[f]vspec.*-n 250' | grep python | awk '{print $2}' | head -1)
echo "Python process PID=$PYTHON_PID" | tee -a "$LOG"

if [ -z "$PYTHON_PID" ]; then
    echo "ERROR: Could not find python process" | tee -a "$LOG"
    exit 1
fi

touch /tmp/fvspec-diag-last-check
stall_count=0
check_num=0

while kill -0 "$PYTHON_PID" 2>/dev/null; do
    sleep "$CHECK_INTERVAL"
    check_num=$((check_num + 1))

    # Count new files since last check — exclude the diagnosis dir itself
    new_files=$(find "$ARTIFACTS_DIR" -path "$DIAG_DIR" -prune -o -type f -newer /tmp/fvspec-diag-last-check -print 2>/dev/null | wc -l)
    touch /tmp/fvspec-diag-last-check

    # Get CPU and thread info
    cpu=$(ps -p "$PYTHON_PID" -o %cpu= 2>/dev/null || echo "dead")
    threads=$(ls /proc/"$PYTHON_PID"/task/ 2>/dev/null | wc -l || echo 0)

    # Count running vs sleeping threads
    running=0
    sleeping=0
    if [ -d "/proc/$PYTHON_PID/task" ]; then
        for tid in $(ls /proc/"$PYTHON_PID"/task/ 2>/dev/null); do
            state=$(cat /proc/"$PYTHON_PID"/task/"$tid"/stat 2>/dev/null | awk '{print $3}')
            case "$state" in
                R) running=$((running + 1)) ;;
                S) sleeping=$((sleeping + 1)) ;;
            esac
        done
    fi

    status="check=$check_num new_files=$new_files cpu=$cpu threads=$threads running=$running sleeping=$sleeping stall_count=$stall_count"
    echo "$(date +%H:%M:%S) $status" | tee -a "$LOG"

    if [ "$new_files" -eq 0 ]; then
        stall_count=$((stall_count + 1))
    else
        stall_count=0
    fi

    # If stalled for STALL_THRESHOLD consecutive checks, capture diagnostics
    if [ "$stall_count" -ge "$STALL_THRESHOLD" ]; then
        echo "$(date +%H:%M:%S) STALL DETECTED after $stall_count checks with no new files" | tee -a "$LOG"

        # Send SIGUSR1 to trigger faulthandler (dumps all Python thread stacks to stderr)
        echo "--- Sending SIGUSR1 for faulthandler dump ---" | tee -a "$LOG"
        kill -SIGUSR1 "$PYTHON_PID" 2>/dev/null || true
        sleep 2

        echo "--- faulthandler output ---" | tee -a "$LOG"
        cp "$STDERR_LOG" "$DIAG_DIR/faulthandler_dump.txt"
        tail -200 "$STDERR_LOG" | tee -a "$LOG"

        # Capture /proc thread states
        echo "--- /proc thread states ---" | tee -a "$LOG"
        for tid in $(ls /proc/"$PYTHON_PID"/task/ 2>/dev/null); do
            state=$(cat /proc/"$PYTHON_PID"/task/"$tid"/stat 2>/dev/null | awk '{print $3}')
            wchan=$(cat /proc/"$PYTHON_PID"/task/"$tid"/wchan 2>/dev/null)
            echo "  Thread $tid: state=$state wchan=$wchan" | tee -a "$LOG"
        done

        echo "$(date +%H:%M:%S) Diagnostics captured. Killing process." | tee -a "$LOG"
        kill "$PYTHON_PID" 2>/dev/null || true
        break
    fi
done

echo "=== Diagnosis complete at $(date) ===" | tee -a "$LOG"
echo "Results in: $DIAG_DIR" | tee -a "$LOG"
