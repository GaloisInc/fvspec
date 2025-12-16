# Batch Operations Scripts

Scripts for managing large-scale benchmark runs across multiple tmux sessions with automatic crash detection and recovery.

## Overview

These scripts help you run benchmarks on thousands of samples by:
- Splitting work into manageable chunks
- Running chunks in parallel tmux sessions
- Logging crashes with exact index ranges
- Providing monitoring and recovery tools

## Quick Start

```bash
# Run full dataset in background (safe to close SSH)
./operations/run-batch-background.sh

# Or run in a tmux session
tmux new -s orchestrator
./operations/run-batch.sh
# Press Ctrl+b d to detach

# Or run directly (stays in foreground)
./operations/run-batch.sh

# Monitor progress
./operations/monitor.sh --watch

# Kill all sessions if needed
./operations/kill-all.sh --variant control-functional
```

**Default settings:**
- 53,408 samples (full dataset)
- `control-functional` variant
- 100 samples/chunk (535 tmux sessions)
- All sessions persist after SSH disconnect

## Scripts

### `count-samples.sh` - Database Query

Check how many samples are available in the database.

**Usage:**
```bash
./operations/count-samples.sh
```

**Output:**
- Total datapoints in database
- Eligible for sampling (after filtering deps > 100)
- Count with unit tests
- Example commands for full dataset runs

**Note:** The actual maximum is **53,408 samples** (not 54,345) due to dependency filtering.

### `run-batch-background.sh` - Background Wrapper

Runs `run-batch.sh` in the background using `nohup`. Safe to close SSH immediately.

**Usage:**
```bash
./operations/run-batch-background.sh [same args as run-batch.sh]
```

**What it does:**
- Starts `run-batch.sh` with `nohup`
- Logs to `operations/logs/run-batch-background__*.log`
- Returns immediately
- Safe to close SSH session while tmux sessions are being created

**Examples:**
```bash
# Full dataset in background
./operations/run-batch-background.sh

# Test run in background
./operations/run-batch-background.sh --total 1000

# Check creation progress
tail -f operations/logs/run-batch-background__*.log
```

### `run-batch.sh` - Main Orchestrator

Launches multiple tmux sessions, each processing a chunk of samples.

**Note:** If you close SSH while this is running, it will be interrupted. Use `run-batch-background.sh` or run in a tmux session instead.

**Usage:**
```bash
./operations/run-batch.sh \
    [--total <n>] \
    [--variant <variant>] \
    [--chunk-size <n>] \
    [--parallelism <n>] \
    [--dry-run]
```

**Arguments:**
- `--total`: Total number of samples to process (default: 53,408 - full dataset)
- `--variant`: Prompt variant name (default: `control-functional`)
  - Other options: `terse-functional`, `control-mvcgen`
- `--chunk-size`: Samples per tmux session (default: 100)
- `--parallelism`: Parallel samples within each chunk (default: 10)
- `--dry-run`: Preview chunks without launching

**Examples:**
```bash
# Process full dataset with all defaults (53,408 samples, control-functional)
./operations/run-batch.sh

# Process 1000 samples (10 chunks × 100 samples)
./operations/run-batch.sh --total 1000

# Process 10000 samples (100 chunks × 100 samples)
./operations/run-batch.sh --total 10000

# Use larger chunks for fewer sessions (267 chunks × 200 samples)
./operations/run-batch.sh --chunk-size 200

# Use different variant on full dataset
./operations/run-batch.sh --variant terse-functional

# Preview without running
./operations/run-batch.sh --dry-run
```

### `monitor.sh` - Status Monitor

Check the status of running chunks (success/failure/running).

**Usage:**
```bash
./operations/monitor.sh [--batch-id <id>] [--watch]
```

**Arguments:**
- `--batch-id`: Filter for specific batch (optional)
- `--watch`: Continuously refresh every 5 seconds

**Examples:**
```bash
# One-time status check
./operations/monitor.sh

# Watch mode (auto-refresh)
./operations/monitor.sh --watch

# Monitor specific batch
./operations/monitor.sh --batch-id 2025-12-16T15-30-00__control-functional__total-1000
```

**Output:**
- Lists all chunks with their status (RUNNING/SUCCESS/FAILED)
- Shows duration for each chunk
- Displays crash details for failed chunks
- Shows active tmux sessions

### `kill-all.sh` - Session Killer

Kill all tmux sessions for a variant or all fvspec sessions.

**Usage:**
```bash
./operations/kill-all.sh [--variant <variant>] [--force]
```

**Arguments:**
- `--variant`: Kill only sessions for this variant (optional)
- `--force`: Skip confirmation prompt

**Examples:**
```bash
# Kill all fvspec sessions (with confirmation)
./operations/kill-all.sh

# Kill only control-functional sessions
./operations/kill-all.sh --variant control-functional

# Force kill without confirmation
./operations/kill-all.sh --variant terse-functional --force
```

### `resume.sh` - Failure Recovery

Restart failed chunks from a previous batch run.

**Usage:**
```bash
./operations/resume.sh \
    --batch-id <id> \
    [--parallelism <n>] \
    [--dry-run]
```

**Arguments:**
- `--batch-id`: Batch ID to resume (from batch log)
- `--parallelism`: Parallel samples per chunk (default: 10)
- `--dry-run`: Preview failures without resuming

**Examples:**
```bash
# Resume all failed chunks from a batch
./operations/resume.sh --batch-id 2025-12-16T15-30-00__control-functional__total-1000

# Preview failures
./operations/resume.sh --batch-id <batch-id> --dry-run
```

