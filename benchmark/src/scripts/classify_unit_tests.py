"""Classify unit tests by Lean transcription difficulty.

This script analyzes unit tests from the fvspec benchmark dataset and categorizes
them by difficulty of transcribing to Lean 4. It uses static analysis (regex + AST)
as the primary classification method, with automatic fallback to LLM-based
classification for low-confidence cases.

## Classification Categories

Tests are classified into 8 categories based on Lean transcription difficulty:

### 1. Pure Functional (EASIEST)
**Description**: Direct function calls with literal arguments and a single assertion.
**Examples**:
    - `assert double([1, 2]) == [2, 4]`
    - `assert add(1, 2) == 3`
**Lean Difficulty**: TRIVIAL - Can be directly translated to LSpec tests
**Detection**: Single assert with function call, no setup, no fixtures, all literal args
**Current Extraction**: ✓ Fully supported by AST extractor

### 2. Simple Parametric (EASY)
**Description**: Multiple test cases via pytest.mark.parametrize, but otherwise pure.
**Examples**:
    - `@pytest.mark.parametrize("x,y", [(1,2), (3,4)])`
**Lean Difficulty**: EASY - Just generates multiple test cases
**Detection**: Has `@pytest.mark.parametrize` decorator + Pure Functional body
**Current Extraction**: ✓ Fully supported by AST extractor

### 3. Approximate Equality (MODERATE)
**Description**: Floating-point comparisons with tolerance checking.
**Examples**:
    - `assert result == pytest.approx(3.14, abs=0.01)`
    - `assert np.isclose(a, b)`
    - `assert torch.allclose(x, y, atol=1e-6)`
**Lean Difficulty**: MODERATE - Need epsilon-based predicates in Lean
**Detection**: Uses `pytest.approx()`, `np.isclose()`, `torch.allclose()`, etc.
**Current Extraction**: ✓ Partially supported (marks as float test)
**Lean Strategy**: Use external validation with numpy.isclose semantics

### 4. Guard Conditions (MODERATE)
**Description**: Early returns or conditional logic that filters test execution.
**Examples**:
    - `if x < 0: return` before assertion
    - Boundary checks that skip invalid inputs
**Lean Difficulty**: MODERATE - Need preconditions or filtered test cases
**Detection**: `return` statements before assertions, early exits
**Current Extraction**: ✗ Not handled (test would be skipped)
**Lean Strategy**: Model as preconditions or split into separate tests

### 5. Exception Handling (MODERATE)
**Description**: Tests that expect exceptions to be raised.
**Examples**:
    - `with pytest.raises(ValueError):`
    - `pytest.raises(KeyError, lambda: dict[key])`
**Lean Difficulty**: MODERATE - Mock exceptions as `Option` or `Result`
**Detection**: `pytest.raises`, `try/except` blocks
**Current Extraction**: ✗ Not handled
**Lean Strategy**: Standard FP approaches: `Option`, `Except`, or custom error types

### 6. Stateful/Multi-step (HARD)
**Description**: Tests requiring object construction, fixtures, or multiple setup steps.
**Examples**:
    - Tests with `self.etcd.put()` then `self.etcd.get()`
    - Multiple variable assignments before assertion
    - Fixture parameters like `def test_foo(etcd):`
**Lean Difficulty**: HARD - Need state modeling, monadic style
**Detection**: `self` parameter, fixture params, multi-statement setup
**Current Extraction**: ✗ Not handled
**Lean Strategy**: Use `Id.run do` notation, model state explicitly

### 7. Library-Dependent (MODERATE)
**Description**: Heavy reliance on external libraries (torch, numpy, pandas, etc.).
**Examples**:
    - `torch.tensor([[1,2], [3,4]])`
    - `np.random.randn(100)`
    - Complex type constructors
**Lean Difficulty**: MODERATE - Use dependency mocking infrastructure
**Detection**: Common library imports and function calls
**Current Extraction**: ✗ Not handled (can't evaluate library calls)
**Lean Strategy**: Dependency autoformalization (already built)
**Note**: We've written extensive depmocking code to handle this

### 8. Untranscribable (IMPOSSIBLE)
**Description**: Tests with inherently imperative/effectful operations.
**Examples**:
    - `time.sleep(1)` - temporal behavior
    - `open('file.txt')` - file I/O
    - `requests.get(url)` - network calls
    - `random.randint()` - non-deterministic
**Lean Difficulty**: IMPOSSIBLE - Cannot be modeled in pure Lean
**Detection**: Time, I/O, network, random number generation
**Current Extraction**: ✗ Not handled (not extractable)
**Lean Strategy**: Do not attempt - these tests should be excluded

## Classification Method

### Primary: Static Analysis
The script uses regex patterns and AST analysis to detect category signals:
- **Regex**: Fast pattern matching for common idioms
- **AST**: Structural analysis (statement counts, node types, etc.)
- **Confidence**: Each pattern contributes to category confidence score

### Fallback: LLM Classification
If confidence is below threshold (default: 0.8), the script uses Claude Haiku:
- Provides test code and category descriptions
- Asks for classification with reasoning
- More accurate for edge cases and ambiguous patterns
- Optional: Can be disabled with `--no-llm` flag

## Confidence Scoring

**HIGH confidence** (>= 0.8): No LLM needed
- Single clear pattern (e.g., only `pytest.raises` → Exception Handling)
- Strong exclusionary signal (e.g., `time.sleep()` → Untranscribable)
- Multiple patterns all agree on same category

**LOW confidence** (< 0.8): Triggers LLM fallback
- Multiple category signals conflict
- Ambiguous patterns (e.g., is `torch.tensor([1,2])` library-dependent?)
- No strong signals detected (edge case)
- Borderline cases (e.g., single library call vs. complex dependency)

## Output Format

The script generates three output files:

### 1. `unit_test_classification.md` (Markdown Table)
Human-readable table with columns:
- **Category**: Classification category (1-8)
- **Count**: Number of tests in this category
- **Percentage**: % of total tests
- **Confidence**: avg/min/max confidence scores
- **LLM Usage**: How many used LLM fallback

### 2. `unit_test_classification.csv` (Spreadsheet Import)
Same data as markdown table, CSV format for Excel/Sheets

### 3. `unit_test_classification_detailed.jsonl` (Per-Test Details)
JSONL file with one test per line, including:
- `pbt_id`: Sample ID
- `test_code`: Full test source code
- `category`: Assigned category (1-8)
- `category_name`: Human-readable name
- `confidence`: Confidence score (0.0-1.0)
- `method`: "static" or "llm"
- `signals`: List of detected patterns
- `reasoning`: LLM reasoning (if used)

## Interpreting the Results

### Category Distribution
The distribution tells you:
- **High % in categories 1-2**: Good! Many tests are already extractable
- **High % in category 8**: Problematic - many tests can't be transcribed
- **High % in categories 6-7**: Challenging - need advanced Lean modeling

### Confidence Scores
- **High avg confidence**: Static heuristics work well
- **Low avg confidence**: Dataset has many edge cases, might need manual review
- **High LLM usage**: Static patterns insufficient, consider improving heuristics

### Prioritization Strategy
Based on results, prioritize:
1. **Quick wins**: Focus on categories 1-3 (already extractable or easy)
2. **Investment**: Categories 4-5 (moderate difficulty, high ROI)
3. **Advanced**: Categories 6-7 (hard but possible with current infrastructure)
4. **Exclude**: Category 8 (impossible, filter these out)

### Validation
To validate classification accuracy:
1. Sample N tests from each category
2. Manually review classifications
3. Look for patterns in misclassified tests
4. Adjust static heuristics or LLM prompt
5. Re-run classification

### Limitations
- **Static analysis**: May miss subtle patterns, especially in complex code
- **LLM classification**: Non-deterministic, may vary between runs
- **Category boundaries**: Some tests legitimately span multiple categories
- **Code quality**: Poor test code may be unclassifiable

## Usage Examples

### Basic usage (auto LLM fallback on low confidence):
```bash
uv run classify-unit-tests
```

### Disable LLM fallback (static only):
```bash
uv run classify-unit-tests --no-llm
```

### Custom confidence threshold:
```bash
uv run classify-unit-tests --confidence-threshold 0.9
```

### Sample subset for testing:
```bash
uv run classify-unit-tests --sample-size 100
```

### Verbose logging:
```bash
uv run classify-unit-tests --verbose
```

## Requirements

- `anthropic` package for LLM fallback
- `ANTHROPIC_API_KEY` environment variable (for LLM mode)
- Access to `benchmark/data/pbt_units/*.json` files

## Implementation Notes

The script is designed to be:
- **Fast**: Static analysis runs in seconds
- **Economical**: Only uses LLM when necessary (Haiku is cheap)
- **Resumable**: Can cache LLM results to avoid re-classification
- **Extensible**: Easy to add new categories or patterns
- **Debuggable**: Detailed logging shows why each test was classified

"""

