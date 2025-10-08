# Benchmark

## Running the benchmark

```bash
# Default: functional style (FVAPPS-style recursive definitions)
uv run fvspec

# Use mvcgen style (imperative with Hoare logic and loop invariants)
uv run fvspec --style mvcgen

# Disable MCP tools for faster execution
uv run fvspec --no-mcp
```

### Verification Styles

- **functional** (default): Pure functional style with recursion and induction
- **mvcgen**: Imperative style with `do` notation, Hoare triples, and `mvcgen` tactic

Set default in `config.toml`:
```toml
[prompt]
style = "mvcgen"  # or "functional"
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
# Preview prompts with functional or mvcgen style
uv run preview_prompts <data_file.json> --style functional
uv run preview_prompts <data_file.json> --style mvcgen
```

Analyze dependencies in scraped tests:

```bash
uv run analyze_deps
```
