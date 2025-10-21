# Documentation Index (Multi-Agent Focus)

This index points to the documentation and code that describe how fvspec orchestrates multiple agents, along with the upstream Inspect guidance we rely on.

## External Reference

- Inspect Multi Agent (https://inspect.aisi.org.uk/multi-agent.html#tools) — outlines three integration patterns (supervisor handoffs, explicit `run()` workflows, agent-as-tool exposure). Key notes: start from a baseline `react()` agent before layering complexity, `run()` clones state so parallel `gather()` calls are safe, `as_tool()` returns only the child agent's final assistant message, and `handoff()` accepts input/output filters (`remove_tools`, `last_message`, custom functions) to control shared history.

## Internal Plans & Strategy

- `benchmark/ideas/depmock/plan.md:1` — step-by-step plan for embedding the dependency autoformalizer as an Inspect subagent, including desired runtime flow, component layout, and reuse of `as_tool()` with `basic_agent` retries.
- `benchmark/ideas/depmock/agents.md:1` — rationale for the dataset-driven autoformalization subagent loop, covering intake, prompting, validation, and how the subagent collaborates with the main specification agent.
- `benchmark/ideas/depmock/human.md:1` — execution checklist for the dependency subagent (hash-based caching, prompt scaffolding, iterative refinement with `lean_compile()`), emphasizing computable outputs.

## Implementation Touchpoints

- `benchmark/src/generate/templates/deps/prompt.py:1` — loads the system, translate, and refine prompts that the dependency autoformalization subagent consumes for each variant.
- `benchmark/src/generate/scaffold/tools/declaration.py:1` — assembles the Lean tooling (`lean_compile()` and `lean_lsp_mcp()`) used by agents, ensuring subagents have diagnostics and compilation hooks.
- `benchmark/src/generate/templates/deps/` — template bundle for dependency agents (variant registry, shared fragments) that the subagent plan references.

## General Project Briefing

- `AGENTS.md:1` — complete repository onboarding for agents (project overview, benchmark flow, tooling), useful context when integrating the multi-agent pieces above.
