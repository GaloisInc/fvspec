# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

fvspec is a benchmark suite for evaluating how AI models perform on formal verification tasks. The project builds on **FVAPPS / Proving the Coding Interview** (Dougherty & Mehta, [arxiv:2502.05714](https://arxiv.org/abs/2502.05714)) by using real-world Hypothesis property-based tests scraped from GitHub, rather than synthetic programming puzzles.

### Background: FVAPPS
FVAPPS (Formally Verified Automated Programming Progress Standards) is a benchmark of 4,715 samples for writing programs and proving their correctness in Lean 4. It generalizes the APPS benchmark by transforming Python unit tests into Lean 4 theorems. The benchmark challenges models to both implement code and prove its correctness.

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
  - `dataset.py` - Loads and samples datapoints from JSON, creates `inspect_ai` datasets
  - `quality_assessment.py` - Extracts metrics from TaskState (token usage, timing, faithfulness, interest)
  - `tools/declaration.py` - Defines `lean_compile()` tool and cleanup functions that write outputs to disk
  - `tools/utilio.py` - Utility functions for subprocess execution and file operations

- **`src/benchmark/templates/`** - Jinja2 prompt templates
  - `system.txt` - System prompt instructing the model to translate Python tests to Lean 4
  - `initial.txt` - User prompt template with dependencies and property-based test

- **`src/benchmark/config.toml`** - Runtime configuration
  - Agent settings: model name, max_attempts, max_tokens
  - Meta settings: logging, debug flags

### `/baselines` - Baseline implementations (minimal structure currently)

### `/data` - Input data
- `scrapedtests.json` - Large JSON file (~1.1GB) containing scraped Python property-based tests with dependencies

### `/artifacts` - Benchmark outputs (gitignored)
Organized by timestamp, then by `<sample_id>_<test_name>/`:
- `Datapoint.json` - Original test metadata
- `Spec.lean` - Generated Lean 4 code extracted from `<code>...</code>` tags
- `QA.json` - Quality assessment metrics

## Common Commands

### Running the benchmark
```bash
# Run benchmark evaluation (from repository root)
uv run fvspec evaluate-fvspec [datafile]

# Default uses data/scrapedtests.json
uv run fvspec evaluate-fvspec
```

### Development tools
```bash
# Format Python code
uv run ruff format

# Run linter
uv run ruff check

# Run tests
uv run pytest

# Preview prompt templates
uv run preview_prompts
```

### Package management
```bash
# Install/sync dependencies (from benchmark/ directory)
uv sync

# Add a dependency
uv add <package>
```

## Architecture Notes

### Benchmark Flow
1. `mk_dataset()` loads datapoints from JSON, samples 100 random items
2. Each datapoint contains a Python property-based test (`pbt`) and its dependencies (`deps`)
3. The `initial.txt` template renders a prompt with the test and dependencies
4. The agent uses the `lean_compile()` tool to typecheck generated Lean code
5. The model responds with Lean 4 code in `<code>...</code>` tags, including faithfulness/interest metrics
6. Cleanup (`write_to_disk`) extracts the code, runs quality assessment, and saves all outputs

### Quality Metrics
The QualityAssessment class extracts:
- Performance: token usage, time, message counts
- Code metrics: lines added, number of `sorry` placeholders
- AI-generated metrics: faithfulness score (how well Lean matches Python), interest score (complexity)

### MCP Integration
The benchmark can use the `lean-lsp-mcp` server (via `uvx lean-lsp-mcp`) to provide Lean LSP functionality through the Model Context Protocol. The `lean_task()` function demonstrates this setup.

## Configuration

Edit `benchmark/src/benchmark/config.toml` to change:
- Model selection (currently `anthropic/claude-sonnet-4-5-20250929`)
- Max attempts and tokens
- Debug/logging flags

## Working with Lean Output

Generated Lean files follow this pattern:
- Type definitions and function signatures with `sorry` placeholders
- Theorem statements with property bounds from the Python tests
- No implementations - only declarations and specifications

Lean files can be typechecked with: `lean <filename>.lean`
