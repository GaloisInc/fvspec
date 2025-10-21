# Depmock Autoformalization Plan

## Objective
Upgrade the current dependency autoformalization workflow from a stub generator into a full inspect_ai-powered agent that translates Python dependency signatures into validated Lean modules using `sonnet-4-5`. The resulting pipeline must plug into the existing CLI (`uv run fvspec deps autoformalize`), respect caching semantics, and capture telemetry needed for benchmark analytics.

## Phase 1 — Agent Foundations
1. [x] **Dependency ingest contract**  
         Define the Pydantic schema for the dependency inputs we can actually extract from the dataset: Python source bodies, signatures, and any inline docstrings/comments. Capture derived fields we need for prompting (e.g., module path, callable kind, argument roles) and the Lean artifact we expect back. Make the schema reusable by both CLI orchestration and inspect_ai datasets.
2. [x] **Prompt scaffolding**  
         Author the system/user prompts that instruct the model to emit Lean stubs for dependencies only—no property-based tests or downstream specs yet—and decide how to surface functional vs mvcgen style variations in the prompt registry.
3. [x] **Callable normalization pass**  
         Design a preprocessing step that rewrites Python methods (functions whose first argument is `self`/`cls`) into a representation the agent can mock: decide when to spoof a minimal Lean structure/class vs. when to flatten into standalone pure functions, and record the transformation so the Lean artifact stays consistent with future spec generation.
4. [x] **Agent module**  
         Implement an inspect_ai agent that loads the prompts, connects to the `sonnet-4-5` backend, and invokes the `lean_compile` MCP tool. Leverage inspect_ai’s built-in retry/backoff and streaming capture while ensuring we record the Lean compilation loop in TaskState.

## Phase 2 — Execution Pipeline
1. [x] **Dataset + run harness**  
         Build an inspect_ai dataset wrapper that yields dependency tasks from the depmock manifest/cache scanner, supports deterministic batching, and exposes sample metadata for logging.
2. [x] **Invocation layer**  
         Expose a Python API (e.g., `run_dependency_autoformalizer(...)`) that the CLI can call, handle partial successes (recoverable Lean errors), capture diagnostics, and propagate failures cleanly.
3. [x] **Caching strategy alignment**  
         Reconcile agent outputs with the existing cache format (hash naming, manifest entries, `Deps.lean` aggregation) and write cache entries with Lean artifacts plus provenance metadata (model, timestamp, source hash).
4. [x] **Module ordering**  
         Add a topological sort that respects Lean import dependencies before aggregating modules into `Deps.lean`, ensuring reproducible builds even when the agent introduces cross-module references.

## Phase 3 — Integration & Telemetry
1. [x] **CLI plumbing**  
         Update `uv run fvspec deps autoformalize` to call the new agent API, stream progress, surface summary statistics, and retain a dry-run mode for smoke tests.
2. [x] **Quality assessment hooks**  
         Extend quality metrics to cover dependency autoformalization (Lean compile counts, retry stats, token/time usage) and emit them into run artifacts for downstream inspection.
3. [x] **Validation workflow**  
         Run targeted samples end-to-end, verify cached outputs compile, assess prompt effectiveness, and collect follow-up action items for tuning.

## Deliverables
1. [ ] Inspect_ai agent module for dependency autoformalization using `sonnet-4-5`.
2. [ ] Updated CLI command and supporting APIs that invoke the agent and integrate with caching.
3. [ ] Extended run artifacts containing Lean outputs, provenance, and telemetry for each dependency translation.
4. [ ] Thorough documentation explaining how to interpret the new artifacts dir