import ast
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Annotated, Literal

import typer
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

DATADIR = Path(".") / "data"
TOTAL_PBTS = 60776  # Total lines in pbts.jsonl (wc -l data/pbts.jsonl)


class Category(str, Enum):
    """Test classification categories."""

    PURE_FUNCTIONAL = "pure_functional"
    SIMPLE_PARAMETRIC = "simple_parametric"
    APPROXIMATE_EQUALITY = "approximate_equality"
    GUARD_CONDITIONS = "guard_conditions"
    EXCEPTION_HANDLING = "exception_handling"
    STATEFUL_MULTISTEP = "stateful_multistep"
    LIBRARY_DEPENDENT = "library_dependent"
    UNTRANSCRIBABLE = "untranscribable"


CATEGORY_NAMES = {
    Category.PURE_FUNCTIONAL: "1. Pure Functional",
    Category.SIMPLE_PARAMETRIC: "2. Simple Parametric",
    Category.APPROXIMATE_EQUALITY: "3. Approximate Equality",
    Category.GUARD_CONDITIONS: "4. Guard Conditions",
    Category.EXCEPTION_HANDLING: "5. Exception Handling",
    Category.STATEFUL_MULTISTEP: "6. Stateful/Multi-step",
    Category.LIBRARY_DEPENDENT: "7. Library-Dependent",
    Category.UNTRANSCRIBABLE: "8. Untranscribable",
}


