# Dependency Mocking: Approaches and Tradeoffs

**Context**: When translating Python property-based tests (using NumPy/PyTorch) to Lean 4, we must "mock" these libraries. The benchmark generates *specifications*, but eventually agents or humans will need to *prove* theorems about them.

**Core tension**: Approaches that work well for specification generation may break down during proof, because Lean's tactics rely on *computation*.

---

**🚨 CRITICAL CONSTRAINT ADDED**: Computation is non-negotiable. Approaches marked with ⛔ NONSTARTER do not support `#eval`, `rfl`, or `decide` and are therefore not viable. Only approaches C, D, and F (with caveats) remain on the table.

See `DEPMOCK.human.md` for focused discussion of viable computational approaches.

---

## The Problem with Bare Axioms

### Current Approach (Approach A) ⛔ NONSTARTER - NO COMPUTATION

Many generated specs use bare axioms:

```lean
axiom Tensor : Type
axiom Tensor.add : Tensor → Tensor → Tensor
axiom Tensor.matmul : Tensor → Tensor → Tensor

theorem add_commutative (a b : Tensor) :
  Tensor.add a b = Tensor.add b a := by
  -- Stuck! Can't proceed.
  -- Can't use rfl (nothing computes)
  -- Can't use simp (no simp lemmas)
  -- Can't unfold (axioms don't unfold)
  sorry
```

**The problem**: Axioms are completely opaque. No computational or symbolic leverage for proof tactics.

**When this fails**: The moment anyone tries to prove theorems. Common tactics that rely on computation:
- `rfl` - definitional equality (requires reduction)
- `decide` - decision procedures (requires evaluation)
- `simp` - simplification (requires reduction rules)
- Even `grind` - needs some computational foothold

---

## Alternative Approaches

### Approach B: Property Axioms (Coq/Rocq-style) ⛔ NONSTARTER - NO COMPUTATION

Inspired by the treatment of real numbers in Coq's standard library.

**Idea**: Axiomatize the *properties* we care about, not just the functions.

**NOTE**: While this enables symbolic reasoning, it does NOT support computation. Cannot use `#eval`, `rfl` (on axioms), or `decide`. This approach is incompatible with our requirement that proof tactics must have computational leverage.

```lean
-- Still declare types and functions as axioms
axiom Array : Type
axiom Array.add : Array → Array → Array

-- But now axiomatize PROPERTIES
axiom add_comm : ∀ (a b : Array), Array.add a b = Array.add b a
axiom add_assoc : ∀ (a b c : Array),
  Array.add (Array.add a b) c = Array.add a (Array.add b c)
axiom add_zero : ∀ (a : Array), Array.add a zero = a

-- Now the theorem is trivial!
theorem add_commutative (a b : Array) :
  Array.add a b = Array.add b a := by
  exact add_comm a b
```

#### More Interesting: Deriving Properties

With enough property axioms, we can prove derived theorems:

```lean
axiom Array.scale : Float → Array → Array

-- Property axioms for scalar multiplication
axiom scale_distributive : ∀ (k : Float) (a b : Array),
  Array.scale k (Array.add a b) =
  Array.add (Array.scale k a) (Array.scale k b)

axiom scale_associative : ∀ (k1 k2 : Float) (a : Array),
  Array.scale k1 (Array.scale k2 a) = Array.scale (k1 * k2) a

axiom scale_one : ∀ (a : Array), Array.scale 1.0 a = a

-- Prove a derived property using symbolic reasoning
theorem double_is_add (a : Array) :
  Array.scale 2.0 a = Array.add a a := by
  have h1 : Array.scale 2.0 a = Array.scale (1.0 + 1.0) a := by rfl
  have h2 : Array.scale (1.0 + 1.0) a =
            Array.scale 1.0 (Array.scale 1.0 a) := by
    rw [scale_associative]
    rfl
  have h3 : Array.scale 1.0 (Array.scale 1.0 a) =
            Array.add (Array.scale 1.0 a) (Array.scale 1.0 a) := by
    rw [← scale_distributive]
  rw [h1, h2, h3, scale_one, scale_one]
```

