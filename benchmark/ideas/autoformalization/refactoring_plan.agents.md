# Phase 3: Smart Runtime Function Discovery with tree-sitter

**Status**: ✅ Implementation Complete (integration pending)
**Goal**: Achieve 90%+ function code coverage using runtime tree-sitter parsing
**Approach**: No database changes needed - be smarter at runtime!
**Result**: 92% coverage achieved on 50-sample validation

## Core Insight

Instead of changing the external `pbts_full.db` database, use **tree-sitter at runtime** to intelligently parse Python code and extract what we need. tree-sitter is already a dependency!

## Architecture

### 1. New Module: `src/generate/scaffold/function_discovery.py` ✅

**Implementation Status:** Complete (commit 2a663ce8)

Use tree-sitter to parse and extract:

**From PBT code:** ✅
- Test class structure (what class is being tested?)
- Method calls in the test (what's actually being invoked?)
- Filter test infrastructure (assertions, Hypothesis, mocks)

**From source field:** ⚠️ NOT IMPLEMENTED
- Source field contains file paths, not actual code (discovered during implementation)
- Cannot parse source field as originally planned
- Workaround: Use database lookup with scope awareness

**From Functions table (as fallback):** ✅
- Exact/fuzzy matching with confidence scoring
- Scope-aware matching (prioritize same repo_id)

### 2. Strategy Cascade ✅

**Implementation Status:** Complete with 4 strategies

```python
def discover_function_code(pbt: Datapoint, session: Session) -> FunctionInfo | None:
    # Strategy 1: Parse test class inheritance (confidence: 0.8, coverage: 4%)
    if test_class := parse_test_class(pbt.code):
        if target_class := infer_target_from_test_class(test_class):
            return lookup_function_exact(session, target_class, pbt.repo_id)

    # Strategy 2: Parse test method calls (confidence: 0.7-0.75, coverage: 72%)
    if calls := extract_test_calls(pbt.code):
        if main_call := identify_primary_call(calls):
            if not is_stdlib(main_call):
                simple_name = main_call.split(".")[-1]
                return lookup_function_exact(session, simple_name, pbt.repo_id)

    # Strategy 3: Use test name (confidence: 0.5-0.6, coverage: 4%)
    if match := re.match(r"test_(\w+)", pbt.name):
        func_name = match.group(1)
        return lookup_function_exact(session, func_name, pbt.repo_id) \
            or lookup_function_fuzzy(session, func_name, pbt.repo_id)

    # Strategy 4: Associated functions (confidence: 0.4, coverage: 16%)
    if associated := get_associated_function_names(session, pbt.id):
        for func_name in associated[:3]:
            if func := lookup_function_exact(session, func_name, pbt.repo_id):
                return func

    return None  # Failed to discover (8% of samples)
```

**Actual Results on 50-sample validation:**
- Call analysis: 72% (primary strategy)
- Associated functions: 16% (from pbt_functions table)
- Name matching: 4%
- Test class: ~0% (most tests aren't class-based)
- Failed: 8%

### 3. Tree-sitter Parsing Examples ✅

**Implemented utilities:**
- `parse_python(code: str) -> Node | None` - Parse Python code to AST
- `get_node_text(node: Node, code: bytes) -> str` - Extract text from node
- `find_nodes_by_type(root: Node, node_type: str) -> list[Node]` - Find all matching nodes

**Parse test class to find target:** ✅
```python
# Implemented: parse_test_class(pbt_code: str) -> tuple[str, str | None] | None
# Parse: class TestMyClass(unittest.TestCase)
# Extract: ("TestMyClass", "unittest.TestCase")
# Then: infer_target_from_test_class() → "MyClass"
```

**Parse method calls in test:** ✅
```python
# Implemented: extract_test_calls(pbt_code: str) -> list[tuple[str, str]]
# Parse: self.klass(key)
# Extract: ("self.klass", "method")

# Parse: hashutil.md5_file_b64('a.bin')
# Extract: ("hashutil.md5_file_b64", "method")

# Then: identify_primary_call() filters test infrastructure and returns most common
```

**Parse source field:** ❌ NOT IMPLEMENTED
```python
# DISCOVERY: source field is just a file path, not code content
# Cannot parse as originally planned
```

### 4. Fix Existing Bugs ✅

**Stdlib filtering:** ✅ FIXED
```python
# Implemented in function_discovery.py
STDLIB_MODULES = {
    'base64', 'hashlib', 'os', 'sys', 'json', 'pickle', 'datetime', 're',
    'collections', 'pytest', 'hypothesis', 'numpy', 'pandas', 'torch',
    'tensorflow', 'scipy', 'sklearn', 'requests', ...  # 60+ modules
}

BUILTINS = set(dir(builtins))  # Fixed: was using dir(__builtins__)

def is_stdlib(func_name: str) -> bool:
    simple_name = func_name.split(".")[-1]
    if simple_name in BUILTINS:
        return True
    module = func_name.split(".")[0]
    return module in STDLIB_MODULES
```

**Bug Fixed:** `open()` now correctly detected as builtin (was using `dir(__builtins__)` which fails when `__builtins__` is a module instead of dict)

**Scope-aware matching:** ✅ IMPLEMENTED
```python
# Implemented in queries.py: lookup_function_exact()
# When looking for 'open':
# 1. First try: Same-repo function (repo_id match)
# 2. Fallback: Any repo (if no same-repo match)
# 3. Filter: is_stdlib() prevents builtin 'open' from being considered
```

### 5. Enhanced Dependencies Analysis ⏳

**Status:** Planned but NOT YET IMPLEMENTED

**Would analyze function-under-test's dependencies (not PBT's):**
```python
def get_true_dependencies(function_code: str, repo_id: int) -> list[str]:
    """
    Parse function_code with tree-sitter
    Extract all function calls
    Filter out stdlib
    Return custom functions that need mocking
    """
```

**Current workaround:** FunctionInfo includes empty `dependencies: []` field for future use

### 6. Integration Points ⏳

**Status:** NOT YET IMPLEMENTED - Next phase

**Update depmock runner:** TODO
- Use `function_discovery.discover_function_code()`
- Get true dependencies from discovered function
- Fall back to current approach if discovery fails

**Update prompts:** TODO
- When function code found: include it in prompt
- When not found: use PBT-based inference (current)
- Always indicate confidence level

**Track metrics:** TODO
- `function_discovered: bool`
- `discovery_method: DiscoveryMethod` enum
- `discovery_confidence: float`

### 7. Testing Strategy

**Phase 1: Validate on gold standard** ✅ DONE
- Tested on 50 random samples
- Measured coverage by strategy
- 92% overall coverage achieved

**Phase 2: Dashboard integration** ✅ DONE
- Added "Function Analysis" tab to data_explorer (commit b7447a2d)
- Shows AST-based function call analysis
- Displays heuristic scoring for main function identification
- Compares database metadata vs actual code usage

**Phase 3: Gradual rollout** ⏳ PENDING
- Start with high-confidence discoveries (>0.8)
- Expand to medium confidence (>0.5)
- Monitor quality metrics

**Testing Infrastructure:** ✅ COMPLETE
- 18 pytest tests in `test_function_discovery.py`
- All tests passing, CI-compatible (no database required)
- Test coverage: parsing, inference, stdlib detection, call identification

## Coverage Results

**Before:** 12% (Functions table exact match only)
**After:** 92% (50-sample validation)
**Achievement:** ✅ Exceeded 90% target

**Breakdown by strategy (actual results):**
- **+72%**: Call analysis in test body (primary strategy)
- **+16%**: Associated functions from pbt_functions table
- **+4%**: Name matching (exact/fuzzy)
- **+0%**: Test class inheritance (most tests aren't class-based)
- **-8%**: Failed to discover

**Key learnings:**
- Source field parsing NOT viable (contains file paths, not code)
- Call analysis is the workhorse (72% coverage with high confidence)
- Test class strategy underperformed expectations (4% vs predicted 30%)
- Associated functions table more useful than anticipated (16%)

## Implementation Steps - ACTUAL TIMELINE

### Completed ✅

1. **Add tree-sitter parsing utilities** ✅ DONE (commit 2a663ce8)
   - Parse test classes, extract inheritance
   - Parse function calls, classify types
   - ~~Parse source field~~ (discovered: not viable)

2. **Implement discovery cascade** ✅ DONE (commit 2a663ce8)
   - Test class → target class mapping
   - Call analysis → primary function
   - Name matching with confidence
   - Added: Associated functions fallback

3. **Fix existing bugs** ✅ DONE (commit 2a663ce8)
   - Stdlib filtering (fixed `open()` builtin detection)
   - Scope-aware function lookup (prioritize same repo_id)
   - Name collision resolution

4. **Testing & validation** ✅ DONE
   - 18 pytest tests (commit 2a663ce8)
   - 50-sample validation (92% coverage)
   - Dashboard integration (commit b7447a2d)

5. **Code compliance fix** ✅ DONE (commit 40beb832)
   - Changed dataclass to Pydantic BaseModel
   - Now complies with benchmark/CLAUDE.md style guide

### Pending ⏳

6. **Integrate with depmock** TODO
   - Update runner to use `discover_function_code()`
   - Update prompts with discovered code
   - Add confidence tracking metrics
   - Track discovery_method in artifacts

7. **Dependency analysis** TODO
   - Implement `get_true_dependencies()` using tree-sitter
   - Parse discovered function code for its dependencies
   - Filter deps field using actual function dependencies

## Why This Works

- ✅ No database changes needed
- ✅ tree-sitter already a dependency
- ✅ Runtime solution (flexible, iterative)
- ✅ Handles classes, methods, functions
- ✅ Can improve incrementally
- ✅ Fixes existing bugs simultaneously

## Success Criteria

### Phase 1: Core Implementation ✅ COMPLETE

- [x] Parse 95%+ of PBT code without errors (tree-sitter handles all Python)
- [x] Discover function code for 90%+ of samples (achieved 92%)
- [x] Fix all name collision bugs (stdlib filtering, scope-aware matching)
- [x] Dashboard shows discovery results (Function Analysis tab)
- [x] Comprehensive test suite (18 tests, all passing)
- [x] Code style compliance (Pydantic BaseModel)

### Phase 2: Integration ⏳ PENDING

- [ ] Precision >90% on gold standard (need manual annotation)
- [ ] Depmock uses discovered function code
- [ ] Prompts include discovered function with confidence level
- [ ] Metrics tracking (discovery_method, confidence)
- [ ] Depmock filters deps using actual function dependencies

## Related Documents & Artifacts

- `dependency_analysis.md` - Original problem analysis (issue #59)
- Git commit history:
  - `b7447a2d` - Function interdependency analysis dashboard
  - `d3230226` - Type check fix for data-explorer
  - `2a663ce8` - Main implementation: smart function discovery with tree-sitter
  - `40beb832` - Code compliance fix: Pydantic BaseModel
- PR #61: https://github.com/GaloisInc/fvspec/pull/61
- Branch: `q/analyze-deps-2`

## Implementation Files

**Core functionality:**
- `src/generate/scaffold/function_discovery.py` - Main discovery logic (520 lines)
- `src/generate/scaffold/dataset/queries.py` - Database query utilities
- `src/tests/test_function_discovery.py` - Test suite (18 tests)

**Dashboard:**
- `src/generate/scaffold/dataset/dashboard.py` - Interactive data explorer with Function Analysis tab

**Data models:**
- `FunctionInfo` - Pydantic model with name, code, type, confidence, discovery_method, dependencies
- `DiscoveryMethod` - Enum: TEST_CLASS, CALL_ANALYSIS, NAME_MATCH, FUNCTIONS_TABLE, FAILED
