# AGENTS.md

> **Note**: This file is symlinked from `CLAUDE.md` and `KNOWLEDGE.md` to ensure consistent guidance across different AI code assistants.

## Project Overview

fvspec is a benchmark suite for evaluating AI models on formal verification tasks. It extends **FVAPPS / Proving the Coding Interview** (Dougherty & Mehta, [arxiv:2502.05714](https://arxiv.org/abs/2502.05714)) by using real-world Hypothesis property-based tests from GitHub instead of synthetic puzzles.

**Goal:** Translate Python property-based tests into Lean 4 specifications with `sorry` placeholders, focusing on specification quality over full implementation.

**Key design principles:**
- Two verification approaches: **functional** (FVAPPS-style recursion) and **mvcgen** (imperative with Hoare logic)
- Real-world tests (not LLM-generated) to avoid benchmark contamination
- Structural faithfulness metrics for objective quality assessment
- Interactive LSP feedback via MCP tools for iterative development
- Computation is non-negotiable: use `def` with `sorry` (not `axiom`) to maintain computability

**Funding:** Advanced Research + Invention Agency (ARIA)

## Repository Structure

- **`/benchmark`** - Main benchmark generation system (see `benchmark/AGENTS.md`)
  - Python package using `inspect_ai` framework
  - Dataset sampling, prompt variants, quality assessment
  - MCP integration for Lean LSP tools
  - See `benchmark/ideas/*.md` for research notes

- **`/baselines`** - Baseline implementations (see `baselines/AGENTS.md`)
  - Minimal currently; will contain baseline model evaluations

- **`/leaderboard`** - Public leaderboard website (see `leaderboard/AGENTS.md`)
  - Three-service architecture: Next.js frontend, Hono API, BullMQ worker
  - Secure sandboxed execution of `lake build` with attestations
  - Real-time submission tracking and results display

- **`/benchmark/artifacts`** - Benchmark outputs (gitignored)
  - Timestamped run directories with `.eval` logs, Lean specs, metrics

## Development Environment

Requires `uv`, `elan`, `lefthook`, maybe more (like `ripgrep` is a dep of an mcp tool we might be involving?)

## Quick Start

See subdirectory `AGENTS.md` files for detailed documentation:
- **Benchmark generation:** `benchmark/AGENTS.md`
- **Baselines:** `baselines/AGENTS.md`
- **Leaderboard website:** `leaderboard/AGENTS.md`

## General Code Style

**Python:**
- `from datetime import datetime` (not `import datetime`)
- Absolute imports preferred
- Pydantic for all data models

**Lean:**
- Use `def` with `sorry` over `axiom` (maintains computability)

**Git:**
- Conventional commits with exhaustive bodies
- All pre-commit hooks must pass
- Co-authored commits
