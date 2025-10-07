# Ideas for Improving Metrics and Quality Assessment

This document tracks ideas for measuring translation quality in the fvspec benchmark.

## Current State

### Subjective Metrics (LLM Self-Assessment)

The model provides:

- **faithfulness_subjective**: How well the Lean spec captures the Python test (0-10)
- **interest_subjective**: How complex/interesting the specification is (0-10)

**Problems**: "Vibey", unreliable, no ground truth validation.

### Structural Faithfulness Metrics (Implemented)

Objective, programmatic analysis without LLM inference:

1. **parameter_coverage**: Fraction of Python parameters found in Lean
2. **type_correspondence**: Correctness of Python→Lean type mappings
3. **strategy_coverage**: Hypothesis bounds/constraints found in Lean
4. **assertion_coverage**: Ratio of Lean properties to Python assertions
5. **dependency_coverage**: Dependency names found in Lean code
6. **overall**: Weighted average of above (25% params, 25% types, 20% strategy, 20% assertions, 10% deps)

**Status**: ✅ Implemented in `quality_assessment.py`, tested in `test_metrics.py`

---

## Future Ideas

### 1. Correctness & Soundness

#### Vacuity Detection ⭐

**Goal**: Catch specifications that are trivially true or don't actually constrain behavior.

**Approach: Tactic Testing** (most promising)

- Try replacing `by sorry` with simple tactics: `rfl`, `trivial`, `simp`, `decide`
- If any succeed, the theorem might be vacuous
- Score based on which tactics work (rfl = most vacuous, decide = least)

**Example**:

```lean
theorem foo (x : Int) (h : 0 ≤ x ∧ x ≤ 100) : x = x := by sorry
-- Proves with 'rfl' → Very vacuous! Lost the actual property.
```

**Advantages**:

- Uses Lean's own judgment
- No implementation needed, just tests theorem statements
- Catches non-syntactic vacuity

**Implementation sketch**:

```python
@dataclass
class VacuityMetrics:
    proves_with_rfl: bool
    proves_with_trivial: bool
    proves_with_simp: bool
    proves_with_decide: bool
    vacuity_score: float  # 1.0 = very vacuous, 0.0 = requires work
```

**Questions**:

- Which tactics to test? (current idea: rfl, trivial, simp, decide)
- How to weight them in scoring?
- How to handle theorems with multiple sorries?
- Timeout settings?

**Alternative approaches**:

- **Syntactic analysis**: Check if hypotheses appear in conclusions (naive, misses implicit usage)
- **Contradiction detection**: Try to prove `False` from hypotheses (catches over-constrained specs)
- **Hypothesis usage tracking**: Parse proof to see which assumptions are used

#### Type Safety Beyond Compilation

- Count type errors from Lean LSP
- Track refinement iterations needed
- Measure use of unsafe casts

---

### 2. Completeness (Catching Missing Properties)

#### Assertion Coverage Gap Analysis

- Track which specific Python assertions have no corresponding Lean property
- Semantic matching, not just counting
- Identify "orphaned" assertions lost in translation

#### Hypothesis Strategy Completeness

- Beyond bounds: lists with size constraints, unique elements, filtered values
- Custom strategies with complex predicates
- Composite/recursive strategies

#### Edge Case Coverage

- None/null/empty cases
- Boundary conditions (0, max_int, empty list)
- Error cases (division by zero, index out of bounds)

---

### 3. Round-Trip / Oracle Checking 📌 (Tabled)

**Goal**: Empirical validation that Lean claims match Python behavior.

**Approach**:

1. Parse Lean theorem to extract preconditions and postcondition
2. Run Python Hypothesis test, collect generated examples
3. For each example, check if it satisfies Lean's preconditions and postcondition
4. Metric: % of examples where Lean's claim holds

**What it catches**:

- Unsound specs (Lean claims something Python contradicts)
- Wrong bounds in preconditions
- Missing constraints

**Example**:

```python
# Python: @given(x=st.integers(0, 100))
# Lean: (h : 0 ≤ x ∧ x ≤ 150)  # Wrong bound!
# Check: Does Hypothesis generate x > 100? Mismatch detected.
```

**Why tabled**: High complexity (need Lean expression evaluator, predicate parser, Hypothesis example collector) for uncertain value gain. Structural metrics already provide good coverage.

**Future work**: Could start with simple numeric bounds validation before expanding to full postconditions.

---

### 4. Semantic Equivalence

#### Property Extraction & Differential Testing

- Extract Lean property as executable Python function
- Generate inputs satisfying preconditions
- Check if Python and Lean agree
- Requires implementations (blocked for now)

#### Quantifier Correctness

- Check `∀` usage matches `@given`
- Existential claims (`∃`) correctly translated
- Nested quantifier order

---

### 5. Provability (Can We Actually Prove This?)

#### Automated Proof Attempts

- Try standard tactics with timeout
- Track which theorems are auto-provable
- Measures theorem difficulty for verification tools

#### Proof Complexity Estimation

- Quantifier alternations
- Term nesting depth
- Non-linear arithmetic, recursion, induction

#### Sorry Depth Analysis

