# Batch Operations Cheatsheet

Quick reference for common operations.

## Check Available Samples

```bash
# Query database for exact counts
./operations/count-samples.sh
# Shows: Total = 54,345, Eligible = 53,408 (after filtering)
```

## Launch Batch Runs

```bash
# Full dataset in background (safe to close SSH)
./operations/run-batch-background.sh

# Or in tmux session
tmux new -s orchestrator
./operations/run-batch.sh
# Ctrl+b d to detach

# Full dataset (foreground)
./operations/run-batch.sh

# Preview without running
./operations/run-batch.sh --dry-run

# Test with 1000 samples
./operations/run-batch.sh --total 1000

# Fewer sessions: larger chunks (267 chunks × 200 samples)
./operations/run-batch.sh --chunk-size 200

# Use different variant
./operations/run-batch.sh --variant terse-functional

# Combine options
./operations/run-batch.sh --total 10000 --chunk-size 200 --parallelism 20
```

## Monitor Progress

```bash
# One-time check
./operations/monitor.sh

# Auto-refresh every 5 seconds
./operations/monitor.sh --watch

# Filter by batch ID
./operations/monitor.sh --batch-id <batch-id>
```

## Manage Sessions

```bash
# List all fvspec sessions
tmux ls | grep fvspec_

# Attach to a session
tmux attach -t fvspec_control-functional_0-50

# Detach (when inside tmux)
Ctrl+b d

# Kill all sessions for a variant
./operations/kill-all.sh --variant control-functional

# Force kill without confirmation
./operations/kill-all.sh --force
```

## Handle Failures

```bash
# View crash logs
ls operations/logs/CRASH__*

# Resume failed chunks
./operations/resume.sh --batch-id <batch-id>

# Preview failures
./operations/resume.sh --batch-id <batch-id> --dry-run
```

## Log Files

```bash
# View batch metadata
cat operations/logs/batch__<timestamp>__<variant>__total-<n>.log

# View chunk output
cat operations/logs/chunk__<batch-id>__<start>-<end>.log

# View chunk status
cat operations/logs/chunk__<batch-id>__<start>-<end>.status

# Find all crashes
ls operations/logs/CRASH__*
```

## Useful Patterns

### Run multiple variants in parallel
```bash
# Full dataset on all variants
./operations/run-batch.sh &
./operations/run-batch.sh --variant terse-functional &
./operations/run-batch.sh --variant control-mvcgen &
wait

# Or smaller test
./operations/run-batch.sh --total 500 &
./operations/run-batch.sh --total 500 --variant terse-functional &
./operations/run-batch.sh --total 500 --variant control-mvcgen &
wait
```

### Monitor specific variant
```bash
watch -n 5 "tmux ls | grep fvspec_control-functional"
```

### Count successes/failures
```bash
grep -r "status=SUCCESS" operations/logs/*.status | wc -l
grep -r "status=FAILED" operations/logs/*.status | wc -l
```

### Find which indices crashed
```bash
grep "crash_start_idx" operations/logs/*.status
```

### Clean up old logs
```bash
# Archive logs older than 7 days
find operations/logs -name "*.log" -mtime +7 -exec mv {} operations/logs/archive/ \;
```

## Common Issues

### "Session already exists"
```bash
# List existing sessions
tmux ls | grep fvspec_

# Kill the session
tmux kill-session -t <session-name>

# Or kill all
./operations/kill-all.sh --force
```

### "No space left on device"
```bash
# Check disk usage
df -h

# Clean up old artifacts
rm -rf benchmark/artifacts/runs/old-run-*
```

### Chunk stuck in RUNNING
```bash
# Attach to see what's happening
tmux attach -t <session-name>

# If truly stuck, kill it
tmux kill-session -t <session-name>

# Update status manually
echo "status=FAILED" >> operations/logs/chunk__<batch-id>__<start>-<end>.status
```

## Performance Tuning

### High-memory system
```bash
./operations/run-batch.sh \
    --variant control-functional \
    --total 10000 \
    --chunk-size 100 \
    --parallelism 20
```

### Low-memory system
```bash
./operations/run-batch.sh \
    --variant control-functional \
    --total 1000 \
    --chunk-size 25 \
    --parallelism 5
```

### Fastest completion (many small chunks)
```bash
./operations/run-batch.sh \
    --variant control-functional \
    --total 1000 \
    --chunk-size 10 \
    --parallelism 10
```
