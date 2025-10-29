# Unit Test Autoformalization for fvspec

## Context

**Problem:** FVAPPS demonstrated that specs alone are vulnerable to "ignore-the-spirit-of-the-thing attacks" - trivial or constant implementations that satisfy formal specs but not the actual intent. fvspec upgrades the dataset with *embedded unit tests* within property-based tests. Now we need to translate these into Lean 4.

**FVAPPS comparison:** In FVAPPS (LeetCode problems), unit tests were straightforward enough that *string templating* sufficed for autoformalization. Example: `assert solution.twoSum([2,7,11,15], 9) == [0,1]` → `#guard twoSum [2,7,11,15] 9 = [0,1]`.

**This dataset is different:** Real-world GitHub property-based tests include:
- Complex reference implementations (NumPy array operations)
- Mocking and side effects (`patch`, `MagicMock`)
- Async operations with schedulers
- Library-specific assertions (`torch.testing.assert_close`)
- Embedded test logic beyond simple equality

String templating will work for only ~30% of the dataset. The rest requires more sophisticated translation or strategic omission.

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

## Dataset Analysis

### Sample Overview

Analyzed 15+ datapoints from `benchmark/data/scrapedtests.json` (60,776 total PBTs).

**Sampling methodology:** Used random sampling (seed=42) to avoid selection bias. Indices: `41905,7296,1639,48598,18024,16049,14628,9144,48265,6717,44348,48540,58469,35741,5697`. Also examined patterns across TypeScript/JavaScript tests using content-based filtering.

**Languages:**
- Python (NumPy/PyTorch/Polars/Hypothesis)
- TypeScript/JavaScript (fast-check)

**Unit test patterns found:**

1. **Simple assertions** (easiest to translate)
```python
# Python
assert calc * calc % prime == square
assert result.shape == df.shape
```
```typescript
// TypeScript
assert.equal(actual, max)
assert.isTrue(Maybes.isJust(item))
```

2. **Reference implementations** (medium difficulty)
```python
def ref_sum(X, lengths):
    Y = X.reshape(lengths.size, d)
    rv = np.zeros((lengths.size, 1)).astype(np.float32)
    for ii in range(lengths.size):
        rv[ii] = np.sum(Y[ii, :lengths[ii]])
    return [rv.reshape((2, 3, 4, 5)[:4 - num_reduce_dim])]
```

3. **Multiple assertions per test** (common)
```typescript
assert.isFalse(Strings.isEmpty(str));
assert.isTrue(Strings.isNotEmpty(str));
```

4. **Mocking/side effects** (challenging)
```python
with patch('action_completer.validator.extract_context') as mocked:
    mocked.return_value = (group, parent_name, action, fragments)
    validator.validate(Document(text='', cursor_position=cursor_position))
    mocked_validate_action.assert_called_with(...)
```

5. **Async operations** (TypeScript-specific)
```typescript
fc.asyncProperty(..., async (packages, s) => {
    const fetch = s.scheduleFunction(...)
    dependencyTree(selectedPackage, fetch)
    while (s.count() !== 0) { await s.waitOne() }
})
```

6. **Specialized libraries** (domain-specific)
- `torch.testing.assert_close(dequantized_data, ref_fp32)`
- `assert_series_equal(s, result)` (Polars)
- `self.assertDeviceChecks(dc, op, [X, Y], [0])` (Caffe2)

## Difficulty Assessment

### Feasibility Spectrum

**Easy (40-50% of dataset):**
- Pure functions with concrete values (literals or traceable through AST)
- Variables assigned to constants
- Simple expressions and method calls on concrete objects
- Example: `X = [1,2,3]; assert double(X) == [2,4,6]`
- **Translation:** AST analysis + constant propagation → direct extraction
- **Tools:** Python `ast` module, `treesitter_python` for complex cases

**Medium (35-45% of dataset):**
- Tests with Hypothesis-generated values or random/external data
- Requires RUNNING the PBT to capture concrete examples
- Example: `@given(xs=st.lists(st.integers())) def test(xs): assert f(xs) == g(xs)`
- **Floating-point comparisons** (very common!) - use LSpec with external validation
- **Translation strategy:**
  - Run PBT with Hypothesis (capture 3-5 successful examples)
  - Extract concrete input/output pairs
  - Generate Lean tests from captured examples
  - Leverage dependency mocking for NumPy/torch operations
- **Assumption:** Can execute PBTs to generate concrete test cases