- Not just count, but location: helper functions vs main theorem
- Sorries in type definitions vs proofs

---

### 6. Task Difficulty Prediction

#### Python Complexity Metrics

- Cyclomatic complexity
- Halstead metrics
- Control flow branches
- Nesting depth

#### Hypothesis Strategy Complexity

- Composite strategies (tuples, recursive)
- Custom strategies with `.filter()` or `.map()`
- Strategy dependencies

#### Dependency Complexity

- Dependency graph depth
- Circular dependencies
- External imports

#### Mathematical Sophistication

- Domain characterization (arithmetic vs algebra vs graph theory)
- Required background knowledge

---

### 7. Specification Quality

#### Lean Idiomaticity

- Mathlib idiom usage
- Naming conventions
- Standard library patterns

#### Modularity

- Helper function factoring
- Separation of concerns

#### Readability

- Comment density
- Line length distribution
- Name clarity (avoid `x1`, `tmp`)

---

### 8. Model Behavior Analysis

#### Tool Usage Patterns

- `lean_compile` call frequency and timing
- Iteration based on errors
- Recovery vs giving up

#### Error Recovery

- Which error types trigger recovery?
- Which cause catastrophic failure?
- Parse errors vs type errors vs logic errors

#### Token Efficiency

- Tokens per line of Lean
- Verbosity in explanations
- Repeated/redundant generations

---

### 9. Dataset Characterization

#### Property Type Taxonomy

- Algebraic laws (commutativity, associativity, identity)
- Ordering properties (monotonicity, boundedness)
- Invariants, precondition/postcondition pairs
- Statistical properties

#### Domain Distribution

- Type analysis (numeric, strings, lists, custom types)
- Pure vs stateful functions
- Deterministic vs probabilistic

#### Test Origin Analysis

- Source repo/project tracking
- Test quality in source
- Library vs application code

---

### 10. Meta-Metrics

#### Inter-Annotator Agreement

- Human evaluation of faithfulness
- Correlation with structural metrics

#### Discriminative Power

- Do metrics distinguish good from bad?
- Or does everything score 0.7-0.8?

#### Stability

- Variance across multiple runs
- Temperature sensitivity

---

### 11. Practical Impact

#### Verification Cost Estimation

- Predicted time to prove (if someone tried)
- Proof search complexity

#### Reusability

- Generality vs over-fitting to one test
- Potential for use in other projects

#### Bug-Finding Potential

- Mutation testing: does spec catch code changes?

---

## Prioritization

### High Priority (Consider Next)

1. **Vacuity detection** - Critical for soundness, addresses CLEVER critique
2. **Task difficulty prediction** - Understand what makes samples hard
3. **Assertion-to-property mapping** - More fine-grained completeness

### Medium Priority

4. **Automated proof attempts** - Measures verification difficulty
5. **Quantifier analysis** - If easy to implement statically
6. **Model behavior tracking** - Already collecting some data

### Lower Priority (Needs More Infrastructure)

7. **Round-trip oracle checking** - High complexity, uncertain ROI
8. **Property differential testing** - Requires implementations
9. **Dataset characterization** - More for analysis than evaluation

### Future Work (Post-Capabilities-Improvement)

10. **Full semantic equivalence checking** - When implementations are reliable
11. **Mutation testing** - When we have proven specs

---

## Design Principles

Based on our discussion and lessons from Verina/CLEVER:

✅ **Prefer static/deductive/programmatic checks** over LLM inference
✅ **Use real-world tests as ground truth**, not LLM-generated specs
✅ **Leverage Lean's type checker** for post-hoc validation
✅ **Don't require implementations/proofs** during task generation stage
✅ **Focus on specification quality**, not full verification (yet)

❌ **Avoid relying on current LLM capabilities** to implement functions correctly
❌ **Don't add complexity without clear value** (high complexity-to-value ratio)
❌ **Don't leak implementation details** through test cases

---

# Dependency Mocking

## The Problem

The scraped property-based tests from GitHub are heavily dependent on numerical computing libraries, particularly **PyTorch** and **NumPy**. Translating these tests to Lean 4 requires "mocking" or approximating these rich, complex libraries within a proof assistant that:

- Has no standard tensor/array library
- Has no automatic differentiation framework
- Has no GPU execution model
- Is designed for _specification_, not _execution_

## Current State: What Sonnet 4.5 Does

Looking at generated artifacts (e.g., `test_logit`, `test_index_uint8`, `test_torch_is_leaf`), the model employs several strategies:

**1. Abstract Type Axioms**

```lean
axiom Tensor : Type → Type
```

Declares tensors exist without defining them. Philosophically sound for specification work—we care about _properties_, not _implementations_.

**2. Parameterized Structures**

```lean
structure Tensor (shape : List Nat) where
  data : Unit  -- Placeholder
```

Captures shape information at the type level while leaving implementation undefined.

**3. Explicit Structures for PyTorch Concepts**

```lean
structure Tensor where
  data : Array Float
  requires_grad : Bool
```

Models PyTorch's computation graph concepts directly in Lean's type system.

**4. Sorry-Driven Implementation Stubs**