@dataclass
class Signal:
    """A detected pattern in test code."""

    pattern: str
    category: Category
    weight: float  # 0.0 to 1.0


@dataclass
class Classification:
    """Classification result for a single test."""

    pbt_id: str
    test_name: str
    test_code: str
    category: Category
    confidence: float
    method: Literal["static", "llm"]
    signals: list[str]
    reasoning: str | None = None


def analyze_statefulness_ast(test_code: str) -> tuple[bool, list[str]]:
    """Analyze test code using AST to detect true statefulness.

    Returns: (is_stateful, reasons)

    Stateful indicators:
    - Assignments to non-local variables
    - Multiple assignments (variable reassignments or object mutations)
    - Attribute assignments (obj.attr = ...)
    - Method calls that mutate objects (append, pop, etc.)
    - self parameter usage
    """
    try:
        tree = ast.parse(test_code)
    except SyntaxError:
        # Can't parse, fall back to heuristics
        return (False, [])

    reasons = []
    has_self = False
    assignments = []
    mutations = []

    for node in ast.walk(tree):
        # Check for self parameter
        if isinstance(node, ast.FunctionDef):
            if node.args.args and node.args.args[0].arg == "self":
                has_self = True
                reasons.append("uses self parameter")

        # Check for assignments
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments.append(target.id)
                elif isinstance(target, ast.Attribute):
                    # obj.attr = value (mutation)
                    mutations.append("attribute assignment")
                elif isinstance(target, ast.Subscript):
                    # obj[key] = value (mutation)
                    mutations.append("subscript assignment")

        # Check for augmented assignments (+=, -=, etc.)
        if isinstance(node, ast.AugAssign):
            reasons.append("augmented assignment (+=, etc.)")

        # Check for mutating method calls
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                method_name = node.func.attr
                # Common mutating methods
                mutating_methods = {
                    "append",
                    "extend",
                    "insert",
                    "remove",
                    "pop",
                    "clear",
                    "update",
                    "add",
                    "discard",
                    "sort",
                    "reverse",
                    "put",
                    "set",
                    "write",
                    "close",
                }
                if method_name in mutating_methods:
                    mutations.append(f"mutating method: {method_name}()")

    # Detect multiple assignments to same variable (state changes)
    from collections import Counter

    assignment_counts = Counter(assignments)
    reassignments = [var for var, count in assignment_counts.items() if count > 1]

    if has_self:
        return (True, reasons)

    if reassignments:
        reasons.append(f"variable reassignments: {', '.join(reassignments[:3])}")

    if mutations:
        reasons.extend(mutations[:3])  # Limit to first 3

    # Consider it stateful if there are multiple indicators
    is_stateful = len(reasons) >= 2 or (len(assignments) > 3 and len(reasons) > 0)

    return (is_stateful, reasons)


