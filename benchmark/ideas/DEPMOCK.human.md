# Dependency Mocking: Computable Approaches

**Constraint**: Computing is mandatory. We need `#eval`, `rfl`, `decide`, and other computation-based tactics to work.

**Context**: When translating Python property-based tests (using NumPy/PyTorch) to Lean 4, we must "mock" these libraries. Unlike specification-only approaches, we require that proof agents can actually *compute* with these mocks during theorem proving.

---

## Viable Approaches (Computation Required)

### Approach C: Concrete Implementations

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
- ✅ Can test generated code against Python behavior

**Cons:**
- ❌ Enormous implementation effort (years of work for full NumPy/PyTorch)
- ❌ Shape polymorphism requires dependent types (very complex)
- ❌ Floating-point semantics are underspecified
- ❌ Still need proofs of basic properties (commutativity, etc.)
- ❌ Implementation details leak into proofs

**Feasibility:**
- Full implementation: Not feasible short-term
- Minimal subset: Tractable - ~50-100 core operations
- Strategy: Start with most common operations from scraped tests

---

### Approach D: Hybrid (Mathlib + Concrete Implementations)

Use Mathlib for simple operations (vectors, matrices), implement the rest concretely where needed.

```lean
-- Use Mathlib's matrices for 2D operations (these compute!)
import Mathlib.Data.Matrix.Basic

def Matrix.add := Matrix.add  -- from Mathlib

-- Implement simpler tensor operations concretely
structure Tensor1D where
  data : Array Float

def Tensor1D.add (a b : Tensor1D) : Tensor1D :=
  ⟨Array.zipWith (· + ·) a.data b.data⟩

-- For complex operations, use FFI or stub with sorry (temporarily)
def Tensor.conv2d (x : Tensor) (kernel : Tensor) : Tensor := sorry
```

**Pros:**
- ✅ Best of both worlds where possible
- ✅ Mathlib gives proven foundations that compute
- ✅ Can compute with Mathlib operations
- ✅ Pragmatic - implement only what we need
- ✅ Incrementally expand coverage

**Cons:**
- ❌ Requires identifying the boundary (what uses Mathlib vs custom?)
- ❌ Mathlib matrices are 2D only (tensors are n-dimensional)
- ❌ Complex operations still need work
- ❌ Mixing styles might confuse models

**Feasibility:** Most practical short-term approach.

---

### Approach F: FFI to Python (Shallow Embedding)

Use Lean's C FFI to call actual NumPy/PyTorch libraries.

```lean
@[extern "python_array_add"]
opaque Array.add : Array → Array → Array

-- Can execute: #eval Array.add myArray1 myArray2
-- But proofs need property axioms:
axiom add_comm : ∀ (a b : Array), Array.add a b = Array.add b a
```

**Pros:**
- ✅ Real implementations - exact Python semantics
- ✅ Can execute and test with `#eval`
- ✅ Behavioral validation possible
- ✅ Could do "oracle testing" (compare Lean execution vs Python)
- ✅ No need to reimplement complex operations
- ✅ Perfect for testing/validation phase

**Cons:**
- ❌ FFI calls are opaque to the prover (can `#eval` but `rfl` won't reduce)
- ❌ Requires complex Python/C/Lean interop layer
- ❌ Doesn't help with proof automation (still need property axioms)
- ❌ Breaks proof-carrying code guarantees
- ❌ Can't use `decide` tactic (needs reduction)

**Feasibility:** Interesting hybrid - computable for testing, but needs property axioms for proving.

---

## Comparison: What Can Compute?

| Approach | `#eval` | `rfl` | `decide` | Proof Tactics | Implementation Effort |
|----------|---------|-------|----------|---------------|---------------------|
| **C: Concrete** | ✅ | ✅ | ✅ | ✅ Max leverage | ❌ Years (full), ✅ Weeks (subset) |
| **D: Hybrid** | ✅ | ✅ (partial) | ✅ (partial) | ✅ Good leverage | ✅ Practical |
| **F: FFI** | ✅ | ❌ | ❌ | ⚠️ Needs axioms | ✅ Low (interop setup) |

---

## Recommendations

### Short Term: Approach D (Hybrid)

**Strategy:**
1. Use Mathlib for operations that map cleanly:
   - Vectors, matrices (2D)
   - Basic arithmetic, norms
   - Linear algebra where available

2. Implement simple operations concretely:
   - Array indexing, slicing
   - Element-wise operations (add, mul, abs)
   - Reductions (sum, max, min)
   - Shape queries

3. Use FFI (Approach F) for validation:
   - Compare concrete implementations against Python
   - Catch semantic mismatches early

4. Accept `sorry` for complex operations temporarily:
   - conv2d, attention, autograd
   - Document clearly: "TODO: needs implementation"

**Coverage goal:** 80% of common operations computable within 6 months.

---

### Medium Term: Expand Concrete Coverage

**Priorities based on scraped test frequency:**
- NumPy: broadcasting, advanced indexing, matmul
- PyTorch: tensor creation, basic autograd operations
- Shape manipulation: reshape, transpose, concatenate

**Approach:**
- Build Lean implementations incrementally
- Property-test against Python (via FFI oracle)
- Prove basic properties (commutativity, associativity)

---

### Long Term: Full Computational Semantics

**Goals:**
- All common operations compute
- Type-level shape tracking (dependent types)
- Proven properties for algebraic laws
- Integration with proof automation (grind, aesop)

**Dependencies:**
- Lean ecosystem maturity (SciLean project)
- Mathlib tensor support
- Improved dependent type ergonomics

---

## Open Questions for Discussion

1. **Minimal viable subset:** Which 50-100 operations cover 80% of scraped tests?
   - Need to analyze `data/scrapedtests.json` dependency frequencies

2. **Shape tracking:** How to balance expressiveness vs. complexity?
   - Option A: Erase shapes (simpler, less type safety)
   - Option B: Dependent types for shapes (complex, maximum safety)
   - Option C: Separate shape validation from computation

3. **Floating-point semantics:** How precise do we need to be?
   - Exact IEEE 754? (hard!)
   - Real numbers with rounding? (Mathlib support?)
   - Abstract float type with axioms? (easier, less precise)

4. **FFI for validation:** Worth the engineering effort?
   - Build Python-Lean bridge for oracle testing?
   - Or just trust our implementations and test manually?

5. **mvcgen integration:** How do imperative implementations interact with Hoare logic?
   - Can we `#eval` imperative programs in `do` notation? Answer: yes. 
   - Do we need separate computational vs. specification versions?

---

## Next Steps

**Before next meeting:**
1. Analyze dependency frequency in `scrapedtests.json`
2. Draft minimal API (50-100 operations)
3. Prototype 3-5 operations concretely to test approach
4. Estimate implementation timeline

**Decision needed:**
- Commit to Hybrid approach (D) as baseline?
- Allocate resources for concrete implementations?
- Investigate FFI feasibility for validation?