```lean
def Tensor.pow (t : Tensor) (n : Float) : Tensor := sorry
def clip (t : Tensor Float) (min max : Option Float) : Tensor Float := sorry
```

Function signatures capture interfaces without implementations. Proof obligations remain, but _types are checked_.

**5. Domain-Specific Helper Structures**

```lean
structure NNModule where params : Unit
structure HypothesisSettings where max_examples seed : Nat
```

The model invents reasonable Lean representations for Python test infrastructure.

## The Challenge Landscape

### Semantic Impedance Mismatch

**Python/NumPy/PyTorch:**

- Dynamic shapes (can change at runtime)
- Implicit broadcasting
- Mutable operations (`tensor[i] = val`)
- Side effects (GPU state, random seeds)
- Automatic differentiation via runtime graph building

**Lean 4:**

- Static types (shapes must be known at compile time)
- Explicit everything
- Immutability by default
- Pure functions only (monadic for effects)
- No built-in autodiff

**Example Tension:**

```python
# Python: shape discovered at runtime
x = np.random.rand(n, m)
y = x + x  # Broadcasting works magically
```

```lean
-- Lean: shape must be in the type
def add (x y : Tensor [n, m]) : Tensor [n, m] := sorry
-- What if shapes don't match? Need dependent types or runtime checks!
```

### Fidelity vs. Abstraction Tradeoff

**High Fidelity** (closer to Python):

- ✅ Captures nuanced behavior (broadcasting rules, numerical precision)
- ❌ Complex type-level programming (dependent types, proof obligations)
- ❌ Requires extensive Lean libraries (Mathlib tensors, numerical analysis)
- ❌ May not even be _possible_ to specify precisely (e.g., floating-point ULP guarantees)

**High Abstraction** (mathematical essence):

- ✅ Simple, clean specifications
- ✅ Focuses on _properties_ not _mechanisms_
- ❌ Loses details that matter (does the test check numerical stability or just correctness?)
- ❌ Risk of vacuity (spec too weak to be meaningful)

**Current approach leans toward high abstraction**—this seems right for a _specification benchmark_.

### Library Completeness Problem

To properly mock torch/numpy, we'd need Lean equivalents for:

**NumPy Core:**

- `ndarray` with shape, dtype, strides
- Broadcasting rules
- Indexing (slicing, boolean masks, advanced indexing)
- Universal functions (ufuncs)
- Linear algebra (matmul, solve, eig)
- Random number generation

**PyTorch Core:**

- `Tensor` with device, dtype, requires_grad
- Autograd graph (forward/backward)
- Optimizers, loss functions
- nn.Module abstraction
- CUDA kernels, streams

**This would be _years_ of work** to build in Lean. We're not doing verification of numerical libraries—we're verifying _programs that use_ numerical libraries.

## Approaches to Dependency Mocking

### A. Full Formalization (Mathlib-style)

Build or use existing Lean libraries for linear algebra and numerical computing.

**Pros:**

- Most rigorous
- Proofs would be _real_ proofs
- Could leverage existing Mathlib work (matrices, vectors, norms)

**Cons:**

- Enormous upfront investment
- Shape-polymorphic operations require dependent types (hard!)
- Floating-point arithmetic is underspecified in Mathlib
- NumPy semantics don't always match mathematical definitions

**Verdict:** Not feasible for this benchmark. Maybe in 5-10 years with mature Lean4 numerical libraries.

### B. Axiomatic Interfaces (Current Approach)

Declare types and functions axiomatically, focus on high-level properties.

**Pros:**

- Practical: works today with Sonnet 4.5
- Flexible: model can choose abstraction level
- Type-checks: Lean verifies signatures
- Focuses on _specification quality_ not _implementation_

**Cons:**