def detect_signals(test_code: str) -> list[Signal]:
    """Detect classification signals in test code using regex and AST.

    Returns list of signals with category and weight.
    """
    signals = []

    # Category 8: Untranscribable (check first - these are exclusionary)
    if re.search(r"\btime\.sleep\(", test_code):
        signals.append(Signal("time.sleep()", Category.UNTRANSCRIBABLE, 1.0))
    if re.search(r"\bdatetime\.now\(", test_code):
        signals.append(Signal("datetime.now()", Category.UNTRANSCRIBABLE, 1.0))
    if re.search(r"\bopen\(", test_code):
        signals.append(Signal("open() file I/O", Category.UNTRANSCRIBABLE, 1.0))
    if re.search(r"\brandom\.", test_code) or re.search(r"np\.random\.", test_code):
        signals.append(
            Signal("random number generation", Category.UNTRANSCRIBABLE, 1.0)
        )
    if re.search(r"\brequests\.(get|post|put)", test_code):
        signals.append(Signal("network calls", Category.UNTRANSCRIBABLE, 1.0))

    # Category 5: Exception Handling
    if re.search(r"pytest\.raises\(", test_code):
        signals.append(Signal("pytest.raises()", Category.EXCEPTION_HANDLING, 1.0))
    if re.search(r"with pytest\.raises\(", test_code):
        signals.append(Signal("with pytest.raises()", Category.EXCEPTION_HANDLING, 1.0))
    if re.search(r"\btry:", test_code) and re.search(r"\bexcept\b", test_code):
        signals.append(Signal("try/except block", Category.EXCEPTION_HANDLING, 0.8))

    # Category 3: Approximate Equality
    if re.search(r"pytest\.approx\(", test_code):
        signals.append(Signal("pytest.approx()", Category.APPROXIMATE_EQUALITY, 1.0))
    if re.search(r"np\.isclose\(", test_code):
        signals.append(Signal("np.isclose()", Category.APPROXIMATE_EQUALITY, 1.0))
    if re.search(r"torch\.allclose\(", test_code):
        signals.append(Signal("torch.allclose()", Category.APPROXIMATE_EQUALITY, 1.0))
    if re.search(r"\.isclose\(", test_code):
        signals.append(Signal(".isclose()", Category.APPROXIMATE_EQUALITY, 0.7))
    if re.search(r"\batol\s*=", test_code) or re.search(r"\brtol\s*=", test_code):
        signals.append(
            Signal("tolerance parameters", Category.APPROXIMATE_EQUALITY, 0.6)
        )

    # Category 4: Guard Conditions
    # Look for early returns
    if re.search(r"^\s+return\s*$", test_code, re.MULTILINE):
        signals.append(Signal("early return", Category.GUARD_CONDITIONS, 0.8))
    if re.search(r"if .+:\s+return", test_code):
        signals.append(
            Signal("conditional early return", Category.GUARD_CONDITIONS, 0.9)
        )

    # Category 6: Stateful/Multi-step (use AST analysis)
    is_stateful, stateful_reasons = analyze_statefulness_ast(test_code)
    if is_stateful and stateful_reasons:
        # High confidence if we have concrete AST evidence
        confidence = 0.8 if len(stateful_reasons) >= 2 else 0.7
        reason_str = "; ".join(stateful_reasons[:2])  # First 2 reasons
        signals.append(
            Signal(f"AST: {reason_str}", Category.STATEFUL_MULTISTEP, confidence)
        )
    # Check for fixture parameters (pytest specific)
    # Distinguish from pytest.mark.parametrize by looking for fixtures
    if re.search(r"def test_\w+\([^)]+\):", test_code):
        # Has parameters - could be fixtures (lower confidence)
        # Don't add if we already detected parametrize
        has_parametrize = any(s.category == Category.SIMPLE_PARAMETRIC for s in signals)
        if not has_parametrize:
            signals.append(
                Signal(
                    "function parameters (fixtures?)", Category.STATEFUL_MULTISTEP, 0.5
                )
            )

    # Category 7: Library-Dependent
    library_patterns = [
        (r"torch\.", "torch"),
        (r"np\.", "numpy"),
        (r"pd\.", "pandas"),
        (r"tf\.", "tensorflow"),
        (r"jnp\.", "jax"),
    ]
    for pattern, lib_name in library_patterns:
        if re.search(pattern, test_code):
            signals.append(
                Signal(f"{lib_name} library call", Category.LIBRARY_DEPENDENT, 0.7)
            )

    # Category 2: Simple Parametric
    if re.search(r"@pytest\.mark\.parametrize", test_code):
        signals.append(
            Signal("pytest.mark.parametrize", Category.SIMPLE_PARAMETRIC, 0.8)
        )

    # Category 1: Pure Functional (by absence of other signals)
    # This is a weak signal - only use if nothing else detected
    if len(signals) == 0:
        # Check for single assert with function call
        if re.search(r"assert \w+\(.+\)\s*==", test_code):
            signals.append(
                Signal(
                    "single assert with function call", Category.PURE_FUNCTIONAL, 0.6
                )
            )

    return signals


def classify_static(test_code: str) -> tuple[Category, float, list[str]]:
    """Classify test using static analysis.

    Returns: (category, confidence, list of signal descriptions)
    """
    signals = detect_signals(test_code)

    if not signals:
        # No signals detected - ambiguous
        return (Category.PURE_FUNCTIONAL, 0.3, ["no clear patterns detected"])

    # Untranscribable is exclusionary - if detected with high weight, that's it
    untranscribable = [s for s in signals if s.category == Category.UNTRANSCRIBABLE]
    if untranscribable and max(s.weight for s in untranscribable) >= 0.9:
        return (
            Category.UNTRANSCRIBABLE,
            max(s.weight for s in untranscribable),
            [s.pattern for s in untranscribable],
        )

    # Count votes per category, weighted
    category_scores: dict[Category, float] = defaultdict(float)
    for signal in signals:
        category_scores[signal.category] += signal.weight

    # Get top category
    top_category = max(category_scores.items(), key=lambda x: x[1])[0]
    top_score = category_scores[top_category]

    # Calculate confidence based on:
    # 1. Strength of top category
    # 2. Lack of conflicting signals
    total_score = sum(category_scores.values())
    confidence = top_score / total_score if total_score > 0 else 0.0

    # If parametrize is detected but other signals too, might be parametric + something
    # Adjust confidence down if multiple strong signals
    num_strong_signals = sum(1 for s in signals if s.weight >= 0.8)
    if num_strong_signals > 1:
        confidence *= 0.8

    signal_descriptions = [s.pattern for s in signals if s.category == top_category]

    return (top_category, confidence, signal_descriptions)


