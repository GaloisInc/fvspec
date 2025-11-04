# Reality Check: Can We Find Function Under Test Code?

## Investigation Results

Tested on 50 random samples with improved name matching:
- **Found in Functions table: ~12%**
- **Found in associated_functions: ~10%**

This is a **major limitation** of the proposed approach.

## Why Is Coverage So Low?

### 1. Many PBTs Test Classes, Not Functions
```python
def test_pickle_unpickle_cache_multiple_rounds(self, key):
    zi_0 = self.klass(key)  # Testing a CLASS CONSTRUCTOR
    # ...
```
- The "function under test" is `self.klass.__init__`
- This is a method, not captured as a standalone function

### 2. Many PBTs Test Operators/Properties
```python  
def test_property(x):
    assert old.sine(x) ** 2 + old.cosine(x) ** 2 == pytest.approx(1)
```
- Testing a MATHEMATICAL IDENTITY, not a specific function
- Both `sine` and `cosine` are equally "under test"

### 3. Many PBTs Test Integration/Workflows
```python
def test_atomic_iter_with_concurrent_steps():
    # Tests interaction between multiple components
```
- No single "function under test"
- Testing system behavior

### 4. Test Names Don't Always Match Function Names
```python
# Test name: test_avg_pool3d
# Actual function: meta_adaptive_avg_pool3d
```
- Naming conventions vary
- Abbreviations, prefixes, suffixes

## What DOES Work

The ~12% where we CAN find the function code includes:
- Simple utility functions (e.g., `md5_file_b64`)
- Helper functions with clear naming
- Functions in well-structured codebases

## Implications for the Refactoring Plan

### Original Plan Assumption (WRONG)
"We can identify the function under test and get its code from the Functions table for most samples"

### Reality
"We can only get function code for ~12% of samples"

### What This Means

**Option 1: Accept Limited Coverage**
- Implement the approach for the 12% where it works
- Fall back to current approach for others
- Mark samples as "has_function_code: bool"

**Option 2: Expand Function Extraction**
- Add class methods to Functions table
- Add property getters/setters
- Add lambda functions
- **Problem**: This is dataset preprocessing, not runtime

**Option 3: Runtime Code Extraction**
- At benchmark runtime, try to extract function code from source
- Parse the original source files
- **Problem**: Source files not always available, complex parsing

**Option 4: Hybrid Approach**
- Use Functions table when available (12%)
- For others, use PBT code + deps field (current approach)
- Focus depmocking improvements on the 12% with clear targets

## Recommended Path Forward

### Phase 1: Improve What We Have (Current System)
1. Fix the `deps` field name collision issue
2. Add stdlib detection to filter out `open`, `hashlib.md5`, etc.
3. Improve depmocking prompt to clarify "helper for the function being tested"

### Phase 2: Add Function Code When Available
1. Add optional `function_under_test_code` field
2. Populate it when Functions table has a match (~12%)
3. Use enhanced prompts for these cases
4. Track metrics: "has_function_code: true/false"

### Phase 3: Dataset Enhancement (Long-term)
1. Improve dataset scraping to capture more code
2. Add class methods, properties to Functions table
3. Add better function-test associations at dataset level
4. This is a data preprocessing issue, not a benchmark issue

## Revised Architecture

### For samples WITH function code (~12%)
```
1. Identify function under test (name matching)
2. Get code from Functions table
3. Analyze ITS dependencies (not PBT dependencies)
4. Build dependency DAG
5. Autoformalize dependencies
6. Generate spec with full context
```

### For samples WITHOUT function code (~88%)
```
1. Use PBT code as primary source
2. Filter deps field to remove stdlib
3. Autoformalize custom helpers from deps
4. Generate spec from PBT assertion
5. Include "function signature inferred from test"
```

## Key Takeaway

**The Functions table is a supplementary resource, not the primary source.**

We should:
- Use it opportunistically when available
- Not depend on it for the core flow
- Focus on improving the PBT-based analysis
- Track availability as a quality metric

The original refactoring plan was **too optimistic** about function code availability. A more pragmatic hybrid approach is needed.
