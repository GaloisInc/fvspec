# Phase 2 Refactor: Implementation Plan

**Status**: Phase 1 ✅ Complete | Phase 2 ✅ Complete | Phase 3-5 ⏳ Pending
**Branch**: `q/analyze-deps-2`
**Commits**: 348852c1 (Phase 1), cbe60a54 (Phase 2 Step 1), 6a3d01ce (Phase 2 Complete)

## Overview

Two-agent architecture: **Implementation Agent** (formalize function + deps) → **Spec Agent** (generate theorem statements).
- Implementation: ZERO sorry (fully computable)
- Spec: sorry expected (stating theorems, not proving)
- Orchestrator: Pure Python logic (no LLM)

---

## ✅ Phase 1: Rename (COMPLETE)

**Goal**: Rename directories and update all imports.

- ✅ Renamed `depmock/` → `formalize_impl/`
- ✅ Renamed `deps/` templates → `impl/`
- ✅ Updated all Python imports and function names
- ✅ All 155 tests passing
- ✅ Commit: 348852c1

---

## ✅ Phase 2: Function Discovery Integration (COMPLETE)

**Goal**: Integrate function discovery into formalize_impl agent.

### What Was Implemented

**Session Wiring**:
- Added `pass_session_to_state()` solver to inject database session
- Updated `register_dependency_tools()` to use session for discovery
- Session flows: task setup → payload generation → function discovery

**Model Metadata**:
- Added `confidence` and `discovery_method` fields to `DependencyPayload`
- Created `FunctionDiscoveryInfo` model for result tracking
- Added `is_function_under_test` computed property
- All discovery metadata included in template context

**Agent Tracking**:
- Agent logs discovered functions with confidence and method
- Provides visibility into discovered vs. explicit dependencies

**Templates**:
- Created `function_under_test.prompt` fragment with comprehensive context
- Emphasizes PRIMARY implementation target with stricter ZERO sorry requirement
- Shows confidence, discovery method, and PBT usage example
- Integrated into both functional and mvcgen variants

**Results**:
- ✅ All 155 tests passing
- ✅ Backward compatible (session parameter optional)
- ✅ Commit: 6a3d01ce

---

## ✅ Phase 3: Spec Agent (COMPLETE)

**Goal**: Create separate agent for spec generation from PBT.

### What Was Implemented

**Models & Validation**:
- SpecPayload, SpecResult, SpecValidation models (all frozen/immutable)
- validate_spec_output(): Checks compiles + has statements (sorry is GOOD!)
- extract_signatures(): Parses Lean code to extract function signatures

**Agent & Runner**:
- spec_generation_agent(): Stub implementation (full LSP loop for Phase 4)
- run_spec_agent(): Orchestrates spec generation per datapoint
- Templates: Reusing existing templates/spec/ (already handles theorem generation)

**Testing**:
- 38 new spec tests (all passing)
- 193 total tests (155 original + 38 new)
- Test coverage: models, validation, signature extraction, integration

**Results**:
- ✅ 7 new files, ~950 LOC
- ✅ All tests passing
- ✅ Commits: 8a1f0677 (Steps 1-2), 64144a4f (Steps 3-6)

---

## ⏳ Phase 4: Orchestration (PENDING)

**Goal**: Wire everything together with Python orchestration logic.

**High-level tasks**:
1. Rewrite `task.py` orchestration:
   - Run impl agent → validate zero sorry → extract signatures
   - Run spec agent with impl signatures → validate compiles
2. Update `quality_assessment.py` to track both agents separately
3. New artifact structure:
   ```
   {sample_id}__{pbt_name}/
   ├── Spec.lean     # From spec agent (with sorry)
   ├── Impl.lean     # From impl agent (zero sorry)
   ├── impl/         # Implementation modules
   └── qa.json       # Metrics from both agents
   ```

---

## ⏳ Phase 5: Validation & Optimization (PENDING)

**Goal**: Validate system works, optimize based on metrics.

**High-level tasks**:
1. Run full benchmark (50+ samples)
2. Analyze results (discovery rate, success rates, failure modes)
3. Optimize prompts based on analysis
4. A/B test vs baseline
5. Update documentation

---

## Success Criteria Summary

### Phase 1 ✅
- [x] All 155 tests pass after rename
- [x] No logic changes, pure refactor

### Phase 2 ✅
- [x] Function discovery integrated in dataset.py
- [x] Discovery tracked in agent.py
- [x] Discovery metadata in models.py
- [x] Templates created for function_under_test
- [x] All tests pass

### Phase 3 ⏳
- [ ] Spec agent generates valid Lean (compiles)
- [ ] 95%+ specs have theorem statements
- [ ] Specs reference impl signatures correctly
- [ ] Specs use sorry for proof obligations

### Phase 4 ⏳
- [ ] Impl agent: 100% zero sorry (fully computable)
- [ ] Spec agent: >90% have sorry (stating theorems)
- [ ] Both agents succeed in 95%+ of samples
- [ ] Orchestration metrics tracked

### Phase 5 ⏳
- [ ] Structural faithfulness improvement vs baseline
- [ ] Implementation correctness validated
- [ ] Spec captures PBT invariants
- [ ] Pipeline latency acceptable

---

## Quick Reference

### Commands

```bash
# Development
uv run pytest src/tests/ -v              # Run all tests
uv run ruff format && uv run ruff check  # Lint/format

# Single sample test
uv run fvspec --variant control-functional --sample-size 1

# Full benchmark
uv run fvspec --variant control-functional --sample-size 50 --parallelism 10

# View results
uv run inspect view --log-dir artifacts
```

### Current Branch Status

**Branch**: `q/analyze-deps-2`
**Base**: `main`
**Commits**:
- 348852c1: Phase 1 rename complete
- cbe60a54: Phase 2 partial (dataset integration)
- 6a3d01ce: Phase 2 complete (function discovery integration)

**Ready to continue**: Phase 3 (Spec Agent)