async def classify_with_llm_async(
    test_code: str, api_key: str
) -> tuple[Category, float, str]:
    """Classify test using Claude Haiku (async version).

    Returns: (category, confidence, reasoning)
    """
    try:
        import anthropic
    except ImportError:
        print(
            "Error: anthropic package not installed. Install with: uv pip install anthropic"
        )
        sys.exit(1)

    client = anthropic.AsyncAnthropic(api_key=api_key)

    prompt = f"""Classify this Python unit test into one of 8 categories based on difficulty of transcribing to Lean 4:

1. Pure Functional - Direct function call with literals, single assertion, no setup (TRIVIAL)
2. Simple Parametric - pytest.mark.parametrize but otherwise pure functional (EASY)
3. Approximate Equality - Floating point comparisons with pytest.approx/np.isclose/torch.allclose (MODERATE)
4. Guard Conditions - Early returns or conditional logic filtering test execution (MODERATE)
5. Exception Handling - pytest.raises or try/except expecting exceptions (MODERATE - mock as Option/Except)
6. Stateful/Multi-step - Requires fixtures, self parameter, or multi-step setup (HARD)
7. Library-Dependent - Heavy use of external libraries (MODERATE - we have depmocking infrastructure)
8. Untranscribable - Time-dependent, I/O, network calls, random numbers (IMPOSSIBLE)

Test code:
```python
{test_code}
```

Respond with:
1. The category number (1-8)
2. A confidence rating from 1-10 (how sure you are)
3. A brief reason (one sentence)

Format: "Category X, Confidence Y: <reason>"
Example: "Category 3, Confidence 9: Uses pytest.approx for floating point comparison"
"""

    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text.strip()

        # Parse response: "Category X, Confidence Y: reason"
        match = re.match(
            r"Category (\d+),?\s*Confidence (\d+):\s*(.+)", text, re.IGNORECASE
        )
        if not match:
            print(f"Warning: Could not parse LLM response: {text}")
            return (Category.PURE_FUNCTIONAL, 0.5, "Could not parse response")

        category_num = int(match.group(1))
        confidence_rating = int(match.group(2))
        reasoning = match.group(3)

        # Normalize confidence from 1-10 to 0.0-1.0
        confidence = confidence_rating / 10.0

        category_map = {
            1: Category.PURE_FUNCTIONAL,
            2: Category.SIMPLE_PARAMETRIC,
            3: Category.APPROXIMATE_EQUALITY,
            4: Category.GUARD_CONDITIONS,
            5: Category.EXCEPTION_HANDLING,
            6: Category.STATEFUL_MULTISTEP,
            7: Category.LIBRARY_DEPENDENT,
            8: Category.UNTRANSCRIBABLE,
        }

        category = category_map.get(category_num, Category.PURE_FUNCTIONAL)
        return (category, confidence, reasoning)

    except Exception as e:
        print(f"Warning: LLM classification failed: {e}")
        return (Category.PURE_FUNCTIONAL, 0.5, f"LLM error: {e}")


def classify_test_static(
    pbt_id: str,
    test_name: str,
    test_code: str,
) -> tuple[Category, float, list[str]]:
    """Classify a single test with static analysis only.

    Returns: (category, confidence, signals)
    """
    return classify_static(test_code)


async def classify_batch_with_llm(
    tests: list[tuple[str, str, str]],  # [(pbt_id, test_name, test_code), ...]
    api_key: str,
    parallelism: int,
    verbose: bool,
    progress_callback=None,
) -> list[tuple[Category, float, str]]:
    """Classify a batch of tests with LLM in parallel using trio.

    Returns: List of (category, confidence, reasoning) tuples, same order as input
    progress_callback: Optional callback(completed_count) called after each classification
    """
    import trio

    results = [None] * len(tests)
    completed_count = 0
    count_lock = trio.Lock()

    async def classify_one(index: int, test_code: str):
        """Classify a single test and store result."""
        nonlocal completed_count
        try:
            category, confidence, reasoning = await classify_with_llm_async(
                test_code, api_key
            )
            results[index] = (category, confidence, reasoning)
        except Exception as e:
            if verbose:
                print(f"Warning: LLM classification failed for test {index}: {e}")
            results[index] = (Category.PURE_FUNCTIONAL, 0.5, f"LLM error: {e}")
        finally:
            # Update progress
            async with count_lock:
                completed_count += 1
                if progress_callback:
                    progress_callback(completed_count)

    # Use trio's semaphore to limit parallelism
    semaphore = trio.Semaphore(parallelism)

    async def limited_classify(index: int, test_code: str):
        async with semaphore:
            await classify_one(index, test_code)

    async with trio.open_nursery() as nursery:
        for i, (_, _, test_code) in enumerate(tests):
            nursery.start_soon(limited_classify, i, test_code)

    return results  # type: ignore


def classify_test(
    pbt_id: str,
    test_name: str,
    test_code: str,
    confidence_threshold: float,
    use_llm: bool,
    api_key: str | None,
    verbose: bool,
) -> Classification:
    """Classify a single test with automatic LLM fallback (synchronous version).

    Note: This is kept for compatibility but won't be used in the batched flow.
    """
    # Try static analysis first
    category, confidence, signals = classify_static(test_code)

    method: Literal["static", "llm"] = "static"
    reasoning = None

    # Fallback to LLM if confidence is low
    if use_llm and confidence < confidence_threshold:
        if not api_key:
            if verbose:
                print(
                    f"Warning: Low confidence ({confidence:.2f}) for {test_name} "
                    "but no API key available for LLM fallback"
                )

    return Classification(
        pbt_id=pbt_id,
        test_name=test_name,
        test_code=test_code,
        category=category,
        confidence=confidence,
        method=method,
        signals=signals,
        reasoning=reasoning,
    )


