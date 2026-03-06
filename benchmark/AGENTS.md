# Benchmark Generation

Benchmark generation system using the `inspect_ai` framework.

## Key Components

**`src/generate/scaffold/`** - Core evaluation
- `orchestration.py` - Three-agent orchestration (impl → spec + units in parallel)
- `dataset/` - Sample loading, unit test extraction, function discovery
- `formalize/impl/` - Implementation agent
- `formalize/spec/` - Specification agent
- `formalize/units/` - Units agent
- `quality_assessment.py` - Metrics extraction
- `tools/declaration.py` - Lean LSP via MCP

**`src/generate/templates/`** - Jinja2 prompts
- `spec/` and `impl/` directories with prompt variants
- Shared fragments in `*/common/fragments/` (use `{% include %}`)
- **Naming**: `.prompt.template` (Jinja2 markup) vs `.prompt` (plain)
- **⚠️ Testing**: Template bugs are subtle - verify rendered output when modifying

**`data/pbts_full.db`** - SQLite database
- 54,345 PBTs, 6.3M unit tests, 448K PBT-function associations
- SQLModel ORM for type-safe queries

## Common Commands

**Note:** Don't run benchmarks from agents - user runs them in separate terminal.

```bash
# Run benchmarks
uv run fvspec --variant control-mvcgen --sample-size 50 --parallelism 10
uv run fvspec compare-variants --variant control-functional --variant terse-functional

# View results
uv run inspect view --log-dir artifacts

# Development
uv run ruff format && uv run ruff check && uv run pytest
```

## Architecture

**Three-Agent Flow:**
1. Sample from SQLite with filtering
2. **Unit test generation** - LLM-based units agent generates LSpec (Tests.lean), stored in metadata
3. **Function discovery** - Tree-sitter lookup (92% coverage)
4. **Implementation Agent** - Generate FUT + dependencies → Impl.lean (zero sorry)
5. **Signature extraction** - Parse types from Impl.lean
6a. **Specification Agent** - Generate theorems → Spec.lean (with sorry)
6b. **Units Agent** - Generate unit tests → Tests.lean
    *(Steps 6a and 6b run in parallel according to orchestration.py)*
7. Quality assessment, save artifacts

**Artifacts:** `artifacts/<timestamp>__<variant>/<sample_id>__<pbt_name>/`
- `Spec.lean` - theorem statements (with sorry)
- `Impl.lean` - implementations (zero sorry)
- `Tests.lean` - unit tests
- `qa.json` - metrics

**Variants:**
- **Functional** (`control-functional`, `terse-functional`) - Pure FP recursion
- **mvcgen** (`control-mvcgen`) - Imperative Hoare logic

**Metrics:** tokens, time, lines, sorry count, structural coverage, unit test availability

## Configuration

Edit `config.toml` for model/variant/wandb. **CRITICAL:** Keep `entity = "fvspec"`.

## Database Schema

**SQLModel ORM** (`dataset/models.py`, `connection.py`, `queries.py`):
- Datapoint table: `id`, `repo_id`, `name`, `code`, `summary`
- JSON fields: `.get_deps()` / `.get_dep_names()`
- Use `get_session(db_path)` context manager

## Postproduction Pipeline

After running benchmarks, postproduction scripts process results:

**`src/scripts/postproduction/`** - Post-processing tools
- **`merge/`** - Merge multiple runs into unified JSONL dataset with automatic deduplication
  - `uv run merge src/scripts/postproduction/merge/runs.txt`
  - Combines runs, deduplicates by sample_id (quality-based), applies schema pruning
  - See `src/scripts/postproduction/merge/README.md` for details

- **`grader/`** - LLM-based difficulty assessment using Claude Haiku 4.5
  - `uv run grader artifacts/dataset-out/fvspec.jsonl`
  - Rates proof difficulty (0-10) with justification
  - Uses structured outputs with prompt caching for cost efficiency
  - See `src/scripts/postproduction/grader/README.md` for details

- **`metrics/`** - Lean code structure and complexity analysis
  - `uv run metrics artifacts/dataset-out/fvspec.jsonl`
  - Extracts line counts, declaration counts, nesting depth, proof complexity
  - Fast regex-based parsing (~100-1000 samples/second)
  - See `src/scripts/postproduction/metrics/README.md` for details

- **`turncount/`** - Extract true turn counts from .eval zip files into qa.json
  - `uv run turncount artifacts/runs/`
  - Counts assistant messages (turns) and tool messages per subagent conversation
  - Resume-safe: skips qa.json files already enriched (use `--force` to re-compute)

- **`accumulate_wandb/`** - Download and analyze W&B runs
  - `uv run python -m scripts.postproduction.accumulate sync`
  - Downloads run data (metrics, files, config) for offline analysis
  - Streamlit dashboard for interactive exploration
  - See `src/scripts/postproduction/accumulate_wandb/README.md` for details

**Typical workflow:**
```bash
# 1. Merge runs
uv run merge src/scripts/postproduction/merge/runs.txt

# 2. Compute Lean metrics (optional)
uv run metrics artifacts/dataset-out/fvspec.jsonl

# 3. Grade difficulty (optional)
uv run grader artifacts/dataset-out/fvspec.metrics.jsonl

# 4. Analyze results
```

## Code Style

**Python:** Absolute imports, Pydantic (not dataclasses), `from datetime import datetime`
**Commits:** Conventional, pass hooks, co-author

See `ideas/UNITS.agents.md` and `ideas/WANDB.agents.md` for additional details.
