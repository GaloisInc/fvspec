# Dependency Mocking: Dataset-Driven Autoformalization

**Context.** Every scraped datapoint already ships the raw Python dependency stubs inside its `deps` array. Rather than inventing abstract mocks, we can spin up a focused autoformalization loop that translates those concrete code snippets into computable Lean modules. This approach inherits the virtues of the fully concrete strategy (everything reduces, tactics get leverage) without demanding that we hand-design a general-purpose NumPy/PyTorch clone.

---

## Strategy Shift

- **Legacy thinking:** enumerate possible mocking styles (axioms, property axioms, partial concretes, FFI) and pick the least-worst compromise.
- **New direction:** treat every `deps` payload as training data for an auxiliary agent whose only job is “take this Python helper, return a Lean version that computes.”
- **Key observation:** the scraped repos already expose the exact helper functions authors rely on; we are no longer guessing the API surface.

This pushes us toward an *autoformalization subagent* that runs alongside the main benchmark agent. The benchmark agent still produces Lean specifications with `sorry`s, but it can now import Lean modules synthesized by the dependency subagent instead of gesturing at unspecified library calls.

---

## Autoformalization Subagent Loop

1. **Datapoint intake.**
   - Input: `pbt`, `deps`, `dep_names`, and light metadata (repo, hash).
   - Goal: identify which dependency blocks matter for the test at hand (regex counts from `analyze_deps_regex.py` help prioritization).

2. **Chunk + classify dependencies.**
   - Group related snippets (e.g., validator utilities vs. tensor helpers).
   - Label expected behaviors: pure functions, stateful objects, constants, fixtures.

3. **Prompt the autoformalizer.**
   - System prompt: “You are a Lean 4 developer who must produce computable code; sorried stubs are allowed only if accompanied by executable scaffolding.”
   - Provide: original Python code, inferred types, any Docstrings/examples from the snippet.
   - Ask for: Lean code with concrete implementations and unit-check harnesses (`#eval`, simple tests).

4. **Validation pass.**
   - Syntax check via `lean --check` or `lean_compile()`.
   - Execute lightweight evaluations (`#eval`, `decide`) to ensure the definitions actually compute.
   - If validation fails, feed diagnostics back into the subagent (loop until pass or retry budget exhausted).

5. **Artifact output.**
   - Emit `Deps/<sample_id>/<dep_name>.lean`.
   - Record metadata: source hash, validation logs, computed sample outputs.
   - Surface import statements that the main benchmark prompt can reference.

---

## Why This Beats Prior Approaches

- **Concrete by construction.** The generated Lean code mirrors real Python helpers, so everything reduces without guesswork.
- **Scalable.** Works sample-by-sample; we do not need a monolithic mock library.
- **Traceable.** Each Lean snippet links back to an exact Python origin, enabling consistency checks and future regeneration if the scraper updates.
- **Composable.** The main agent can selectively import only the Lean modules that a theorem needs, no huge prelude required.
- **Token-aware.** Because this runs as a dedicated loop, we can budget separate context windows and reuse cached conversions across samples.

This is effectively the “Concrete Implementations” plan scoped to the actual dataset we own. Instead of building tensors from scratch, we autoformalize just the helpers that real-world property tests already depend upon.

---

## Implementation Notes for Agents

- **Subagent orchestration.** Run the dependency autoformalizer before the main spec agent. Persist artifacts so future benchmark runs can skip regeneration for unchanged hashes.
- **Prioritization heuristics.**
  - Frequency from `import_counts.csv`.
  - Complexity signals (e.g., presence of NumPy/PyTorch calls vs. simple validators).
  - Failure telemetry (retry stubborn snippets later with more guidance).
- **Prompt scaffolding.**
  - Include Python doctests/examples when available.
  - Ask for companion Lean tests whenever the snippet has deterministic behavior.
  - Encourage reuse of Mathlib constructs when natural (e.g., lists, arrays, finsets).
- **Multi-turn refinement.** Allow the subagent to call `lean_compile()` iteratively, gathering error messages and patching its own output.
- **Deliverables to the main agent.**
  - Module import path.
  - Summary of provided functions/constants.
  - Any remaining `sorry` placeholders (should be rare and explicitly documented).

---

## Open Design Questions

1. **Deduplication.** Multiple datapoints may reference identical helpers. We should hash normalized Python source and cache the Lean translation globally.
2. **Side effects.** Some deps set global state or rely on I/O. Decide whether to model them concretely (e.g., use `IO` in Lean) or stub them with deterministic replacements.
3. **Numerics vs. validators.** Validators (like config coercion helpers) should be straightforward; tensor-heavy snippets may still require incremental hand-holding. Identify where additional Mathlib or SciLean support is beneficial.
4. **Testing harness.** Investigate round-tripping: run the original Python helper on random inputs (via Hypothesis) and compare against Lean results using the same samples.
5. **Integration cadence.** Decide whether the autoformalizer runs offline (precompute library) or online (lazy-generate per benchmark invocation).

---

## Historical Context (Archived)

Earlier drafts surveyed axiomatic mocks, hybrid property approaches, and FFI tricks. Those notes remain relevant as cautionary tales, but the active plan is to invest in the dataset-driven autoformalization subagent described above. Should we run into cases where the Python source is missing or intractable, we can revisit hybrid or FFI tactics, but the default assumption is that the `deps` payload contains everything we need.

