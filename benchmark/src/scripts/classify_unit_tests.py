"""Classify unit tests by Lean transcription difficulty.

This script analyzes unit tests from the fvspec benchmark dataset and categorizes
them by difficulty of transcribing to Lean 4. It uses static analysis (regex + AST)
as the primary classification method, with automatic fallback to LLM-based
classification for low-confidence cases.

## Classification Categories

Tests are classified into 12 categories organized into 4 tiers based on Lean transcription difficulty.
This is a multi-label classification system: tests have a primary category (highest difficulty tier)
and optional secondary tags representing orthogonal concerns.

### Tier 1: Simple (Easiest to Transcribe)

**1.1 Pure Functional (No Deps)** - Direct function calls with literal arguments, no libraries
- Example: `assert double([1, 2]) == [2, 4]`
- Lean Difficulty: TRIVIAL
- Detection: Single assert, no mutations, no library imports

**1.2 Simple Parametric (No Deps)** - pytest.mark.parametrize but no libraries
- Example: `@pytest.mark.parametrize("x,y", [(1,2), (3,4)])`
- Lean Difficulty: EASY
- Detection: Has parametrize decorator but no library dependencies

**1.3 Numeric Pure Functional** - Float comparisons with tolerance but pure functional
- Example: `assert result == pytest.approx(3.14, abs=0.01)`
- Lean Difficulty: EASY
- Detection: pytest.approx, np.isclose, torch.allclose but no state/libraries

### Tier 2: Moderate (Needs Lean Expertise)

**2.1 Library-Dependent Pure** - Uses torch/numpy/pandas but purely functional
- Example: `assert torch.tensor([1, 2]).sum() == 3`
- Lean Difficulty: MODERATE
- Detection: Library imports but no mutations
- Strategy: Use dependency autoformalization infrastructure

**2.2 Library-Dependent Parametric** - Parametrize + libraries
- Example: Parametrized test with numpy arrays
- Lean Difficulty: MODERATE
- Detection: Both parametrize and library imports

**2.3 Structural Validation** - isinstance/hasattr/type checks
- Example: `assert isinstance(result, dict)`
- Lean Difficulty: MODERATE
- Detection: Type checking functions

### Tier 3: Complex (Significant Transcription Effort)

**3.1 Stateful Sequential** - Multiple assignments, mutations, but no libraries
- Example: `x = []; x.append(1); assert len(x) == 1`
- Lean Difficulty: HARD
- Detection: AST analysis finds mutations, reassignments
- Strategy: Use Id.run do notation, model state explicitly

**3.2 Complex Control Flow** - Loops + conditions, exception handling
- Example: `with pytest.raises(ValueError):`
- Lean Difficulty: HARD
- Detection: Loops, nested conditions, try/except blocks
- Strategy: Mock exceptions as Option/Except types

**3.3 Multi-Step Integration** - Multiple function calls, setup/teardown
- Example: Tests with fixture setup and multiple operations
- Lean Difficulty: HARD
- Detection: Multiple function calls, pytest fixtures

### Tier 4: Very Hard (May Need Axioms/Sorry)

**4.1 Stateful + Library-Dependent** - Mutations + torch/numpy/etc
- Example: `tensor.zero_(); assert tensor.sum() == 0`
- Lean Difficulty: VERY HARD
- Detection: Both library imports and mutations

**4.2 Concurrent/Async** - async/await, threading, multiprocessing
- Example: `async def test_foo(): await bar()`
- Lean Difficulty: VERY HARD
- Detection: async/await keywords, threading imports

**4.3 Meta/Reflection** - getattr/setattr/eval/__dict__ manipulation
- Example: `setattr(obj, 'field', value)`
- Lean Difficulty: VERY HARD
- Detection: Reflection APIs

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
- **Category**: Classification category (1.1-4.3, 12 total)
- **Count**: Number of tests with this as primary category
- **Percentage**: % of total tests
- **Confidence**: Average confidence for primary classification
- **LLM Usage**: How many used LLM fallback

### 2. `unit_test_classification.csv` (Spreadsheet Import)
Same data as markdown table, CSV format for Excel/Sheets

### 3. `unit_test_classification_detailed.jsonl` (Per-Test Details)
JSONL file with one test per line, including:
- `pbt_id`: Sample ID
- `test_code`: Full test source code
- `primary_category`: Primary assigned category (enum value)
- `primary_category_name`: Human-readable name (e.g., "1.1 Pure Functional (No Deps)")
- `primary_confidence`: Confidence score for primary (0.0-1.0)
- `tags`: List of secondary categories (enum values)
- `tag_names`: Human-readable names for tags
- `tag_confidences`: Dict mapping tag names to confidence scores
- `method`: "static" or "llm"
- `signals`: List of detected patterns
- `reasoning`: LLM reasoning (if used)

## Interpreting the Results

### Category Distribution
The distribution tells you:
- **High % in Tier 1 (1.1-1.3)**: Good! Many tests are simple and directly transcribable
- **High % in Tier 2 (2.1-2.3)**: Moderate - need library mocking but feasible
- **High % in Tier 3 (3.1-3.3)**: Challenging - need advanced Lean modeling
- **High % in Tier 4 (4.1-4.3)**: Very hard - may need axioms or manual intervention

### Multi-Label Tags
Tests can have multiple tags indicating orthogonal concerns:
- A test might be "3.1 Stateful Sequential" (primary) + "2.3 Structural Validation" (tag)
- Tags help identify tests that cross multiple difficulty dimensions
- Use tags to filter for specific patterns (e.g., all tests with structural validation)

### Confidence Scores
- **High avg confidence**: Static heuristics work well
- **Low avg confidence**: Dataset has many edge cases, might need manual review
- **High LLM usage**: Static patterns insufficient, consider improving heuristics

### Prioritization Strategy
Based on results, prioritize:
1. **Quick wins**: Focus on Tier 1 (1.1-1.3) - simple and directly transcribable
2. **Investment**: Tier 2 (2.1-2.3) - moderate difficulty, high ROI with depmocking
3. **Advanced**: Tier 3 (3.1-3.3) - hard but possible with state modeling
4. **Research**: Tier 4 (4.1-4.3) - very hard, may need axioms or advanced techniques

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

# Classification thresholds and parameters
DEFAULT_CONFIDENCE_THRESHOLD = 0.75  # Default for LLM fallback
DEFAULT_TAG_THRESHOLD = 0.5  # Minimum score for multi-label tags
DEFAULT_LLM_FALLBACK_CONFIDENCE = 0.5  # Confidence when LLM fails/can't parse
EARLY_STOP_MULTIPLIER = 10  # Stop after N*sample_size tests scanned

# Signal detection confidence weights (used in detect_signals)
CONFIDENCE_STATEFUL_STRONG = 0.85  # Multiple statefulness signals
CONFIDENCE_STATEFUL_MODERATE = 0.75  # Single statefulness signal
CONFIDENCE_LIBRARY_PURE = 0.75  # Library usage but pure functional
CONFIDENCE_CONTROL_FLOW = 0.75  # Exception handling, loops, conditions
CONFIDENCE_NUMERIC = 0.8  # Numeric/float approximation patterns
CONFIDENCE_PARAMETRIC_NO_DEPS = 0.85  # pytest.mark.parametrize without libraries
CONFIDENCE_PARAMETRIC_WITH_DEPS = 0.8  # pytest.mark.parametrize with libraries
CONFIDENCE_PURE_FUNCTIONAL = 0.8  # Simple pure functional patterns
CONFIDENCE_PURE_FUNCTIONAL_AST = 0.75  # AST-confirmed no mutations
CONFIDENCE_STRUCTURAL = 0.7  # isinstance/hasattr/type checks
CONFIDENCE_MULTI_STEP = 0.7  # Multiple function calls
CONFIDENCE_ASYNC = 0.9  # async/await/threading patterns
CONFIDENCE_META = 0.9  # Reflection/meta programming
CONFIDENCE_FALLBACK = 0.6  # When no signals detected


class Category(str, Enum):
    """Test classification categories with multi-label support.

    Categories are organized into tiers by transcription difficulty.
    Tests can have multiple categories (primary + tags).
    """

    # Tier 1: Simple (easiest to transcribe)
    PURE_FUNCTIONAL_NO_DEPS = "pure_functional_no_deps"
    SIMPLE_PARAMETRIC_NO_DEPS = "simple_parametric_no_deps"
    NUMERIC_PURE_FUNCTIONAL = "numeric_pure_functional"

    # Tier 2: Moderate (needs some Lean expertise)
    LIBRARY_DEPENDENT_PURE = "library_dependent_pure"
    LIBRARY_DEPENDENT_PARAMETRIC = "library_dependent_parametric"
    STRUCTURAL_VALIDATION = "structural_validation"

    # Tier 3: Complex (significant transcription effort)
    STATEFUL_SEQUENTIAL = "stateful_sequential"
    COMPLEX_CONTROL_FLOW = "complex_control_flow"
    MULTI_STEP_INTEGRATION = "multi_step_integration"

    # Tier 4: Very Hard (may need axioms/sorry)
    STATEFUL_LIBRARY_DEPENDENT = "stateful_library_dependent"
    CONCURRENT_ASYNC = "concurrent_async"
    META_REFLECTION = "meta_reflection"


CATEGORY_TIERS = {
    Category.PURE_FUNCTIONAL_NO_DEPS: 1,
    Category.SIMPLE_PARAMETRIC_NO_DEPS: 1,
    Category.NUMERIC_PURE_FUNCTIONAL: 1,
    Category.LIBRARY_DEPENDENT_PURE: 2,
    Category.LIBRARY_DEPENDENT_PARAMETRIC: 2,
    Category.STRUCTURAL_VALIDATION: 2,
    Category.STATEFUL_SEQUENTIAL: 3,
    Category.COMPLEX_CONTROL_FLOW: 3,
    Category.MULTI_STEP_INTEGRATION: 3,
    Category.STATEFUL_LIBRARY_DEPENDENT: 4,
    Category.CONCURRENT_ASYNC: 4,
    Category.META_REFLECTION: 4,
}


CATEGORY_NAMES = {
    Category.PURE_FUNCTIONAL_NO_DEPS: "1.1 Pure Functional (No Deps)",
    Category.SIMPLE_PARAMETRIC_NO_DEPS: "1.2 Simple Parametric (No Deps)",
    Category.NUMERIC_PURE_FUNCTIONAL: "1.3 Numeric Pure Functional",
    Category.LIBRARY_DEPENDENT_PURE: "2.1 Library-Dependent Pure",
    Category.LIBRARY_DEPENDENT_PARAMETRIC: "2.2 Library-Dependent Parametric",
    Category.STRUCTURAL_VALIDATION: "2.3 Structural Validation",
    Category.STATEFUL_SEQUENTIAL: "3.1 Stateful Sequential",
    Category.COMPLEX_CONTROL_FLOW: "3.2 Complex Control Flow",
    Category.MULTI_STEP_INTEGRATION: "3.3 Multi-Step Integration",
    Category.STATEFUL_LIBRARY_DEPENDENT: "4.1 Stateful + Library-Dependent",
    Category.CONCURRENT_ASYNC: "4.2 Concurrent/Async",
    Category.META_REFLECTION: "4.3 Meta/Reflection",
}


@dataclass
class Signal:
    """A detected pattern in test code."""

    pattern: str
    category: Category
    weight: float  # 0.0 to 1.0


@dataclass
class Classification:
    """Classification result for a single test with multi-label support.

    Primary category represents the main transcription difficulty.
    Tags represent additional orthogonal concerns.
    """

    pbt_id: str
    test_name: str
    test_code: str
    primary_category: Category
    primary_confidence: float
    tags: list[Category]  # Additional categories above tag_threshold
    tag_confidences: dict[Category, float]  # Confidence for each tag
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
    """Detect classification signals in test code for 12 categories.

    Returns list of signals with category and weight.
    Multiple signals can fire - supports multi-label classification.
    """
    signals = []

    # First, detect key characteristics
    has_torch = bool(re.search(r"\btorch\.", test_code))
    has_numpy = bool(re.search(r"\bnp\.", test_code))
    has_pandas = bool(re.search(r"\bpd\.", test_code))
    has_tf = bool(re.search(r"\btf\.", test_code))
    has_jax = bool(re.search(r"\bjnp\.", test_code))
    has_library = has_torch or has_numpy or has_pandas or has_tf or has_jax

    # Detect numeric/floating point operations
    has_numeric = bool(
        re.search(r"pytest\.approx\(", test_code)
        or re.search(r"np\.isclose\(", test_code)
        or re.search(r"torch\.allclose\(", test_code)
        or re.search(r"\.isclose\(", test_code)
        or re.search(r"\batol\s*=", test_code)
        or re.search(r"\brtol\s*=", test_code)
    )

    # Detect parametrize decorator
    has_parametrize = bool(re.search(r"@pytest\.mark\.parametrize", test_code))

    # Detect structural validation patterns
    has_structural = bool(
        re.search(r"\bisinstance\(", test_code)
        or re.search(r"\bhasattr\(", test_code)
        or re.search(r"\btype\(", test_code)
        or re.search(r"assert.*\blen\(", test_code)
    )

    # Detect control flow complexity
    has_loops = bool(
        re.search(r"\bfor\b", test_code) or re.search(r"\bwhile\b", test_code)
    )
    has_nested_conditions = len(re.findall(r"\bif\b", test_code)) >= 2
    has_exception_handling = bool(
        re.search(r"pytest\.raises\(", test_code)
        or re.search(r"with pytest\.raises\(", test_code)
        or (re.search(r"\btry:", test_code) and re.search(r"\bexcept\b", test_code))
    )

    # Detect concurrency/async
    has_async = bool(
        re.search(r"\basync\s+def\b", test_code)
        or re.search(r"\bawait\b", test_code)
        or re.search(r"\bthreading\.", test_code)
        or re.search(r"\bmultiprocessing\.", test_code)
    )

    # Detect meta/reflection
    has_meta = bool(
        re.search(r"\bgetattr\(", test_code)
        or re.search(r"\bsetattr\(", test_code)
        or re.search(r"\beval\(", test_code)
        or re.search(r"\b__dict__\b", test_code)
        or re.search(r"\b__class__\b", test_code)
    )

    # Detect multiple function calls / integration style
    function_calls = len(re.findall(r"\b\w+\([^)]*\)", test_code))
    has_setup_teardown = bool(
        re.search(r"\bsetup\(", test_code)
        or re.search(r"\bteardown\(", test_code)
        or re.search(r"@pytest\.fixture", test_code)
    )
    has_integration = function_calls >= 3 or has_setup_teardown

    # AST-based statefulness analysis
    is_stateful, stateful_reasons = analyze_statefulness_ast(test_code)

    # --- Tier 4: Very Hard ---

    # 4.2 Concurrent/Async
    if has_async:
        signals.append(
            Signal(
                "async/await or threading", Category.CONCURRENT_ASYNC, CONFIDENCE_ASYNC
            )
        )

    # 4.3 Meta/Reflection
    if has_meta:
        signals.append(
            Signal(
                "getattr/setattr/eval/reflection",
                Category.META_REFLECTION,
                CONFIDENCE_META,
            )
        )

    # 4.1 Stateful + Library-Dependent
    if is_stateful and has_library:
        confidence = 0.85 if len(stateful_reasons) >= 2 else 0.75
        reason_str = "; ".join(stateful_reasons[:2])
        signals.append(
            Signal(
                f"stateful + library: {reason_str}",
                Category.STATEFUL_LIBRARY_DEPENDENT,
                confidence,
            )
        )

    # --- Tier 3: Complex ---

    # 3.1 Stateful Sequential (if not library-dependent)
    if is_stateful and not has_library:
        confidence = (
            CONFIDENCE_NUMERIC if len(stateful_reasons) >= 2 else CONFIDENCE_STRUCTURAL
        )
        reason_str = "; ".join(stateful_reasons[:2])
        signals.append(
            Signal(f"AST: {reason_str}", Category.STATEFUL_SEQUENTIAL, confidence)
        )

    # 3.2 Complex Control Flow
    if has_exception_handling or (has_loops and has_nested_conditions):
        patterns = []
        if has_exception_handling:
            patterns.append("exception handling")
        if has_loops:
            patterns.append("loops")
        if has_nested_conditions:
            patterns.append("nested conditions")
        signals.append(
            Signal(
                ", ".join(patterns),
                Category.COMPLEX_CONTROL_FLOW,
                CONFIDENCE_STATEFUL_MODERATE,
            )
        )

    # 3.3 Multi-Step Integration
    if has_integration and not is_stateful:
        signals.append(
            Signal(
                f"{function_calls} function calls / setup-teardown",
                Category.MULTI_STEP_INTEGRATION,
                0.7,
            )
        )

    # --- Tier 2: Moderate ---

    # 2.1 Library-Dependent Pure (library but NOT stateful)
    if has_library and not is_stateful and not has_parametrize:
        libs = []
        if has_torch:
            libs.append("torch")
        if has_numpy:
            libs.append("numpy")
        if has_pandas:
            libs.append("pandas")
        if has_tf:
            libs.append("tensorflow")
        if has_jax:
            libs.append("jax")
        signals.append(
            Signal(
                f"{', '.join(libs)} (pure)",
                Category.LIBRARY_DEPENDENT_PURE,
                CONFIDENCE_STATEFUL_MODERATE,
            )
        )

    # 2.2 Library-Dependent Parametric
    if has_library and has_parametrize:
        signals.append(
            Signal(
                "parametrize + library",
                Category.LIBRARY_DEPENDENT_PARAMETRIC,
                CONFIDENCE_NUMERIC,
            )
        )

    # 2.3 Structural Validation
    if has_structural:
        signals.append(
            Signal(
                "isinstance/hasattr/type checks", Category.STRUCTURAL_VALIDATION, 0.7
            )
        )

    # --- Tier 1: Simple ---

    # 1.3 Numeric Pure Functional
    if has_numeric and not is_stateful and not has_library:
        signals.append(
            Signal(
                "numeric/float approx (pure)",
                Category.NUMERIC_PURE_FUNCTIONAL,
                CONFIDENCE_NUMERIC,
            )
        )

    # 1.2 Simple Parametric (No Deps)
    if has_parametrize and not has_library:
        signals.append(
            Signal(
                "pytest.mark.parametrize (no deps)",
                Category.SIMPLE_PARAMETRIC_NO_DEPS,
                0.85,
            )
        )

    # 1.1 Pure Functional (No Deps)
    # Positive evidence: AST found no mutations
    if (
        not is_stateful
        and not has_library
        and not has_parametrize
        and not has_structural
        and not has_loops
        and not has_exception_handling
    ):
        # Check for simple assertion patterns
        if re.search(r"assert \w+\(.+\)\s*==", test_code):
            signals.append(
                Signal(
                    "single assert with function call",
                    Category.PURE_FUNCTIONAL_NO_DEPS,
                    0.8,
                )
            )
        elif len(stateful_reasons) == 0:
            # AST confirmed no statefulness
            signals.append(
                Signal(
                    "AST: no mutations, no deps",
                    Category.PURE_FUNCTIONAL_NO_DEPS,
                    0.75,
                )
            )

    # Fallback: if no signals detected, likely simple pure functional
    if not signals:
        signals.append(
            Signal(
                "no complex patterns detected",
                Category.PURE_FUNCTIONAL_NO_DEPS,
                0.6,
            )
        )

    return signals


def classify_static(
    test_code: str, tag_threshold: float = DEFAULT_TAG_THRESHOLD
) -> tuple[Category, float, list[Category], dict[Category, float], list[str]]:
    """Classify test using static analysis with multi-label support.

    Returns: (primary_category, primary_confidence, tags, tag_confidences, signal_descriptions)

    Args:
        test_code: The test code to classify
        tag_threshold: Minimum score for a category to be included as a tag (default 0.5)
    """
    signals = detect_signals(test_code)

    if not signals:
        # Shouldn't happen - detect_signals has fallback
        return (
            Category.PURE_FUNCTIONAL_NO_DEPS,
            0.6,
            [],
            {},
            ["no complex patterns detected"],
        )

    # Count votes per category, weighted
    category_scores: dict[Category, float] = defaultdict(float)
    for signal in signals:
        category_scores[signal.category] += signal.weight

    # Get top category as primary
    top_category = max(category_scores.items(), key=lambda x: x[1])[0]
    top_score = category_scores[top_category]

    # Primary confidence = normalized score of top category
    total_score = sum(category_scores.values())
    primary_confidence = top_score / total_score if total_score > 0 else 0.0

    # Boost confidence if single category with strong signal
    if len(category_scores) == 1 and top_score >= 0.7:
        primary_confidence = min(primary_confidence * 1.1, 0.95)

    # Get tags: other categories above tag_threshold
    tags = []
    tag_confidences = {}
    for category, score in category_scores.items():
        if category != top_category and score >= tag_threshold:
            tags.append(category)
            # Normalize tag confidence relative to total
            tag_confidences[category] = score / total_score if total_score > 0 else 0.0

    # Sort tags by confidence (descending)
    tags.sort(key=lambda c: tag_confidences[c], reverse=True)

    # Collect signal descriptions for primary category
    signal_descriptions = [s.pattern for s in signals if s.category == top_category]

    return (
        top_category,
        primary_confidence,
        tags,
        tag_confidences,
        signal_descriptions,
    )


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

    prompt = f"""Classify this Python unit test into one of 12 categories based on difficulty of transcribing to Lean 4:

**Tier 1: Simple (easiest)**
1. Pure Functional (No Deps) - Direct function call with literals, no libraries
2. Simple Parametric (No Deps) - pytest.mark.parametrize but no libraries
3. Numeric Pure Functional - Float comparisons (pytest.approx) but no state/libraries

**Tier 2: Moderate (needs Lean expertise)**
4. Library-Dependent Pure - Uses torch/numpy/pandas but purely functional
5. Library-Dependent Parametric - Parametrize + libraries
6. Structural Validation - isinstance/hasattr/type checks

**Tier 3: Complex (significant effort)**
7. Stateful Sequential - Multiple assignments, mutations, but no libraries
8. Complex Control Flow - Loops + conditions, exception handling
9. Multi-Step Integration - Multiple function calls, setup/teardown

**Tier 4: Very Hard (may need axioms)**
10. Stateful + Library-Dependent - Mutations + torch/numpy/etc
11. Concurrent/Async - async/await, threading, multiprocessing
12. Meta/Reflection - getattr/setattr/eval/__dict__ manipulation

Test code:
```python
{test_code}
```

Respond with:
1. The category number (1-12)
2. A confidence rating from 1-10 (how sure you are)
3. A brief reason (one sentence)

Format: "Category X, Confidence Y: <reason>"
Example: "Category 4, Confidence 9: Uses torch.tensor but purely functional"
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
            return (
                Category.PURE_FUNCTIONAL_NO_DEPS,
                DEFAULT_LLM_FALLBACK_CONFIDENCE,
                "Could not parse response",
            )

        category_num = int(match.group(1))
        confidence_rating = int(match.group(2))
        reasoning = match.group(3)

        # Normalize confidence from 1-10 to 0.0-1.0
        confidence = confidence_rating / 10.0

        category_map = {
            1: Category.PURE_FUNCTIONAL_NO_DEPS,
            2: Category.SIMPLE_PARAMETRIC_NO_DEPS,
            3: Category.NUMERIC_PURE_FUNCTIONAL,
            4: Category.LIBRARY_DEPENDENT_PURE,
            5: Category.LIBRARY_DEPENDENT_PARAMETRIC,
            6: Category.STRUCTURAL_VALIDATION,
            7: Category.STATEFUL_SEQUENTIAL,
            8: Category.COMPLEX_CONTROL_FLOW,
            9: Category.MULTI_STEP_INTEGRATION,
            10: Category.STATEFUL_LIBRARY_DEPENDENT,
            11: Category.CONCURRENT_ASYNC,
            12: Category.META_REFLECTION,
        }

        category = category_map.get(category_num, Category.PURE_FUNCTIONAL_NO_DEPS)
        return (category, confidence, reasoning)

    except Exception as e:
        print(f"Warning: LLM classification failed: {e}")
        return (
            Category.PURE_FUNCTIONAL_NO_DEPS,
            DEFAULT_LLM_FALLBACK_CONFIDENCE,
            f"LLM error: {e}",
        )


