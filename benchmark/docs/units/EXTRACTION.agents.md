# Unit Test Extraction: Semantic Similarity Problem

## Problem Summary

**Status:** 0% extraction rate on 100-sample measurement (2025-11-10)

**Root cause:** The "overlapping unit tests" in the database are linked via **shallow function matching** (any shared function call), not **semantic matching** (actually testing the same functionality).

**Example:**
- PBT: `test_tile` - tests the `Tile` operator via `core.CreateOperator('Tile', ...)`
- "Overlapping" unit tests: 111,878 tests that share utility functions like `np.random.rand`, `st.integers`
- Actual overlap: 0 - these unit tests test completely different functionality (e.g., `TypeRegistry`, `wb_type.assign()`)

**Shared functions are utilities, not target functions:**
```python
['astype', 'core.CreateOperator', 'np.asarray', 'np.random.rand', 'np.tile', 'st.integers']
```

These are numpy/hypothesis utilities, not the semantic function under test.

## Measurement Results

From `data/unit-extraction-test__n100_s0__results.json`:

```
Extraction Success Rate: 0.0%
  • Successful: 0 / 100
  • Has overlapping tests: 96 (96.0%)
  • Overlapping tests per PBT: min=0, max=474672, avg=124324.1
```

**96% of PBTs have "overlapping" unit tests, but 0% yield extractable assertions** because the unit tests are semantically unrelated.

## What We Tried

