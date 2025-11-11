# Unit Test Autoformalization for fvspec

## Context

**Problem:** FVAPPS demonstrated that specs alone are vulnerable to "ignore-the-spirit-of-the-thing attacks" - trivial or constant implementations that satisfy formal specs but not the actual intent. fvspec upgrades the dataset by including *traditional unit tests* alongside property-based tests. These unit tests test the same functions as the PBTs but provide concrete examples. Now we need to translate these unit tests into Lean 4.

**FVAPPS comparison:** In FVAPPS (LeetCode problems), unit tests were straightforward enough that *string templating* sufficed for autoformalization. Example: `assert solution.twoSum([2,7,11,15], 9) == [0,1]` → `#guard twoSum [2,7,11,15] 9 = [0,1]`.

**Key insight:** The dataset contains **two types of tests**:
1. **Property-based tests (PBTs)** - Hypothesis/fast-check tests with generators (e.g., `@given(xs=st.lists(...))`)
2. **Unit tests** - Traditional tests with concrete values stored separately in the database

These tests are linked via **shared functions**: both the PBT and unit tests call the same function under test.

**Database schema:**
```
datapoints (PBTs)
  ├─ pbt_functions (junction) → functions (shared function definitions)
  └─ (linked via shared functions)
     └─ unit_test_functions (junction) → unit_tests (concrete test cases)
```

**Our task:** Extract assertions from the unit tests (not the PBTs!) and translate them to Lean LSpec.

**Lean 4 testing mechanism:** We'll use **LSpec**, a testing framework for Lean 4 (inspired by Haskell's Hspec):

```lean
import LSpec

#lspec
  test "solve example 1" (solve 4 ["0001", "1000", "0011", "0111"] = [1, 3]) $
  test "solve example 2" (solve 3 ["010", "101", "0"] = [-1])
```

**How it works:**
1. `test` takes a description and a proposition (must be `Testable`)
2. Tests compile but don't run until function is implemented
3. Better error messages than `#guard_msgs` (shows expected vs actual)
4. Can group tests conceptually with `group`

