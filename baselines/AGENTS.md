# Baselines

Baseline implementations for measuring benchmark performance.

1. Load samples from local JSONL (`data/fvspec-mar27.jsonl`) or `quinn-dougherty/fvspec` from HuggingFace. Configured via `data_source` in `config.toml` or `--data-source` CLI flag.
2. Write a solver with `inspect-ai` that uses `lean-lsp-mcp` tools and the `lake-template` boilerplate dir in tmpdirs.
3. Write outcome stats to `.toml` and `.json` in timestamped subdirectories under `artifacts/results/<eval-timestamp>/` for automatic loading into `typst` in `./../comms/paper/*.typ`
4. The task is to actually write the proof-- to fill in the sorry in `Spec.lean`
5. Binary difficulty buckets: pick 50% easy, 50% hard. Uses `difficulty_binary` (v2 grader, few-shot calibrated Haiku) when available, falls back to `difficulty_subjective_haiku` with threshold at 4.0. Ranseed fixes the shuffle within buckets.
6. We have `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` in monorepo root `.env`. Use inspect-ai primitives for parallelism.

## Scoring

- **Binary**: proved = 1.0 if zero `sorry` remaining AND `lake build` succeeds with no sorry warnings
- **Partial credit**: `max(0, sorries_removed / sorries_original)` — sorry count can increase when proof is closer to solved

## Structure

- `src/baselines/solver.py` — inspect_ai Task, solvers, scorer
- `src/baselines/dataset.py` — JSONL/HF loading, stratified sampling
- `src/baselines/tools.py` — Lean LSP MCP tool wrappers (write_lean_spec, lean_diagnostic_messages, lean_goal, lean_multi_attempt, lean_local_search)
- `src/baselines/models.py` — Pydantic data models
- `src/baselines/config.py` + `config.toml` — Configuration (models: snt46, ops46, gpt54mini, gemini25pro)
- `src/baselines/stats.py` — Results aggregation from .eval files into timestamped `artifacts/results/<ts>/` dirs
- `src/baselines/prompts/` — System and user prompt templates
- `src/baselines/workspace.py` — Per-sample workspace lifecycle
- `src/viz/build.py` — `doteval-dashboard` static site generator for cross-model comparison and trajectory viewing
- `src/viz/templates/` — Jinja2 templates (base, index overview, trajectories viewer)

Pattern pointers from `./../benchmark/AGENTS.md`:
- `pydantic.BaseModel` in dedicated `models.py` files
- prompt loading from `.prompt` and `.prompt.template` plaintext files
- Tools set on `state.tools` in the solver, not on the Task

## Usage

```bash
uv sync
uv run fvspec sample-info                    # Show bucket distribution
uv run fvspec run -m snt46                   # Run with Claude Sonnet 4.6
uv run fvspec run -m gpt54mini --parallelism 5   # Run with GPT 5.4 Mini
uv run fvspec stats                          # Aggregate results → artifacts/results/<timestamp>/
uv run doteval-dashboard artifacts/*.eval    # Build cross-model comparison dashboard
```

## Development

```bash
uv sync
uv run pytest src/tests/ -v
```

See root `AGENTS.md` for codestyle guidelines.
