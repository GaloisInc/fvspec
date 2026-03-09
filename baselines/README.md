# Baselines

Evaluate frontier LLMs on proving theorems from the fvspec benchmark.

## Setup

```bash
uv sync
```

## Usage

### Run evaluation

```bash
# Single model
uv run fvspec run --model anthropic/claude-sonnet-4-20250514

# With options
uv run fvspec run --model openai/gpt-4o --ranseed 42 --parallelism 10
```

Or directly via `inspect eval` (gives access to all inspect flags like `--limit`):

```bash
uv run inspect eval src/baselines/solver.py --model anthropic/claude-sonnet-4-20250514 -T ranseed=42
uv run inspect eval src/baselines/solver.py --model google/gemini-2.5-pro -T ranseed=42 --limit 5
```

### Aggregate results

```bash
uv run fvspec stats
# Writes artifacts/results.toml
```

### Inspect sample distribution

```bash
uv run fvspec sample-info
# easy: 300 samples
# medium: 400 samples
# hard: 300 samples
```