**This works!** We can do symbolic reasoning using the property axioms as rewrite rules.

#### Tradeoffs

**Pros:**
- ✅ Can prove derived theorems using symbolic reasoning
- ✅ Don't need full implementations
- ✅ Focuses on the *mathematical essence* (algebraic laws)
- ✅ More explicit about what properties we're relying on

**Cons:**
- ❌ Still can't compute (no `#eval`, `decide` tactics won't work)
- ❌ Must axiomatize the RIGHT properties upfront
- ❌ If you forget a crucial property, you're stuck
- ❌ Risk of inconsistency (might axiomatize contradictory properties)
- ❌ Verbose - each function needs multiple property axioms
- ❌ Requires model to infer properties from Python tests (harder task)

---

### Approach C: Concrete Implementations ✅ VIABLE - FULL COMPUTATION

Build real Lean implementations of array/tensor operations.

```lean
structure Array where
  data : List Float
  size_eq : data.length = 10

def Array.add (a b : Array) : Array :=
  ⟨List.zipWith (· + ·) a.data b.data, by sorry⟩

theorem add_commutative (a b : Array) :
  Array.add a b = Array.add b a := by
  simp [Array.add]
  -- Now we'd need to prove List.zipWith commutes
  -- But at least things COMPUTE and simplify
  sorry
```

**Pros:**
- ✅ Everything computes - can use `rfl`, `decide`, `#eval`
- ✅ No risk of inconsistent axioms
- ✅ Can validate specs by running them
- ✅ Tactics have maximum leverage

**Cons:**
- ❌ Enormous implementation effort (years of work for NumPy/PyTorch)
- ❌ Shape polymorphism requires dependent types (very complex)
- ❌ Floating-point semantics are underspecified
- ❌ Still need proofs of basic properties (commutativity, etc.)
- ❌ Implementation details leak into proofs

**Verdict:** Not feasible for this benchmark in the short-medium term.

---

### Approach D: Hybrid (Mathlib + Concrete Implementations) ✅ VIABLE - PARTIAL COMPUTATION

Use Mathlib for simple operations (vectors, matrices), concrete implementations for the rest (NOT property axioms!).

```lean
-- Use Mathlib's matrices for 2D operations
def Matrix.add := Matrix.add  -- from Mathlib

-- But use property axioms for tensors
axiom Tensor : Type
axiom Tensor.conv2d : Tensor → Tensor → Tensor
axiom conv2d_output_shape : ∀ (x : Tensor) (kernel : Tensor),
  (Tensor.conv2d x kernel).shape = compute_conv_output_shape x.shape kernel.shape
```

**Pros:**
- ✅ Best of both worlds where possible
- ✅ Mathlib gives proven foundations for "easy" stuff
- ✅ Can compute with Mathlib operations

