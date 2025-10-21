# Depmock Next Steps Blueprint

The current depmock pipeline now delivers dataset plumbing, CLI integration, caching/telemetry, and ordered Lean aggregation. Remaining work focuses on replacing the stub executor with a real inspect_ai agent, tightening validation, and supporting downstream consumers. This document tracks open cruxes and proposed experiments.

## 1. Replace Stub Executor with Real inspect_ai Agent

### Status
- CLI invokes `run_dependency_autoformalizer`, but the executor emits stubs.
- No inspect_ai `Task` yet that exercises the dependency prompts against a model.

### Tasks
1. **Agent invocation harness**
   - Create `generate/scaffold/depmock/agent_runner.py` that:
     - Builds a `MemoryDataset` from `DependencySampleSpec`.
     - Wraps `dependency_autoformalizer` in an inspect_ai `Task` using `basic_agent` + `autoformalize_dependency_tool`.
     - Configures retry/backoff and `lean_compile` tooling.
2. **Executor bridge**
   - In `run_dependency_autoformalizer`, replace stub `executor` with a call into the new harness.
   - Capture outputs (Lean code, diagnostics) and map to `DependencyResult`.
   - Thread through attempt counts/diagnostics for provenance.
3. **Model integration**
   - Start with `cfg.agent.model` (`anthropic/claude-sonnet-4-5-20250929`).
   - Ensure CLI options allow overriding model/max tokens if needed.
4. **Testing**
   - Add deterministic integration test using a small fake executor + dataset.
   - Consider VCR-style fixtures or snapshot tests for prompt structure.

## 2. Lean Validation & Retry Semantics

### Current behavior
- `--validate` runs `lean` on aggregated `Deps.lean`, but stubs mean limited coverage.
- No automatic retry on recoverable Lean diagnostics (since executor is stubbed).

### Next experiments
1. **Lean-guided retry loop**
   - Parse diagnostics from `lean_compile` tool results.
   - If Lean reports undefined symbols, feed diagnostics back through `_dependency_autoformalizer`.
2. **Per-module validation**
   - Validate individual modules before aggregation to isolate failures.
   - Store validation results alongside manifest entries for debugging.
3. **CI smoke test**
   - Add a GitHub CI job (or local script) that runs `uv run fvspec deps autoformalize --dry-run --validate --sample-size 1` to ensure toolchain health.

## 3. Documentation & Onboarding

### Immediate needs
1. **AGENTS.md** already updated with CLI flags; add a short “Why stubs?” note until agent lands.
2. **New README section** covering:
   - `dependency_report.json` schema.
   - How to interpret validation results.
   - How to read provenance metadata.

## 4. Stretch Goals

1. **Prompt & normalization refinement**
   - Collect a corpus of dependencies with known Lean implementations and run A/B tests once the agent is live.
   - Expand telemetry (`DependencyRunReport`) with normalization strategy distribution to catch misclassifications.
   - Produce user-facing docs describing normalization strategies for educators.
2. **Cache evolution**
   - Add CLI pruning (`deps cache-prune`), remote sync support, and manifest validation flags.
3. **Downstream integration with autoformalizer outputs**
   - Update main spec-generation pipeline to optionally load dependency Lean modules (vs. stub stubs).
   - Provide a `Deps.lean` import in generated specs guarded by configuration.
4. **Batch scheduling**
   - Consider keep-alive patterns for expensive models (reuse sessions across dependencies).
5. **Mocking Playbook**
   - Combine results from `analyze_deps` with autoformalizer runs to prioritize human-crafted mocks.

## Summary Checklist

- [ ] Implement inspect_ai dependency agent harness and integrate into CLI executor.
- [ ] Support Lean-guided retries + per-module validation in telemetry.
- [ ] Expand prompt A/B testing capabilities and track normalization analytics. *(stretch goal)*
- [ ] Enhance cache tooling (prune, remote sync, validation metadata). *(stretch goal)*
- [ ] Finish documentation updates (README, AGENTS) reflecting new reports.
- [ ] Investigate stretch goals for full spec integration and human-in-the-loop mocks.
