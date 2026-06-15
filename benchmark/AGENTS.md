# Benchmark Generation

Benchmark generation system using the `inspect_ai` framework.

## Key Components

**`src/generate/scaffold/`** - Core evaluation
- `orchestration.py` - Unified agent orchestration (discovery → deps → formalize → plausible)
- `dataset/` - Sample loading, function discovery
- `formalize/agent.py` - Unified formalization agent (produces both Impl.lean and Spec.lean)
- `formalize/impl/` - Dependency formalization agent (function_impl_agent for deps only)
- `quality_assessment/` - Metrics extraction
- `tools/declaration.py` - Lean LSP via MCP

**`src/generate/templates/`** - Jinja2 prompts
- `formalize/` - Unified formalization prompt variants (A/B testing infra)
- `impl/` - Dependency formalization prompts
- Shared fragments in `*/common/fragments/` (use `{% include %}`)
- **Naming**: `.prompt.template` (Jinja2 markup) vs `.prompt` (plain)
- **⚠️ Testing**: Template bugs are subtle - verify rendered output when modifying

**`GaloisInc/fvspec-pbt`** (Hugging Face Hub) - Input dataset
- Each row is a PBT with embedded dependencies, summary, and metadata
- Loaded via `mk_dataset()` in `scaffold/dataset/` (`datasets.load_dataset`)
- Override with a local JSONL under `data/` via `--datafile <name>`

## Common Commands

**Note:** Don't run benchmarks from agents - user runs them in separate terminal.

```bash
# Run benchmarks
uv run fvspec --variant control-functional --sample-size 50 --parallelism 10

# View results
uv run inspect view --log-dir artifacts

# Development
uv run ruff format && uv run ruff check && uv run pytest
```

## Architecture

**Unified Agent Flow:**
1. Sample from `GaloisInc/fvspec-pbt` (HF Hub) with filtering
2. **Function discovery** - Tree-sitter lookup (92% coverage)
3. **Dependency formalization** - Each dep gets its own `function_impl_agent` call (KNOWN_TEST_INFRA deps are skipped)
4. **Unified formalization agent** - Sees full context (PBT + summary + discovered code + deps), produces both Impl.lean (zero sorry) and Spec.lean (theorems with sorry) via LSP tool loop
5. **Plausible testing** - Validate generated files
6. Quality assessment, save artifacts

**Artifacts:** `artifacts/<timestamp>__<variant>/<sample_id>__<pbt_name>/`
- `Spec.lean` - theorem statements (with sorry)
- `Impl.lean` - implementations (zero sorry)
- `qa.json` - metrics

**Variants:**
- `control-functional` - Pure FP recursion (only variant currently)
- A/B testing infra (FormalizationVariantRegistry) supports adding more variants

**Metrics:** tokens, time, lines, sorry count, structural coverage

## Configuration

Edit `config.toml` for model/variant/wandb. **CRITICAL:** Keep `entity = "fvspec"`.

## Dataset Schema

**Pydantic models** (`dataset/models.py`, `queries.py`):
- Datapoint: `id`, `name`, `code`, `summary`, `repo`, `metrics`, embedded `dependencies`
- Loaded from `GaloisInc/fvspec-pbt` (HF Hub) via `mk_dataset()`

## Postproduction Pipeline

After running benchmarks, postproduction scripts process results:

**`src/scripts/postproduction/`** - Unified CLI: `uv run postprod <subcommand>`
- **`turncount/`** - Extract true turn counts from .eval zip files into qa.json
- **`merge/`** - Merge multiple runs into unified JSONL dataset with deduplication
- **`metrics/`** - Lean code structure and complexity analysis (regex-based)
- **`grader/`** - LLM-based difficulty assessment using Claude Haiku 4.5

**Typical workflow:**
```bash
# 1. Enrich turn counts (operates on raw run artifacts)
uv run postprod turncount artifacts/runs/

# 2. Merge runs
uv run postprod merge src/scripts/postproduction/merge/runs.txt

# 3. Compute Lean metrics (optional)
uv run postprod metrics artifacts/dataset-out/fvspec.jsonl

# 4. Grade difficulty (optional)
uv run postprod grader artifacts/dataset-out/fvspec.metrics.jsonl
```

## Code Style

**Python:** Absolute imports, Pydantic (not dataclasses), `from datetime import datetime`
**Commits:** Conventional, pass hooks, co-author

See `ideas/WANDB.agents.md` for additional details.