**Hard (15% of dataset):**
- Device-specific operations (GPU/CPU checks) - environment-dependent
- Framework-specific testing utilities that check internal state
- Statistical properties that require significant computation
- **Translation:** May need simplification or external validation

**Infeasible (5% of dataset):**
- Mocking/patching (fundamentally imperative side effects)
- Async operations with schedulers
- Tests that check side effects (file I/O, network, timers)
- **Translation:** Skip or document as untestable in pure functional setting

## Key Challenges

### 1. The `sorry` Problem (Not Actually a Problem!)

**Initial confusion:** Thought we needed unit tests to compile during benchmark generation.

**Actual workflow:**
1. **Benchmark generation (our job):**
   - Generate spec with `sorry`
   - Generate unit tests
   - Tests don't compile yet (expected!)
   - Package both as task specification

2. **Benchmark evaluation (model's job):**
   - Model sees spec with `sorry` + unit tests
   - Model implements the function (removes `sorry`)
   - Unit tests now compile and validate model's implementation

**Solution:** No stub generation needed! Unit tests are part of the challenge, not something we validate during generation.

**We only need to validate:**
- Unit tests are syntactically valid Lean
- Unit tests match the expected format
- Unit tests reference the correct function name
- NOT: whether tests pass (can't know without implementation)

### 2. Reference Implementation Translation

Many PBTs include reference implementations (e.g., NumPy operations). With dependency autoformalization:
- NumPy operations → autoformalized Lean dependencies
- Library-specific operations → available via mocked deps
- Semantic equivalence maintained through dependency translation

**Example:**
```python
def ref_sum(X, lengths):
    Y = X.reshape(lengths.size, d)
    rv = np.zeros((lengths.size, 1)).astype(np.float32)
    for ii in range(lengths.size):
        rv[ii] = np.sum(Y[ii, :lengths[ii]])
    return [rv.reshape((2, 3, 4, 5)[:4 - num_reduce_dim])]
```

**With dependency mocking:** Array operations (reshape, slicing, sum) are available as autoformalized dependencies. The reference implementation becomes a Lean function using those deps.

This is less of a blocker than initially estimated.

### 3. Multiple Assertions

Many tests have multiple assertions (e.g., 3-5 per test). Options:
- Generate multiple `#guard` statements
- Combine into tuple comparison
- Pick "most representative" assertion

### 4. Floating-Point Comparisons

Common pattern: `torch.testing.assert_close(actual, expected, rtol=1e-5, atol=1e-8)`

This is **extremely common** in real-world tests. Need a standard approach.

**Problem:** Implementing epsilon-closeness for floats in `#guard_msgs` is too complex and brittle.

**Solution: Hybrid approach with LSpec**

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
-- Expected: ~1.41421356 (within 1e-5)
#eval sqrt_approx 2.0

-- Expected: ~3.14159 (within 1e-6)
#eval compute_pi 1000
```

**During benchmark evaluation:**
1. Run `lean --run spec.lean` and capture stdout
2. Parse output with Python test validator
3. Compare float results with appropriate tolerance (rtol/atol)
4. Report detailed pass/fail as score metrics

**Advantages:**
- Leverages **LSpec** where it works well (~40-50% of tests)
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

### 5. Library-Specific Assertions

Examples:
- `assert_series_equal` (Polars)
- `self.assertDeviceChecks` (Caffe2)
- `assert_frame_equal` (Pandas)

These encode complex structural equality. Translation requires:
- Understanding library semantics
- Lean equivalent or simplification

## String Templating Feasibility

**Where FVAPPS-style string templating works:**

```python
# Pattern: Simple assertion with concrete values
assert function(input) == output
assert_equal(result, expected)
assert result == expected
```

**Static analysis rules (with `ast` + `treesitter_python`):**

With proper AST analysis and constant propagation, we can extract much more:

**✅ Extractable with AST analysis:**

1. **Variables with constant values:**
   ```python
   X = [1, 2, 3]
   result = double(X)
   assert result == [2, 4, 6]
   # → Extract: double([1, 2, 3]) == [2, 4, 6]
   ```

2. **Method calls on concrete objects:**
   ```python
   s = Series([1, 2, 3])
   assert s.n_chunks() == 1
   # → Extract: Series([1, 2, 3]).n_chunks() == 1
   ```

3. **Simple computed expressions:**
   ```python
   x = 5
   y = 10
   assert add(x, y) == 15
   # → Extract: add(5, 10) == 15
   ```

4. **Unrollable loops with concrete bounds:**
   ```python
   for i in [0, 1, 2]:
       assert f(i) == i * 2
   # → Extract 3 tests: f(0)==0, f(1)==2, f(2)==4
   ```

**AST Analysis Strategy:**
```python
import ast

class TestExtractor(ast.NodeVisitor):
    def __init__(self):
        self.symbol_table = {}  # Track variable assignments
        self.tests = []

    def visit_Assign(self, node):
        # Track: X = [1, 2, 3]
        if isinstance(node.value, ast.Constant):
            self.symbol_table[node.targets[0].id] = node.value

    def visit_Assert(self, node):
        # Extract assertion, substitute known values
        test = self.extract_with_substitution(node.test)
        self.tests.append(test)
```

**❌ Still need runtime execution for:**

1. **Hypothesis-generated values:**
   ```python
   @given(xs=st.lists(st.integers()))  # No concrete xs in code
   def test(xs):
       assert sort(xs) == sorted(xs)
   ```

2. **External/random data:**
   ```python
   X = torch.randn(10, 10)  # Random, can't extract statically
   assert check(X)
   ```

3. **Framework method calls:**
   ```python
   self.assertDeviceChecks(dc, op, [X], [0])  # Framework-specific
   ```

4. **Complex dependencies:**
   ```python
   X_base = torch.tensor(X).to('cpu')  # X from @given decorator
   ```

**Revised estimate with AST analysis:** 40-50% statically extractable
- Simple literals: 10-15%
- AST-traceable variables/expressions: 25-35%
- Need runtime execution: 35-45%
- Infeasible: 5-15%

**Feasibility by pattern:**

| Pattern | Extractable? | LSpec Output |
|---------|--------------|--------------|
| `assert f(x) == y` | ✅ Yes | `test "desc" (f x = y)` |
| `assert_equal(a, b)` | ✅ Yes | `test "desc" (a = b)` |
| `assert a in b` | ⚠️ Maybe | `test "desc" (a ∈ b)` if membership defined |
| `torch.testing.assert_close(...)` | ✅ Yes | Use plain `#eval`, validate externally |
| `with patch(...) as mock:` | ❌ No | Requires mocking |
| `assert_frame_equal(...)` | ❌ No | Complex library type |
| Reference function in test body | ❌ No | Requires translation |

**Estimated extractable subset: ~80-90% of dataset**
- 40-50% statically extractable (AST analysis + constant propagation)
- 35-45% extractable by RUNNING PBTs to capture examples
- 5-15% infeasible (mocking, async, side effects)

For the remaining 20%, need:
- AST-based translation for complex cases
- External validation harness
- Or strategic omission (5% truly infeasible)

### Translation Strategy: Type Decidability

LSpec requires that propositions have a `Testable` instance (usually via `Decidable`):

**What works with LSpec:**
- Decidable equality: `x = y` where `DecidableEq α`
- Numeric comparisons: `x < y`, `x ≤ y` with decidable instances
- Boolean expressions: `p ∧ q`, `p ∨ q`, `¬p`
- List operations: `xs.length = n`, `x ∈ xs`
- Custom types with `deriving DecidableEq`

**Example Testable instances:**
```lean
-- Built-in for decidable equality
instance (x y : α) [DecidableEq α] [Repr α] : Testable (x = y) := ...

-- Custom instances can provide better error messages
instance : Testable (myProp x y) := ...
```

**Implication for extraction:**
```python
# Python assertion
assert f([1, 2, 3]) == [2, 4, 6]  # ✅ Translatable
```

```lean
-- Lean LSpec test
test "f basic" (f [1, 2, 3] = [2, 4, 6])
```

**With dependency autoformalization:**
- NumPy arrays → Lean array types (via deps)
- `np.array_equal` → Lean equality (via deps)
- Dependencies provide `DecidableEq` instances
- LSpec tests work seamlessly

## Recommended Approach

### Short-term (MVP)

1. **Opportunistic unit test generation**
   - **Key principle:** Unit tests are optional enhancements, not requirements
   - If extractable: Generate unit tests
   - If not extractable: Keep sample in benchmark without unit tests
   - Don't filter out samples that lack unit tests

2. **Focus on easy subset (40-50%)**
   - Pure functions with simple assertions
   - Direct translation to **LSpec tests**
   - Skip complex library dependencies for now

2. **Generated task specification with LSpec**
   ```lean
   import LSpec

   -- Generated spec (from PBT property) - with sorry
   -- Model must implement this
   def double_of_list (xs : List Int) : List Int := sorry

   -- Generated unit tests (from unit test extraction)
   -- These validate the model's implementation
   -- ONLY generated if unit tests were extractable
   def tests : TestSeq :=
     test "double basic" (double_of_list [1, 2, 3] = [2, 4, 6]) $
     test "double empty" (double_of_list [] = []) $
     test "double negatives" (double_of_list [-1, 0, 1] = [-2, 0, 2])

   #lspec tests
   ```

   **No stub needed!** Tests run against whatever the model implements.

3. **Hybrid example with floats:**
   ```lean
   import LSpec

   def sqrt_approx (x : Float) : Float := sorry

   -- Exact integer tests (LSpec)
   def exactTests : TestSeq :=
     test "sqrt of 4" (sqrt_approx_int 4 = 2) $
     test "sqrt of 9" (sqrt_approx_int 9 = 3)

   #lspec exactTests

   -- Float tests (runtime validated externally)
   -- Expected: ~1.41421356 (rtol=1e-5, atol=1e-8)
   #eval sqrt_approx 2.0

   -- Expected: ~2.0 (rtol=1e-5, atol=1e-8)
   #eval sqrt_approx 4.0
   ```

4. **Extraction strategies (in order of preference)**

   **Strategy 1: AST-based static extraction (40-50% of tests)**

   Use Python's `ast` module for constant propagation and symbolic execution:

   ```python
   import ast

   class TestExtractor(ast.NodeVisitor):
       def __init__(self):
           self.symbol_table = {}  # Variable → value mapping
           self.tests = []

       def visit_Assign(self, node):
           # Track: X = [1, 2, 3]
           if self.is_concrete_value(node.value):
               var_name = self.get_target_name(node.targets[0])
               self.symbol_table[var_name] = self.eval_node(node.value)

       def visit_Assert(self, node):
           # Extract: assert f(X) == Y
           # Substitute known values from symbol_table
           test = self.extract_with_substitution(node.test)
           if test.has_all_concrete_values():
               self.tests.append(test)
   ```

   **Handles:**
   - Variable assignments: `X = [1, 2, 3]; assert f(X) == [2, 4, 6]`
   - Simple expressions: `assert f(2 + 3) == 10`
   - Method calls: `s = Series([1,2]); assert s.sum() == 3`
   - Loop unrolling: `for i in range(3): assert f(i) == i*2`

   **Strategy 2: Run-and-capture (35-45% of tests)**

   For Hypothesis-generated values:
   ```python
   @given(st.lists(st.integers()))
   def test_sort_idempotent(xs):
       result = sort(xs)
       assert sort(result) == result
   ```

   Approach:
   1. Run PBT with Hypothesis in "example capture" mode
   2. Intercept 3-5 successful test executions
   3. Log concrete inputs and outputs: `xs=[3,1,2] → result=[1,2,3]`
   4. Generate Lean tests from captured examples

   ```lean
   import LSpec

   #lspec
     test "sort captured example 1" (sort [3, 1, 2] = [1, 2, 3]) $
     test "sort captured example 2" (sort [] = []) $
     test "sort captured example 3" (sort [5] = [5])
   ```

   **Strategy 3: Skip (5-15% of tests)**
   - Mocking, async, I/O, side effects
   - Keep sample without unit tests

   **Key insight:** AST analysis handles ~40-50% statically. Runtime execution handles another ~35-45%.

### Medium-term (Full dataset)

1. **Tiered translation system**
   - Easy: Direct translation
   - Medium: Stub + hint generation
   - Hard: Human-in-loop or skip

2. **Reference implementation handling**
   - Attempt automatic translation for simple cases
   - Generate `sorry`'d reference function for complex cases
   - Include original Python as comment

3. **Library support**
   - Build Lean library of common test helpers
   - `approx_equal : Float → Float → Float → Bool` (rtol/atol)
   - List/Array structural equality helpers

### Long-term (Research)

1. **Interactive test generation**
   - Use LSP feedback to iteratively refine tests
   - Start with simple tests, add complexity
   - Validate against Lean compiler

2. **Dual-representation strategy**
   - Generate both Lean tests AND external test harness
   - Lean tests: Simple structural checks
   - External: Full semantic validation (Python subprocess)

3. **Metrics for test quality**
   - Coverage of assertions translated
   - Percentage of compilable tests
   - Semantic preservation score

## Example Translations

### Simple (Ready now)

**Python:**
```python
@given(n=st.lists(st.integers(min_value=-2**126, max_value=2**126)))
def test_double_of_list(n: List[int]):
    assert my_library.double_of_list(n) == [i * 2 for i in n]
```

**Lean (with LSpec):**
```lean
import LSpec

-- Spec (with sorry)
def double_of_list (xs : List Int) : List Int := sorry

-- Unit tests (concrete examples extracted from or inspired by PBT)
def tests : TestSeq :=
  test "double basic" (double_of_list [1, 2, 3] = [2, 4, 6]) $
  test "double empty" (double_of_list [] = []) $
  test "double negatives" (double_of_list [-1, 0, 1] = [-2, 0, 2])

#lspec tests
```

**During benchmark generation:** These tests won't compile (expected - no implementation yet).

**During benchmark evaluation:** Models implement `double_of_list`, LSpec validates their implementation with clear error messages.

### Medium (Needs work)

**Python:**
```python
def test_square_root_mod_prime(square, prime):
    calc = square_root_mod_prime(square, prime)
    assert calc * calc % prime == square
```

**Lean:**
```lean
-- Spec
def square_root_mod_prime (square : Nat) (prime : Nat) : Nat := sorry

-- Property (can't easily test with sorry)
-- theorem sqrt_mod_prime_correct (square prime : Nat) (h : Nat.Prime prime) :
--   let calc := square_root_mod_prime square prime
--   calc * calc % prime = square % prime := sorry

-- Unit tests would need a computable implementation
-- Even with concrete examples, can't evaluate through sorry:
-- /--
-- info: 2
-- -/
-- #guard_msgs in
-- #eval square_root_mod_prime 4 7  -- Would fail: can't evaluate sorry
```

**During evaluation:** Models must implement `square_root_mod_prime` to make tests compilable. Tests then validate correctness.

### Medium (With dependency support)

**Python:**
```python
@given(...)
def test_quantize_and_dequantize_op(nrows: int, ncols: int):
    input_data = torch.rand(nrows, ncols).float()
    quantized = torch.ops.fbgemm.FloatToBfloat16Quantized(input_data)
    dequantized = torch.ops.fbgemm.Bfloat16QuantizedToFloat(quantized)
    torch.testing.assert_close(dequantized, ref_fp32)
```

**Lean (with mocked dependencies):**
```lean
-- Dependencies autoformalized: torch tensors, quantization ops
import Fvspec.Deps  -- Contains FloatToBfloat16Quantized, Bfloat16QuantizedToFloat

def quantize_dequantize (input : Tensor Float) : Tensor Float :=
  let quantized := FloatToBfloat16Quantized input
  Bfloat16QuantizedToFloat quantized

-- Float tensor test (runtime validated externally)
-- Expected: [[0.999, 2.001], [2.998, 4.002]] (rtol=1e-3, atol=1e-3)
#eval quantize_dequantize (Tensor.fromList [[1.0, 2.0], [3.0, 4.0]])
```

**Key:** External validator parses Lean output and applies tolerance checking.

**Assumption:** `Fvspec.Deps` contains autoformalized torch operations. Feasible with dependency system.

## Impact on Benchmark

### Metrics to Track

**During benchmark generation (our metrics):**
1. **Test extractability rate:** % of samples with extractable unit tests (target: 80-90%)
2. **Test syntactic validity:** % of extracted tests that are syntactically valid Lean (target: 99%)
3. **Test format correctness:** % that use proper format (exact: LSpec, float: documented `#eval`) (target: 99%)
4. **Test type distribution:** Breakdown of exact vs float tests per sample

**During benchmark evaluation (model metrics):**
1. **Test compilability rate:** % of model solutions where spec file compiles (indicates implementation exists)
2. **LSpec test passage rate:** % of LSpec tests that pass (with detailed error messages)
3. **Float test passage rate:** % of float tests that pass (runtime validation with tolerance)
4. **Overall test passage rate:** Combined score across LSpec and float tests
5. **Per-test results:** Detailed breakdown from LSpec output showing which tests passed/failed

**Important:** Samples without unit tests remain in the benchmark. These metrics measure enhancement quality, not sample filtering.

### Quality Assessment Enhancement

Current structural metrics:
- Parameter coverage
- Type correspondence
- Strategy coverage
- Dependency coverage

**New unit test metrics (per sample):**

*Generation time (our work):*
- Has unit tests: Bool (whether any tests were extractable)
- Unit test count: Int (# of `#guard_msgs` statements generated, 0 if none)
- Unit tests syntactically valid: Bool

*Evaluation time (model's work):*
- Unit test compilation success: Bool (did model provide implementation?)
- Unit test passage: Bool (is model's implementation correct?)
- Per-test results: List of pass/fail for each `#guard_msgs`

**Scoring approach:**
- Samples without unit tests: Scored only on existing metrics (structural faithfulness, etc.)
- Samples with unit tests: **Models get bonus score if tests compile and pass**
- Unit tests provide objective validation signal for model solutions

This provides more objective quality signal than self-reported "faithfulness" scores.

## Open Questions

1. **Should tests be part of the benchmark scoring?**
   - **Decision:** Yes, as a bonus score (not required)
   - Samples without tests: Scored on existing metrics
   - Samples with tests: Bonus points if tests compile/pass
   - Encourages models to leverage unit test information when available

2. **How to handle the sorry problem?**
   - **Not a problem!** Tests validate model implementations during evaluation, not during generation

3. **Should we generate tests for dependencies too?**
   - Dependencies also have unit tests in PBTs
   - Could validate dependency autoformalization

4. **What's the minimum viable test suite?**
   - 1-3 tests per function?
   - Focus on "smoke tests" vs comprehensive coverage?

5. **How to balance test coverage vs compilation success?**
   - More tests = more validation
   - But more tests = more failure points

## Implementation Plan

### Phase 1: String Template Extractor (Week 1)

**Goal:** Extract unit tests from the templatable 30%

**Components:**
1. **Pattern matcher** (regex or AST-based)
   ```python
   import ast
   import re

   def extract_simple_assertions(pbt_code: str) -> List[UnitTest]:
       """Extract assertions matching: assert f(x) == y"""
       tree = ast.parse(pbt_code)
       tests = []
       for node in ast.walk(tree):
           if isinstance(node, ast.Assert):
               if is_simple_equality(node.test):
                   tests.append(parse_assertion(node))
       return tests
   ```

2. **Complexity classifier**
   - Check for truly blocking patterns: `patch`, `mock`, `async`, `await`, I/O operations
   - NumPy/torch/pandas: NOT blocking (dependencies will be autoformalized)
   - If blocking pattern found: Mark as infeasible
   - Else: Attempt template extraction

3. **Lean code generator (LSpec-based hybrid)**
   ```python
   def generate_lean_test(func_name: str, inputs: List[str], output: str,
                          is_float: bool = False, rtol: float = 1e-5, atol: float = 1e-8,
                          test_name: str = "") -> str:
       """Generate Lean unit test - LSpec for exact, #eval for float"""
       inputs_str = " ".join(inputs)

       if is_float:
           # For floating-point: plain #eval with documented expected value
           return f"""-- Expected: ~{output} (rtol={rtol}, atol={atol})
#eval {func_name} {inputs_str}
"""
       else:
           # For exact: use LSpec test
           return f"""test "{test_name}" ({func_name} {inputs_str} = {output})"""

   def generate_test_suite(tests: List[TestCase]) -> str:
       """Generate complete LSpec test suite"""
       exact_tests = [t for t in tests if not t.is_float]
       float_tests = [t for t in tests if t.is_float]

       suite = "import LSpec\n\n"

       if exact_tests:
           suite += "def tests : TestSeq :=\n"
           for i, test in enumerate(exact_tests):
               suite += f"  {generate_lean_test(**test)}"
               suite += " $\n" if i < len(exact_tests) - 1 else "\n"
           suite += "\n#lspec tests\n\n"

       if float_tests:
           suite += "-- Float tests (external validation)\n"
           for test in float_tests:
               suite += generate_lean_test(**test) + "\n"

       return suite
   ```

   **Detection logic:**
   ```python
   def is_float_test(output_type: type) -> bool:
       """Determine if test needs tolerance checking"""
       return output_type in [float, np.ndarray, torch.Tensor] and has_float_dtype(output_type)
   ```

4. **Validation (during benchmark generation)**
   - Parse generated Lean with `lean --version` (syntax check only)
   - Verify LSpec test format
   - Check function names match spec
   - Ensure tests use proper `TestSeq` structure
   - **Don't try to compile/run tests** (no implementation exists yet!)

**Metrics to track:**
- Extraction attempt rate (% of samples with assertion patterns)
- Template success rate (% that generate syntactically valid Lean)
- Format correctness rate (% with proper LSpec structure)
- **Samples remain in dataset even if 0% extraction rate** - unit tests are optional

### Phase 2: Validation Infrastructure (Week 2-3)

For extracted unit tests:

1. Syntax validation (parse with Lean)
2. Format validation (LSpec `TestSeq` structure for exact, documented `#eval` for float)
3. Reference validation (function names match specs)
4. LSpec test suite structure (proper `test` composition with `$`)
5. Generate test statistics (counts, exact vs float breakdown, coverage)

**No compilation needed during generation!** Tests will be compiled during evaluation.

### Phase 3: External Test Validator (Week 3)

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

### Phase 4: Test Helper Library (Optional)

If needed for helper functions (not for epsilon comparisons):

```lean
-- Fvspec/TestHelpers.lean
namespace Fvspec.TestHelpers

-- Helper functions for test data generation, formatting, etc.
-- NOT for epsilon comparisons (handled externally)

end Fvspec.TestHelpers
```

### Phase 5: Coverage Expansion (Week 4+)

Incrementally add support for:
1. List membership tests (`∈`)
2. Reference function translation (leverage dependency autoformalization)
3. Complex assertions (breaking down into multiple tests)
4. Multi-dimensional float outputs (tensors, matrices) with external validation

Target: 80% coverage by end of month (leveraging dependency system + hybrid test approach)

## Conclusion

**Difficulty: Medium (with dependency support)**

Unit test autoformalization is achievable for ~80% of dataset with dependency autoformalization support:
- 30% trivial (string templating)
- 50% medium (leverage mocked dependencies for NumPy/torch/etc)

The remaining 20% requires:
- Strategic choices about stub generation vs comment-out
- Library development (test helpers, numeric libraries)
- Possibly external validation harness for complex cases

**Recommendation:** Start with MVP (easy subset with LSpec) to validate the approach, then leverage dependency autoformalization to expand to 80-90% coverage.

**LSpec is the right choice:** More idiomatic than `#guard_msgs`, better error messages, proper testing framework. Combined with external validation for floats, provides comprehensive test coverage.

**Next steps (MVP):**
1. **Build AST-based static extractor** - handles 40-50% of tests without execution
   - Python `ast` module for parsing
   - Constant propagation and symbol table
   - Expression evaluation for concrete values
   - Loop unrolling for simple patterns
2. **Integrate LSpec** for exact tests (better than `#guard_msgs`)
3. Prototype unit test extraction for 10 examples:
   - All with AST extraction (variables, expressions, method calls)
   - Mix of exact and float tests
4. Build float test validator (parses Lean output, applies tolerance)
5. Measure extraction rate across full dataset (AST only)
6. Implement evaluation-time scoring with LSpec + external validation
7. Integrate with `inspect_ai` scoring system

**Future work (post-MVP):**
- **PBT executor** - runtime execution to capture Hypothesis-generated examples
  - Would handle additional 35-45% of tests
  - Requires setting up Python execution environment
  - Intercept Hypothesis test runs to log concrete examples
  - Trade-off: Complexity vs coverage (40-50% AST extraction may be sufficient for MVP)

**Critical takeaways:**
1. **Unit tests validate MODEL implementations, not benchmark generation** - tests run during evaluation, not generation
2. **AST analysis is powerful** - handles 40-50% of tests statically (variables, expressions, method calls)
3. **Use Python `ast` + `treesitter_python`** - enables sophisticated static extraction with constant propagation
4. **Runtime execution for the rest** - captures Hypothesis-generated examples for 35-45% of tests
5. **Double down on LSpec** - proper testing framework, idiomatic, better error messages than `#guard_msgs`
6. **External validation for floats** - pragmatic hybrid approach avoids complex Lean float logic
7. **LSpec advantages:** Test composition with `$`, `group` for organization, integrates with SlimCheck
8. **Unit tests are optional** - Samples without extractable tests stay in the benchmark
9. **Target: 80-90% of samples have unit tests** - but 100% of samples remain in benchmark
10. **We don't need stubs** - models provide implementations during evaluation
11. **Build AST extractor first, then runtime executor** - maximizes static extraction before expensive execution
