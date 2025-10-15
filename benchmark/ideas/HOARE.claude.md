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

