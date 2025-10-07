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
