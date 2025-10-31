# Benchmark Generation

This directory contains the fvspec benchmark generation system using the `inspect_ai` framework.

## Key Components

- **`src/generate/scaffold/`** - Core evaluation infrastructure
  - `task.py` - Benchmark task definition
  - `dataset.py` - Sample loading, unit test extraction
  - `quality_assessment.py` - Metrics extraction (tokens, timing, faithfulness, structural metrics)
  - `tools/declaration.py` - Lean LSP tools via MCP, cleanup, score registration
  - `depmock/` - Dependency autoformalization system

- **`src/generate/templates/`** - Jinja2 prompt templates
  - `spec/` - Spec generation prompts (functional, mvcgen, terse variants)
  - `deps/` - Dependency translation prompts
  - Shared fragments in `*/common/fragments/` (single source of truth for repeated guidance; use `{% include %}` to reduce redundancy)

- **`data/pbts_full.db`** - Python property-based tests (SQLite database)
  - **Database**: SQLite with SQLModel ORM for type-safe queries
  - **Statistics**: 54,345 PBTs, 6.3M unit tests, 448K PBT-function associations
  - Uses efficient DB queries and sampling (no need for indexing)

## Common Commands

**Note:** Don't run benchmarks from agents - user runs them in separate terminal.

```bash
# Run benchmarks
uv run fvspec --variant control-mvcgen --sample-size 50 --parallelism 10
uv run fvspec compare-variants --variant control-functional --variant terse-functional

# Dependency autoformalization
uv run fvspec deps autoformalize --sample-id 5 --sample-id 47
uv run fvspec deps cache-clear-local

# View results
uv run inspect view --log-dir artifacts

# Development
uv run ruff format && uv run ruff check && uv run pytest
```

## Architecture

**Flow:**
1. Sample N datapoints from SQLite database (SQL queries with filtering)
2. **Unit test extraction** (per sample during dataset creation):
   - AST-based static analysis extracts concrete test cases from PBT code
   - Supports pytest.mark.parametrize, loop unrolling, variable substitution
   - Generates LSpec test suites in Lean (Tests.lean)
   - Stored in metadata (NOT shown to model) for evaluation purposes
   - Float tests use external validation with numpy.isclose semantics
3. Render prompts with test + dependencies
4. Agent uses Lean LSP tools (`lean_diagnostic_messages`, `lean_goal`, `lean_multi_attempt`, `lean_local_search`)
5. Model returns Lean code in `<code>...</code>` tags with faithfulness/interest scores
6. Extract code, run quality assessment, save artifacts

**Artifacts structure:**
```
artifacts/<timestamp>__<variant>/<sample_id>__<pbt_name>/
  ├── Spec.lean         # model-generated
  ├── Tests.lean        # extracted unit tests
  ├── Deps.lean         # dependencies (if any)
  └── qa.json           # quality metrics
```

**Variants:**
- **Functional** (`control-functional`, `terse-functional`): Pure FP, FVAPPS-style recursion
- **mvcgen** (`control-mvcgen`): Imperative with Hoare logic (`⦃Pre⦄ code ⦃Post⦄`)

**Metrics:**
- Performance: tokens, time, message counts
- Code: lines, sorry count, success
- Structural: parameter/type/assertion/dependency coverage
- Unit tests: count, availability

## Configuration

Edit `benchmark/src/generate/config.toml` for model, sample_size, variant, wandb settings.

**CRITICAL:** Keep `entity = "fvspec"` for team collaboration.

## Database Schema

**SQLModel ORM** (`src/generate/scaffold/dataset/models.py`):
- **Datapoint table**: PBTs with metadata (id, repo_id, name, code, summary, etc.)
- **JSON fields**: `deps` and `dep_names` stored as TEXT, accessed via `.get_deps()` / `.get_dep_names()`
- **Field names**: `code` (PBT code), `name` (test name) - differs from legacy JSONL (`pbt`, `pbt_name`)
- **Queries**: Use `get_session(db_path)` context manager for connections

**Key modules**:
- `dataset/connection.py` - Database engine and session management
- `dataset/models.py` - SQLModel table definitions
- `dataset/queries.py` - Common queries (sampling, unit tests, counts)

## Code Style

**Python:**
- `from datetime import datetime` (not `import datetime`)
- Absolute imports: `from generate.scaffold.depmock.runner import ...`
- Pydantic models: `BaseModel`, `.model_dump_json()`, `Field()`, `frozen=True`
- SQLModel: Use `get_session()` context managers, `.get_deps()` for JSON parsing

**Commits:** Conventional subject, exhaustive body, pass pre-commit hooks, co-author with Claude.

## References

- Unit test design: `ideas/UNITS.agents.md`
- Wandb details: `ideas/WANDB.agents.md`
- Template analysis: See git history for TEMPLATE_REDUNDANCY_ANALYSIS