### `run-chunk.sh` - Worker Script

Internal worker script called by `run-batch.sh`. Not meant for direct use.

## Crash Detection

When a chunk crashes, the scripts capture:
- **Exact index range** where the crash occurred (`start_idx`, `end_idx`)
- **Exit code** from the failed process
- **Full log output** in `logs/CRASH__*.log`
- **Status file** with crash metadata in `logs/chunk__*.status`

Example crash log filename:
```
logs/CRASH__2025-12-16T15-30-00__control-functional__total-1000__100-150.log
```

This tells you the crash occurred while processing samples [100, 150).

## Log Files

All logs are stored in `benchmark/operations/logs/`:

```
logs/
├── batch__<timestamp>__<variant>__total-<n>.log      # Batch metadata
├── chunk__<batch-id>__<start>-<end>.log              # Chunk output
├── chunk__<batch-id>__<start>-<end>.status           # Chunk status
└── CRASH__<batch-id>__<start>-<end>.log              # Crash details
```

### Status File Format

Each chunk creates a `.status` file:

```bash
status=RUNNING|SUCCESS|FAILED
start_idx=0
end_idx=50
variant=control-functional
started=2025-12-16T15:30:00
finished=2025-12-16T15:45:00  # Only if completed
exit_code=0                    # Only if completed
crash_start_idx=25             # Only if failed
crash_end_idx=50               # Only if failed
pid=12345
```

## Tmux Session Names

Sessions are named: `fvspec_<variant>_<start>-<end>`

Examples:
- `fvspec_control-functional_0-50`
- `fvspec_terse-functional_50-100`
- `fvspec_control-mvcgen_900-950`

**Tmux Commands:**
```bash
# List all sessions
tmux ls

# Attach to a session
tmux attach -t fvspec_control-functional_0-50

# Detach from session (inside tmux)
Ctrl+b d

# Kill a specific session
tmux kill-session -t <session-name>
```

## Workflow Examples

### Example 1: Full Dataset Run (Default)

```bash
# Launch full dataset with all defaults (53,408 samples, control-functional)
./operations/run-batch.sh

# Monitor in watch mode
./operations/monitor.sh --watch

# If crashes occur, wait for other chunks to finish, then resume
./operations/resume.sh --batch-id <batch-id>
```

### Example 2: Test Run (Smaller Sample)

```bash
# Launch with 1000 samples for testing
./operations/run-batch.sh --total 1000

# Check status periodically
./operations/monitor.sh

# If you need to stop everything
./operations/kill-all.sh --variant control-functional
```

### Example 3: Custom Configuration

```bash
# Use larger chunks for fewer sessions (267 chunks × 200 samples)
./operations/run-batch.sh --chunk-size 200

# Higher parallelism for faster processing
./operations/run-batch.sh --parallelism 20

# Combine options
./operations/run-batch.sh --chunk-size 200 --parallelism 20

# Preview before running
./operations/run-batch.sh --dry-run
```

### Example 4: Parallel Variant Testing

```bash
# Run multiple variants simultaneously on full dataset
./operations/run-batch.sh &
./operations/run-batch.sh --variant terse-functional &
./operations/run-batch.sh --variant control-mvcgen &

# Monitor all variants
./operations/monitor.sh --watch
```

## Troubleshooting

### Chunks stuck in RUNNING state

Check if tmux sessions are still active:
```bash
tmux ls | grep fvspec_
```

Attach to session to see what's happening:
```bash
tmux attach -t <session-name>
```

### Out of memory / resource exhaustion

Reduce parallelism or chunk size:
```bash
./operations/run-batch.sh \
    --variant control-functional \
    --total 1000 \
    --chunk-size 25 \
    --parallelism 5
```

### Resume not working

Check the batch ID is correct:
```bash
ls operations/logs/batch__*
```

Verify status files exist:
```bash
ls operations/logs/chunk__<batch-id>__*.status
```

## Best Practices

1. **Chunk Size** (for 53,408 sample dataset):
   - **100 samples/chunk** (default) = 534 sessions - Good balance
   - **200 samples/chunk** = 267 sessions - Fewer sessions, less overhead
   - **50 samples/chunk** = 1068 sessions - Faster failure detection, more overhead
   - Smaller chunks = faster failure detection, more session management
   - Larger chunks = less overhead, slower failure detection

2. **Parallelism**:
   - Default of 10 works well for most systems
   - Increase if you have high CPU/memory capacity
   - Decrease if you see resource exhaustion

3. **Monitoring**:
   - Use `--watch` mode to track progress
   - Check logs if chunks are taking longer than expected
   - Look for CRASH files immediately

4. **Recovery**:
   - Let successful chunks finish before resuming failures
   - Use `--dry-run` to preview what will be resumed
   - Archive old logs after successful resume

5. **Large Runs** (10k+ samples):
   - Run overnight or over weekend
   - Use `nohup` or systemd if not using tmux
   - Monitor disk space (logs + artifacts grow large)
   - Consider splitting by variant to isolate issues

## Integration with Main Workflow

These scripts complement the main `uv run fvspec` command:

```bash
# Single run (manual)
uv run fvspec --start-idx 0 --end-idx 100

# Full dataset batch run (automated)
./operations/run-batch.sh
```

The batch scripts automate multiple sequential calls to `fvspec` across tmux sessions:
- Default: 53,408 samples (full eligible dataset)
- Default: `control-functional` variant
- Default: 100 samples per chunk (534 tmux sessions)
- Default: 10 parallel samples within each chunk
