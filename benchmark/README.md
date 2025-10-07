# Benchmark

## Running the benchmark

```bash
uv run fvspec
```

## Dashboard

View benchmark results interactively:

```bash
uv run panel serve src/scripts/dashboard.py
```

With custom arguments:

```bash
uv run panel serve src/scripts/dashboard.py --args -d "artifacts/2025-10-01T13-26-28" -x "interest" -y "faithfulness"
```

## Testing

Run smoke tests to verify the pipeline won't crash:

```bash
uv run pytest
```

## Other utilities

Preview prompt templates:

```bash
uv run preview_prompts
```

Analyze dependencies in scraped tests:

```bash
uv run analyze_deps
```
