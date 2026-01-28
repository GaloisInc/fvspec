# fvspec Job Stall Recovery Playbook

## Purpose
Diagnose and recover from stalled benchmark jobs without losing progress or corrupting data.

## When to Use This Playbook
- Job appears frozen for >30 minutes
- Memory usage is high but no progress visible
- RAM safeguards triggered but job not recovering

---

## Phase 1: Confirm the Stall

### 1.1 Check Log Freshness
```bash
# Get current time and last log update
date
stat -c '%y' benchmark/operations/logs/chunk__*.log | tail -1

# If last update >30 minutes ago → likely stalled
```

### 1.2 Check Recent Progress
```bash
# Last few log entries should show step progression
tail -10 benchmark/operations/logs/chunk__*.log

# Look for timestamps - should be within last 10-15 minutes if active
```

### 1.3 Verify File Write Activity
```bash
# Count Lean files modified in last 15 minutes
find benchmark/artifacts/.tmp -type f -name "*.lean" -mmin -15 2>/dev/null | wc -l

# If count is 0 → no write activity → likely stalled
```

### 1.4 Check Memory Pressure
```bash
# Current memory state
free -h

# If "available" < 500MB → severe memory pressure
```

---

## Phase 2: Identify the Culprit

### 2.1 Find the Main fvspec Process
```bash
# Get main Python orchestrator PID
ps aux | grep "python.*fvspec --variant" | grep -v grep

# Note the PID and check its state:
# - 'S' (sleeping) = normal
# - 'D' (uninterruptible sleep) = STALLED waiting for I/O
# - 'R' (running) = active
```

### 2.2 Find Memory Hogs
```bash
# List all Lean processes by memory usage
ps aux | grep lean | awk '$6 > 10000000' | sort -k6 -rn

# Look for processes using >10GB RSS (column 6, in KB)
# Typical culprit: lean --worker using 20-25GB
```

### 2.3 Identify the Stuck Sample
```bash
# Extract sample ID from the biggest lean process
ps aux | grep "lean --worker" | grep -oP 'fvspec_\d+_[^/]+'

# This tells you which sample is stuck (e.g., fvspec_10482_test_segment_one_hot_n5m7b7v8)
```

### 2.4 Check Process CPU Usage
```bash
# Get detailed stats for suspected stuck process
# Replace STUCK_PID with the PID from step 2.2
ps -p STUCK_PID -o pid,state,%cpu,%mem,etime,cmd

# If %CPU < 10% and state is 'S' or 'D' → likely stuck
# If ELAPSED time > 1 hour for one worker → pathological case
```

---

## Phase 3: Determine What's Safe to Kill

### 3.1 Process Hierarchy Safety Rules

**NEVER KILL:**
- The tmux session itself
- The main bash wrapper script
- The Python orchestrator (unless doing full restart)
- The systemd-run scope

**SAFE TO KILL (in order of preference):**
1. **Individual lean --worker processes** (PID 2338699 style)
   - These are spawned per-file compilation
   - LSP will respawn them if needed
   - Job orchestrator will retry the sample

2. **Lake build processes for a single sample**
   - Kills one sample's build tree
   - Orchestrator will mark it failed and continue

3. **Entire sample tree** (all processes for fvspec_XXXXX_*)
   - Nuclear option for one sample
   - Job continues with remaining samples

### 3.2 Verify Job Can Recover
```bash
# Check that orchestrator is alive and in good state
ps -p $(pgrep -f "python.*fvspec --variant" | head -1) -o pid,state,cmd

# If state is 'D' (uninterruptible) → killing worker won't help
# If state is 'S' (sleeping) → it's waiting for worker, safe to kill worker
```

---

## Phase 4: Execute Kill

### 4.1 Option 1: Kill Stuck Lean Worker (SAFEST)
```bash
# Get the PID of the stuck lean --worker (from Phase 2.2)
STUCK_PID=$(ps aux | grep "lean --worker" | awk '$6 > 20000000 {print $2; exit}')

# Kill it
kill -9 $STUCK_PID

# Why this is safe:
# - Orchestrator expects workers to fail sometimes
# - Sample will be marked as failed or retried
# - done.txt not updated until chunk completes
# - No data corruption risk
```

### 4.2 Option 2: Kill Entire Sample Tree
```bash
# Get the stuck sample ID
STUCK_SAMPLE=$(ps aux | grep "lean --worker" | grep -oP 'fvspec_\d+_[^/]+' | head -1)

# Kill all processes for this sample
pkill -9 -f "$STUCK_SAMPLE"

# Why this is safe:
# - Kills only one sample's work
# - Orchestrator will mark sample failed
# - Other samples continue processing
```

