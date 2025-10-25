# AGENTS.md

> **Note**: This file is symlinked from `CLAUDE.md` and `KNOWLEDGE.md` to ensure consistent guidance across different AI code assistants.

## Project Overview

fvspec is a benchmark suite for evaluating AI models on formal verification tasks, extending **FVAPPS / Proving the Coding Interview** (Dougherty & Mehta, [arxiv:2502.05714](https://arxiv.org/abs/2502.05714)) by using real-world Hypothesis property-based tests from GitHub instead of synthetic puzzles. The project translates Python tests into Lean 4 specifications with `sorry` placeholders, focusing on specification quality over full implementation.

### Key Design Choices

**Two verification approaches:**
- **Functional variants** (`control-functional`, `terse-functional`): FVAPPS-style recursive definitions with pure functional programming and traditional theorem proving
- **mvcgen variants** (`control-mvcgen`): Imperative programs with Hoare logic specifications (`⦃Pre⦄ code ⦃Post⦄`) and loop invariants, best for stateful algorithms and PyTorch/NumPy operations

**Learning from benchmarks:** Addresses Verina and CLEVER criticisms by using real-world (not LLM-generated) tests, evaluating specification quality with structural faithfulness metrics, and providing interactive LSP feedback via MCP tools.

**Computation is non-negotiable:** All definitions must eventually be computable for downstream proof automation. Use `def` with `sorry` over `axiom` to maintain computability.

**Funding**: Advanced Research + Invention Agency (ARIA)

## Additional Documentation

See `benchmark/ideas/*.md` for research notes: `METRICS.claude.md` (quality metrics), `depmock/human.md` (dependency formalization), `HOARE.claude.md` (mvcgen/Hoare logic). Files marked `.claude.md` are exploratory; `.human.md` are for team review.

## Development Environment

Use Nix flakes with direnv: run `direnv allow` to activate. Provides: `elan`, `uv`, `typst`, `nodejs_24`, `lefthook`, `pandoc`, `claude-code`.

## Repository Structure

- **`/benchmark`** - Main Python package using `inspect_ai` framework
  - `src/generate/scaffold/`: Core task, agent, dataset, quality assessment, and MCP tools
  - `src/generate/templates/`: Jinja2 prompt templates with variant system (`common/`, `variants/`, `registry.toml`)
  - `src/generate/config.toml`: Runtime configuration (model, sample_size, variants, wandb)
  - `data/pbts.jsonl`: 116GB scraped tests (**never load fully**; run `uv run fvspec index-data` once to create `.index` for fast sampling)

- **`/artifacts`** - Outputs (gitignored): `<timestamp>__<variant>/` directories with `.eval` logs, `Spec.lean`, `qa.json`, dependency files

- **`/baselines`** - Baseline implementations (minimal currently)

## Common Commands

**Note:** Agents should NOT run the benchmark (`uv run fvspec`) - the user will do that in a separate terminal.

### Dataset setup (one-time)
```bash
uv run fvspec index-data  # Creates pbts.jsonl.index (~1-2MB) for fast sampling
```

### Running benchmarks
```bash
uv run fvspec --list-variants  # Show available variants
uv run fvspec --variant control-mvcgen --sample-size 50 --parallelism 10
uv run fvspec compare-variants --variant control-functional --variant terse-functional
```

### Dependency autoformalization
```bash
uv run fvspec deps autoformalize --sample-id 5 --sample-id 47
uv run fvspec deps autoformalize --sample-size 10 --ranseed 42 --dry-run
uv run fvspec deps cache-clear-local  # Clear local cache
```

Produces Lean files per dependency (`deps/`), consolidated as `Fvspec/Deps.lean`. Uses cached modules or emits computable stubs. Options: `--dry-run`, `--skip-cached`, `--validate`. Writes `dependency_report.json` with timing/diagnostics.

### Viewing results
```bash
uv run inspect view --log-dir artifacts
uv run inspect view --log-dir artifacts/2025-10-14T15-30-00__control-functional
```

### Development tools (run from `./benchmark`)
```bash
uv run ruff format && uv run ruff check && uv run ty check && uv run pytest
uv run preview-prompts test_prompts.json --prompt-type spec --sample-size 10
uv sync  # Install dependencies
uv add <package>  # Add dependency
```

**Commit discipline:** Conventional subject, exhaustive body, all pre-commit hooks pass, co-authored commits.

## Architecture

**Benchmark flow:** Dataset sampling → Variant prompt rendering → Agent with MCP tools (`lean_diagnostic_messages`, `lean_goal`, `lean_multi_attempt`, `lean_local_search`) → Lean code in `<code>...</code>` tags → Quality assessment → Metrics registration.

**Quality metrics:** Performance (tokens, time), code metrics (LOC, `sorry` count), subjective (faithfulness 0-10, interest 0-10), structural faithfulness (parameter/type/assertion coverage).

**MCP integration:** Uses `lean-lsp-mcp` (via `uvx`) for real-time LSP feedback. Always enabled. Tools provide diagnostics, proof state, parallel tactic attempts, and API search.

**Task registration:** Registered via `_registry.py` entry points for `eval_set()` retry support.

## Configuration

Edit `benchmark/src/generate/config.toml`: model name, max_tokens, sample_size (100), variant, wandb settings. **CRITICAL:** Keep `entity = "fvspec"` unchanged for team collaboration. All settings override-able via CLI.

## Code Style

**Python:**
- Use `from datetime import datetime` (not `import datetime`)
- Absolute imports: `from generate.scaffold.depmock.runner import ...`
- Pydantic for all data models: `BaseModel`, `.model_dump_json()`, `Field()`, `frozen=True`

**Lean:** Type-check with `lean <file>.lean`. Use `def` with `sorry` (not `axiom`) to maintain computability for downstream proof automation.
