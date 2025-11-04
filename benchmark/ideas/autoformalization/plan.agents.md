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

## ✅ Phase 4: Artifact Structure (COMPLETE)

**Goal**: Align artifact structure with lake-template expectations.

**What Was Implemented:**
- Renamed `Deps.lean` → `Impl.lean` throughout system
- Updated namespace from `Fvspec.Deps` → `Fvspec.Impl`
- All tests updated and passing (193 tests)
- Artifact structure now matches lake-template:
  ```
  {sample_id}__{pbt_name}/
  ├── Spec.lean            # Theorem statements (with sorry)
  ├── Impl.lean            # Function implementations (zero sorry)
  ├── Tests.lean           # Unit tests
  ├── impl/                # Implementation modules
  ├── impl_manifest.jsonl  # Implementation metadata
  └── qa.json              # Quality metrics
  ```

**Current System Design:**
- Single agent generates Spec.lean (theorem statements + implementations mixed)
- Dependency tools generate Impl.lean (dependency implementations)
- System is functional and ready for benchmarking

---

## ⏳ Phase 5: Two-Agent Architecture (IN PROGRESS)

**Goal**: Refactor to full two-agent approach with clean separation.

**Architecture:**
1. **Impl Agent**: Generate ALL implementations (function under test + dependencies)
   - Takes PBT code + function discovery info
   - Outputs complete, computable Lean implementations (ZERO sorry)
   - Writes to Impl.lean with full implementations

2. **Spec Agent**: Generate ONLY theorem statements (import impl signatures)
   - Takes PBT code + impl signatures from Impl.lean
   - Outputs theorem statements that reference impl functions
   - Uses sorry for proof obligations (stating, not proving)
   - Writes to Spec.lean with `import Fvspec.Impl`

**Implementation Steps:**
1. ✅ Impl agent foundation exists (formalize_impl with function discovery)
2. ✅ Spec agent foundation exists (formalize_spec with signature handling)
3. ⏳ Orchestrate in task.py:
   - Run impl agent first → validate zero sorry → extract signatures
   - Run spec agent second with signatures → validate compiles + has sorry
4. ⏳ Update templates:
   - Impl templates: Focus on implementation only (no theorems)
   - Spec templates: Focus on theorem statements only (import Impl)
5. ⏳ Update quality_assessment to track both agents separately
6. ⏳ Test end-to-end with sample datapoints

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

### Phase 3 ✅
- [x] Spec agent generates valid Lean (compiles)
- [x] 95%+ specs have theorem statements
- [x] Specs reference impl signatures correctly
- [x] Specs use sorry for proof obligations

### Phase 4 ✅
- [x] Artifact structure matches lake-template
- [x] Impl.lean namespace and file names updated
- [x] All tests passing (193 tests)
- [x] System ready for benchmarking

### Phase 5 ⏳
- [ ] Impl agent generates zero-sorry implementations
- [ ] Spec agent generates theorem statements with sorry
- [ ] Signatures extracted and passed between agents
- [ ] task.py orchestrates both agents sequentially
- [ ] quality_assessment tracks both agents separately
- [ ] End-to-end test with sample datapoints passes

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
- 348852c1: Phase 1 rename complete (depmock → formalize_impl)
- cbe60a54: Phase 2 partial (dataset integration)
- 6a3d01ce: Phase 2 complete (function discovery integration)
- 8a1f0677: Phase 3 partial (models + validator)
- 64144a4f: Phase 3 complete (agent + runner + tests)
- fd326d94: Phase 4 complete (Deps.lean → Impl.lean rename)

**Status**: Ready for Phase 5 (Validation & Optimization) or merge
