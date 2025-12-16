# Quick Start - Server Usage

Ultra-simple guide for running benchmarks on the server.

## TL;DR - Safe for SSH Disconnect

```bash
cd benchmark

# Run in background (safe to close SSH)
./operations/run-batch-background.sh

# Or run in a tmux session
tmux new -s orchestrator
./operations/run-batch.sh
# Press Ctrl+b d to detach
```

That's it! Runs the full dataset (53,408 samples) with all defaults.

## What Happens

When you run the batch script:
1. Creates 535 tmux sessions automatically (takes 1-2 minutes)
2. Each session processes 100 samples
3. Logs everything to `operations/logs/`
4. Crashes are logged with exact index ranges
5. **All sessions persist after SSH disconnect**

## Monitoring

```bash
# Watch progress (auto-refresh every 5 seconds)
./operations/monitor.sh --watch

# One-time check
./operations/monitor.sh

# Check sample counts
./operations/count-samples.sh
```

## Common Options

```bash
# Preview without running
./operations/run-batch.sh --dry-run

# Test with 1000 samples
./operations/run-batch.sh --total 1000

# Use larger chunks (fewer sessions)
./operations/run-batch.sh --chunk-size 200

# Different variant
./operations/run-batch.sh --variant terse-functional
```

## No Manual Tmux Management

You don't need to:
- Create tmux sessions
- Manage session names
- Attach/detach manually

Everything is automated. Just:
1. Run `./operations/run-batch-background.sh` (or in tmux)
2. Wait 1-2 minutes for all sessions to be created
3. Close SSH (sessions keep running)
4. Come back later and check `./operations/monitor.sh`

## Running in Background - Three Methods

### Method 1: Background Script (Easiest)
```bash
./operations/run-batch-background.sh
# Safe to close SSH immediately after this starts
```

### Method 2: Tmux Session (Recommended)
```bash
tmux new -s orchestrator
./operations/run-batch.sh
# Press Ctrl+b d to detach, or just close SSH
```

### Method 3: nohup (Manual)
```bash
nohup ./operations/run-batch.sh > operations/logs/batch.log 2>&1 &
tail -f operations/logs/batch.log
# Ctrl+C to stop tailing, safe to close SSH
```

All methods achieve the same result: the tmux sessions persist after you disconnect.

## If Something Crashes

Crashes are logged with exact index ranges in:
```
operations/logs/CRASH__*.log
```

Resume failed chunks:
```bash
./operations/resume.sh --batch-id <batch-id>
```

## Kill Everything

```bash
# Kill all sessions for control-functional variant
./operations/kill-all.sh --variant control-functional

# Kill ALL fvspec sessions
./operations/kill-all.sh
```

## Defaults

- **Total**: 53,408 samples (full eligible dataset)
- **Variant**: `control-functional`
- **Chunk size**: 100 samples per session (535 sessions)
- **Parallelism**: 10 samples in parallel per chunk

All can be overridden with flags.

## Full Documentation

See `README.md` and `CHEATSHEET.md` for complete details.
