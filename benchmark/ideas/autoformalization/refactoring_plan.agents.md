# Phase 3: Smart Function Discovery - Integration Plan

**Status**: ✅ Core Complete (92% coverage) → ⏳ Integration Pending
**Branch**: `q/analyze-deps-2` | **PR**: #61
**Implementation**: Commits 2a663ce8, 40beb832, b7447a2d

## What's Built

**Module**: `src/generate/scaffold/function_discovery.py` (520 lines)
- `discover_function_code(pbt, session)` - Main discovery with 4-strategy cascade
- Tree-sitter parsing: test classes, function calls, stdlib filtering
- Scope-aware database lookups: `lookup_function_exact()`, `lookup_function_fuzzy()`
- **Result**: 92% coverage (72% call analysis, 16% associated functions, 4% name matching)

**Models**: `FunctionInfo(name, code, type, confidence, discovery_method, dependencies)`

**Testing**: 18 pytest tests, all passing (CI-compatible)

**Dashboard**: Function Analysis tab in data explorer (commit b7447a2d)

## Key Learnings

1. **Call analysis dominates** - 72% vs predicted 25% (most successful strategy)
2. **Source field unusable** - Contains file paths, not code (discovered during implementation)
3. **Test classes rare** - Only 4% vs predicted 30% (most tests aren't class-based)
4. **Associated functions valuable** - 16% from pbt_functions table

## Next Steps: Integration (Phase 2)

### 1. Integrate with Depmock Runner ⏳ HIGH PRIORITY

**File**: `src/generate/scaffold/depmock/runner.py`

**Changes needed**:
```python
# In prepare_deps_context() or similar:
from generate.scaffold.function_discovery import discover_function_code

function_info = discover_function_code(pbt, session)
if function_info and function_info.code:
    # Include function code in prompt context
    # Track discovery_method and confidence in metrics
```

**Benefits**:
- Provide actual function-under-test code to model (not just PBT)
- Fix confusion between "function under test" vs "dependency" (issue #59)
- Higher quality specifications with concrete implementation reference

### 2. Update Prompts ⏳

**Files**: `src/generate/templates/deps/*.jinja2`

**Add section**:
```jinja2
{% if function_code %}
## Function Under Test

Confidence: {{ discovery_confidence }}
Method: {{ discovery_method }}

```lean
-- Implementation discovered from test analysis
{{ function_code }}
```
{% endif %}
```

### 3. Track Metrics ⏳

**File**: `src/generate/scaffold/quality_assessment.py`

**Add to metrics**:
```python
{
    "function_discovered": bool,
    "discovery_method": str,  # DiscoveryMethod enum value
    "discovery_confidence": float,
    "function_lines": int | None,
}
```

**Analysis questions**:
- Does higher confidence correlate with better spec quality?
- Does including function code improve structural faithfulness?
- Which discovery method produces best results?

### 4. Dependency Analysis (Future) 🔮

**New function**:
```python
def get_true_dependencies(function_code: str, repo_id: int, session: Session) -> list[str]:
    """
    Parse discovered function's dependencies using tree-sitter.
    Filter stdlib, return only custom functions needing mocking.
    """
```

**Integration**:
- Parse function_code AST for function calls
- Filter out stdlib (reuse `is_stdlib()`)
- Lookup each dependency in Functions table
- Replace/augment current `deps` field with actual dependencies

## Implementation Order

1. **Start simple** - Just add function code to prompt context (no metrics)
2. **Validate impact** - Run 10-20 samples, manually review specs
3. **Add metrics** - Track discovery_method, confidence, impact on quality
4. **Iterate** - Use metrics to refine strategy weights, confidence thresholds
5. **Dependency analysis** - Only after validating function code helps

## Success Criteria (Phase 2)

- [ ] Depmock runner uses `discover_function_code()`
- [ ] Prompts include discovered function when confidence >0.7
- [ ] Metrics tracked in artifacts/qa.json
- [ ] A/B test: with vs without function code (same samples)
- [ ] Structural faithfulness improvement measured

## Files Modified (Future Work)

```
src/generate/scaffold/depmock/runner.py      # Use discovery
src/generate/templates/deps/*.jinja2         # Add function section
src/generate/scaffold/quality_assessment.py  # Track metrics
```

## References

- Issue #59: Understand function under test vs dependency
- `dependency_analysis.md`: Original problem analysis
- PR #61: https://github.com/GaloisInc/fvspec/pull/61