**Critical constraint:** Tests cause a *compile error* if:
1. The test fails (proposition doesn't hold)
2. The evaluation encounters a `sorry` placeholder (can't evaluate through sorry)

**Timeline clarification:**
- **During benchmark generation:** We generate specs with `sorry` + unit tests. Tests won't compile yet (no implementation).
- **During benchmark evaluation:** Language models attempt to implement the function. Unit tests validate their implementations.
- Unit tests are part of the TASK SPECIFICATION, not validation of benchmark generation.

## Dataset Structure

### What's in the Database

The `pbts_full.db` SQLite database contains:

**Tables:**
- `datapoints` - Property-based tests (54,345 PBTs)
- `unit_tests` - Traditional unit tests (6.3M tests)
- `functions` - Shared function definitions
- `pbt_functions` - Which functions does each PBT test?
- `unit_test_functions` - Which functions does each unit test test?

**Key relationships:**
- A PBT tests one or more functions (via `pbt_functions`)
- A unit test tests one or more functions (via `unit_test_functions`)
- **Overlapping tests:** PBTs and unit tests that share function names

**Example from samples.md:**

PBT ID 03133 (`test_etcd_get_serializable`) has **48 overlapping unit tests** including:
```python
def test_get_unknown_key(self, etcd):
    value, meta = etcd.get('probably-invalid-key')
    assert value is None
    assert meta is None
```

This unit test calls `etcd.get()`, which is also tested by the PBT. We can extract the concrete assertion `etcd.get('probably-invalid-key')` returns `(None, None)`.

### Querying Overlapping Unit Tests

The database query `get_overlapping_unit_tests(session, pbt_id)` returns:

```python
[
    {
        "shared_functions": ["func1", "func2"],
        "unit_tests": [
            {
                "code": "def test_foo():\n    assert func1(1) == 2",
                "name": "test_foo",
                "source_file": "tests/test_module.py",
                "start_line": 10,
                "end_line": 12,
            },
            ...
        ]
    }
]
```

**Our extraction task:**
1. Query overlapping unit tests for a given PBT
2. Parse each unit test's `code` field with AST analysis
3. Extract concrete assertions (e.g., `assert func1(1) == 2`)
4. Translate to LSpec format
5. Filter to only include tests for the target function (the one we're formalizing)

## Unit Test Patterns in the Dataset

From `samples.md`, we see real-world unit tests with diverse patterns:

### 1. Simple Assertions (Easiest to Translate)

**Python:**
```python
def test_get_unknown_key(self, etcd):
    value, meta = etcd.get('probably-invalid-key')
    assert value is None
    assert meta is None
```

**LSpec translation:**
```lean
test "get unknown key returns None"
  (etcd.get "probably-invalid-key" = (none, none))
```

### 2. Multiple Assertions per Test (Common)

**Python:**
```python
def test_replace_success(self, etcd):
    etcd.put('/doot/thing', 'toot')
    status = etcd.replace('/doot/thing', 'toot', 'doot')
    v, _ = etcd.get('/doot/thing')
    assert v == b'doot'
    assert status is True
```

**LSpec translation:**
```lean
-- Option 1: Multiple tests
test "replace updates value" (etcd.get "/doot/thing" = "doot") $
test "replace returns true" (etcd.replace "/doot/thing" "toot" "doot" = true)

-- Option 2: Compound assertion
test "replace updates value and returns true"
  (let status := etcd.replace "/doot/thing" "toot" "doot"
   let v := etcd.get "/doot/thing"
   status = true ∧ v = "doot")
```

### 3. Parametrized Tests

**Python:**
```python
@pytest.mark.parametrize("x,y,expected", [(1, 2, 3), (5, 10, 15)])
def test_add(x, y, expected):
    assert add(x, y) == expected
```

**LSpec translation:**
```lean
test "add 1 2" (add 1 2 = 3) $
test "add 5 10" (add 5 10 = 15)
```

### 4. Floating-Point Tests (Need External Validation)

**Python:**
```python
def test_curvatures_sphere(...):
    kmax, kmin = shape.point_principal_curvatures(scale=scale)
    assert torch.allclose(kmax, ones / radius, atol=1e-1, rtol=1e-1)
```

**LSpec translation:**
```lean
-- Use plain #eval with documented expected value
-- External validator checks tolerance during evaluation
-- Expected: kmax ≈ ones / radius (rtol=1e-1, atol=1e-1)
#eval shape.point_principal_curvatures scale
```

### 5. Complex Setup (Framework-Dependent)

**Python:**
```python
def test_nested_transactions(self, etcd):
    etcd.transaction(
        compare=[],
        success=[etcd.transactions.put('/doot/txn1', '1'),
                 etcd.transactions.txn(
                     compare=[],
                     success=[etcd.transactions.put('/doot/txn2', '2')],
                     failure=[])],
        failure=[]
    )
    value, _ = etcd.get('/doot/txn1')
    assert value == b'1'
    value, _ = etcd.get('/doot/txn2')
    assert value == b'2'
```

**Challenge:** Requires stateful execution (transaction, then get). May need to:
- Skip tests with complex setup
- Simplify to just the assertion part
- Mark as "needs runtime execution"

### 6. Framework-Specific Assertions

**Python:**
```python
with pytest.raises(ValueError):
    func(invalid_input)
```

**Translation:** Could map to Lean's exception handling, but complex. May skip for MVP.

## Difficulty Assessment

### Feasibility Spectrum

Based on the unit tests in `samples.md` (not the PBTs!):

**Easy (30-40% of unit tests):**
- Pure assertions with concrete values: `assert f(1, 2) == 3`
- Simple variable assignments: `x = f(1); assert x == 2`
- String/numeric comparisons: `assert value == b'doot'`
- Multiple assertions in sequence (can extract each)
- **Translation:** Direct AST analysis → LSpec
- **Tools:** Python `ast` module for parsing

**Medium (30-40% of unit tests):**
- Tests with setup code that can be traced: `etcd.put(...); assert etcd.get(...) == ...`
- Parametrized tests (pytest.mark.parametrize): Unroll to multiple LSpec tests
- Floating-point assertions: Use external validation with tolerance
- Tests calling the target function with dependencies
- **Translation:** AST analysis + constant propagation + external validation
- **Tools:** Python `ast`, numpy.isclose semantics for validation

**Hard (20-30% of unit tests):**
- Tests requiring complex state setup (database, network)
- Framework-specific testing utilities (unittest.TestCase methods)
- Tests with mocking/patching
- Tests that check side effects (file I/O)
- **Translation:** May need simplification or strategic omission

**Infeasible (5-10% of unit tests):**
- Async operations with schedulers
- Tests that check exceptions/error handling (pytest.raises)
- GPU/device-specific tests
- Tests that validate internal state (not return values)
- **Translation:** Skip or document as untestable in pure functional setting

## Key Challenges

### 1. Identifying the Target Function

**Problem:** A unit test may call multiple functions, but we only care about the one we're formalizing.

**Example:**
```python
def test_workflow(self):
    data = preprocess(input)      # dependency
    result = target_function(data) # ← target function
    assert result == expected
```

**Solution:**
- Extract the PBT's target function name from the datapoint
- Filter unit test assertions to only include calls to that function
- Or: Include dependency calls if we've autoformalized those dependencies

### 2. Handling Test Fixtures and Setup

**Problem:** Many unit tests use pytest fixtures or setUp methods:

```python
def test_something(self, etcd):  # etcd is a fixture
    result = etcd.get('key')
    assert result == expected
```

**Solution:**
- For MVP: Skip tests that require fixtures we can't instantiate
- Future: Model fixtures as Lean values (e.g., `let etcd := mockEtcd`)

### 3. The `sorry` Problem (Not Actually a Problem!)

**Initial confusion:** Thought we needed unit tests to compile during benchmark generation.

**Actual workflow:**
1. **Benchmark generation (our job):**
   - Generate spec with `sorry`
   - Generate unit tests from overlapping unit tests
   - Tests don't compile yet (expected!)
   - Package both as task specification

2. **Benchmark evaluation (model's job):**
   - Model sees spec with `sorry` + unit tests
   - Model implements the function (removes `sorry`)
   - Unit tests now compile and validate model's implementation

**Solution:** No stub generation needed! Unit tests are part of the challenge, not something we validate during generation.

**We only need to validate:**
- Unit tests are syntactically valid Lean
- Unit tests match the expected format (LSpec structure)
- Unit tests reference the correct function name
- NOT: whether tests pass (can't know without implementation)

### 4. Multiple Assertions per Test

Many unit tests have multiple assertions (e.g., 3-5 per test). Options:
- Generate multiple LSpec `test` statements (one per assertion)
- Combine into compound assertion with `∧`
- Pick "most representative" assertion

**Recommendation:** Generate multiple tests (one per assertion) for clear error messages.

### 5. Floating-Point Comparisons

Common pattern: `torch.testing.assert_close(actual, expected, rtol=1e-5, atol=1e-8)`

**Problem:** Implementing epsilon-closeness for floats in LSpec is too complex and brittle.

**Solution: Hybrid approach**

**For exact tests (integers, strings, lists of ints, bools):**
Use **LSpec** for compile-time validation:
```lean
import LSpec

#lspec
  test "double basic" (double_of_list [1, 2, 3] = [2, 4, 6]) $
  test "double empty" (double_of_list [] = [])
```

**For floating-point tests:**
Use plain `#eval` without LSpec, document expected value, validate externally:
```lean
-- Expected: ~1.41421356 (rtol=1e-5, atol=1e-8)
#eval sqrt_approx 2.0

-- Expected: ~3.14159 (rtol=1e-6, atol=1e-8)
#eval compute_pi 1000
```

**During benchmark evaluation:**
1. Run `lean --run spec.lean` and capture stdout
2. Parse output with Python test validator
3. Compare float results with appropriate tolerance (rtol/atol)
4. Report detailed pass/fail as score metrics

**Advantages:**
- Leverages **LSpec** where it works well (~30-40% of tests)
- Better error messages than `#guard_msgs` (shows expected vs actual)
- More idiomatic Lean testing framework
- Avoids complex Lean float comparison logic
- Flexible tolerance handling in Python for floats
- Still provides strong validation signal

**Test validator pseudocode:**
```python
def validate_float_test(actual: str, expected: float, rtol: float, atol: float) -> bool:
    actual_float = parse_lean_output(actual)
    return abs(actual_float - expected) <= atol + rtol * abs(expected)
```

## Recommended Approach

### Phase 1: MVP - Static Extraction from Unit Tests (Current Focus)

**Goal:** Extract unit tests from the database and translate simple assertions to LSpec

**Components:**
1. **Database query** - `get_overlapping_unit_tests(session, pbt_id)` ✅ (already implemented)
2. **AST extractor** - Parse unit test code, extract assertions ✅ (exists in `units/ast_extractor.py`)
3. **Function filtering** - Only keep assertions for the target function
4. **LSpec generator** - Generate Lean test code ✅ (exists in `units/lspec_generator.py`)
5. **Integration** - Wire up in `extract_datapoint_unit_tests()` ⚠️ (currently returns None)

**What to extract (easiest subset first):**
- Simple assertions: `assert f(x) == y`
- Multiple assertions: Generate multiple tests
- Parametrized tests: Unroll parameters
- Variable assignments: Track with symbol table

**What to skip for MVP:**
- Tests requiring fixtures
- Tests with complex setup
- Mocking/patching
- Async operations
- Framework-specific assertions

**Implementation checklist:**
- [x] Database schema with overlapping tests
- [x] Query function `get_overlapping_unit_tests()`
- [x] AST extractor with constant propagation
- [x] LSpec generator
- [ ] **Wire up extraction in `extract_datapoint_unit_tests()`** ← TODO
- [ ] Filter assertions by target function name
- [ ] Handle parametrized tests
- [ ] Test on sample datapoints

**Example workflow:**
```python
def extract_datapoint_unit_tests(dp: Datapoint) -> str | None:
    """Extract unit tests from overlapping unit tests in database."""
    with get_session(db_path) as session:
        overlaps = get_overlapping_unit_tests(session, dp.id)

    if not overlaps:
        return None

    # Determine target function from PBT
    target_func = infer_target_function(dp)

    all_tests = []
    for overlap in overlaps:
        for unit_test in overlap["unit_tests"]:
            # Extract tests from unit test code
            tests = extract_unit_tests(
                pbt_code=unit_test["code"],
                func_name=target_func
            )
            if tests:
                all_tests.extend(tests.exact_tests + tests.float_tests)

    if not all_tests:
        return None

    # Generate LSpec code
    return generate_test_suite(TestSuite(
        exact_tests=[t for t in all_tests if not t.is_float],
        float_tests=[t for t in all_tests if t.is_float],
        extraction_stats={"method": "db_unit_tests", "count": len(all_tests)}
    ))
```

### Phase 2: Validation Infrastructure

For extracted unit tests:

1. Syntax validation (parse with Lean)
2. Format validation (LSpec `TestSeq` structure for exact, documented `#eval` for float)
3. Reference validation (function names match specs)
4. LSpec test suite structure (proper `test` composition with `$`)
5. Generate test statistics (counts, exact vs float breakdown, coverage)

**No compilation needed during generation!** Tests will be compiled during evaluation.

### Phase 3: External Test Validator (For Float Tests)

For float tests during evaluation:

```python
class FloatTestValidator:
    def parse_lean_output(self, output: str) -> Any:
        """Parse Lean #eval output (floats, lists, tensors)"""
        # Handle various Lean output formats

    def validate_float_test(self, actual: str, expected: float,
                           rtol: float, atol: float) -> bool:
        """Validate float test with tolerance"""
        actual_val = self.parse_lean_output(actual)
        return abs(actual_val - expected) <= atol + rtol * abs(expected)

    def validate_test_file(self, spec_file: Path) -> TestResults:
        """Run Lean file, parse output, validate all tests"""
        # Run: lean --run spec_file
        # Parse stdout
        # Match outputs to expected values
        # Return detailed results
```

Integrates with `inspect_ai` scoring system.

### Phase 4: Coverage Expansion

Incrementally add support for:
1. Parametrized tests (pytest.mark.parametrize) - unroll to multiple LSpec tests
2. Tests with simple fixtures - model as Lean values where possible
3. Multiple assertions - generate multiple LSpec tests
4. Float tests - external validation
5. List membership tests (`x in xs` → `x ∈ xs`)

Target: 60-70% of overlapping unit tests extractable by end of MVP.

## Metrics to Track

**During benchmark generation (our metrics):**
1. **Unit test availability rate:** % of PBTs with overlapping unit tests (from DB)
2. **Test extraction rate:** % of available unit tests successfully extracted
3. **Test syntactic validity:** % of extracted tests that are syntactically valid Lean
4. **Test format correctness:** % using proper format (exact: LSpec, float: documented `#eval`)
5. **Tests per PBT:** Distribution of how many tests extracted per PBT
6. **Test type distribution:** Breakdown of exact vs float tests per sample

**During benchmark evaluation (model metrics):**
1. **Test compilability rate:** % of model solutions where Tests.lean compiles
2. **LSpec test passage rate:** % of LSpec tests that pass (with detailed error messages)
3. **Float test passage rate:** % of float tests that pass (runtime validation with tolerance)
4. **Overall test passage rate:** Combined score across LSpec and float tests
5. **Per-test results:** Detailed breakdown from LSpec output showing which tests passed/failed

**Important:** Samples without extractable unit tests remain in the benchmark. These metrics measure enhancement quality, not sample filtering.

## Current Implementation Status

**✅ Completed (Infrastructure Ready):**

1. **Database schema** with overlapping unit tests
   - `unit_tests` table with 6.3M tests
   - `pbt_functions` and `unit_test_functions` junction tables
   - `get_overlapping_unit_tests()` query function

2. **Core extraction module** (`src/generate/scaffold/units/`)
   - `ast_extractor.py`: AST-based static analysis ✅
     * Python `ast` module with constant propagation
     * Expression evaluation for concrete values
     * Loop unrolling for simple patterns
     * pytest.mark.parametrize support
     * Variable substitution and symbol table
     * Float detection (automatic)
   - `lspec_generator.py`: LSpec code generation ✅
     * Generates proper TestSeq structure
     * Separates exact tests from float tests
     * Clean, idiomatic Lean code
   - `float_validator.py`: External validation ✅
     * numpy.isclose semantics (rtol/atol)
     * Runs lean --run and parses output
     * Tolerance checking for evaluation
   - `models.py`: Pydantic data models (TestCase, TestSuite) ✅

3. **Pipeline integration points** (stubbed)
   - `dataset/__init__.py`: `extract_datapoint_unit_tests()` ⚠️ (returns None)
   - `tools/declaration.py`: Writes Tests.lean to disk ✅
   - `quality_assessment.py`: Metrics tracking ✅
   - `wandb_logger.py`: Wandb integration ✅

4. **Test coverage:** 136 tests, all passing ✅

**⚠️ TODO (Critical Path to MVP):**

1. **Implement `extract_datapoint_unit_tests()` function**
   - Query `get_overlapping_unit_tests(session, pbt_id)`
   - Determine target function name from PBT
   - Run AST extractor on each unit test's code
   - Filter to only assertions for target function
   - Generate LSpec code via `generate_test_suite()`

2. **Add target function inference**
   - Extract function name from PBT metadata or code
   - Handle cases where function name doesn't match test name

3. **Test on sample datapoints**
   - Run on datapoints from `samples.md` (e.g., ID 03133 with 48 unit tests)
   - Measure extraction success rate
   - Validate generated LSpec code

4. **Handle edge cases**
   - Multiple functions in one unit test
   - Tests with no extractable assertions
   - Parametrized tests
   - Tests with fixtures

## Expected Extraction Rate

Based on the unit tests in `samples.md`:

**Optimistic estimate: 60-70% of overlapping unit tests**
- ~30-40% with simple assertions (direct extraction)
- ~30-40% with moderate complexity (parametrize, multiple assertions, simple setup)
- ~20-30% too complex (fixtures, mocking, state)
- ~5-10% infeasible (async, exceptions, side effects)

**Realistic estimate for MVP: 30-40%**
- Focus on the easiest patterns first
- Skip complex cases for initial implementation
- Expand coverage in future phases

**Note:** Not all PBTs have overlapping unit tests. From database stats:
- 54,345 PBTs total
- 6.3M unit tests total
- 448K PBT-function associations
- Average ~116 unit tests per PBT (but highly variable)

Some PBTs may have 0 overlapping tests, others may have hundreds.

## Example Translations

### Simple (Ready Now)

**Database query result:**
```python
{
    "shared_functions": ["double_of_list"],
    "unit_tests": [
        {
            "code": """
def test_double_basic():
    assert double_of_list([1, 2, 3]) == [2, 4, 6]
def test_double_empty():
    assert double_of_list([]) == []
""",
            "name": "test_double_basic",
            ...
        }
    ]
}
```

**Generated LSpec:**
```lean
import LSpec

#lspec
  test "double basic" (double_of_list [1, 2, 3] = [2, 4, 6]) $
  test "double empty" (double_of_list [] = [])
```

**During benchmark generation:** These tests won't compile (expected - no implementation yet).

**During benchmark evaluation:** Models implement `double_of_list`, LSpec validates their implementation with clear error messages.

### With Parametrize (Medium)

**Unit test code:**
```python
@pytest.mark.parametrize("x,y,expected", [(1, 2, 3), (5, 10, 15)])
def test_add(x, y, expected):
    assert add(x, y) == expected
```

**Generated LSpec:**
```lean
import LSpec

#lspec
  test "add 1 2" (add 1 2 = 3) $
  test "add 5 10" (add 5 10 = 15)
```

### With Floating Point (Medium)

**Unit test code:**
```python
def test_sqrt():
    result = sqrt_approx(2.0)
    assert abs(result - 1.41421356) < 1e-5
```

**Generated LSpec:**
```lean
import LSpec

-- Exact tests would go here if any

-- Float tests (external validation)
-- Expected: ~1.41421356 (rtol=1e-5, atol=1e-8)
#eval sqrt_approx 2.0
```

**Key:** External validator parses Lean output and applies tolerance checking.

## Conclusion

**Status: Infrastructure complete, integration pending**

Unit test autoformalization is **ready to implement** with the following steps:

1. ✅ Database contains 6.3M unit tests with PBT associations
2. ✅ AST extraction code is complete and tested
3. ✅ LSpec generation works correctly
4. ⚠️ Need to wire up `extract_datapoint_unit_tests()` to query DB and run extraction
5. ⚠️ Need to test on real datapoints and measure success rate

**Critical distinction from original document:**
- Unit tests are **in the database**, not embedded in PBTs
- We extract from **overlapping unit tests**, not from PBT code
- PBTs and unit tests are **linked by shared functions**

**Estimated difficulty:** Medium
- Infrastructure is complete
- Main work is integration and filtering
- Expected 30-40% extraction rate for MVP (60-70% with future improvements)

**Next steps:**
1. Implement the database query + AST extraction pipeline
2. Test on sample PBTs with known overlapping unit tests
3. Measure extraction success rate
4. Iterate on function identification and filtering
5. Expand to handle more complex patterns

**Timeline:** ~1-2 weeks for MVP implementation and testing