- Risk of vacuity (specs too weak)
- No executable code (can't test)
- Difficult to validate "correctness" of axioms
- Model might hallucinate nonsensical axioms

**Verdict:** **This is what we're doing, and it's probably right.** But we need guardrails (metrics!) to catch vacuous specs.

### C. Shallow Embedding via Lean's FFI

Use Lean's C FFI to call actual NumPy/PyTorch libraries.

**Pros:**

- Real implementations
- Can execute tests
- Behavioral validation possible

**Cons:**

- Breaks proof-carrying code (FFI calls are `opaque`)
- Requires Python/C interop layer
- Still need Lean _types_ for the foreign functions
- Doesn't help with proofs (still need axioms)

**Verdict:** Interesting for _validation_, but doesn't solve the specification problem.

### D. Hybrid: Axioms + Mathlib for "Easy" Operations

Use Mathlib for simple stuff (vectors, matrices, basic algebra), axioms for complex operations.

**Pros:**

- Best of both worlds?
- Mathlib gives us proven foundations where possible

**Cons:**

- Requires identifying the boundary (what's "easy"?)
- Mathlib matrices are 2D only (tensors are n-dimensional)
- Still need axioms for most interesting operations

**Verdict:** Worth considering as capabilities improve. Most of our tests are "hard" (conv2d, attention, quantization).

### E. Property-Based Approximation

Instead of mocking _implementations_, mock _properties_.

**Example:**
Instead of:

```lean
def Tensor.clip (t : Tensor α) (min max : α) : Tensor α := sorry
```

Specify properties:

```lean
axiom clip_bounds : ∀ (t : Tensor α) (min max : α) (i : Index),
  min ≤ t.get i ∧ t.get i ≤ max →
  (t.clip min max).get i = t.get i

axiom clip_clamps_low : ∀ (t : Tensor α) (min max : α) (i : Index),
  t.get i < min →
  (t.clip min max).get i = min
```

**Pros:**

- Directly captures test intent
- More specific than bare axioms
- Could be proven from implementations (if we had them)

**Cons:**

- Verbose
- Model needs to infer these properties from Python tests
- Still doesn't give us executability

**Verdict:** This is what **good theorem statements** should look like! But it's a higher bar for the model.

## Specific Challenges: torch vs. numpy

### NumPy

Relatively "simple" (still complex!):

- Pure functions mostly
- Well-defined broadcasting
- Explicit types (dtype)

**Actionable:** Could build a minimal Lean NumPy-like API with axioms for common operations (rand, array indexing, arithmetic, matmul). Maybe ~50-100 operations cover 80% of tests.

### PyTorch

Much harder:

- **Autograd:** Computation graphs are _runtime_ constructs. How do we model `requires_grad`, `backward()`, leaf/non-leaf in a pure language?
  - Current approach: model `requires_grad` as a boolean field, ignore gradient _values_.
  - This captures _structure_ but not _semantics_.

- **Device abstraction:** `tensor.to('cuda')` moves data. Lean has no device concept.
  - Current approach: `inductive Device | CPU | GPU`, ignore memory/performance.

- **nn.Module:** Object-oriented, stateful, with initialization and parameter registration.
  - Current approach: `structure NNModule where params : Unit`. Very abstract!

- **Dynamic shapes:** PyTorch tensors can have runtime-determined shapes.
  - Lean requires compile-time types. Dependent types could help but complicate everything.

**Actionable:** Focus on _pure forward-pass properties_ initially. Ignore autograd details unless the test specifically checks gradient behavior.

## What Matters for Our Benchmark?

Recall our goals:

1. Evaluate **AI model ability to translate** Python → Lean
2. Measure **specification quality** (faithfulness, structural metrics)
3. Focus on **specification generation**, not full verification (sorry is OK!)
4. Learn what makes formal verification hard for AI

**Therefore:**

**What We Need:**

- ✅ **Type-correct** Lean code (compiles)
- ✅ **Reasonable abstractions** (Tensor, Module, operations)
- ✅ **Property capture** (theorems match test intent)
- ✅ **Metrics to detect badness** (vacuity, missing properties)

**What We Don't Need:**

- ❌ Executable implementations
- ❌ Proven correctness of mock libraries
- ❌ Bit-exact floating-point semantics
- ❌ Full PyTorch API coverage

**Gray Area (Think Harder):**

- 🤔 How much shape information in types? `Tensor [2, 3, 4]` vs. `Tensor`?
- 🤔 Do we need property axioms or just function signatures?
- 🤔 How to validate that axioms are "reasonable" (not contradictory)?
- 🤔 Should we guide the model with a standard library, or let it invent?

## Recommendations

### Short Term (Current State)

1. **Accept axiomatic mocking as the strategy.** It's working reasonably well in generated samples.

2. **Add metrics to detect problems:**
   - Vacuity detection (tactic testing) catches trivial theorems
   - Type complexity metrics (how many axioms? how many sorry?)
   - Shape consistency checks (if using dependent types)

3. **Document common patterns.** Create a "Lean NumPy/PyTorch Style Guide" for the model:

   ```lean
   -- Preferred: parameterized structures
   structure Tensor (shape : List Nat) where data : Unit

   -- Acceptable: bare axioms
   axiom Tensor : Type

   -- Avoid: overcomplicated dependent types (unless necessary)
   ```

4. **Sample-based validation.** For simple operations (arithmetic, indexing), we could write "golden" Lean specs and compare.

### Medium Term (Next 6-12 Months)

5. **Build a minimal standard library.** Provide the model with:
   - `Lean.Tensor` module with ~50 common operations
   - `Lean.PyTorch` module with basic autograd types
   - Property axioms for key operations

6. **Integrate Mathlib where possible.** Use matrices, vectors, norms from Mathlib for tests that fit.

7. **Experiment with shape tracking.** Try generating both:
   - `Tensor α` (shape-erased, simpler)
   - `Tensor (shape : List Nat)` (shape-tracked, more info)

8. **Property-based spec generation.** Train/prompt the model to generate property axioms, not just function signatures.

### Long Term (1-2+ Years)

9. **Wait for Lean ecosystem maturity.** Projects like SciLean (scientific computing in Lean) will provide foundations.

10. **Executable specifications.** Use Lean's compiler to generate runnable code, validate against Python tests.

11. **Proof automation for numerical properties.** Tactics like `polyrith` or `interval` could auto-prove simple theorems.

## Open Questions

1. **Shape polymorphism:** Dependent types for shapes vs. shape-erased tensors? Trade-off between expressiveness and complexity.

2. **Property granularity:** How detailed should theorem statements be?
   - Coarse: `∀ x, clip x min max is correct` (vague!)
   - Fine: `∀ x i, x[i] < min → (clip x min max)[i] = min` (verbose!)

3. **Dependency standardization:** Let model invent fresh axioms every time vs. provide a fixed standard library?

4. **Validation strategy:** Without executable code or proofs, how do we know a spec is "good"?
   - Structural metrics (parameter coverage, type correspondence) ← we have this!
   - Vacuity detection (trivial provability) ← we're building this
   - Human evaluation (sample-based, expensive)
   - LLM-as-judge (another model rates quality)

5. **Autograd representation:** For tests that check gradient computation, how do we model backprop in Lean?

6. **Failure modes:** What Python tests are **fundamentally untranslatable**?
   - Performance tests (must run in <100ms)
   - Numerical stability tests (check ULP precision)
   - Concurrency/parallelism tests
   - Tests with heavy side effects

## Conclusion

**Dependency mocking is inherently hard** because we're bridging incompatible worlds (imperative Python with rich libraries ↔ pure Lean with minimal numerics).

**Our current approach (axiomatic mocking with sorry) is pragmatic and appropriate** for a specification benchmark focused on AI evaluation.

**The main risk is vacuity**—specs that type-check but say nothing interesting. Metrics like vacuity detection and structural faithfulness are our defense against this.

**For torch/numpy specifically:**

- NumPy is more tractable (pure functions, clear semantics)
- PyTorch is harder (autograd, devices, dynamic shapes)
- Focus on _forward-pass properties_ initially
- Consider building a small standard library to guide the model

**The benchmark is successful if:**

1. Generated Lean code type-checks ✓ (already mostly true)
2. Specifications capture test intent (structural metrics measure this)
3. We can distinguish good from bad translations (vacuity + metrics)
4. Results improve as AI capabilities advance (track over time)

We don't need perfect torch/numpy in Lean. We need _good enough_ mocks to evaluate AI translation quality. And we're probably already there!

---

# mvcgen and monadic program logic

## The Paradigm Shift: Lean 4.22 and Beyond

In August 2025, **Lean 4.22** introduced `Std.Do.Triple`, a Hoare logic framework for monadic programs, fundamentally changing how imperative code can be verified in Lean. This is the infrastructure that **Dougherty & Mehta would have "heavily used"** when building FVAPPS (see CLAUDE.md) if it had been available in 2024.

By Q4 2025 with **Lean 4.23**, this tooling will be mature enough to transform how we approach this benchmark.

### What is mvcgen?

`mvcgen` (monadic verification condition generator) is proof automation that analyzes locally imperative programs and converts Hoare triple obligations into pure verification conditions:

```lean
-- Instead of manually reasoning about state transformations...
⦃Precondition⦄
  imperativeProgram
⦃Postcondition⦄

-- mvcgen generates clean verification conditions (VCs):
-- 1. Loop invariant preservation
-- 2. Initial invariant establishment
-- 3. Postcondition from invariant + termination
-- 4. Early return handling
```

These VCs can then be discharged by the new **`grind` tactic** (an SMT-style proof automation tool also from 4.22) or other standard tactics.

**Key insight from [Markus Himmel's blog post](https://markushimmel.de/blog/my-first-verified-imperative-program/)**: mvcgen transforms imperative verification from a monolithic proof burden into a **compositional, interactive process**. You specify loop invariants, mvcgen tells you what remains to prove, and automation like `grind` handles "obvious" steps.

### Why This Changes Everything for Our Benchmark

#### Before Lean 4.22: Functional-Only Verification

Pre-4.22 FVAPPS and early fvspec samples show this pattern:

```lean
-- Pure functional style with recursion
def fibonacci (n : Nat) : Nat :=
  match n with
  | 0 => 0
  | 1 => 1
  | n+2 => fibonacci n + fibonacci (n+1)

-- Prove properties via structural induction
theorem fib_positive (n : Nat) : 0 ≤ fibonacci n := by
  induction n with
  | zero => rfl
  | succ n ih => ... -- Manual structural reasoning
```

**Limitations**:

- Natural for recursive algorithms (list processing, tree traversal)
- Awkward for algorithms that are _conceptually_ imperative (loops, mutable state)
- Forces unnatural translations of Python code that uses `for`/`while`
- Loop invariants exist implicitly in induction hypotheses (hard to see!)

#### After Lean 4.22: Native Imperative Verification

```lean
-- Direct imperative style with `do` notation
def fibonacci (n : Nat) : Nat := Id.run do
  let mut a := 0
  let mut b := 1
  for _ in [0:n] do
    let tmp := a + b
    a := b
    b := tmp
  return a

-- Verify with Hoare triples and loop invariants
theorem fib_correct (n : Nat) : fibonacci n = ... := by
  mvcgen  -- Generate verification conditions
  case loop_invariant =>
    -- State explicit invariant: a = fib(i), b = fib(i+1)
    intro i a b h_inv
    ...
  case postcondition =>
    grind  -- Automation handles the "obvious" parts
```

**Advantages**:

- ✅ Matches Python code structure 1:1
- ✅ Loop invariants are **explicit and named** (not hidden in induction)
- ✅ Compositional: prove loop bodies separately from whole function
- ✅ Automation (grind) reduces proof burden
- ✅ More natural for systems/algorithms code

### Impact on fvspec Benchmark Tasks

Our benchmark translates **Hypothesis property-based tests** from Python to Lean. Many of these tests check imperative or stateful code:

**Example: Array mutation tests**

```python
@given(arr=st.lists(st.integers()), idx=st.integers(0, 100))
def test_array_update(arr, idx):
    if idx < len(arr):
        old_val = arr[idx]
        arr[idx] = 42
        assert arr[idx] == 42
        assert all(arr[i] == old_arr[i] for i in range(len(arr)) if i != idx)
```

#### Pre-4.22 Translation: Functional Encoding

```lean
def arrayUpdate (arr : List Int) (idx : Nat) (val : Int) : List Int :=
  arr.set idx val

theorem arrayUpdate_correct (arr : List Int) (idx : Nat) (h : idx < arr.length) :
  let arr' := arrayUpdate arr idx 42
  arr'.get ⟨idx, by ...⟩ = 42 ∧
  ∀ i, i ≠ idx → arr'.get? i = arr.get? i := by
  sorry
```

**Issues**:

- `List.set` is functional (creates new list), not mutable
- Doesn't match Python's imperative semantics
- Verbose manual indexing proofs
- Loses the "mutation" concept entirely

#### Post-4.22 Translation: Imperative Encoding

```lean
def arrayUpdate (arr : Array Int) (idx : Nat) (val : Int) : StateM (Array Int) Unit := do
  let mut a := arr
  a := a.set! idx val

theorem arrayUpdate_correct (arr : Array Int) (idx : Nat) (h : idx < arr.size) :
  ⦃fun s => s = arr⦄
    arrayUpdate arr idx 42
  ⦃fun _ s => s[idx] = 42 ∧ ∀ i ≠ idx, s[i] = arr[i]⦄ := by
  mvcgen
  · -- Assignment preserves properties
    grind
  · -- Postcondition follows
    grind
```

**Advantages**:

- Uses `Array` (contiguous, mutable-style) not `List`
- Hoare triples directly express pre/postconditions
- `mvcgen` + `grind` automate most reasoning
- **Closer to Python's execution model**

### What mvcgen Enables That We Couldn't Do Before

#### 1. **Stateful Computations with Explicit Invariants**

Python tests often involve stateful transformations:

```python
@given(data=st.lists(st.floats()))
def test_cumulative_sum(data):
    cumsum = []
    total = 0.0
    for x in data:
        total += x
        cumsum.append(total)
    assert len(cumsum) == len(data)
    assert cumsum[-1] == sum(data)  # Final value is total sum
```

Pre-4.22: Awkward functional recursion with accumulators.

Post-4.22: Natural imperative loop with loop invariant:

```lean
def cumulativeSum (data : List Float) : List Float := Id.run do
  let mut cumsum := []
  let mut total := 0.0
  for x in data do
    total := total + x
    cumsum := cumsum.push total
  return cumsum

theorem cumsum_correct (data : List Float) :
  let result := cumulativeSum data
  result.length = data.length ∧
  result.getLast? = some (data.sum) := by
  mvcgen
  case loop_invariant =>
    -- Invariant: cumsum.length = processed elements
    --            cumsum.getLast = sum of processed elements
    ...
```

**The loop invariant is now a first-class citizen**, not buried in an induction hypothesis!

#### 2. **Neural Network Modules with State**

PyTorch tests often involve stateful modules:

```python
@given(x=tensors(shape=(10, 20)), training=st.booleans())
def test_dropout(x, training):
    dropout = nn.Dropout(p=0.5)
    dropout.train(training)
    y = dropout(x)
    assert y.shape == x.shape
    if not training:
        assert torch.equal(y, x)  # No dropout during eval
```

Pre-4.22: Model `nn.Module` with awkward functional state passing or `StateM` without verification support.

Post-4.22: Native `StateM` verification with `mvcgen`:

```lean
structure Dropout where
  p : Float
  training : Bool

def Dropout.forward (self : Dropout) (x : Tensor) :
  StateM PRNGState Tensor := do
  if self.training then
    let mask ← bernoulli x.shape (1.0 - self.p)
    return x * mask / (1.0 - self.p)
  else
    return x

theorem dropout_eval_identity (m : Dropout) (x : Tensor) (h : ¬m.training) :
  ⦃fun s => True⦄
    m.forward x
  ⦃fun y s => y = x⦄ := by
  mvcgen
  case if_branch =>
    contradiction  -- Training is false
  case else_branch =>
    grind
```

The Hoare triple + `mvcgen` combination lets us reason about stateful operations (even with randomness via `StateM`) in a compositional way.

#### 3. **Loop Invariants for Iterative Algorithms**

Many algorithms are naturally iterative (gradient descent, search, dynamic programming). Before 4.22, these required unnatural recursive encodings.

**Example: Binary search**

```python
@given(arr=st.lists(st.integers()).filter(lambda x: x == sorted(x)),
       target=st.integers())
def test_binary_search(arr, target):
    left, right = 0, len(arr) - 1
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1  # Not found
```

Post-4.22 with mvcgen:

```lean
def binarySearch (arr : Array Int) (target : Int)
  (h_sorted : arr.isSorted) : Option Nat := Id.run do
  let mut left := 0
  let mut right := arr.size - 1

  while left ≤ right do
    let mid := (left + right) / 2
    if arr[mid] = target then
      return some mid
    else if arr[mid] < target then
      left := mid + 1
    else
      right := mid - 1

  return none

theorem binarySearch_sound (arr : Array Int) (target : Int)
  (h_sorted : arr.isSorted) :
  ∀ i, binarySearch arr target h_sorted = some i → arr[i] = target := by
  mvcgen
  case loop_invariant =>
    -- Invariant: if target in arr, then target in arr[left:right+1]
    intro left right h_range
    ...
  case postcondition =>
    grind
```

The loop invariant captures the **search space shrinking** property, which was implicit and hard to express in recursive versions.

### Challenges and Open Questions for fvspec

#### 1. **Model Capability: Can LLMs Write Good Loop Invariants?**

Loop invariants are **the hardest part** of Hoare logic. They require:

- Understanding algorithm intent (what is this loop computing?)
- Identifying preserved properties across iterations
- Expressing relationships between loop variables

**Question**: Will Claude/GPT-4/o1 be able to generate correct loop invariants from Python property tests?

**Hypothesis**: Models might handle simple invariants (bounds, lengths) but struggle with complex relational invariants (sortedness, graph properties).

**Metric idea**: Measure "invariant strength" — how much does the invariant constrain the state space?

#### 2. **Evaluation: How Do We Score mvcgen-Based Specs?**

Our current metrics (parameter coverage, type correspondence, etc.) assume functional/declarative Lean code. With imperative code + Hoare triples, we need new metrics:

**Proposed metrics**:

- **Loop invariant coverage**: Do loop invariants mention key variables from the Python test?
- **VC discharge rate**: What % of verification conditions are auto-provable by `grind`?
- **Invariant tightness**: Can the postcondition be proved from the loop invariant + termination condition? (If not, invariant is too weak.)
- **Vacuity via invariant strength**: Try trivial invariants (`True`) — if mvcgen still succeeds, the spec is vacuous.

**Challenge**: Parsing Hoare triples and loop invariants from generated Lean code requires understanding `mvcgen` syntax. Need updated parsers.

#### 3. **Task Design: Should We Force Imperative Style?**

**Option A: Let the model choose**

- Pro: Tests model's ability to select appropriate paradigm
- Con: Harder to compare across samples (functional vs imperative)

**Option B: Prompt for imperative + mvcgen**

- Pro: Focuses evaluation on new capability
- Pro: Better matches Python code structure
- Con: Some algorithms are naturally recursive (tree traversal)

**Recommendation**: Add a `style` tag to samples (functional/imperative/stateful) based on Python code structure. Prompt accordingly. Track success rates per style.

#### 4. **Temporal Scope: When Will This Be Usable?**

**Current state (Lean 4.22, released Aug 2025)**:

- `Std.Do.Triple` is **experimental**
- Limited documentation (Markus Himmel's blog is the main resource)
- Few examples in the wild
- No Mathlib integration yet

**Expected state (Lean 4.23, Q4 2025)**:

- More stable API
- Better documentation
- Community examples and patterns
- Possibly integrated into Mathlib's verification workflows

**Expected state (Lean 4.24+, 2026)**:

- Mature tooling
- Standard library annotated with Hoare specs
- Tactics for common loop patterns (sum, filter, map)
- Integration with other verification tools (Aeneas, etc.)

**Timeline for fvspec**:

- **Now (Q3 2025)**: Monitor but don't rely on mvcgen yet
- **Q4 2025**: Start piloting mvcgen-based samples, collect data
- **2026**: Make mvcgen a first-class evaluation target

#### 5. **Dependency Mocking: Does mvcgen Help with torch/numpy?**

**Short answer: Yes, dramatically.**

PyTorch operations are inherently stateful:

- Autograd builds computation graphs (state)
- `.backward()` mutates `.grad` fields
- Optimizers update parameters in-place
- Training loops are imperative

**Before 4.22**, modeling these required:

- Complex `StateM` encodings without verification support
- Functional wrappers that don't match Python semantics
- Axioms for everything (no way to prove properties of stateful code)

**After 4.22**, we can:

- Model `Tensor` with `requires_grad` as stateful objects
- Write imperative training loops with Hoare triples
- Specify loop invariants for gradient descent (e.g., loss decreases)
- Use mvcgen to verify optimizer steps

**Example: Gradient Descent Loop**

```python
@given(x=tensors(), lr=st.floats(0.001, 0.1), steps=st.integers(1, 100))
def test_gradient_descent_decreases_loss(x, lr, steps):
    x.requires_grad = True
    initial_loss = loss_fn(x)

    for _ in range(steps):
        loss = loss_fn(x)
        loss.backward()
        with torch.no_grad():
            x -= lr * x.grad
        x.grad.zero_()

    final_loss = loss_fn(x)
    assert final_loss <= initial_loss
```

With mvcgen, we can write:

```lean
theorem gd_decreases_loss (x : Tensor) (lr : Float) (steps : Nat)
  (h_lr_pos : 0 < lr) (h_lr_small : lr < 0.1)
  (h_convex : isConvex loss_fn) :
  ⦃fun s => s.loss = loss_fn x⦄
    gradientDescent x lr steps
  ⦃fun x_final s => loss_fn x_final ≤ loss_fn x⦄ := by
  mvcgen
  case loop_invariant =>
    -- Invariant: loss is non-increasing
    intro i x_i s h_inv
    have h_step : loss_fn x_i.next ≤ loss_fn x_i := by
      -- Use convexity + gradient descent step
      apply gradient_step_decreases_loss h_convex h_lr_pos
    omega  -- Chain inequalities
  case postcondition =>
    grind
```

**This was essentially impossible before 4.22.**

### Practical Next Steps for Benchmark Development

#### Short Term (Q3-Q4 2025)

1. **Add mvcgen detection to quality assessment**

   ```python
   @dataclass
   class QualityMetrics:
       uses_mvcgen: bool
       hoare_triple_count: int
       loop_invariant_count: int
       vc_discharge_success_rate: float  # Via compilation logs
   ```

2. **Pilot study: Compare functional vs imperative specs**
   - Select 20 samples suitable for imperative style
   - Generate both functional (pre-4.22) and imperative (with mvcgen) specs
   - Compare: readability, faithfulness, provability, token usage
   - Identify which Python patterns benefit most from mvcgen

3. **Update prompts to mention mvcgen as an option**

   ```
   For imperative Python code (loops, mutation), consider using
   Lean 4.22's Std.Do.Triple with mvcgen for verification.
   Specify loop invariants and use Hoare triples ⦃P⦄ prog ⦃Q⦄.
   ```

4. **Build example library**
   - 10-15 exemplar translations using mvcgen
   - Cover common patterns: array updates, cumulative operations, search algorithms
   - Include loop invariants with explanations
   - Use as few-shot examples in prompts

#### Medium Term (2026)

5. **Make imperative style the default** for suitable tasks
   - Classify Python tests by structure (functional/imperative/stateful)
   - Imperative tests → prompt for mvcgen
   - Update evaluation to expect Hoare triples

6. **Develop loop invariant quality metrics**
   - Syntactic coverage (variables mentioned)
   - Semantic strength (try weakening, does proof break?)
   - Inductive provability (is invariant actually preserved?)

7. **Automate VC discharge checking**
   - Parse mvcgen output from Lean LSP
   - Track which VCs are discharged automatically
   - Measure `grind` success rate per VC type

8. **Integrate with torch/numpy mocking**
   - Build standard library of imperative PyTorch operations with Hoare specs
   - Provide as dependencies to the model
   - Measure reuse vs. hallucination

#### Long Term (2027+)

9. **Full verification pipeline**
   - Generate Lean code with `mvcgen`
   - Auto-prove VCs with `grind`/`aesop`/`omega`
   - Human-in-the-loop for remaining `sorry`s
   - Track: what % of specs are fully verified?

10. **Benchmark for proof automation**
    - Evaluate different tactics on generated VCs
    - Compare `grind` vs. SMT solvers via Lean-auto
    - Feed results back to Lean developers (which tactics should improve?)

11. **Cross-prover comparison**
    - Generate Dafny/F\*/Why3 from same Python tests
    - Compare: expressiveness, automation, proof effort
    - Lean's mvcgen vs. Dafny's loop invariants

### Conclusion: mvcgen as a Game-Changer

The introduction of `mvcgen` in Lean 4.22 represents a **paradigm shift** from purely functional verification to native imperative program verification with interactive proof assistance.

**For fvspec specifically**:

- ✅ **Better semantic alignment**: Imperative Lean matches imperative Python
- ✅ **Explicit invariants**: Loop invariants are no longer implicit in induction
- ✅ **Compositionality**: Prove loop bodies and postconditions separately
- ✅ **Automation**: `grind` reduces proof burden, higher success rates expected
- ✅ **Stateful systems**: Can finally model PyTorch's autograd, nn.Module, optimizers

**Risks and Challenges**:

- ❌ Model capability: Writing good loop invariants is hard (even for humans!)
- ❌ Evaluation complexity: New metrics needed for Hoare logic
- ❌ Maturity: Std.Do is experimental, API may change
- ❌ Documentation: Limited resources, learning curve steep

**Strategic recommendation**:

**Begin experimenting with mvcgen in Q4 2025 as Lean 4.23 stabilizes, but don't make it required yet.** Run parallel evaluations (functional vs. imperative) to quantify benefits. By 2026, imperative specifications with mvcgen should be the benchmark's primary evaluation target for suitable tasks.

This aligns with our ARIA funding goal: understanding **how AI can help with formal verification**. If models can't generate good loop invariants in 2025, that's valuable data. If they _can_, that's transformative for verified software engineering.

**The question isn't whether mvcgen will change the game—it already has.** The question is: **can AI models learn to play the new game?**