def stream_unit_tests(
    pbts_jsonl: Path,
    sample_size: int | None,
    ranseed: int,
    verbose: bool,
    progress_callback=None,
):
    """Stream unit tests from pbts.jsonl line by line with optional random sampling.

    Yields: (pbt_id, test_name, test_code, has_units) tuples

    If sample_size is specified, uses early-stopping reservoir sampling to collect exactly
    sample_size tests (or fewer if not enough exist) without scanning the entire file.
    Otherwise, yields all tests found.

    Early stopping: Stops scanning after finding 10x the requested sample size to ensure
    good randomness while keeping performance fast for small samples.

    This avoids loading the entire 116GB file into memory.
    progress_callback: Optional function to call with (line_count, pbts_without_units) for progress updates
    """
    if not pbts_jsonl.exists():
        raise FileNotFoundError(f"{pbts_jsonl} not found")

    import random

    rng = random.Random(ranseed)

    # Reservoir for sampling
    reservoir: list[tuple[str, str, str]] = []
    test_count = 0
    line_count = 0
    pbts_without_units = 0

    # Early stopping: collect 10x sample_size tests then stop (ensures good randomness)
    # This makes -n 10 very fast while still being random
    early_stop_multiplier = 10
    early_stop_threshold = sample_size * early_stop_multiplier if sample_size else None

    with open(pbts_jsonl) as f:
        for line in f:
            line_count += 1

            # Early stopping for sampling: stop after collecting enough tests
            if early_stop_threshold and test_count >= early_stop_threshold:
                if verbose:
                    print(
                        f"Early stopping: collected {test_count} tests (target: {sample_size})"
                    )
                break

            # Parse JSON line
            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                if verbose:
                    print(f"Warning: Could not parse line {line_count}: {e}")
                continue

            # Check if this PBT has unit tests
            has_overlapping_tests = (
                "overlapping_tests" in data and data["overlapping_tests"]
            )

            if not has_overlapping_tests:
                pbts_without_units += 1
                if progress_callback:
                    progress_callback(line_count, pbts_without_units)
                continue

            pbt_id = str(data.get("id", "unknown"))
            has_units = False

            for overlap in data["overlapping_tests"]:
                if "unit_tests" not in overlap:
                    continue

                for unit_test in overlap["unit_tests"]:
                    if "code" in unit_test and "test_name" in unit_test:
                        has_units = True
                        test_data = (pbt_id, unit_test["test_name"], unit_test["code"])

                        if sample_size:
                            # Reservoir sampling
                            if test_count < sample_size:
                                reservoir.append(test_data)
                            else:
                                # Randomly replace elements with decreasing probability
                                j = rng.randint(0, test_count)
                                if j < sample_size:
                                    reservoir[j] = test_data
                            test_count += 1

                            # Check early stop threshold within inner loop too
                            if (
                                early_stop_threshold
                                and test_count >= early_stop_threshold
                            ):
                                break
                        else:
                            # No sampling, yield immediately
                            test_count += 1
                            yield test_data

                # Break out of overlap loop if we hit early stop
                if (
                    sample_size
                    and early_stop_threshold
                    and test_count >= early_stop_threshold
                ):
                    break

            if not has_units:
                pbts_without_units += 1

            # Update progress for this PBT line
            if progress_callback:
                progress_callback(line_count, pbts_without_units)

    # If we were sampling, shuffle and yield the reservoir
    if sample_size:
        rng.shuffle(reservoir)
        for test_data in reservoir:
            yield test_data

    if verbose:
        print(f"Finished processing {line_count} lines, found {test_count} tests total")
        if sample_size:
            print(f"Sampled {len(reservoir)} tests (requested: {sample_size})")
        print(f"PBTs without unit tests: {pbts_without_units}")