### 4.3 Option 3: Restart Entire Chunk (NUCLEAR)
⚠️ Only if Options 1-2 don't work and orchestrator is deadlocked

```bash
# 1. Get current progress
tail -1 benchmark/operations/logs/chunk__*.log
# Note the "Steps: XX/100" number

# 2. Kill the tmux session
tmux kill-session -t fvspec_orchestrator_$(ls -t benchmark/operations/logs/chunk__*.log | head -1 | grep -oP '\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}')

# 3. Manually mark partial progress in done.txt (OPTIONAL - prevents reprocessing)
# If you were at step 53/100 for range 10400-10500, estimate ~10453 completed
# DON'T add to done.txt if unsure - redundant work is safer than skipped work

# 4. Restart chunk with reduced parallelism
cd benchmark/operations
./run-batch-sequential-background.sh \
  --variant control-functional \
  --start-idx 10400 \
  --end-idx 10500 \
  --parallelism 6  # Reduced from 10
```

---

## Phase 5: Verify Recovery

### 5.1 Monitor Log Activity
```bash
# Watch for new log entries
tail -f benchmark/operations/logs/chunk__*.log

# Should see new "Steps:" entries within 2-5 minutes
```

### 5.2 Check Process Tree
```bash
# Verify new Lean workers spawned
ps aux | grep lean | wc -l

# Should see active compilation processes
```

### 5.3 Monitor Memory
```bash
# Watch memory usage stabilize
watch -n 10 free -h

# Should see "available" memory increase if stuck worker is gone
```

### 5.4 Confirm Progress
```bash
# Check that step count is increasing
watch -n 60 'tail -1 benchmark/operations/logs/chunk__*.log | grep Steps'

# "Steps: XX/100" number should increment
```

---

## Common Scenarios

### Scenario A: Single Lean Worker Using 20-25GB, CPU <10%
**Diagnosis:** Pathological sample hitting memory limits
**Action:** Kill worker (Option 1)
**Recovery Time:** 2-5 minutes

### Scenario B: Python Orchestrator in 'D' State
**Diagnosis:** Deadlocked waiting for LSP response
**Action:** Kill stuck worker (Option 1), if no recovery in 5min → kill sample tree (Option 2)
**Recovery Time:** 5-10 minutes

### Scenario C: Multiple Samples Stuck, Memory >95%
**Diagnosis:** Systemic memory exhaustion
**Action:** Restart chunk with lower parallelism (Option 3)
**Recovery Time:** Immediate (fresh start)

### Scenario D: No Progress, But Processes Show >20% CPU
**Diagnosis:** Not actually stalled, just slow under throttling
**Action:** Wait another 15-30 minutes, monitor
**Recovery Time:** N/A (false alarm)

---

## Data Integrity Guarantees

### What's Protected
- ✅ `done.txt` only updated on successful chunk completion
- ✅ Killed samples marked as failures, not successes
- ✅ Artifacts written atomically or not at all
- ✅ Database transactions are isolated

### What's NOT Protected
- ⚠️ Work-in-progress artifacts in `.tmp/` (cleaned on restart)
- ⚠️ Partial log files (cosmetic only)
- ⚠️ Memory stats for failed samples

### Safe Recovery Rule
**If a chunk was interrupted, it's safe to:**
1. **Re-run the entire chunk** → will reprocess all samples
2. **Skip the chunk** → mark entire range as done (data loss)
3. **Manually inspect** → check artifacts, selectively mark ranges

**Never do:**
- ❌ Edit done.txt while job is running
- ❌ Modify .tmp/ directories manually
- ❌ Kill systemd-run scope directly
- ❌ Force kill tmux with SIGKILL on the session

---

## Quick Reference Commands

```bash
# Detect stall
stat -c '%y' benchmark/operations/logs/chunk__*.log | tail -1

# Find stuck worker
ps aux | grep "lean --worker" | awk '$6 > 20000000'

# Kill stuck worker
kill -9 <PID>

# Monitor recovery
tail -f benchmark/operations/logs/chunk__*.log

# Check memory
free -h

# Emergency: restart chunk
tmux kill-session -t fvspec_orchestrator_*
```

---

## Prevention

### Reduce Likelihood of Future Stalls
1. Lower parallelism for high-index samples: `--parallelism 6-8` instead of 10
2. Use smaller chunk sizes: `--chunk-size 50` instead of 100
3. Monitor memory proactively: set up alerts at 80% usage
4. Implement per-sample timeout (future work)

### Early Warning Signs
- Memory climbing >25GB
- "available" memory <1GB for >10 minutes
- CPU% of Lean workers dropping below 15%
- Log updates slowing to >5 minutes between entries
