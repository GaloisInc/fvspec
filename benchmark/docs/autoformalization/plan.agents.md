# TODOs

## ✅ RESOLVED: it looks like specs are getting added to `Impl.lean`

**Status**: Fixed with defense-in-depth approach

**Root causes**:
1. Impl agent hallucinations (~50% rate generating specs when asked for impls)
2. Conditional orchestration writes leaving validation artifacts
3. Naive string concatenation causing "already defined" errors

**Solutions implemented**:
1. **Orchestration cleanup** (commit 78f40df): Unconditional workspace file writes
2. **Post-hoc filtering** (commit 6554cb2): Strip Fvspec.Spec namespaces from impl output
3. **Intelligent merging** (commit feb8f86): Replace string concatenation with structured module merger

**Documentation**:
- Evidence analysis: `HALLUCINATION.md`
- Filtering guide: `FILTERING_IMPLEMENTATION.md`
- Merging guide: `LEAN_MERGER.md`

**Test coverage**: 41 new tests added (22 filtering + 19 merging)
**Impact**: 0% spec pollution, 0% "already defined" errors in artifacts 
