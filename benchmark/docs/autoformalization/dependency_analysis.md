# Understanding Dependencies vs Associated Functions vs Function Under Test

## Current Data Model (from database schema)

### 1. **Associated Functions** (`pbt_functions` table)
- **What it contains**: ALL functions called by the PBT code
- **How it's populated**: Static analysis / AST extraction during dataset creation
- **Includes**:
  - The function under test (e.g., `hashutil.md5_file_b64`)
  - Helper functions (e.g., `valid_keys()`)
  - Standard library calls (e.g., `base64.b64encode`, `hashlib.md5`)
  - Method calls (e.g., `.read()`, `.write()`, `.hex()`)

### 2. **Dependencies** (`deps` field + `dep_names` field)
- **What it SHOULD contain**: Custom helper functions that need to be defined
- **How it's populated**: Heuristic-based during dataset creation
- **Current issues**:
  - **Sparse**: Most samples have empty `deps` (e.g., samples 1, 2 have `deps=[]`)
  - **Name collisions**: Sometimes pulls wrong function (e.g., `open` in sample 5 pulls unrelated `open` method instead of builtin)
  - **Inconsistent**: Some real helpers missing, some stdlib functions incorrectly included

### 3. **Function Under Test** (NOT explicitly stored)
- **What it is**: The PRIMARY function being tested by the PBT
- **How to identify**: Currently we must INFER it from:
  - Test name (e.g., `test_md5_file_b64_*` → `md5_file_b64`)
  - Call patterns in PBT code
  - Which function is in associated_functions but NOT stdlib
  - Which function appears in the SAME REPO as the PBT

## Examples from Dataset

### Sample 1: `test_property`
```python
@given(x=strategies.floats(...))
def test_property(x):
    assert old.sine(x) ** 2 + old.cosine(x) ** 2 == pytest.approx(1)
```
- **Associated functions**: `['old.cosine', 'old.sine']`
- **deps**: `[]` (empty!)
- **Function under test**: BOTH `old.sine` AND `old.cosine` (testing mathematical identity)
- **Real dependencies**: NONE (both are the functions being tested)

### Sample 2: `test_hex_to_b64_id`
```python
@given(st.binary())
def test_hex_to_b64_id(data):
    hex_str = data.hex()
    assert hashutil.hex_to_b64_id(hex_str) == base64.b64encode(data).decode('ascii')
```
- **Associated functions**: `['base64.b64encode', 'data.hex', 'decode', 'hashutil.hex_to_b64_id', 'st.binary']`
- **deps**: `[]` (empty!)
- **Function under test**: `hashutil.hex_to_b64_id`
- **Real dependencies**: NONE (uses stdlib functions only)

### Sample 5: `test_md5_file_b64_three_files`
```python
@given(st.binary(), st.text(), st.binary())
def test_md5_file_b64_three_files(data1, text, data2):
    open('a.bin', 'wb').write(data1)
    # ...
    assert b64hash == path_hash
```
- **Associated functions**: `['base64.b64encode', 'decode', 'digest', 'hashlib.md5', 'hashutil.md5_file_b64', ...]`
- **deps**: `['open']` with code for WRONG `open` (name collision!)
- **Function under test**: `hashutil.md5_file_b64`
- **Real dependencies**: NONE (uses builtin `open`, not the one in deps!)

### Sample 10: `test_pickle_unpickle_cache_multiple_rounds`
```python
@hypothesis.given(key=valid_keys())
def test_pickle_unpickle_cache_multiple_rounds(self, key):
    zi_0 = self.klass(key)
    # ...
```
- **Associated functions**: `['hypothesis.given', 'pickle.dumps', 'pickle.loads', 'valid_keys']`
- **deps**: `['valid_keys']` with correct code!
- **Function under test**: `self.klass` (the class being tested)
- **Real dependencies**: `valid_keys()` - a hypothesis strategy factory

## The Key Distinction

### Function Under Test
- **Purpose**: The code we want to SPECIFY and VERIFY
- **In Lean**: We write `def myFunc (args) := sorry` or full implementation
- **Example**: `hashutil.md5_file_b64`, `old.sine`, `self.klass`

### Dependencies (for depmocking)
- **Purpose**: Helper functions that the function-under-test CALLS
- **In Lean**: We need these to write the spec, but DON'T want to fully verify them
- **Two types**:
  1. **Stdlib/External** (e.g., `base64.b64encode`, `open`, `hashlib.md5`)
     - Mock these as axioms or simple stubs
  2. **Custom helpers** (e.g., `valid_keys()`)
     - Need the actual code to translate

### Associated Functions (observational)
- **Purpose**: Metadata for understanding what the PBT calls
- **Contains**: Function under test + all dependencies + stdlib + methods
- **Use**: Analysis, not directly for spec generation

## Implications for fvspec

### Current Problem
The `deps` field is meant to store "custom helper functions that need translating", but:
1. It's incomplete (many samples have empty deps when they shouldn't)
2. It has name collisions (pulls wrong functions from codebase)
3. It doesn't distinguish between "helper for the function under test" vs "the test setup code"

### What We Actually Need

**For depmocking loop:**
- Dependencies that the FUNCTION UNDER TEST calls (not what the PBT calls!)
- Example: If we're testing `md5_file_b64`, we need its dependencies
- We DON'T need dependencies of the TEST SETUP CODE

**For main spec loop:**
- The function under test signature
- The property being tested (the assertion)
- The function under test's dependencies (from depmock)

### The Confusion
Right now we're conflating:
- "Functions called by the PBT" (associated_functions)
- "Functions needed to define the function under test" (TRUE dependencies)
- "Functions listed in deps field" (unreliable mix)

## Proposed Solution

1. **Identify function under test** from test name + repo analysis
2. **Get TRUE dependencies** by analyzing the function-under-test's code (not the PBT code!)
3. **Classify associated functions**:
   - Function under test: translate fully
   - Custom helpers: depmock
   - Stdlib: axiomize or skip
4. **Depmocking targets**: Only custom helpers that the function-under-test needs

