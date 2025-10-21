# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

fvspec is a benchmark suite for evaluating how AI models perform on formal verification tasks. The project builds on **FVAPPS / Proving the Coding Interview** (Dougherty & Mehta, [arxiv:2502.05714](https://arxiv.org/abs/2502.05714)) by using real-world Hypothesis property-based tests scraped from GitHub, rather than synthetic programming puzzles.

### Background: FVAPPS

FVAPPS (Formally Verified Automated Programming Progress Standards) is a benchmark of 4,715 samples for writing programs and proving their correctness in Lean 4. It generalizes the APPS benchmark by transforming Python unit tests into Lean 4 theorems. The benchmark challenges models to both implement code and prove its correctness.

**Note on mvcgen/monadic program logic**: Dougherty & Mehta would have heavily used mvcgen (monadic verification condition generator) if it had been merged into Lean 4 master when they created FVAPPS. This tool enables interactive verification of imperative programs using Hoare triples, allowing developers to specify loop invariants and generate verification conditions. See [Markus Himmel's blog post](https://markushimmel.de/blog/my-first-verified-imperative-program/) for details on how mvcgen transforms imperative program verification into a compositional, interactive proof process in Lean 4.

### This Project's Extension

While FVAPPS uses curated programming puzzles, this project:

- Scrapes real-world property-based tests written with Hypothesis from GitHub repositories
- Translates these tests into Lean 4 theorem statements and function signatures
- Focuses on specification generation rather than full implementation (uses `sorry` placeholders)
- Evaluates translation quality with faithfulness and interest metrics

### Learning from Criticisms: Verina and CLEVER

This project incorporates lessons from critiques of FVAPPS:

**Verina** ([verina.io](https://verina.io/)) identified that LLMs struggle with verifiable code generation (only 3.6% successful proofs) and proposed:

- Automated specification evaluation for soundness and completeness
- Modular task design for different verification scenarios
- Comprehensive test suites for specifications

**CLEVER** ([arxiv:2505.13938](https://arxiv.org/abs/2505.13938)) criticized existing benchmarks for:

- Test-case supervision that leaks implementation details
- LLM-generated annotations
- Specifications that allow vacuous solutions

This project addresses these concerns by:

- Using real-world Hypothesis tests as ground truth (not LLM-generated)
- Evaluating specification quality with faithfulness metrics
- Leveraging property-based tests which express invariants without leaking implementations
- Using Lean's type checker for post-hoc verification via `lean_compile()` tool

**Funding**: Advanced Research + Invention Agency (ARIA)

## Additional Documentation

**For research, design, and creative work**: Consult `benchmark/ideas/*.md` for in-depth discussion of:

- **`METRICS.claude.md`** - Metric design and quality assessment strategies, vacuity detection approaches
- **`depmock/human.md`** - Dependency mocking strategies (torch/numpy) with focus on computable implementations
- **`depmock/agents.md`** - Historical exploration of dependency mocking approaches (includes non-viable options for context)
- **`HOARE.claude.md`** - mvcgen and monadic program logic for imperative verification

These documents contain brainstorming, trade-off analysis, and detailed rationale that inform benchmark development decisions. Files marked `.claude.md` are exploratory/historical; `.human.md` files are intended for team review.

## Development Environment

This project uses Nix flakes with direnv for environment management:

- Run `direnv allow` to activate the development environment
- The flake provides: `elan` (Lean toolchain), `uv` (Python package manager), `typst`, `nodejs_24`, `lefthook`, `pandoc`, and `claude-code`

## Repository Structure

The repository is organized into three main areas:

### `/benchmark` - Main benchmark implementation

Python package using `inspect_ai` framework for AI evaluations. Key components:

- **`src/benchmark/scaffold/`** - Core evaluation infrastructure
  - `task.py` - Defines the `fvspec` task that runs the benchmark
  - `agent.py` - Agent configuration using `inspect_ai` basic_agent with Lean MCP tools
  - `dataset.py` - Loads and samples datapoints from JSON, creates `inspect_ai` datasets (configurable sample size)
  - `quality_assessment.py` - Extracts metrics from TaskState (token usage, timing, faithfulness, interest, structural metrics)
  - `tools/declaration.py` - Defines `lean_compile()` tool, cleanup functions, and score registration for inspect_ai viewer
  - `tools/utilio.py` - Utility functions for subprocess execution and file operations

- **`src/benchmark/_registry.py`** - Task registration for inspect_ai
  - Registers `fvspec` task via entry point for `eval_set()` retry support and log management

- **`src/benchmark/templates/`** - Jinja2 prompt templates with variant system
  - `variants/` - Directory containing prompt variants for A/B testing
  - `shared/` - Shared prompt fragments and default templates
  - `registry.toml` - Master index of available variants with metadata
  - `prompt.py` - Prompt loading logic with variant selection and Jinja2 templating
  - `registry.py` - Variant registry for loading and validating variants

- **`src/benchmark/config.toml`** - Runtime configuration
  - Agent settings: model name, max_tokens
  - Dataset settings: sample_size (default: 100)
  - Prompt settings: default variant selection
  - Meta settings: logging, debug flags

### `/baselines` - Baseline implementations (minimal structure currently)

### `benchmark/data` - Input data

- `scrapedtests.json` - Large JSON file (~1.1GB) containing scraped Python property-based tests with dependencies

### `/benchmark/src/scripts` - Utility scripts

- `analyze_deps.py` - Analyzes import dependencies in scraped property-based test data

### `/artifacts` - Benchmark outputs (gitignored)

Organized by timestamp/variant, then by `<sample_id>_<test_name>/`:

- `<timestamp>__variant_<name>/` - Single variant run directories
- `comparison_<timestamp>/` - Multi-variant A/B testing results
- `.eval` files - Binary inspect_ai log files (viewable with `uv run inspect view --log-dir artifacts`)
- `datapoint.json` - Original test metadata
- `Spec.lean` - Generated Lean 4 code extracted from `<code>...</code>` tags
- `qa.json` - Quality assessment metrics with scores

## Common Commands

### Running the benchmark

You actually shouldn't run the benchmark as an agent. i'll do that in a different terminal.

```bash
# Default run with control-functional variant and 100 samples
uv run fvspec

# List available variants
uv run fvspec --list-variants

# Run specific variant
uv run fvspec --variant control-mvcgen
uv run fvspec --variant terse-functional

# Control sample size (default: 100)
uv run fvspec --sample-size 50

# Control parallelism (default: config.meta.parallelism)
uv run fvspec --parallelism 10

# Disable MCP tools (faster, but less interactive)
uv run fvspec --no-mcp

# Combine options
uv run fvspec --variant control-mvcgen --sample-size 200 --no-mcp

# A/B testing: compare multiple variants in parallel
uv run fvspec compare-variants
uv run fvspec compare-variants --variant control-functional --variant terse-functional --sample-size 50
```

#### Dependency utilities

```bash
# Autoformalize dependencies for specific datapoints (writes Lean stubs or cached modules)
uv run fvspec deps autoformalize --sample-id 5 --sample-id 47

# Sample N datapoints and generate dependency Lean files
uv run fvspec deps autoformalize --sample-size 10 --ranseed 42

# Clear dependency cache (forces regeneration next time)
uv run fvspec deps cache-flush
```

`autoformalize` produces one Lean file per dependency under the run's `deps/` directory; if no cached Lean exists a computable stub is emitted and recorded for later refinement. Aggregated output in `Fvspec/Deps.lean` wraps all modules inside the namespace exactly once.

Additional behavior to know:

- `--dry-run` emits Lean stubs without invoking the autoformalizer agent. Use this for smoke tests or when the backend is unavailable.
- `--skip-cached/--no-skip-cached` controls whether cached dependencies are regenerated. Even when skipping, cached files are copied into the run-specific `deps/` directory.
- `--validate` typechecks the aggregated `Deps.lean` per sample and records exit codes in the run report.
- Each invocation writes `dependency_report.json` at the root of the artifacts directory. The report captures timing, retry counts, dependency outcomes, diagnostics, and validation results, enabling quick inspection without opening every sample directory.
- Sample directories under `artifacts/<timestamp>__variant_<variant>-deps/` contain ordered Lean modules (`<Module>.lean`) and a consolidated `Deps.lean`, mirroring the module graph used during validation.

### Viewing Results

```bash
# View all results in artifacts directory with inspect_ai viewer
uv run inspect view --log-dir artifacts

# View specific run
uv run inspect view --log-dir artifacts/2025-10-14T15-30-00__variant_control-functional

# View comparison results
uv run inspect view --log-dir artifacts/comparison_2025-10-14T15-45-00
```

The inspect viewer displays all quality metrics as scores with explanations, including token usage, time, faithfulness, structural metrics, and more.

### Prompt Variants

The benchmark uses a **variant system** for A/B testing different prompting strategies. Variants support two verification approaches:

**Functional variants** (e.g., `control-functional`, `terse-functional`):
- FVAPPS-style recursive definitions
- Pure functional programming
- Traditional theorem proving with induction
- Best for: mathematical functions, recursive algorithms

**mvcgen variants** (e.g., `control-mvcgen`):
- Imperative programs with `do` notation and mutable variables
- Hoare logic specifications with `⦃Precondition⦄ program ⦃Postcondition⦄`
- Loop invariants and verification conditions via `mvcgen` tactic
- Best for: loops, stateful algorithms, PyTorch/NumPy operations

You can set the default variant in `config.toml`:
```toml
[prompt]
variant = "control-functional"

[dataset]
sample_size = 100
```

See `benchmark/README.md` for detailed documentation on creating and comparing variants.

### Development tools

**Please make sure you `cd` into `./benchmark` to run these commands!**

```bash
# Format Python code
uv run ruff format

# Run linter
uv run ruff check

# Run typechecker
uv run ty check

# Run tests
uv run pytest

# Preview prompt templates (both styles)
uv run preview_prompts test_prompts.json --style functional
uv run preview_prompts test_prompts.json --style mvcgen
```

### Commit discipline

- Keep the commit subject within the conventional character limit and follow it with two blank lines before a thorough, exhaustive body that enumerates every change.
- Run every pre-commit hook and resolve the results—formatting, linting, type checking, and the full test suite must pass before you commit.
- Always include both the user and the agent as co-authors so the history records shared ownership of the change.

### Package management

```bash
# Install/sync dependencies (from benchmark/ directory)
uv sync

# Add a dependency
uv add <package>
```

## Architecture Notes

### Benchmark Flow

1. `mk_dataset()` loads datapoints from JSON, samples N random items (configurable via `--sample-size`, default: 100)
2. Each datapoint contains a Python property-based test (`pbt`) and its dependencies (`deps`)
3. The variant's prompt templates render system and initial prompts with the test and dependencies
4. The agent uses the `lean_compile()` tool to typecheck generated Lean code
5. The model responds with Lean 4 code in `<code>...</code>` tags, including faithfulness/interest metrics
6. Cleanup (`write_to_disk`) extracts the code, runs quality assessment, registers scores, and saves all outputs
7. All metrics are registered as inspect_ai `Score` objects with explanations for the viewer

### Quality Metrics

The QualityAssessment class extracts and registers as scores:

- **Performance**: token usage, time, message counts
- **Code metrics**: lines added, number of `sorry` placeholders, success status
- **Subjective metrics**: AI self-reported faithfulness (0-10) and interest (0-10) scores
- **Structural faithfulness**: Objective metrics computed from code analysis
  - Parameter coverage, type correspondence, strategy coverage
  - Assertion coverage, dependency coverage
  - Overall weighted average

All metrics appear in `inspect view` with explanatory text.

### Task Registration

Tasks are registered via `_registry.py` and `pyproject.toml` entry points:
```toml
[project.entry-points.inspect_ai]
benchmark = "generate._registry"
```

This enables `eval_set()` to serialize tasks for retry support and log management.

### MCP Integration

The benchmark uses the `lean-lsp-mcp` server (via `uvx lean-lsp-mcp`) to provide Lean LSP functionality through the Model Context Protocol. MCP is enabled by default. Disable with `--no-mcp` flag for faster execution.

## Configuration

Edit `benchmark/src/generate/config.toml` to change:

- Model selection (currently `anthropic/claude-sonnet-4-5-20250929`)
- Max attempts and tokens
- Dataset sample size (default: 100)
- Default prompt variant
- Debug/logging flags

All settings can be overridden via CLI arguments.

## Code Style & Conventions

### Import Style

**Datetime imports**: Always use `from datetime import datetime`, never `import datetime`:
- ✅ **Do:** `from datetime import datetime` then `datetime.now()`
- ❌ **Don't:** `import datetime` then `datetime.datetime.now()`

This style is consistent across the entire codebase.

**Absolute imports**: Prefer fully qualified module paths (e.g. `from generate.scaffold.depmock.runner import ...`) instead of relative imports such as `from .runner import ...`. Absolute imports keep the package structure explicit, help static tooling, and reduce ambiguity when files move.

### Pydantic Usage

**Use Pydantic aggressively throughout the codebase.** All data models should be Pydantic `BaseModel` classes:

- ✅ **Do:** Use `BaseModel` for all data structures
- ✅ **Do:** Use `.model_dump_json(indent=4)` for JSON serialization
- ✅ **Do:** Use `Field()` for field descriptions and validation
- ✅ **Do:** Use `frozen=True` for immutable models
- ✅ **Do:** Add docstrings to models explaining their purpose
- ❌ **Don't:** Write manual `__init__` methods
- ❌ **Don't:** Write custom `toJSON()` methods
- ❌ **Don't:** Use plain Python classes for data that could be validated

**Benefits:** Automatic validation, type safety, consistent serialization, better IDE support.

## Working with Lean Output

Generated Lean files follow this pattern:

- Type definitions and function signatures with `sorry` placeholders
- Theorem statements with property bounds from the Python tests
- No implementations - only declarations and specifications

Lean files can be typechecked with: `lean <filename>.lean`

### Design Philosophy: Computation is Non-Negotiable

**Critical constraint**: While we initially ship specifications with `sorry` placeholders, **all definitions must eventually be computable**. The ultimate goal is for downstream solvers—primarily future language models and AI proof techniques—to implement all the `sorry`s.

**Why computation (`#eval`) is a priority:**

- Downstream proof agents need computational leverage from tactics like `rfl`, `decide`, and `simp`
- Axioms and opaque definitions provide no reduction rules for proof automation
- Computable implementations enable both validation (via `#eval`) and proof tactics
- This requirement drives our dependency mocking strategy (see `benchmark/ideas/depmock/human.md`)

**Implication**: When generating or designing Lean code for this benchmark, prefer concrete implementations over axioms, even if incomplete initially. A `def` with `sorry` is better than an `axiom`, because it can later be filled in while maintaining computability.