**Cons:**
- ❌ Requires identifying the boundary (what's "easy"?)
- ❌ Mathlib matrices are 2D only (tensors are n-dimensional)
- ❌ Most interesting operations are still "hard" (need axioms)
- ❌ Mixing styles might confuse models

**Verdict:** Worth considering as capabilities improve. But most scraped tests involve "hard" operations.

---

### Approach E: Sorry Stubs (Not Axioms) ⛔ NONSTARTER - NO COMPUTATION

Use `sorry` in definitions instead of axioms:

**NOTE**: Using `sorry` instead of `axiom` is safer but still provides NO computation. Cannot use `#eval`, `rfl`, or `decide`. This approach is incompatible with our computation requirement.

```lean
def Tensor : Type := Unit  -- placeholder
def Tensor.add (a b : Tensor) : Tensor := sorry
def Tensor.matmul (a b : Tensor) : Tensor := sorry

-- Property lemmas as theorems (not axioms)
theorem add_comm (a b : Tensor) : Tensor.add a b = Tensor.add b a := sorry
```

**Pros:**
- ✅ Less risky than axioms (can't introduce inconsistency)
- ✅ Clear that these need implementation/proof later
- ✅ Type-checks and shows intent

**Cons:**
- ❌ Still doesn't help with computation
- ❌ Proofs still need the property theorems
- ❌ Essentially the same as approach B but with `sorry` instead of `axiom`

---

### Approach F: FFI to Python (Shallow Embedding) ⚠️ VIABLE WITH CAVEATS - LIMITED COMPUTATION

Use Lean's C FFI to call actual NumPy/PyTorch.

**NOTE**: FFI enables `#eval` but NOT `rfl` or `decide` (FFI calls are opaque to the reducer). Still needs property axioms or theorems for proving. Useful for validation but not for full proof automation.

```lean
@[extern "python_array_add"]
opaque Array.add : Array → Array → Array

-- Still need to state properties as axioms
axiom add_comm : ∀ (a b : Array), Array.add a b = Array.add b a
```

**Pros:**
- ✅ Real implementations - can execute and test
- ✅ Behavioral validation possible
- ✅ Could do "oracle testing" (compare Lean execution vs Python)

**Cons:**
- ❌ FFI calls are opaque to the prover (still need axioms for properties)
- ❌ Requires complex Python/C/Lean interop layer
- ❌ Doesn't help with proofs (no computational reduction)
- ❌ Breaks proof-carrying code guarantees

**Verdict:** Interesting for *validation* and testing, but doesn't solve the proof problem.

---

## Implications for the Benchmark

### During Specification Generation (Current Focus)

**Bare axioms work fine:**
- Type-checks ✓
- Model can generate reasonable abstractions ✓
- Captures high-level structure ✓

### During Proof (Future Phase)

**Bare axioms break down completely.** Proof agents will need either:

1. **Property axioms** (Approach B) - can do symbolic reasoning
2. **Concrete implementations** (Approach C) - can compute
3. **Hybrid** (Approach D) - mix both strategies

### Key Questions for Benchmark Design

**Q1: Can AI models generate good property axioms?**

The model would need to infer from Python:
```python
assert a + b == b + a
```

To Lean:
```lean
axiom add_comm : ∀ (a b : Array), Array.add a b = Array.add b a
```

Plus generate *sufficient* properties to prove derived theorems. This is a harder task than generating bare axioms.

**Q2: What properties are "sufficient"?**

For a minimal Array API, we'd need:
- Arithmetic: commutativity, associativity, identity, distributivity
- Indexing: bounds, update semantics
- Shape: preservation, broadcasting rules
- Special cases: zero, one, empty

**Q3: Risk of inconsistency?**

With property axioms, the model could generate:
```lean
axiom foo_prop1 : ∀ x, f x = 0
axiom foo_prop2 : ∀ x, f x = 1
-- Contradiction! Can now prove False.
```

Need **consistency checking** or **conservative axioms** (e.g., only generate properties that match standard algebraic structures).

---

## Recommendations

### Short Term (Current State)

1. **Continue with bare axioms + sorry for specification generation.** It's working.

2. **Add metrics to detect insufficient axiomatization:**
   - Count of axioms vs functions (too few properties?)
   - Theorem dependencies (do theorems never use axioms? Suspicious!)

3. **Document the limitation** in generated samples:
   ```lean
   -- WARNING: These axioms are sufficient for type-checking but insufficient
   -- for theorem proving. To prove properties, add axioms for algebraic laws.
   ```

### Medium Term (When Focusing on Proof)

4. **Experiment with property axiom generation:**
   - Prompt models to generate property axioms alongside function axioms
   - Test on simple examples (arithmetic, commutativity)
   - Measure: can models prove derived theorems?

5. **Build a minimal standard library with property axioms:**
   - 20-30 core NumPy operations with key properties
   - Provide as a dependency for the model
   - Track: does model reuse vs hallucinate?

6. **Consistency checking:**
   - Run automated checks for obvious contradictions
   - Try to prove `False` from generated axioms (timeout = safe)

### Long Term (2026+)

7. **Hybrid approach:**
   - Use SciLean or Mathlib4 for operations where available
   - Property axioms for the rest
   - Eventually: full implementations with proof automation

8. **Evaluate proof agents:**
   - Can they complete proofs given property axioms?
   - Which properties are most useful?
   - Which Python patterns translate to provable Lean?

---

## Example: Realistic PyTorch Property Axioms

What would "good" property axioms for a PyTorch subset look like?

```lean
-- Type
axiom Tensor : Type

-- Operations
axiom Tensor.add : Tensor → Tensor → Tensor
axiom Tensor.mul : Tensor → Tensor → Tensor
axiom Tensor.matmul : Tensor → Tensor → Tensor
axiom Tensor.sum : Tensor → Float
axiom Tensor.shape : Tensor → List Nat

-- Arithmetic properties
axiom add_comm : ∀ a b, Tensor.add a b = Tensor.add b a
axiom add_assoc : ∀ a b c, Tensor.add (Tensor.add a b) c = Tensor.add a (Tensor.add b c)
axiom mul_comm : ∀ a b, Tensor.mul a b = Tensor.mul b a
axiom mul_add_distrib : ∀ a b c,
  Tensor.mul a (Tensor.add b c) = Tensor.add (Tensor.mul a b) (Tensor.mul a c)

-- Shape properties
axiom add_shape_preserved : ∀ a b,
  Tensor.shape a = Tensor.shape b →
  Tensor.shape (Tensor.add a b) = Tensor.shape a

axiom matmul_shape : ∀ a b,
  Tensor.shape a = [m, n] →
  Tensor.shape b = [n, p] →
  Tensor.shape (Tensor.matmul a b) = [m, p]

-- Aggregation properties
axiom sum_add : ∀ a b,
  Tensor.shape a = Tensor.shape b →
  Tensor.sum (Tensor.add a b) = Tensor.sum a + Tensor.sum b

axiom sum_mul_scalar : ∀ a k,
  Tensor.sum (Tensor.mul a (Tensor.const k)) = k * Tensor.sum a

-- With these, we can prove derived properties!
theorem double_sum (a : Tensor) :
  Tensor.sum (Tensor.add a a) = 2.0 * Tensor.sum a := by
  rw [sum_add (by rfl)]
  ring
```

**This is probably the right approach for medium-term benchmark development.**

---

## Conclusion (SUPERSEDED BY REVISED CONCLUSION BELOW)

~~**For specification generation**: Bare axioms are fine.~~

~~**For theorem proving**: Need property axioms or concrete implementations.~~

~~**Recommendation**: Evolve toward **property axiom generation** (Approach B) as the primary strategy~~

**⚠️ This original conclusion is SUPERSEDED.** With the computation constraint added, property axioms (Approach B) are no longer viable. See REVISED CONCLUSION below.

---

## REVISED CONCLUSION (With Computation Constraint)

**Given that computation is non-negotiable:**

**Approaches A, B, and E are eliminated.** They provide no computational leverage and are incompatible with `#eval`, `rfl`, and `decide`.

**Only viable approaches:**
- ✅ **Approach C**: Concrete implementations (full computation, high effort)
- ✅ **Approach D**: Hybrid Mathlib + concrete (partial computation, practical)
- ⚠️ **Approach F**: FFI to Python (can `#eval`, but opaque for proofs)

**Recommended path forward:** **Approach D (Hybrid)** as described in `DEPMOCK.human.md`:
1. Use Mathlib where operations map cleanly
2. Implement simple operations concretely (~50-100 core operations)
3. Use FFI (Approach F) for validation/testing
4. Accept temporary `sorry` only for truly complex operations, with clear path to concrete implementation

**This eliminates property axioms as a strategy.** While property axioms enable symbolic reasoning, they fail the fundamental requirement of computational leverage. We must build real implementations.

---

# Additional Context from Original Design Document

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

## Summary: Bridging Incompatible Worlds

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
