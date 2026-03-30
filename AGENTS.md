# AGENTS.md

> **Note**: This file is symlinked from `CLAUDE.md` and `KNOWLEDGE.md` to ensure consistent guidance across different AI code assistants.

## Project Overview

fvspec is a benchmark for evaluating AI models on formal verification tasks. Extends **FVAPPS / Proving the Coding Interview** ([arxiv:2502.05714](https://arxiv.org/abs/2502.05714)) using real-world Hypothesis property-based tests instead of synthetic puzzles.

**Goal:** Translate Python PBTs into Lean 4 specifications with `sorry` placeholders.

**Key principles:**
- Single unified formalization agent produces both `Impl.lean` and `Spec.lean`
- Real-world tests to avoid contamination
- Structural faithfulness metrics
- Interactive LSP via MCP tools
- Use `def` with `sorry` (not `axiom`) for computability

**Funding:** Advanced Research + Invention Agency (ARIA)

## Repository Structure

- **`/benchmark`** - Benchmark generation (`inspect_ai`, JSONL, unified formalization agent) and postproduction pipeline
  - `src/generate/` - Core benchmark generation (dep formalization + unified formalization agent)
  - `src/scripts/postproduction/` - Post-processing tools (merge, grader, W&B accumulator)
- **`/baselines`** - Baseline model evaluations, results aggregation, and `doteval-dashboard` trajectory viewer
- **`/leaderboard`** - Public dataset explorer (Next.js, embedded Hono API)
- **`/benchmark/artifacts`** - Generated outputs (gitignored)

See subdirectory `CLAUDE.md` and `README.md` files for details.

## Development

Requires: `uv`, `elan`, `lefthook`, `pnpm`

## Code Style

**Python:** `from datetime import datetime`, absolute imports, Pydantic/SQLModel for data
**Lean:** `def` with `sorry` (not `axiom`)
**Git:** Conventional commits, pass pre-commit hooks, co-author