def classify_test_static(
    pbt_id: str,
    test_name: str,
    test_code: str,
) -> tuple[Category, float, list[Category], dict[Category, float], list[str]]:
    """Classify a single test with static analysis only.

    Returns: (primary_category, primary_confidence, tags, tag_confidences, signals)
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
            results[index] = (
                Category.PURE_FUNCTIONAL_NO_DEPS,
                DEFAULT_LLM_FALLBACK_CONFIDENCE,
                f"LLM error: {e}",
            )
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
    primary_category, primary_confidence, tags, tag_confidences, signal_descriptions = (
        classify_static(test_code)
    )

    method: Literal["static", "llm"] = "static"
    reasoning = None

    # Fallback to LLM if confidence is low
    if use_llm and primary_confidence < confidence_threshold:
        if not api_key:
            if verbose:
                print(
                    f"Warning: Low confidence ({primary_confidence:.2f}) for {test_name} "
                    "but no API key available for LLM fallback"
                )

    return Classification(
        pbt_id=pbt_id,
        test_name=test_name,
        test_code=test_code,
        primary_category=primary_category,
        primary_confidence=primary_confidence,
        tags=tags,
        tag_confidences=tag_confidences,
        method=method,
        signals=signal_descriptions,
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
    early_stop_multiplier = EARLY_STOP_MULTIPLIER
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
    ] = DEFAULT_CONFIDENCE_THRESHOLD,
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
            (
                primary_category,
                primary_confidence,
                tags,
                tag_confidences,
                signal_descriptions,
            ) = classify_static(test_code)
            static_results.append(
                (
                    pbt_id,
                    test_name,
                    test_code,
                    primary_category,
                    primary_confidence,
                    tags,
                    tag_confidences,
                    signal_descriptions,
                )
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
            primary_category,
            primary_confidence,
            tags,
            tag_confidences,
            signal_descriptions,
        ) in enumerate(static_results):
            if not no_llm and primary_confidence < confidence_threshold and api_key:
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
                primary_category,
                primary_confidence,
                tags,
                tag_confidences,
                signal_descriptions,
            ) in enumerate(static_results):
                method: Literal["static", "llm"] = "static"
                reasoning = None

                # Check if this test used LLM
                if i in needs_llm_indices:
                    # LLM only returns primary category (no multi-label support yet)
                    primary_category, primary_confidence, reasoning = llm_results[
                        llm_idx
                    ]
                    # Clear tags when using LLM (LLM doesn't support multi-label yet)
                    tags = []
                    tag_confidences = {}
                    method = "llm"
                    llm_count += 1
                    llm_idx += 1

                # Write to JSONL
                record = {
                    "pbt_id": pbt_id,
                    "test_name": test_name,
                    "primary_category": primary_category,
                    "primary_category_name": CATEGORY_NAMES[primary_category],
                    "primary_confidence": primary_confidence,
                    "tags": tags,
                    "tag_names": [CATEGORY_NAMES[tag] for tag in tags],
                    "tag_confidences": {
                        CATEGORY_NAMES[cat]: conf
                        for cat, conf in tag_confidences.items()
                    },
                    "method": method,
                    "signals": signal_descriptions,
                    "reasoning": reasoning,
                    "test_code": test_code,
                }
                jsonl_file.write(json.dumps(record) + "\n")

                # Update stats for primary category
                category_counts[primary_category] += 1
                category_confidences[primary_category].append(primary_confidence)
                if method == "llm":
                    category_llm_usage[primary_category] += 1

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
