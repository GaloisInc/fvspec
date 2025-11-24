# Post-Production Analysis: W&B Run Accumulator

Tools for downloading and analyzing W&B runs after benchmark execution.

## Overview

This tool helps you:
1. **Specify runs** to analyze in `manifest.toml`
2. **Download** all run data (metrics, files, config) to local disk
3. **Explore** the data interactively via Streamlit dashboard

## Quick Start

### 1. Configure Manifest

Edit `src/scripts/postproduction/accumulate/manifest.toml` to list the W&B runs you want to analyze:

```toml
[project]
entity = "fvspec"
project = "fvspec"
output_dir = "artifacts/postproduction"

run_names = [
  "2025-11-20T07-48-32__control-functional__idx0-2",
  "2025-11-20T07-45-23__control-functional__s0__n2"
]
```

**Finding run IDs:**
- W&B dashboard URL: `https://wandb.ai/fvspec/fvspec/runs/<run-id>`
- CLI: `wandb run list`
- Python: See "Finding Runs" section below

### 2. Download Runs

```bash
# From the benchmark directory
cd benchmark

# Download all runs listed in manifest.toml
uv run python -m scripts.postproduction.accumulate sync

# Re-download even if already exists
uv run python -m scripts.postproduction.accumulate sync --force
```

This downloads:
- **metadata.json** - Run config, summary, tags, state
- **history.csv** - Per-sample metrics over time
- **files/** - Sample artifacts (.lean, .json files)

### 3. Explore with Streamlit

```bash
# From benchmark directory
cd benchmark

# Launch dashboard
uv run streamlit run src/scripts/postproduction/accumulate/dashboard.py
```

The dashboard provides:
- **Metrics tab**: Plot any metric from history (token usage, success rate, etc.)
- **Config tab**: View run configuration and parameters
- **Files tab**: Browse and view downloaded sample files
- **Summary tab**: Aggregate statistics across the run

## CLI Commands

### `sync` - Download runs

```bash
uv run python -m scripts.postproduction.accumulate sync [OPTIONS]

Options:
  -m, --manifest PATH  Path to manifest.toml [default: src/scripts/postproduction/accumulate/manifest.toml]
  -f, --force         Re-download even if already exists
```

### `list-runs` - Show runs in manifest

```bash
uv run python -m scripts.postproduction.accumulate list-runs

# Output:
# Runs in manifest.toml:
# 1. wqd4mi3y
#    Name: 2025-11-20T07-48-32__control-functional__idx0-2
#    Notes: Sequential sampling test
# ...
```

### `status` - Check download status

```bash
uv run python -m scripts.postproduction.accumulate status

# Output:
# Download status:
# ✓ wqd4mi3y - 15 files
# ✓ 8ld0ihci - 10 files
# ✗ abc123 - not downloaded
```

## Directory Structure

After running `sync`, you'll have:

```
benchmark/
├── src/scripts/postproduction/accumulate/
│   ├── manifest.toml       # Run specifications
│   ├── dashboard.py        # Streamlit dashboard
│   ├── __init__.py         # CLI implementation
│   └── README.md           # This file
└── artifacts/postproduction/  # Downloaded data (gitignored via artifacts/)
    ├── wqd4mi3y/          # Run ID
    │   ├── metadata.json  # Run metadata
    │   ├── history.csv    # Metrics history
    │   └── files/         # Sample artifacts
    │       ├── 2025-11-20T07-48-32__idx0-2__control-functional/
    │       │   ├── 00001_test_property/
    │       │   │   ├── Spec.lean
    │       │   │   ├── Impl.lean
    │       │   │   ├── Tests.lean
    │       │   │   ├── qa.json
    │       │   │   └── datapoint.json
    │       │   └── 00002_test_foo/
    │       │       └── ...
    └── 8ld0ihci/
        └── ...
```

## Finding Runs

### List all runs in W&B

```python
# From benchmark/ directory
# Create find_runs.py

import wandb

api = wandb.Api()
runs = api.runs("fvspec/fvspec")

for run in runs:
    print(f"ID: {run.id}")
    print(f"Name: {run.name}")
    print(f"State: {run.state}")
    print(f"Created: {run.created_at}")
    print()
```

Run with: `uv run python find_runs.py`

### Filter by date or variant

```python
import wandb

api = wandb.Api()

# Filter by tags
runs = api.runs("fvspec/fvspec", filters={"tags": "control-functional"})

# Filter by date
runs = api.runs("fvspec/fvspec", filters={
    "created_at": {"$gte": "2025-11-20"}
})

# Filter by state
runs = api.runs("fvspec/fvspec", filters={"state": "finished"})

for run in runs:
    print(f"{run.id}: {run.name}")
```

## Use Cases

### Compare variants

1. Add runs from different variants to `manifest.toml`
2. Download: `uv run python -m scripts.postproduction.accumulate sync`
3. Analyze in dashboard or Jupyter notebook

### Analyze large-scale runs

1. Add all sequential sampling runs (idx0-10k, idx10k-20k, etc.)
2. Download all data locally
3. Aggregate metrics across runs
4. Generate paper figures

### Debug failed runs

1. Add crashed/failed runs to manifest
2. Download and inspect files/metrics
3. Identify patterns in failures

## Advanced: Programmatic Access

```python
from pathlib import Path
import json
import pandas as pd

# Load run metadata
run_dir = Path("artifacts/postproduction/wqd4mi3y")
with open(run_dir / "metadata.json") as f:
    metadata = json.load(f)

# Load metrics
history = pd.read_csv(run_dir / "history.csv")

# Analyze
print(f"Success rate: {metadata['summary']['summary/success_rate']}")
print(f"Mean token usage: {history['token_usage'].mean()}")

# Load sample files
files_dir = run_dir / "files"
sample_dirs = [d for d in files_dir.iterdir() if d.is_dir()]
for sample_dir in sample_dirs:
    qa_path = list(sample_dir.rglob("qa.json"))[0]
    with open(qa_path) as f:
        qa = json.load(f)
    print(f"{sample_dir.name}: {qa}")
```

## Dependencies

Required packages (should already be in benchmark environment):
- `wandb` - W&B API client
- `typer` - CLI framework
- `rich` - Console formatting
- `pydantic` - Data validation
- `streamlit` - Dashboard framework
- `pandas` - Data analysis

## Notes

- `data/` directory is gitignored by default
- Run data can be large (MBs per run with all files)
- Use `--force` sparingly to avoid redundant downloads
- W&B API rate limits apply (shouldn't be an issue for reasonable usage)
