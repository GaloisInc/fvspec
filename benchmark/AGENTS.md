# Benchmark Generation

Benchmark generation system using the `inspect_ai` framework.

## Key Components

**`src/generate/scaffold/`** - Core evaluation
- `orchestration.py` - Two-agent orchestration (impl → spec)
- `dataset/` - Sample loading, unit test extraction, function discovery
- `formalize/impl/` - Implementation agent
- `formalize/spec/` - Specification agent
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

**Two-Agent Flow:**
1. Sample from SQLite with filtering
2. **Unit test extraction** - AST-based extraction to LSpec (Tests.lean), stored in metadata
3. **Function discovery** - Tree-sitter lookup (92% coverage)
4. **Implementation Agent** - Generate FUT + dependencies → Impl.lean (zero sorry)
5. **Signature extraction** - Parse types from Impl.lean
6. **Specification Agent** - Generate theorems → Spec.lean (with sorry)
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

## Code Style

**Python:** Absolute imports, Pydantic (not dataclasses), `from datetime import datetime`
**Commits:** Conventional, pass hooks, co-author

See `ideas/UNITS.agents.md` and `ideas/WANDB.agents.md` for additional details.
