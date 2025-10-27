# Benchmark Generation

This directory contains the fvspec benchmark generation system using the `inspect_ai` framework.

## Repository Structure

- **`src/generate/scaffold/`** - Core evaluation infrastructure
  - `task.py` - Defines the `fvspec` task that runs the benchmark
  - `agent.py` - Agent configuration using `inspect_ai` basic_agent with Lean MCP tools
  - `dataset.py` - Loads and samples datapoints from JSON, creates `inspect_ai` datasets
  - `quality_assessment.py` - Extracts metrics from TaskState (token usage, timing, faithfulness, structural metrics)
  - `tools/declaration.py` - Lean LSP tools via MCP (diagnostics, goals, multi-attempt, local search), cleanup, score registration
  - `tools/utilio.py` - Utility functions for subprocess execution and file operations

- **`src/generate/templates/`** - Jinja2 prompt templates with variant system
  - `common/` - Shared prompt fragments and default templates
  - `variants/` - Directory containing prompt variants for A/B testing
  - `registry.toml` - Master index of available variants with metadata
  - `prompt.py` - Prompt loading logic with variant selection and Jinja2 templating
  - `registry.py` - Variant registry for loading and validating variants

- **`src/generate/config.toml`** - Runtime configuration
  - Agent settings: model name, max_tokens
  - Dataset settings: sample_size (default: 100)
  - Prompt settings: default variant selection
  - Wandb settings: entity, project, tags

- **`data/pbts.jsonl`** - Large JSONL file (~116GB) containing scraped Python property-based tests
  - **CRITICAL**: Never load entirely into memory. All scripts use streaming/reservoir sampling.
  - **Performance tip**: Run `uv run fvspec index-data` once to create `pbts.jsonl.index` (~1-2MB) for sub-second sampling

- **`src/scripts/`** - Utility scripts
  - `analyze_deps.py` - Analyzes import dependencies in scraped tests

## Common Commands

**Note:** Agents should NOT run the benchmark (`uv run fvspec`) - the user will do that in a separate terminal.

### Dataset setup (one-time)
```bash
# From repository root
uv run fvspec index-data  # Creates pbts.jsonl.index (~1-2MB) for fast sampling
```

### Running benchmarks
```bash
# From repository root
uv run fvspec --list-variants  # Show available variants
uv run fvspec --variant control-mvcgen --sample-size 50 --parallelism 10
uv run fvspec compare-variants --variant control-functional --variant terse-functional
```

### Dependency autoformalization
```bash
# From repository root
uv run fvspec deps autoformalize --sample-id 5 --sample-id 47
uv run fvspec deps autoformalize --sample-size 10 --ranseed 42 --dry-run
uv run fvspec deps cache-clear-local  # Clear local cache
```

Produces Lean files per dependency (`deps/`), consolidated as `Fvspec/Deps.lean`. Uses cached modules or emits computable stubs. Options: `--dry-run`, `--skip-cached`, `--validate`. Writes `dependency_report.json` with timing/diagnostics.

### Viewing results
```bash
# From repository root
uv run inspect view --log-dir artifacts
uv run inspect view --log-dir artifacts/2025-10-14T15-30-00__control-functional
```

The inspect viewer displays all quality metrics as scores with explanations.

### Development tools
```bash
# From ./benchmark directory
uv run ruff format && uv run ruff check && uv run ty check && uv run pytest
uv run preview-prompts test_prompts.json --prompt-type spec --sample-size 10
uv sync  # Install dependencies
uv add <package>  # Add dependency
```

## Architecture

**Benchmark flow:**
1. `mk_dataset()` samples N datapoints from JSONL (indexed if `.index` exists, else reservoir sampling)
2. Variant's prompt templates render system and initial prompts with test and dependencies
3. Agent uses Lean LSP MCP tools (`lean_diagnostic_messages`, `lean_goal`, `lean_multi_attempt`, `lean_local_search`) to interactively develop Lean code
4. Model responds with Lean 4 code in `<code>...</code>` tags, including faithfulness/interest metrics
5. Cleanup (`write_to_disk`) extracts code, runs quality assessment, registers scores, saves outputs
6. All metrics registered as `inspect_ai` `Score` objects with explanations

**Quality metrics:**
- Performance: token usage, time, message counts
- Code metrics: lines added, number of `sorry` placeholders, success status
- Subjective: AI self-reported faithfulness (0-10) and interest (0-10) scores
- Structural faithfulness: parameter coverage, type correspondence, strategy coverage, assertion coverage, dependency coverage

**MCP integration:** Uses `lean-lsp-mcp` (via `uvx`) for real-time LSP feedback. Always enabled. Tools provide:
- `lean_diagnostic_messages`: Structured error messages with severity/positions
- `lean_goal`: Proof state inspection ("Before"/"After" goal states)
- `lean_multi_attempt`: Parallel proof tactic attempts
- `lean_local_search`: Search definitions/theorems to prevent hallucinating APIs

**Task registration:** Registered via `_registry.py` and `pyproject.toml` entry points for `eval_set()` retry support.

**Prompt variants:** Two verification approaches:
- **Functional** (`control-functional`, `terse-functional`): FVAPPS-style recursive definitions, pure functional programming
- **mvcgen** (`control-mvcgen`): Imperative programs with Hoare logic (`⦃Pre⦄ code ⦃Post⦄`), loop invariants, best for stateful/PyTorch/NumPy

## Configuration

Edit `benchmark/src/generate/config.toml`: model name, max_tokens, sample_size (100), variant, wandb settings.

**CRITICAL:** Keep `entity = "fvspec"` unchanged for team collaboration. All settings override-able via CLI.

See `benchmark/ideas/WANDB.agents.md` for wandb artifact and cache details.

## Code Style

**Python:**
- Use `from datetime import datetime` (not `import datetime`)
- Absolute imports: `from generate.scaffold.depmock.runner import ...`
- Pydantic for all data models: `BaseModel`, `.model_dump_json()`, `Field()`, `frozen=True`

**Lean:** Type-check with `lean <file>.lean`. Use `def` with `sorry` (not `axiom`) to maintain computability for downstream proof automation.

**Commit discipline:** Conventional subject, exhaustive body, all pre-commit hooks pass, co-authored commits.