def generate_summary_outputs(
    category_counts: Counter[Category],
    category_confidences: dict[Category, list[float]],
    category_llm_usage: Counter[Category],
    total: int,
    confidence_threshold: float,
    output_dir: Path,
    verbose: bool,
) -> None:
    """Generate markdown table and CSV summary outputs from aggregated stats."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate markdown table
    md_path = output_dir / "unit_test_classification.md"
    with open(md_path, "w") as f:
        f.write("# Unit Test Classification Results\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write(f"Total tests analyzed: {total}\n")
        f.write(f"Confidence threshold: {confidence_threshold}\n\n")

        f.write("| Category | Count | Percentage | Avg Confidence | LLM Usage |\n")
        f.write("|----------|-------|------------|----------------|----------|\n")

        for category_key in Category:
            count = category_counts[category_key]
            pct = (count / total * 100) if total > 0 else 0
            confidences = category_confidences[category_key]
            avg_conf = sum(confidences) / len(confidences) if confidences else 0
            llm_usage = category_llm_usage[category_key]

            f.write(
                f"| {CATEGORY_NAMES[category_key]} | {count} | {pct:.1f}% | "
                f"{avg_conf:.2f} | {llm_usage} ({llm_usage / count * 100 if count > 0 else 0:.0f}%) |\n"
            )

    if verbose:
        print(f"Wrote markdown table to {md_path}")

    # Generate CSV
    csv_path = output_dir / "unit_test_classification.csv"
    with open(csv_path, "w") as f:
        f.write("Category,Count,Percentage,AvgConfidence,LLMUsage,LLMUsagePercent\n")
        for category_key in Category:
            count = category_counts[category_key]
            pct = (count / total * 100) if total > 0 else 0
            confidences = category_confidences[category_key]
            avg_conf = sum(confidences) / len(confidences) if confidences else 0
            llm_usage = category_llm_usage[category_key]
            llm_pct = (llm_usage / count * 100) if count > 0 else 0

            f.write(
                f'"{CATEGORY_NAMES[category_key]}",{count},{pct:.1f},{avg_conf:.2f},'
                f"{llm_usage},{llm_pct:.0f}\n"
            )

    if verbose:
        print(f"Wrote CSV to {csv_path}")


app = typer.Typer()


@app.command()
def main(
    no_llm: Annotated[
        bool, typer.Option(help="Disable LLM fallback (static analysis only)")
    ] = False,
    confidence_threshold: Annotated[
        float, typer.Option(help="Confidence threshold for LLM fallback")
    ] = 0.75,
    sample_size: Annotated[
        int | None,
        typer.Option(
            "-n",
            "--sample-size",
            help="Sample N tests for testing (default: all tests)",
        ),
    ] = None,
    ranseed: Annotated[
        int, typer.Option(help="Random seed for sampling (default: 0)")
    ] = 0,
    parallelism: Annotated[
        int, typer.Option(help="Number of parallel LLM calls (default: 10)")
    ] = 10,
    verbose: Annotated[bool, typer.Option(help="Enable verbose logging")] = False,
    output_dir: Annotated[Path, typer.Option(help="Output directory")] = Path(".")
    / "data",
) -> None:
    """Classify unit tests by Lean transcription difficulty."""
    print("Unit Test Classification")
    print("=" * 60)
    print(f"Confidence threshold: {confidence_threshold}")
    print(f"LLM fallback: {'disabled' if no_llm else 'enabled'}")
    if not no_llm:
        print(f"LLM parallelism: {parallelism}")
    if sample_size:
        print(f"Sample size: {sample_size} tests")
        print(f"Random seed: {ranseed}")
    print()

    # Get API key if LLM is enabled
    api_key = None
    if not no_llm:
        # Try to load from .env in monorepo root (two levels up from benchmark/data/)
        from dotenv import load_dotenv

        # Try multiple possible locations
        possible_env_paths = [
            Path("..") / ".env",  # From benchmark/
            Path("../..") / ".env",  # From benchmark/src/
            Path.cwd() / ".env",  # Current directory
            Path.cwd().parent / ".env",  # Parent of current
        ]

        for env_path in possible_env_paths:
            if env_path.exists():
                load_dotenv(env_path)
                if verbose:
                    print(f"Loaded .env from {env_path}")
                break

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print(
                "Warning: ANTHROPIC_API_KEY not set. LLM fallback will not work for low-confidence cases."
            )
            print(
                f"  Searched for .env in: {', '.join(str(p) for p in possible_env_paths)}"
            )
            print("  Tip: Create a .env file with ANTHROPIC_API_KEY=your_key")
            print()

    # Stream unit tests from pbts.jsonl
    pbts_jsonl = DATADIR / "pbts.jsonl"
    if not pbts_jsonl.exists():
        print(f"Error: {pbts_jsonl} not found")
        raise typer.Exit(1)

    print(f"Streaming unit tests from {pbts_jsonl}...")
    if sample_size:
        print(f"Will stop after {sample_size} tests")
    print()

    # Classify each test as we stream, writing results incrementally
    print("Classifying tests...")

    # Open detailed JSONL output for streaming writes
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "unit_test_classification_detailed.jsonl"

    # Track stats for summary (much smaller memory footprint)
    category_counts: Counter[Category] = Counter()
    category_confidences: dict[Category, list[float]] = defaultdict(list)
    category_llm_usage: Counter[Category] = Counter()
    llm_count = 0
    test_count = 0

    # Setup progress bar with rich
    pbts_without_units = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        # Two progress bars: one for samples, one for unit test classifications
        # For sample scanning: if we have sample_size, estimate we'll scan ~10x that many samples
        # Otherwise, scan all samples
        scan_estimate = (sample_size * 10) if sample_size else TOTAL_PBTS
        sample_task = progress.add_task(
            "[cyan]Scanning samples for tests",
            total=scan_estimate,
        )

        # For test task: use 0 as initial total if no sample_size, we'll update it dynamically
        test_task = progress.add_task(
            "[green]Classifying unit tests",
            total=sample_size if sample_size else 0,
        )

        # Progress callback to update sample scanning progress
        def update_sample_progress(line_count: int, samples_no_units: int):
            nonlocal pbts_without_units
            pbts_without_units = samples_no_units
            # Update every time - sample reading is fast, this won't slow us down
            progress.update(
                sample_task,
                completed=line_count,
                description=f"[cyan]Scanning samples for tests ({samples_no_units} skipped)",
            )

        # Collect all tests first, then process in batches
        all_tests = list(
            stream_unit_tests(
                pbts_jsonl,
                sample_size,
                ranseed,
                verbose,
                progress_callback=update_sample_progress,
            )
        )

        test_count = len(all_tests)

        # Phase 1: Static classification for all tests
        progress.update(
            test_task,
            completed=0,
            total=test_count,
            description=f"[green]Static analysis (0/{test_count})",
        )

        static_results = []
        for i, (pbt_id, test_name, test_code) in enumerate(all_tests):
            category, confidence, signals = classify_static(test_code)
            static_results.append(
                (pbt_id, test_name, test_code, category, confidence, signals)
            )

            # Update progress every 10 tests
            if (i + 1) % 10 == 0 or (i + 1) == test_count:
                progress.update(
                    test_task,
                    completed=i + 1,
                    description=f"[green]Static analysis ({i + 1}/{test_count})",
                )

        # Phase 2: Identify tests that need LLM (low confidence)
        needs_llm = []
        needs_llm_indices = []
        for i, (
            pbt_id,
            test_name,
            test_code,
            category,
            confidence,
            signals,
        ) in enumerate(static_results):
            if not no_llm and confidence < confidence_threshold and api_key:
                needs_llm.append((pbt_id, test_name, test_code))
                needs_llm_indices.append(i)

        # Phase 3: Batch process LLM classifications in parallel
        llm_results = []
        if needs_llm:
            import trio

            # Add an LLM progress task
            llm_task = progress.add_task(
                "[yellow]LLM classifications",
                total=len(needs_llm),
            )

            def update_llm_progress(completed: int):
                """Update progress bar from trio callback."""
                progress.update(
                    llm_task,
                    completed=completed,
                    description=f"[yellow]LLM classifications ({completed}/{len(needs_llm)})",
                )

            if verbose:
                print(
                    f"\nProcessing {len(needs_llm)} tests with LLM (parallelism={parallelism})..."
                )

            llm_results = trio.run(
                classify_batch_with_llm,
                needs_llm,
                api_key,
                parallelism,
                verbose,
                update_llm_progress,
            )

            # Remove the LLM task when done
            progress.remove_task(llm_task)

        # Phase 4: Merge results and write output
        with open(jsonl_path, "w") as jsonl_file:
            llm_idx = 0
            for i, (
                pbt_id,
                test_name,
                test_code,
                category,
                confidence,
                signals,
            ) in enumerate(static_results):
                method: Literal["static", "llm"] = "static"
                reasoning = None

                # Check if this test used LLM
                if i in needs_llm_indices:
                    category, confidence, reasoning = llm_results[llm_idx]
                    method = "llm"
                    llm_count += 1
                    llm_idx += 1

                # Write to JSONL
                record = {
                    "pbt_id": pbt_id,
                    "test_name": test_name,
                    "category": category,
                    "category_name": CATEGORY_NAMES[category],
                    "confidence": confidence,
                    "method": method,
                    "signals": signals,
                    "reasoning": reasoning,
                    "test_code": test_code,
                }
                jsonl_file.write(json.dumps(record) + "\n")

                # Update stats
                category_counts[category] += 1
                category_confidences[category].append(confidence)
                if method == "llm":
                    category_llm_usage[category] += 1

                # Update progress bar
                if (i + 1) % 10 == 0 or (i + 1) == test_count:
                    progress.update(
                        test_task,
                        completed=i + 1,
                        total=test_count,
                        description=f"[green]Writing results ({llm_count} used LLM)",
                    )

        # Final update to ensure sample scanning bar shows complete state
        # Mark as complete with actual line count scanned
        progress.update(
            sample_task,
            completed=scan_estimate,  # Complete the bar visually
            description=f"[cyan]Scanned samples ({pbts_without_units} skipped)",
        )
        progress.update(
            test_task,
            completed=test_count,
            total=test_count if not sample_size else sample_size,
            description=f"[green]Classifying unit tests ({test_count} total, {llm_count} LLM)",
        )

    print()
    print(f"Classified {test_count} tests")
    print(f"LLM fallback used: {llm_count} times ({llm_count / test_count * 100:.1f}%)")
    print(f"Samples without unit tests: {pbts_without_units} skipped")
    print()

    # Generate summary outputs (markdown and CSV) from aggregated stats
    print("Generating summary outputs...")
    generate_summary_outputs(
        category_counts,
        category_confidences,
        category_llm_usage,
        test_count,
        confidence_threshold,
        output_dir,
        verbose,
    )

    print()
    print("Done! Files written:")
    print(f"  - {output_dir / 'unit_test_classification.md'}")
    print(f"  - {output_dir / 'unit_test_classification.csv'}")
    print(f"  - {output_dir / 'unit_test_classification_detailed.jsonl'}")


if __name__ == "__main__":
    app()
