# Benchmark Generation

This directory contains the fvspec benchmark generation system using the `inspect_ai` framework.

## Key Components

- **`src/generate/scaffold/`** - Core evaluation infrastructure
  - `orchestration.py` - Two-agent orchestration (impl → spec)
  - `dataset/` - Sample loading, unit test extraction, function discovery
  - `formalize/impl/` - Implementation agent (function + dependencies)
  - `formalize/spec/` - Specification agent (theorem statements)
  - `quality_assessment.py` - Metrics extraction (tokens, timing, faithfulness, structural metrics)
  - `tools/declaration.py` - Lean LSP tools via MCP, cleanup, score registration

- **`src/generate/templates/`** - Jinja2 prompt templates
  - `spec/` - Spec generation prompts (functional, mvcgen, terse variants)
  - `impl/` - Implementation translation prompts
  - Shared fragments in `*/common/fragments/` (single source of truth for repeated guidance; use `{% include %}` to reduce redundancy)
  - **Naming convention**: Files with Jinja2 markup use `.prompt.template`, files without use `.prompt`
  - **⚠️ Testing note**: Be aggressive about testing beliefs on how template rendering works. Template bugs are harder to detect by default - variables may silently fail to render, includes may not resolve, or Jinja2 logic may produce unexpected output. When modifying templates, verify the actual rendered output matches expectations.

- **`data/pbts_full.db`** - Python property-based tests (SQLite database)
  - **Database**: SQLite with SQLModel ORM for type-safe queries
  - **Statistics**: 54,345 PBTs, 6.3M unit tests, 448K PBT-function associations
  - **Performance**: Add indexes for unit test extraction with `uv run add-unit-test-indexes` (run once per database)

## Common Commands

**Note:** Don't run benchmarks from agents - user runs them in separate terminal.

```bash
# Run benchmarks
uv run fvspec --variant control-mvcgen --sample-size 50 --parallelism 10
uv run fvspec compare-variants --variant control-functional --variant terse-functional

# Dependency autoformalization
uv run fvspec deps autoformalize --sample-id 5 --sample-id 47
uv run fvspec deps cache-clear-local

# Unit test extraction
uv run add-unit-test-indexes                          # Add DB indexes (run once)
uv run measure-unit-extraction --num-samples 100      # Measure extraction rate

# View results
uv run inspect view --log-dir artifacts

# Development
uv run ruff format && uv run ruff check && uv run pytest
```

## Architecture

**Two-Agent Flow:**
1. Sample N datapoints from SQLite database (SQL queries with filtering)
2. **Unit test extraction** (per sample during dataset creation):
   - AST-based static analysis extracts concrete test cases from PBT code
   - Supports pytest.mark.parametrize, loop unrolling, variable substitution
   - Generates LSpec test suites in Lean (Tests.lean)
   - Stored in metadata (NOT shown to model) for evaluation purposes
   - Float tests use external validation with numpy.isclose semantics
3. **Function discovery**: Tree-sitter based lookup (92% coverage)
4. **Implementation Agent**: Generate function implementation → Impl.lean (zero sorry)
5. **Signature extraction**: Parse type signatures from Impl.lean
6. **Specification Agent**: Generate theorem statements → Spec.lean (with sorry)
7. Extract code, run quality assessment, save artifacts

**Artifacts structure:**
```
artifacts/<timestamp>__<variant>/<sample_id>__<pbt_name>/
  ├── Spec.lean         # theorem statements (with sorry)
  ├── Impl.lean         # function implementations (zero sorry)
  ├── Tests.lean        # extracted unit tests
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
- Absolute imports: `from generate.scaffold.formalize.impl.runner import ...`
- Pydantic models: `BaseModel`, `.model_dump_json()`, `Field()`, `frozen=True`. DO NOT USE `dataclasses`!
- SQLModel: Use `get_session()` context managers, `.get_deps()` for JSON parsing

**Commits:** Conventional subject, exhaustive body, pass pre-commit hooks, co-author with Claude.

## References

- Unit test design: `ideas/UNITS.agents.md`
- Wandb details: `ideas/WANDB.agents.md`
- Template analysis: See git history for TEMPLATE_REDUNDANCY_ANALYSIS
