# Baselines

Evaluate frontier LLMs on proving theorems from the fvspec benchmark.

## Setup

```bash
uv sync
```

## Usage

### Run evaluation

```bash
# Using human_name from config.toml
uv run fvspec run -m snt46                          # Claude Sonnet 4.6
uv run fvspec run -m gpt54mini --parallelism 5      # GPT 5.4 Mini
uv run fvspec run -m gemini25pro                     # Gemini 2.5 Pro

# Override sample count
uv run fvspec run -m snt46 -n 3                     # Smoketest with 3 samples
```

Or directly via `inspect eval` (gives access to all inspect flags like `--limit`):

```bash
uv run inspect eval src/baselines/solver.py --model anthropic/claude-sonnet-4-6 -T ranseed=0
uv run inspect eval src/baselines/solver.py --model google/gemini-2.5-pro -T ranseed=0 --limit 5
```

### Aggregate results

```bash
uv run fvspec stats
# Writes artifacts/results/<eval-timestamp>/results.{toml,json}
```

### Inspect sample distribution

```bash
uv run fvspec sample-info
# easy: 25 samples
# medium: 25 samples
# hard: 25 samples
```

### Dashboard

Build a static HTML dashboard comparing models across `.eval` files:

```bash
uv run doteval-dashboard artifacts/*.eval                    # All evals
uv run doteval-dashboard artifacts/2026-03-27*.eval          # Specific run
uv run doteval-dashboard artifacts/*.eval -o my-dashboard/   # Custom output dir
```

Output includes an overview page (charts, per-bucket breakdowns, sample table) and a trajectory viewer (message-by-message conversation traces per sample per model).
