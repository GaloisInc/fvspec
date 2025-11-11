# Unit Test Extraction: TODO

## Current Status (2025-11-10)

**Extraction Rate:** 0% on 100-sample measurement

**Root Cause:** Database links unit tests via shallow function matching (shared utilities like `np.random.rand`), not semantic matching (testing the same function).

**Infrastructure Status:** ✅ Complete and working
- AST + tree-sitter extraction pipeline
- Performance optimizations (batched queries, session reuse)
- Measurement script with detailed metrics
- Database indexing script

See `EXTRACTION.agents.md` for detailed analysis.

## Immediate Next Steps

### Step 1: Implement Utility Function Filtering (1 day)

**Goal:** Filter out utility functions from shared function matching to reduce false positives.

**Tasks:**
- [ ] Create utility function blacklist in `dataset/queries.py`
  ```python
  UTILITY_PREFIXES = ['np.', 'st.', 'torch.', 'tf.', 'pytest.', 'unittest.', 'core.']
  UTILITY_MODULES = {'np', 'st', 'pytest', 'unittest', 'torch', 'tf', 'core', 'hypothesis'}
  ```
- [ ] Add `filter_utility_functions()` helper
- [ ] Modify `get_overlapping_unit_tests()` to filter shared functions
- [ ] Add flag to enable/disable filtering (for comparison)

**Expected result:** 10-30% extraction rate (speculative)

**Files to modify:**
- `src/generate/scaffold/dataset/queries.py`

### Step 2: Re-run Measurement (10 minutes)

```bash
uv run measure-unit-extraction --num-samples 100 --ranseed 0 --output results-filtered.json
```

**Compare with baseline:**
- Baseline: 0% extraction (96% false positives from utilities)
- Target: >10% extraction

**Decision point:**
- If ≥20%: Continue to Step 3 (assertion-based filtering)
- If 10-20%: Evaluate if worth continuing
- If <10%: Consider alternative approaches (runtime execution, synthetic tests)

### Step 3: Implement Assertion-Based Filtering (2-3 days)

**Goal:** Only link unit tests that actually assert on the target function.

**Tasks:**
- [ ] Add `get_asserted_functions()` to AST extractor
  - Extract function calls that appear in assert statements
  - These are the functions actually being validated
- [ ] Add `extract_tested_function()` helper
  - Infer which function a unit test is testing
  - Based on assertions, function name, docstring
- [ ] Modify linking logic to require assertion match
- [ ] Add fuzzy matching for name variations (tile/tiling/tiled)

**Expected result:** 20-40% extraction rate (speculative)

**Files to modify:**
- `src/generate/scaffold/units/ast_extractor.py`
- `src/generate/scaffold/dataset/queries.py` or new filtering module

### Step 4: Re-run Measurement & Evaluate (10 minutes)

```bash
uv run measure-unit-extraction --num-samples 100 --ranseed 0 --output results-assertions.json
```

**Decision point:**
- If ≥30%: Success! Integrate into benchmark pipeline
- If 20-30%: Consider adding Phase 3 (docstring/embedding)
- If <20%: Reevaluate approach

### Step 5: Integration into Benchmark Pipeline (1-2 days)

**Only if extraction rate ≥30%**

**Tasks:**
- [ ] Enable unit test extraction in `mk_dataset()` (currently stubbed)
- [ ] Wire Tests.lean execution into benchmark evaluation
- [ ] Add unit test QA metrics to `qa.json`:
  - `unit_tests_available`: Count of extracted tests
  - `unit_tests_compiled`: Count that compiled
  - `unit_tests_passed`: Count that passed
  - `unit_tests_failed`: Count that failed
- [ ] Add to wandb logging
- [ ] Update quality assessment to track unit test metrics
- [ ] Document in AGENTS.md

**Files to modify:**
- `src/generate/scaffold/dataset/__init__.py`
- `src/generate/scaffold/quality_assessment.py`
- `src/generate/scaffold/wandb_logger.py`
- `benchmark/AGENTS.md`

