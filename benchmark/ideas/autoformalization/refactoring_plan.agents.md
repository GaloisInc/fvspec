# Phase 3: Smart Runtime Function Discovery with tree-sitter

**Status**: Approved and in progress
**Goal**: Achieve 90%+ function code coverage using runtime tree-sitter parsing
**Approach**: No database changes needed - be smarter at runtime!

## Core Insight

Instead of changing the external `pbts_full.db` database, use **tree-sitter at runtime** to intelligently parse Python code and extract what we need. tree-sitter is already a dependency!

## Architecture

### 1. New Module: `src/generate/scaffold/function_discovery.py`

Use tree-sitter to parse and extract:

**From PBT code:**
- Test class structure (what class is being tested?)
- Method calls in the test (what's actually being invoked?)
- Fixtures/setUp to understand test context

**From source field (when available):**
- Class definitions and their methods
- Function definitions
- Docstrings with type hints

**From Functions table (as fallback):**
- Exact/fuzzy matching with better confidence scoring

### 2. Strategy Cascade

```python
def discover_function_code(pbt: Datapoint) -> FunctionInfo:
    # Strategy 1: Parse test class inheritance
    if test_class := parse_test_class(pbt.code):
        if target_class := infer_target_from_test_class(test_class):
            return extract_from_source(target_class, pbt.source)

    # Strategy 2: Parse test method calls
    if calls := extract_test_calls(pbt.code):
        if main_call := identify_primary_call(calls):
            return lookup_in_functions_table(main_call, pbt.repo_id)

    # Strategy 3: Use test name
    if func_name := extract_from_test_name(pbt.name):
        return fuzzy_match_with_treesitter(func_name, pbt.source)

    return None  # Failed to discover
```

### 3. Tree-sitter Parsing Examples

**Parse test class to find target:**
```python
import tree_sitter_python as tspython
from tree_sitter import Language, Parser

# Parse: class TestMyClass(unittest.TestCase)
# Extract: MyClass (strip "Test" prefix)
```

**Parse method calls in test:**
```python
# Parse: self.klass(key)
# Extract: self.klass (constructor call)
# Type: method/constructor

# Parse: hashutil.md5_file_b64('a.bin')
# Extract: hashutil.md5_file_b64
# Type: function call
```

**Parse source field to extract definitions:**
```python
# When pbt.source exists, parse it for:
# - class MyClass: ...
# - def my_function(...): ...
# - Extract full implementation
```

### 4. Fix Existing Bugs (Same Module)

**Stdlib filtering:**
```python
STDLIB_MODULES = {
    'base64', 'hashlib', 'os', 'sys', 'json',
    'pickle', 'datetime', 're', 'collections', ...
}

def is_stdlib(func_name: str) -> bool:
    module = func_name.split('.')[0]
    return module in STDLIB_MODULES or is_builtin(func_name)
```

**Scope-aware matching:**
```python
# When looking for 'open', prefer:
# 1. Local function in same file
# 2. Same-repo function (Functions table with repo_id)
# 3. Skip builtin 'open' entirely
```

### 5. Enhanced Dependencies Analysis

**Analyze function-under-test's dependencies (not PBT's):**
```python
def get_true_dependencies(function_code: str, repo_id: int) -> list[str]:
    """
    Parse function_code with tree-sitter
    Extract all function calls
    Filter out stdlib
    Return custom functions that need mocking
    """
```

### 6. Integration Points

**Update depmock runner:**
- Use `function_discovery.discover_function_code()`
- Get true dependencies from discovered function
- Fall back to current approach if discovery fails

**Update prompts:**
- When function code found: include it in prompt
- When not found: use PBT-based inference (current)
- Always indicate confidence level

**Track metrics:**
- `function_discovered: bool`
- `discovery_method: "test_class" | "call_analysis" | "name_match" | "failed"`
- `discovery_confidence: float`

### 7. Testing Strategy

**Phase 1: Validate on gold standard**
- Manually annotate 20-30 diverse samples
- Test each discovery strategy
- Measure precision/recall

**Phase 2: Dashboard integration**
- Add "Function Discovery" tab to data_explorer
- Show tree-sitter parse results
- Visualize discovery confidence

**Phase 3: Gradual rollout**
- Start with high-confidence discoveries (>0.8)
- Expand to medium confidence (>0.5)
- Monitor quality metrics

## Expected Coverage Gains

Current: 12% (Functions table exact match)
Target: 90%+ via:
- **+30%**: Test class inheritance parsing (classes)
- **+25%**: Call analysis in test body (methods)
- **+20%**: Source field parsing (when available)
- **+13%**: Better name matching with tree-sitter

## Implementation Steps

1. **Add tree-sitter parsing utilities** (~2 days)
   - Parse test classes, extract inheritance
   - Parse function calls, classify types
   - Parse source field, extract definitions

2. **Implement discovery cascade** (~2 days)
   - Test class → target class mapping
   - Call analysis → primary function
   - Name matching with confidence

3. **Fix existing bugs** (~1 day)
   - Stdlib filtering
   - Scope-aware function lookup
   - Name collision resolution

4. **Integrate with depmock** (~2 days)
   - Update runner to use discovery
   - Update prompts with discovered code
   - Add confidence tracking

5. **Testing & validation** (~2 days)
   - Gold standard evaluation
   - Dashboard integration
   - Metrics tracking

**Total: ~9 days of focused work**

## Why This Works

- ✅ No database changes needed
- ✅ tree-sitter already a dependency
- ✅ Runtime solution (flexible, iterative)
- ✅ Handles classes, methods, functions
- ✅ Can improve incrementally
- ✅ Fixes existing bugs simultaneously

## Success Criteria

- [ ] Parse 95%+ of PBT code without errors
- [ ] Discover function code for 90%+ of samples
- [ ] Precision >90% on gold standard
- [ ] Fix all name collision bugs
- [ ] Dashboard shows discovery results
- [ ] Depmock uses discovered dependencies

## Related Documents

- `dependency_analysis.md` - Original problem analysis
- `function_code_availability.md` - Reality check on 12% coverage
- This document supersedes the original database-focused refactoring plan