Our AST extractor is working correctly:
1. ✅ Parses unit test code with ast + tree-sitter fallback
2. ✅ Extracts assert statements
3. ✅ Filters to target function name (inferred from PBT name: "test_tile" → "tile")
4. ❌ Finds 0 assertions for target function (because unit tests don't test that function)

The extraction pipeline is sound. **The dataset linking is the problem.**

## Potential Solutions

### 1. Function Name Similarity (Cheapest)

**Idea:** Filter out utility functions, only match on "real" function calls.

**Utility function blacklist:**
```python
UTILITY_PREFIXES = ['np.', 'st.', 'torch.', 'tf.', 'pytest.', 'unittest.', 'core.']
UTILITY_MODULES = {'np', 'st', 'pytest', 'unittest', 'torch', 'tf', 'core', 'hypothesis'}

def filter_utility_functions(functions):
    """Remove common utility functions from shared function list."""
    return [f for f in functions
            if not any(f.startswith(p) for p in UTILITY_PREFIXES)
            and f.split('.')[0] not in UTILITY_MODULES]
```

**Then re-link:**
```python
shared_real_functions = filter_utility_functions(shared_functions)
if len(shared_real_functions) > 0:
    # Only consider this a match if they share non-utility functions
    link_pbt_to_unit_test(pbt, unit_test)
```

**Pros:**
- Fast, no external dependencies
- Dramatically reduces false positives
- Can run on existing database

**Cons:**
- May still have false positives (if they share a non-utility function by chance)
- Requires good heuristics for what counts as "utility"
- May miss legitimate matches if blacklist is too aggressive

**Expected improvement:** 10-30% extraction rate (speculative)

### 2. Assertion-Based Filtering (Medium)

**Idea:** Only link if unit test has assertions on a function that matches the PBT's target function.

**Implementation:**
```python
def get_asserted_functions(unit_test_code):
    """Extract functions that appear in assert statements.

    These are the functions actually being validated by the unit test.
    """
    tree = ast.parse(unit_test_code)
    asserted_funcs = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            # Extract function calls in the assertion
            for subnode in ast.walk(node.test):
                if isinstance(subnode, ast.Call):
                    func_name = extract_function_name(subnode)
                    asserted_funcs.append(func_name)

    return asserted_funcs

def link_if_asserts_match(pbt, unit_test):
    """Link only if unit test asserts on the PBT's target function."""
    target_func = infer_target_function(pbt)
    asserted = get_asserted_functions(unit_test.code)

    if target_func in asserted:
        return True

    # Also try fuzzy matching
    if any(target_func in func or func in target_func for func in asserted):
        return True

    return False
```

**Pros:**
- Very precise - unit test must actually assert on target function
- Eliminates false positives from shared utilities
- Low computational cost

**Cons:**
- May miss unit tests that test target function indirectly
- Requires good function name extraction from assertions
- Won't work if assertion is on a wrapper/helper function

**Expected improvement:** 20-40% extraction rate (speculative)

### 3. Embedding-Based Similarity (Medium Cost)

**Idea:** Use code embeddings to find semantically similar tests.

**Approach:**
```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('microsoft/codebert-base')

# For each PBT
pbt_embedding = model.encode(pbt_code)

# For each candidate unit test
unit_test_embedding = model.encode(unit_test_code)

# Compute cosine similarity
from sklearn.metrics.pairwise import cosine_similarity
similarity = cosine_similarity([pbt_embedding], [unit_test_embedding])[0][0]

# Keep if similarity > threshold (e.g., 0.7)
if similarity > 0.7:
    link_pbt_to_unit_test(pbt, unit_test)
```

**Pros:**
- Captures semantic similarity well
- No need for hand-crafted heuristics
- Works even if function names differ

**Cons:**
- Expensive: 54K PBTs × 6.3M unit tests = 340B comparisons (need indexing)
- Requires GPU for reasonable speed
- Need to choose good embedding model and similarity threshold
- May need FAISS or similar for efficient nearest-neighbor search

**Implementation notes:**
- Pre-compute embeddings for all unit tests (one-time cost)
- Use approximate nearest neighbor search (FAISS, Annoy)
- Only compute similarities for PBTs (54K lookups vs 340B comparisons)

**Expected improvement:** 40-60% extraction rate (speculative, depends on model quality)

### 4. Function Call Graph Matching (Medium)

**Idea:** Build call graphs, match based on graph similarity.

**Approach:**
```python
def extract_call_graph(code):
    """Extract which functions are called in the code."""
    tree = ast.parse(code)
    calls = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = extract_function_name(node)
            calls.add(func_name)

    return calls

def graph_similarity(pbt_calls, unit_test_calls):
    """Compute Jaccard similarity of call graphs."""
    # Remove utility functions
    pbt_real = filter_utility_functions(pbt_calls)
    unit_real = filter_utility_functions(unit_test_calls)

    if not pbt_real or not unit_real:
        return 0.0

    intersection = len(set(pbt_real) & set(unit_real))
    union = len(set(pbt_real) | set(unit_real))

    return intersection / union if union > 0 else 0.0

# Link if similarity > 0.5
if graph_similarity(pbt_calls, unit_test_calls) > 0.5:
    link_pbt_to_unit_test(pbt, unit_test)
```

**Pros:**
- More precise than just "shared functions"
- Fast to compute (simple set operations)
- Interpretable similarity score

**Cons:**
- Still heuristic-based
- Threshold tuning required
- May miss tests that use different helper functions

**Expected improvement:** 20-35% extraction rate (speculative)

### 5. Docstring/Comment Similarity (Cheap if available)

**Idea:** Match based on what the test claims to test.

**Check unit test docstrings:**
```python
def extract_test_intent(unit_test_code):
    """Extract what the test claims to test from docstring/name."""
    tree = ast.parse(unit_test_code)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # Check docstring
            docstring = ast.get_docstring(node)
            if docstring:
                return docstring.lower()

            # Check function name
            return node.name.lower()

    return ""

def matches_intent(pbt_name, unit_test_intent):
    """Check if unit test intent matches PBT name."""
    # "test_tile" matches "Test that tile operation repeats array"
    target = infer_target_function(pbt_name)  # "tile"
    return target in unit_test_intent
```

**Pros:**
- Very cheap to compute
- Explicit intent matching
- No false positives if docstrings are accurate

**Cons:**
- Depends on docstring quality (many tests lack good docs)
- Won't work if test name is generic (e.g., "test_basic")
- May need fuzzy matching for variations (tile/tiling/tiled)

**Expected improvement:** 10-20% extraction rate (depends heavily on docstring availability)

### 6. LLM-Based Classification (Expensive but Accurate)

**Idea:** Ask an LLM if unit test is relevant to PBT.

**Prompt template:**
```python
RELEVANCE_PROMPT = """
PBT (Property-Based Test):
{pbt_code}

Unit Test:
{unit_test_code}

Question: Does this unit test validate the same functionality as the PBT?

Consider:
- Do they test the same function/operation?
- Do they share the same test objective?
- Ignore shared utility functions (numpy, hypothesis, etc.)

Answer: Yes or No
Confidence: [0-100]
"""

def is_relevant_llm(pbt_code, unit_test_code):
    response = llm.generate(
        RELEVANCE_PROMPT.format(
            pbt_code=pbt_code[:1000],  # Truncate for token limits
            unit_test_code=unit_test_code[:1000]
        )
    )

    return response.startswith("Yes")
```

**Pros:**
- Most accurate semantic matching
- Can handle complex cases (wrappers, indirection, etc.)
- No hand-crafted heuristics needed

**Cons:**
- Very expensive: 54K PBTs × 6.3M unit tests × $0.001 per call = $340M+ (need filtering first!)
- Slow (API rate limits)
- Non-deterministic (need to run multiple times for confidence)
- Requires filtering to manageable subset first

**Practical approach:**
1. Use cheap methods (utility filtering, name matching) to get candidates
2. Use LLM only on top N candidates (e.g., top 10 unit tests per PBT)
3. Cost: 54K × 10 × $0.001 = $540 (manageable)

**Expected improvement:** 50-70% extraction rate (speculative, assuming good filtering first)

## Recommended Approach: Hybrid Pipeline

**Phase 1: Cheap Filtering (Fast, reduces dataset size)**
1. Filter out utility functions from shared function list
2. Only keep PBT-unit test pairs that share ≥1 non-utility function
3. Expected reduction: 6.3M → ~500K candidate unit tests

**Phase 2: Assertion-Based Validation (Medium, high precision)**
1. Extract functions asserted in unit test
2. Check if target function appears in assertions
3. Use fuzzy matching for name variations
4. Expected reduction: 500K → ~50K relevant unit tests

**Phase 3: Name/Docstring Matching (Cheap, high confidence subset)**
1. Check if unit test name or docstring mentions target function
2. Boost confidence for explicit matches
3. Expected: ~10K high-confidence matches

**Phase 4: Optional - Embedding-Based Ranking (Medium, for remaining)**
1. For remaining candidates, compute embedding similarity
2. Rank by similarity score
3. Take top K per PBT (e.g., top 5-10)

**Expected final result:** 30-50% extraction rate with high precision

## Cost-Benefit Analysis

| Approach | Computation Cost | Expected Extraction Rate | Implementation Effort |
|----------|-----------------|-------------------------|----------------------|
| Utility Filtering | Low (1 hour) | 10-30% | 1 day |
| Assertion-Based | Medium (1 day) | 20-40% | 2-3 days |
| Call Graph | Medium (1 day) | 20-35% | 2-3 days |
| Docstring Match | Low (1 hour) | 10-20% | 1 day |
| Embeddings | High (1 week + GPU) | 40-60% | 1 week |
| LLM Classification | Very High ($500+) | 50-70% | 3-5 days |
| **Hybrid (1+2+3)** | **Medium (2 days)** | **30-50%** | **3-5 days** |

## Next Steps

1. **Implement Phase 1 (Utility Filtering)** - Quick win, minimal effort
2. **Re-run measurement script** - See if we get >0% extraction rate
3. **If still low, implement Phase 2 (Assertion-Based)** - Higher precision
4. **Iterate based on results** - Add Phase 3/4 if needed

## Alternative: Give Up on Unit Tests

If even the hybrid approach yields <30% extraction rate, consider:

**Option A: Focus on other QA metrics**
- Structural faithfulness metrics (already implemented)
- Self-assessment scores (already implemented)
- Plausible property testing (already implemented)
- Unit tests become "nice to have" rather than requirement

**Option B: Runtime execution of PBTs**
- Run Hypothesis on PBTs to capture generated test cases
- Extract (input, output) pairs from Hypothesis runs
- Translate to LSpec
- More expensive but guaranteed relevant examples
- Estimated effort: 2-3 weeks

**Option C: Synthetic unit test generation**
- Use LLM to generate unit tests from PBT specification
- Validate with Hypothesis that they're consistent
- Lower trust but guaranteed extractable
- Estimated effort: 1-2 weeks

## Conclusion

The 0% extraction rate is **not a bug in the extraction pipeline** - it's a **dataset linking problem**. The overlapping unit tests are false positives based on shared utility functions.

**Recommended path forward:**
1. Try Phase 1 (utility filtering) - 1 day effort, may yield 10-30%
2. If successful, add Phase 2 (assertion-based) - 2-3 days, target 30-50%
3. If still <30%, consider alternative approaches (runtime execution, synthetic generation)

The extraction infrastructure is solid. We just need better PBT-unit test linking.
