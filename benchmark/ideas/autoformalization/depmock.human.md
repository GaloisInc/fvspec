# Dependency Autoformalization Plan

We will handle dependency mocking by autoformalizing the actual Python snippets provided in each datapoint’s `deps` array. Instead of designing a synthetic mock library, a dedicated subagent will translate those helpers into Lean modules that compute. This document captures the concrete steps required to execute that strategy.

---

## Objectives

- **Computable outputs.** Every generated Lean definition must reduce; no axioms, minimal `sorry`.
- **One subagent per dependency cluster.** The dependency loop runs alongside the main benchmark agent, feeding it Lean modules on demand.
- **Cache by source hash.** Identical Python helpers should only be translated once.
- **Tight validation.** Each artifact passes `lean_compile()` and, when feasible, a small `#eval` smoke test mirroring the Python behavior.

---

## Workflow Breakdown

1. **Inventory & Deduplication**
   - Normalize each dependency snippet (strip comments, trim whitespace).
   - Compute a stable hash to use as the cache key.
   - Store metadata: source repo, datapoint IDs, frequency counts.

2. **Preprocessing**
   - Infer probable types from usage (basic static hints, regex heuristics).
   - Extract docstrings / examples to add to the prompt context.
   - Bucket snippets into categories: validators, numeric helpers, tensor utilities, fixtures.

3. **Autoformalization Agent Loop**
   - Prompt template includes: Python source, inferred type info, expectations about computability, and any tests.
   - The agent iteratively emits Lean code, runs `lean_compile()`, and inspects diagnostics.
   - On failure: the agent patches its own output (multi-turn refinement).
   - Encourage the agent to add Lean-side sanity checks (e.g., `#eval` examples, quick decidable lemmas).

4. **Validation & Packaging**
   - Require a clean `lean --check` or `lean_compile()` run.
   - Capture evaluation logs (inputs/outputs) when the snippet is deterministic.
   - Emit artifacts under `benchmark/lean_deps/<hash>/Module.lean` with an index JSON describing provenance and interface.
   - Surface a summary (functions, constants, pending `sorry`s) for the main agent.

---

## Implementation Tasks

1. **Cache Layer**
   - Schema: hash, original text, Lean output, validation status, last-updated timestamp.
   - CLI helpers to inspect and refresh entries.

2. **Preflight Analyzer**
   - Re-use `analyze_deps_regex.py` counts to prioritize high-impact helpers.
   - Add utility to fetch representative examples from `pbts.jsonl`.

3. **Agent Orchestration**
   - Define Typer command `uv run deps-autoformalize --id <dp>` that drives the loop for a single datapoint.
   - Provide batch mode for nightly regeneration.

4. **Prompt Engineering**
   - Draft system + user prompts.
   - Include clear fulfillment checklist (computable definitions, optional `sorry` only with TODO comment, add quick Lean checks).

5. **Testing Harness**
   - Optional: execute Python snippet with sample inputs and compare to Lean output via JSON interchange (enables regression testing).

6. **Integration Points**
   - Extend main benchmark prompts to import generated modules when present.
   - Document fallback behavior if a dependency fails to autoformalize (e.g., warn but proceed).

---

## Open Questions

- **Stateful dependencies:** how to handle snippets that mutate global state or depend on I/O?
- **Randomness:** if a helper uses randomness, do we stub deterministic behavior or expose Lean RNG equivalents?
- **Performance:** should we pre-warm the cache for the top N dependencies before benchmark runs?
- **Spec drift:** how do we detect when upstream Python helpers change and invalidate prior Lean translations?
- **Verification depth:** when do we require actual proofs versus relying on computational checks?

The plan above should be treated as the living source of truth for dependency handling going forward. Other approaches discussed previously (axioms, hybrid Mathlib stubs, FFI) are archived for reference but no longer active.

