# Post-production Pipeline

Post-processing tools for benchmark results. All tools are accessed via the unified `postprod` CLI:

```bash
uv run postprod --help
```

## Pipeline Order

Run these steps in order after benchmark generation completes:

### 1. Enrich turn counts

Extract true LLM turn counts from `.eval` zip files into `qa.json` files. This operates on the raw run artifacts (before merge).

```bash
uv run postprod turncount artifacts/runs/
```

### 2. Merge runs

Combine multiple run directories into a single deduplicated JSONL dataset.

```bash
uv run postprod merge src/scripts/postproduction/merge/runs.txt
```

### 3. Compute Lean metrics (optional)

Extract code structure and complexity metrics from the Lean files in the merged JSONL.

```bash
uv run postprod metrics artifacts/dataset-out/fvspec.jsonl
```

### 4. Grade difficulty (optional)

Use Claude Haiku to estimate proof difficulty for each sample. Requires `ANTHROPIC_API_KEY`.

```bash
uv run postprod grader artifacts/dataset-out/fvspec.metrics.jsonl
```

## Notes

- Steps 3 and 4 are independent of each other and can run in either order.
- Resume behavior:
  - `turncount`, `metrics`, and `grader` are resume-safe: re-running them skips already-processed samples.
  - `merge` and `validate` always reprocess their entire inputs; they are idempotent but not incremental.
- Each tool has its own `--help` with detailed options (`uv run postprod <tool> --help`).
- See each tool's subdirectory for implementation details.
