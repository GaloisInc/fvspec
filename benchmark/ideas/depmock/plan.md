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

## 3. Prompt & Normalization Refinement

### Observed gaps
- `functional` vs `mvcgen` prompts diverge only in post-processing instructions.
- Normalization hints are descriptive but unchecked by automation.

### Actions
1. **Prompt A/B testing**
   - Collect a corpus of dependencies with known Lean implementations.
   - Run the functional agent end-to-end once available, compare success/Lean validation rates across prompt variants.
2. **Normalization telemetry**
   - Extend `DependencyRunReport` to include normalization strategy (flatten/structure).
   - Analyze distributions to spot edge cases (e.g., methods misclassified).
3. **Prompt documentation**
   - Produce README snippet describing normalization strategies for educators using the dataset.

## 4. Cache Evolution & Persistence

### Currently
- Cache metadata includes provenance (model, attempts, diagnostics).
- `CACHE_SCHEMA_VERSION = 3`.
- Cache lives under `artifacts/dep_cache`.

### Follow-ups
1. **Compaction / pruning**
   - Add CLI command `uv run fvspec deps cache-prune` to remove old schema versions or stale entries.
2. **Remote sync**
   - Explore optional S3/GCS sync to share cache across machines.
   - Introduce `--cache-root` CLI override that feeds into cache helpers.
3. **Manifest referencing**
   - Include `validation` status per module in manifest entries to aid debugging.

## 5. Documentation & Onboarding

### Immediate needs
1. **AGENTS.md** already updated with CLI flags; add a short “Why stubs?” note until agent lands.
2. **New README section** covering:
   - `dependency_report.json` schema.
   - How to interpret validation results.
   - How to read provenance metadata.

## 6. Stretch Goals

1. **Downstream integration with autoformalizer outputs**
   - Update main spec-generation pipeline to optionally load dependency Lean modules (vs. stub stubs).
   - Provide a `Deps.lean` import in generated specs guarded by configuration.
2. **Batch scheduling**
   - Consider keep-alive patterns for expensive models (reuse sessions across dependencies).
3. **Mocking Playbook**
   - Combine results from `analyze_deps` with autoformalizer runs to prioritize human-crafted mocks.

## Summary Checklist

- [ ] Implement inspect_ai dependency agent harness and integrate into CLI executor.
- [ ] Support Lean-guided retries + per-module validation in telemetry.
- [ ] Expand prompt A/B testing capabilities and track normalization analytics.
- [ ] Enhance cache tooling (prune, remote sync, validation metadata).
- [ ] Finish documentation updates (README, AGENTS) reflecting new reports.
- [ ] Investigate stretch goals for full spec integration and human-in-the-loop mocks.