## Alternative Approaches (If Steps 1-4 Fail)

### Option A: Runtime Execution of PBTs (2-3 weeks)

**Idea:** Run Hypothesis on PBTs to capture generated test cases.

**Pros:**
- Guaranteed relevant examples
- Captures actual Hypothesis-generated inputs
- No false positives

**Cons:**
- Expensive: need to execute 54K PBTs
- Requires dependency installation for each repo
- May hit timeouts, crashes, or environment issues
- Needs sandboxing for safety

**Estimated effort:** 2-3 weeks

### Option B: Synthetic Unit Test Generation (1-2 weeks)

**Idea:** Use LLM to generate unit tests from PBT specification.

**Pros:**
- Guaranteed extractable (we control the format)
- Can target specific test patterns (simple assertions)
- Fast to generate

**Cons:**
- Lower trust (LLM-generated, not real-world)
- Need validation (run Hypothesis to check consistency)
- May introduce bias

**Estimated effort:** 1-2 weeks

### Option C: Focus on Other QA Metrics (0 days)

**Idea:** Accept that unit tests aren't feasible, focus on alternatives.

**Already implemented:**
- ✅ Structural faithfulness metrics (parameter/type/assertion coverage)
- ✅ Self-assessment scores (model confidence)
- ✅ Plausible property testing (counterexample finding)

**Pros:**
- No additional work needed
- These metrics already provide QA signal
- Can still publish benchmark without unit tests

**Cons:**
- Miss out on concrete validation examples
- Less comprehensive QA than FVAPPS

## Success Criteria

**Minimum viable (30% extraction rate):**
- Extract unit tests for 30% of PBTs
- Tests compile and provide validation signal
- Integrate into benchmark pipeline

**Stretch goal (50% extraction rate):**
- Extract for 50% of PBTs via hybrid approach
- High precision (few false positives)
- Becomes key differentiator vs FVAPPS

**Acceptable fallback (<30%):**
- Document findings (semantic linking is hard)
- Focus on other QA metrics (structural, plausible, self-assessment)
- Consider alternative approaches for future work

## Timeline Estimates

**Optimistic (if Step 1 works well):**
- Week 1: Steps 0-2 (utility filtering + measurement)
- Week 2: Steps 3-4 (assertion filtering + measurement)
- Week 3: Step 5 (integration)
- **Total: 3 weeks to production**

**Realistic (if need iteration):**
- Week 1: Steps 0-2
- Week 2-3: Steps 3-4 + debugging
- Week 4: Step 5 or pivot to alternatives
- **Total: 4-5 weeks**

**Pessimistic (if semantic linking is too hard):**
- Week 1-2: Attempt Steps 0-4
- Week 3-4: Realize extraction rate still <20%
- Week 5+: Pivot to Option A (runtime execution) or Option C (other metrics)
- **Total: 5+ weeks**

## Dependencies

- Database indexes (Step 0) - blocking for performance
- Utility filtering results (Step 2) - blocking for Step 3 decision
- Assertion filtering results (Step 4) - blocking for Step 5 decision

## Open Questions

1. **What extraction rate is acceptable for production?**
   - Minimum: 30%? 40%?
   - Depends on quality vs coverage tradeoff

2. **Should we materialize filtered links in database?**
   - Pro: Faster queries, one-time cost
   - Con: More complex, need migration

3. **How to handle multiple target functions per PBT?**
   - Some PBTs test multiple functions
   - Current approach: infer single target from name
   - May need to extract all functions tested in PBT

4. **Should we add unit test linking to scraper?**
   - Fix at data collection time vs post-hoc filtering
   - More work but better long-term solution

## Notes

- Keep extraction infrastructure even if low success rate - it's reusable for future datasets
- Document findings in paper - semantic test linking is a research contribution
- The 0% result is valuable negative result - not all PBT datasets have extractable unit tests
