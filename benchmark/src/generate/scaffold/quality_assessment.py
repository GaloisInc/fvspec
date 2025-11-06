"""Quality assessment utilities for benchmarking Lean specifications."""

import ast
import re
from enum import Enum
from typing import TYPE_CHECKING, cast

from inspect_ai.solver import TaskState
from pydantic import BaseModel, Field

from generate.scaffold.dataset import Datapoint
from generate.scaffold.formalize.plausible_runner import Plausibility


class ImplementationLevel(str, Enum):
    """Indicates what level of FUT implementation was provided to the model."""

    PROVIDED = "provided"  # Full FUT source code discovered and implemented
    SIGNATURE = "signature"  # Only type signature/stub provided (discovery failed)
    ABSENT = "absent"  # No FUT implementation (spec-only or error case)


if TYPE_CHECKING:
    from inspect_ai.scorer import Score


class StructuralFaithfulness(BaseModel):
    """Objective structural metrics computed from code analysis.

    These metrics measure how well the Lean specification corresponds to the
    Python property-based test structure without relying on LLM self-assessment.
    """

    parameter_coverage: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Fraction of Python parameters found in Lean code",
    )
    type_correspondence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Fraction of Python types correctly mapped to Lean types",
    )
    strategy_coverage: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Fraction of Hypothesis strategy bounds found in Lean",
    )
    assertion_coverage: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Ratio of Lean properties to Python assertions",
    )
    dependency_coverage: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Fraction of dependency names found in Lean code",
    )
    overall: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Weighted average of all structural metrics",
    )

    @classmethod
    def from_codes(
        cls, python_pbt: str, python_deps: list[str], lean_code: str
    ) -> "StructuralFaithfulness":
        """Compute structural faithfulness metrics from source code.

        Args:
            python_pbt: Python property-based test source code
            python_deps: List of Python dependency function definitions
            lean_code: Generated Lean 4 specification code

        Returns:
            StructuralFaithfulness object with computed metrics
        """
        # Extract Python structure
        py_params = _extract_python_parameters(python_pbt)
        py_types = _extract_python_types(python_pbt)
        py_strategies = _extract_hypothesis_strategies(python_pbt)
        py_assertions = _count_python_assertions(python_pbt)
        py_dep_names = _extract_dependency_names(python_deps)

        # Extract Lean structure
        lean_params = _extract_lean_parameters(lean_code)
        lean_types = _extract_lean_types(lean_code)
        lean_bounds = _extract_lean_bounds(lean_code)
        lean_properties = _count_lean_properties(lean_code)

        # Compute metrics
        param_cov = _compute_parameter_coverage(py_params, lean_params)
        type_corr = _compute_type_correspondence(py_types, lean_types)
        strat_cov = _compute_strategy_coverage(py_strategies, lean_bounds)
        assert_cov = _compute_assertion_coverage(py_assertions, lean_properties)
        dep_cov = _compute_dependency_coverage(py_dep_names, lean_code)

        # Weighted average (can tune these weights)
        overall = (
            0.25 * param_cov
            + 0.25 * type_corr
            + 0.20 * strat_cov
            + 0.20 * assert_cov
            + 0.10 * dep_cov
        )

        return cls(
            parameter_coverage=param_cov,
            type_correspondence=type_corr,
            strategy_coverage=strat_cov,
            assertion_coverage=assert_cov,
            dependency_coverage=dep_cov,
            overall=overall,
        )


# Python parsing utilities


def _extract_python_parameters(code: str) -> list[str]:
    """Extract parameter names from Python function definition."""
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Get parameter names (excluding 'self')
                params = [arg.arg for arg in node.args.args if arg.arg != "self"]
                return params
    except SyntaxError:
        pass
    return []


def _extract_python_types(code: str) -> dict[str, str]:
    """Extract parameter types from Python function annotations."""
    types = {}
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for arg in node.args.args:
                    if arg.arg != "self" and arg.annotation:
                        # Get type annotation as string
                        if isinstance(arg.annotation, ast.Name):
                            types[arg.arg] = arg.annotation.id
                        elif isinstance(arg.annotation, ast.Subscript):
                            # Handle list[int], etc.
                            if isinstance(arg.annotation.value, ast.Name):
                                types[arg.arg] = arg.annotation.value.id
    except SyntaxError:
        pass
    return types


def _extract_hypothesis_strategies(
    code: str,
) -> dict[str, list[tuple[str, int | float]]]:
    """Extract Hypothesis strategy bounds from @given decorator.

    Returns dict mapping param names to list of (constraint_type, value) tuples.
    Example: {"x": [("min_value", 0), ("max_value", 100)]}
    """
    strategies = {}

    # Match patterns like: x=st.integers(0, 100) or x=st.integers(min_value=0, max_value=100)
    param_pattern = r"(\w+)\s*=\s*st\.(\w+)\([^)]*\)"

    for match in re.finditer(param_pattern, code):
        param_name = match.group(1)
        strategy_type = match.group(2)
        strategy_call = match.group(0)

        bounds = []

        # Extract positional bounds for integers/floats
        if strategy_type in ["integers", "floats"]:
            # Match: st.integers(0, 100)
            pos_pattern = r"st\.\w+\((\d+),\s*(\d+)\)"
            pos_match = re.search(pos_pattern, strategy_call)
            if pos_match:
                bounds.append(("min_value", int(pos_match.group(1))))
                bounds.append(("max_value", int(pos_match.group(2))))

        # Extract keyword bounds
        for kw in ["min_value", "max_value", "min_size", "max_size"]:
            kw_pattern = rf"{kw}\s*=\s*(\d+)"
            kw_match = re.search(kw_pattern, strategy_call)
            if kw_match:
                bounds.append((kw, int(kw_match.group(1))))

        if bounds:
            strategies[param_name] = bounds

    return strategies


def _count_python_assertions(code: str) -> int:
    """Count assert statements in Python code."""
    try:
        tree = ast.parse(code)
        count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Assert):
                count += 1
        return count
    except SyntaxError:
        pass
    return 0


def _extract_dependency_names(deps: list[str]) -> list[str]:
    """Extract function/class names from dependency definitions."""
    names = []
    for dep in deps:
        try:
            tree = ast.parse(dep)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    names.append(node.name)
        except SyntaxError:
            pass
    return names


# Lean parsing utilities (regex-based)


def _extract_lean_parameters(code: str) -> list[str]:
    """Extract parameter names from Lean function/theorem definitions."""
    params = []

    # Match: (x : Type) or (x y : Type)
    param_pattern = r"\(([a-zA-Z_]\w*(?:\s+[a-zA-Z_]\w*)*)\s*:\s*[^)]+\)"

    for match in re.finditer(param_pattern, code):
        # Split multiple params: "x y" → ["x", "y"]
        param_names = match.group(1).split()
        params.extend(param_names)

    return params


def _extract_lean_types(code: str) -> dict[str, str]:
    """Extract parameter types from Lean code."""
    types = {}

    # Match: (x : Int) or (x y : Nat)
    param_pattern = (
        r"\(([a-zA-Z_]\w*(?:\s+[a-zA-Z_]\w*)*)\s*:\s*([a-zA-Z_]\w*(?:\s*\w*)*)\)"
    )

    for match in re.finditer(param_pattern, code):
        param_names = match.group(1).split()
        param_type = match.group(2).strip()
        for pname in param_names:
            types[pname] = param_type

    return types


def _extract_lean_bounds(code: str) -> dict[str, list[tuple[str, int | float]]]:
    """Extract numeric bounds from Lean hypotheses.

    Returns dict mapping param names to list of (op, value) tuples.
    Example: {"x": [("≤", 100), ("≥", 0)]}
    """
    bounds = {}

    # Match patterns like: 0 ≤ x, x ≤ 100, x < 50, etc.
    # Unicode operators: ≤ ≥ < > =
    bound_patterns = [
        (r"(\d+)\s*≤\s*(\w+)", "min", "≤"),  # 0 ≤ x
        (r"(\w+)\s*≤\s*(\d+)", "max", "≤"),  # x ≤ 100
        (r"(\d+)\s*≥\s*(\w+)", "max", "≥"),  # 100 ≥ x
        (r"(\w+)\s*≥\s*(\d+)", "min", "≥"),  # x ≥ 0
        (r"(\d+)\s*<\s*(\w+)", "min_exclusive", "<"),
        (r"(\w+)\s*<\s*(\d+)", "max_exclusive", "<"),
        (r"(\d+)\s*>\s*(\w+)", "max_exclusive", ">"),
        (r"(\w+)\s*>\s*(\d+)", "min_exclusive", ">"),
    ]

    for pattern, bound_type, op in bound_patterns:
        for match in re.finditer(pattern, code):
            if bound_type in ["min", "min_exclusive"]:
                value, param = match.group(1), match.group(2)
            else:
                param, value = match.group(1), match.group(2)

            try:
                value_num = int(value)
                if param not in bounds:
                    bounds[param] = []
                bounds[param].append((bound_type, value_num))
            except ValueError:
                pass

    return bounds


def _count_lean_properties(code: str) -> int:
    """Count theorem/property statements in Lean code."""
    # Count 'theorem' and 'lemma' keywords
    count = len(re.findall(r"\btheorem\b", code))
    count += len(re.findall(r"\blemma\b", code))

    # Also count property assertions in theorem bodies
    # Look for common patterns like: result = ..., result ∈ ..., etc.
    count += len(re.findall(r"=\s*[^=]", code))  # Simple equality checks

    return max(1, count)  # At least 1 if code exists


def count_lean_theorems(code: str) -> int:
    """Count theorem and lemma declarations in Lean code.

    This counts only explicit theorem/lemma keywords, not property
    assertions within theorem bodies.
    """
    count = len(re.findall(r"\btheorem\b", code))
    count += len(re.findall(r"\blemma\b", code))
    return count


def _flatten_dict(
    d: dict, parent_key: str = "", sep: str = "_"
) -> dict[str, int | float | str | None]:
    """Recursively flatten a nested dictionary.

    Args:
        d: Dictionary to flatten
        parent_key: Prefix for nested keys
        sep: Separator to join nested keys (default: "_")

    Returns:
        Flattened dictionary with keys joined by separator.
        Booleans are converted to int (0/1) for wandb compatibility.

    Example:
        >>> _flatten_dict({"a": 1, "b": {"c": 2, "d": True}})
        {"a": 1, "b_c": 2, "b_d": 1}
    """
    items: list[tuple[str, int | float | str | None]] = []

    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k

        if isinstance(v, dict):
            # Recursively flatten nested dicts
            items.extend(_flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            # Handle lists - wandb doesn't handle them well
            if not v:
                # Empty list -> None
                items.append((new_key, None))
            elif all(isinstance(item, str) for item in v):
                # Join string lists (e.g., errors)
                items.append((new_key, ", ".join(v)))
            else:
                # For other lists, just log the length
                items.append((f"{new_key}_count", len(v)))
        elif isinstance(v, bool):
            # Convert bool to int for wandb compatibility
            items.append((new_key, 1 if v else 0))
        else:
            # Primitive values: int, float, str, None
            items.append((new_key, v))

    return dict(items)


# Metric computation utilities


def _compute_parameter_coverage(py_params: list[str], lean_params: list[str]) -> float:
    """Compute fraction of Python parameters found in Lean."""
    if not py_params:
        return 1.0  # No params to check

    py_set = set(py_params)
    lean_set = set(lean_params)
    matched = py_set & lean_set

    return len(matched) / len(py_set)


def _compute_type_correspondence(
    py_types: dict[str, str], lean_types: dict[str, str]
) -> float:
    """Compute fraction of Python types correctly mapped to Lean."""
    if not py_types:
        return 1.0

    # Type mapping rules
    TYPE_MAP = {
        "int": ["Int", "Nat", "ℕ", "ℤ", "Integer"],
        "float": ["Float", "Real", "ℝ"],
        "str": ["String"],
        "bool": ["Bool", "Prop"],
        "list": ["List", "Array"],
        "dict": ["Map", "HashMap", "Finmap"],
        "set": ["Set", "Finset"],
    }

    correct = 0
    total = 0

    for param, py_type in py_types.items():
        if param in lean_types:
            total += 1
            lean_type = lean_types[param]

            # Check if mapping is sensible
            if py_type in TYPE_MAP:
                if any(lt in lean_type for lt in TYPE_MAP[py_type]):
                    correct += 1
            else:
                # Unknown type, be lenient (might be custom type)
                correct += 0.5

    return correct / total if total > 0 else 1.0


def _compute_strategy_coverage(
    py_strategies: dict[str, list[tuple[str, int | float]]],
    lean_bounds: dict[str, list[tuple[str, int | float]]],
) -> float:
    """Compute fraction of Hypothesis strategy bounds found in Lean."""
    if not py_strategies:
        return 1.0

    total_bounds = 0
    matched_bounds = 0

    for param, py_bounds in py_strategies.items():
        for bound_type, value in py_bounds:
            total_bounds += 1

            # Check if similar bound exists in Lean
            if param in lean_bounds:
                for lean_bound_type, lean_value in lean_bounds[param]:
                    # Match min_value with min/≥, max_value with max/≤
                    if bound_type == "min_value" and "min" in lean_bound_type:
                        if abs(value - lean_value) <= 1:  # Allow small differences
                            matched_bounds += 1
                            break
                    elif bound_type == "max_value" and "max" in lean_bound_type:
                        if abs(value - lean_value) <= 1:
                            matched_bounds += 1
                            break

    return matched_bounds / total_bounds if total_bounds > 0 else 1.0


def _compute_assertion_coverage(py_assertions: int, lean_properties: int) -> float:
    """Compute ratio of Lean properties to Python assertions."""
    if py_assertions == 0:
        return 1.0 if lean_properties > 0 else 0.0

    # Ideal: at least as many Lean properties as Python assertions
    ratio = lean_properties / py_assertions
    return min(1.0, ratio)  # Cap at 1.0


def _compute_dependency_coverage(dep_names: list[str], lean_code: str) -> float:
    """Compute fraction of dependency names found in Lean code."""
    if not dep_names:
        return 1.0

    found = sum(1 for name in dep_names if name in lean_code)
    return found / len(dep_names)


class QualityAssessment(BaseModel):
    """Quality assessment metrics for a generated Lean specification."""

    sample_id: int
    sample_name: str
    datetime: str
    variant: str = Field(description="Prompt variant name")
    model: str
    token_usage: int
    time: float = Field(description="Generation time in seconds")
    num_messages: int
    num_generate_messages: int
    num_input_messages: int
    success: bool
    num_sorries: int
    num_theorems: int = Field(
        0, description="Number of theorems/lemmas in generated spec"
    )
    lines_pbt: int
    lines_code: int
    num_fns_impl: int = Field(
        description="Number of functions autoformalized (FUT + dependencies)"
    )
    percent_lines_added: float | None = Field(
        None, description="(lines_code - lines_pbt) / lines_pbt"
    )
    # Subjective metrics (self-reported by model)
    faithfulness_subjective: float | None = Field(
        None, description="AI self-reported faithfulness score (0-10)"
    )
    interest_subjective: float | None = Field(
        None, description="AI self-reported interest/complexity score (0-10)"
    )
    # Objective metrics (computed from code structure)
    structural_faithfulness: StructuralFaithfulness | None = Field(
        None, description="Objective structural metrics"
    )
    # Unit test metrics
    has_unit_tests: bool = Field(
        False, description="Whether unit tests were extracted from PBT"
    )
    num_unit_tests: int = Field(0, description="Number of unit tests extracted")
    unit_tests_available: bool = Field(
        False, description="Whether unit tests are available for evaluation"
    )
    # Plausible property testing metrics
    plausibility: Plausibility = Field(
        default_factory=Plausibility,
        description="Results from running Plausible property testing",
    )
    percent_plausible: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Fraction of theorems that kept 'by plausible' after selective reversion",
    )
    impl_autoform_success: bool = Field(
        default=False,
        description="Whether implementation autoformalization succeeded (generated and compiled)",
    )
    spec_sig_success: bool = Field(
        default=True,
        description="Whether specification generation succeeded (produced valid code in <code> tags)",
    )
    implementation_level: ImplementationLevel = Field(
        default=ImplementationLevel.ABSENT,
        description="Level of FUT implementation provided: full source, signature only, or absent",
    )
    actually_invokes_given: bool = Field(
        default=False,
        description="Whether the test actually invokes @given (True = PBT, False = unit test)",
    )

    @classmethod
    def from_task_state(cls, state: TaskState) -> "QualityAssessment":
        """Extract quality metrics from a completed task state."""
        datapoint = cast(Datapoint, state.metadata.get("datapoint"))
        date_time = cast(str, state.metadata.get("date_time"))
        variant = cast(str, state.metadata.get("variant"))
        lines_pbt = datapoint.code.count("\n")

        # Extract code metrics
        pattern = r"(?s)<code>(.*?)</code>"
        mtch = re.search(pattern, state.messages[-1].text)
        if not mtch:
            success = False
            spec_sig_success = False
            num_sorries = 0
            num_theorems = 0
            lines_code = 0
            percent_lines_added = 0.0
            code_snippet = ""
        else:
            code_snippet = mtch.group(1)
            spec_sig_success = True  # Spec agent produced valid code
            num_sorries = code_snippet.count("sorry")
            num_theorems = count_lean_theorems(code_snippet)
            lines_code = code_snippet.count("\n")
            percent_lines_added = (lines_code - lines_pbt) / lines_pbt

        # Check impl autoformalization status
        impl_result_data = state.metadata.get("impl_result")
        impl_autoform_success = False  # Default to False (no impl or failed)
        if impl_result_data:
            # impl_result may be dict or FunctionImplResult object
            if isinstance(impl_result_data, dict):
                # Check both success (generation) and compiles (validation)
                impl_autoform_success = impl_result_data.get(
                    "success", False
                ) and impl_result_data.get("compiles", False)
            else:
                # FunctionImplResult object
                impl_autoform_success = (
                    impl_result_data.success and impl_result_data.compiles
                )

        # Overall success: spec succeeded (backward compatible for spec-only tasks)
        # For tasks with impl, both spec and impl must succeed
        if impl_result_data:
            success = spec_sig_success and impl_autoform_success
        else:
            success = spec_sig_success

        # Extract subjective faithfulness metric (self-reported by model)
        f_pattern = r"Faithfulness.*:\s*([0-9]*.?[0-9]+)/([0-9]+)"
        f_mtch = re.search(f_pattern, state.messages[-1].text, re.IGNORECASE)
        faithfulness_subj = None
        if f_mtch:
            faithfulness_subj = float(f_mtch.group(1)) / float(f_mtch.group(2)) * 10.0

        # Extract subjective interest metric (self-reported by model)
        i_pattern = r"Interest.*:\s*([0-9]*.?[0-9]+)/([0-9]+)"
        i_mtch = re.search(i_pattern, state.messages[-1].text, re.IGNORECASE)
        interest_subj = None
        if i_mtch:
            interest_subj = float(i_mtch.group(1)) / float(i_mtch.group(2)) * 10.0

        # Compute objective structural faithfulness metrics
        structural = None
        if success and code_snippet:
            try:
                structural = StructuralFaithfulness.from_codes(
                    python_pbt=datapoint.code,
                    python_deps=datapoint.get_deps(),
                    lean_code=code_snippet,
                )
            except Exception:
                # If structural analysis fails, continue without it
                pass

        # Extract unit test information from metadata
        unit_tests_lspec = state.metadata.get("unit_tests_lspec")
        has_unit_tests = unit_tests_lspec is not None
        num_unit_tests = 0
        if has_unit_tests and unit_tests_lspec:
            # Count number of test cases in the LSpec code
            # Each test is a line containing 'test "'
            num_unit_tests = unit_tests_lspec.count('test "')

        # Extract plausibility metrics from metadata
        plausibility = state.metadata.get("plausibility", Plausibility())
        # Ensure it's a Plausibility object (may be dict from JSON deserialization)
        if isinstance(plausibility, dict):
            plausibility = Plausibility(**plausibility)

        # Compute percent_plausible: fraction of theorems with 'by plausible' in final code
        # This reflects the selective reversion (passed theorems keep plausible, failed revert to sorry)
        percent_plausible = None
        if success and code_snippet and num_theorems > 0:
            # Use regex to handle variable whitespace between 'by' and 'plausible'
            num_plausible = len(re.findall(r"by\s+plausible", code_snippet))
            percent_plausible = num_plausible / num_theorems

        # Extract implementation level from metadata
        implementation_level_str = state.metadata.get(
            "implementation_level", ImplementationLevel.ABSENT.value
        )
        # Convert string to enum
        try:
            implementation_level = ImplementationLevel(implementation_level_str)
        except ValueError:
            implementation_level = ImplementationLevel.ABSENT

        # Check if @given is actually invoked in the PBT code
        # Look for @given decorator usage (handles various formatting)
        # Matches: @given(...), @given (...), @st.given(...), @hypothesis.given(...)
        pbt_code = datapoint.code
        actually_invokes_given = bool(
            re.search(
                r"@(?:st\.|hypothesis\.)?given\s*\(",
                pbt_code,
                re.MULTILINE,
            )
        )

        return cls(
            sample_id=datapoint.id,
            sample_name=datapoint.name,
            datetime=date_time,
            variant=variant,
            model=state.output.model,
            token_usage=state.token_usage,
            time=state.output.time,
            num_messages=len(state.messages),
            num_generate_messages=sum(
                1 for sm in state.messages if sm.source == "generate"
            ),
            num_input_messages=sum(1 for sm in state.messages if sm.source == "input"),
            lines_pbt=lines_pbt,
            success=success,
            num_sorries=num_sorries,
            num_theorems=num_theorems,
            lines_code=lines_code,
            num_fns_impl=state.metadata.get(
                "num_fns_impl", 1
            ),  # Default to 1 (FUT only)
            percent_lines_added=percent_lines_added,
            faithfulness_subjective=faithfulness_subj,
            interest_subjective=interest_subj,
            structural_faithfulness=structural,
            has_unit_tests=has_unit_tests,
            num_unit_tests=num_unit_tests,
            unit_tests_available=has_unit_tests,
            plausibility=plausibility,
            percent_plausible=percent_plausible,
            impl_autoform_success=impl_autoform_success,
            spec_sig_success=spec_sig_success,
            implementation_level=implementation_level,
            actually_invokes_given=actually_invokes_given,
        )

    def to_inspect_scores(self) -> dict[str, "Score"]:
        """Export metrics as inspect_ai Score objects for viewer.

        Returns:
            Dictionary mapping score names to Score objects
        """
        from inspect_ai.scorer import Score

        scores = {
            "token_usage": Score(
                value=self.token_usage,
                explanation=f"Total tokens used: {self.token_usage}",
            ),
            "time": Score(
                value=self.time,
                explanation=f"Generation time in seconds: {self.time:.2f}",
            ),
            "num_messages": Score(
                value=self.num_messages,
                explanation=f"Total messages exchanged: {self.num_messages}",
            ),
            "success": Score(
                value="C" if self.success else "I",
                explanation="Successfully generated Lean code in <code> tags"
                if self.success
                else "Failed to generate valid Lean code",
            ),
            "spec_sig_success": Score(
                value="C" if self.spec_sig_success else "I",
                explanation="Spec agent produced valid code in <code> tags"
                if self.spec_sig_success
                else "Spec agent failed to generate valid code",
            ),
            "impl_autoform_success": Score(
                value="C" if self.impl_autoform_success else "I",
                explanation="Implementation autoformalized and compiled successfully"
                if self.impl_autoform_success
                else "Implementation autoformalization failed or didn't compile",
            ),
            # Note: implementation_level is kept in qa.json but excluded from scores
            # because it's categorical metadata (not a numeric metric to aggregate)
            "num_sorries": Score(
                value=self.num_sorries,
                explanation=f"Number of 'sorry' placeholders in generated code: {self.num_sorries}",
            ),
            "num_theorems": Score(
                value=self.num_theorems,
                explanation=f"Number of theorem/lemma declarations: {self.num_theorems}",
            ),
            "lines_code": Score(
                value=self.lines_code,
                explanation=f"Lines of Lean code generated: {self.lines_code}",
            ),
            "num_fns_impl": Score(
                value=self.num_fns_impl,
                explanation=f"Number of functions autoformalized (FUT + deps): {self.num_fns_impl}",
            ),
        }

        # Add optional metrics if available
        if self.percent_lines_added is not None:
            scores["percent_lines_added"] = Score(
                value=self.percent_lines_added,
                explanation=f"Percent lines added relative to Python test: {self.percent_lines_added:.1%}",
            )

        if self.faithfulness_subjective is not None:
            scores["faithfulness_subjective"] = Score(
                value=self.faithfulness_subjective,
                explanation=f"AI self-reported faithfulness (0-10): {self.faithfulness_subjective:.1f}",
            )

        if self.interest_subjective is not None:
            scores["interest_subjective"] = Score(
                value=self.interest_subjective,
                explanation=f"AI self-reported complexity/interest (0-10): {self.interest_subjective:.1f}",
            )

        # Add structural faithfulness metrics if available
        if self.structural_faithfulness is not None:
            sf = self.structural_faithfulness
            scores["structural_faithfulness_overall"] = Score(
                value=sf.overall,
                explanation=f"Weighted average of structural metrics: {sf.overall:.2%}",
            )
            scores["parameter_coverage"] = Score(
                value=sf.parameter_coverage,
                explanation=f"Fraction of Python parameters found in Lean: {sf.parameter_coverage:.2%}",
            )
            scores["type_correspondence"] = Score(
                value=sf.type_correspondence,
                explanation=f"Fraction of Python types correctly mapped to Lean: {sf.type_correspondence:.2%}",
            )
            scores["strategy_coverage"] = Score(
                value=sf.strategy_coverage,
                explanation=f"Fraction of Hypothesis strategy bounds found in Lean: {sf.strategy_coverage:.2%}",
            )
            scores["assertion_coverage"] = Score(
                value=sf.assertion_coverage,
                explanation=f"Ratio of Lean properties to Python assertions: {sf.assertion_coverage:.2%}",
            )
            scores["dependency_coverage"] = Score(
                value=sf.dependency_coverage,
                explanation=f"Fraction of dependency names found in Lean: {sf.dependency_coverage:.2%}",
            )

        # Unit test metrics
        if self.has_unit_tests:
            scores["has_unit_tests"] = Score(
                value=1.0,
                explanation=f"Unit tests extracted: {self.num_unit_tests} test(s) available for evaluation",
            )
            scores["num_unit_tests"] = Score(
                value=self.num_unit_tests,
                explanation=f"Number of extracted unit tests: {self.num_unit_tests}",
            )
        else:
            scores["has_unit_tests"] = Score(
                value=0.0,
                explanation="No unit tests could be extracted from the PBT",
            )

        # Plausible property testing metrics
        plaus = self.plausibility
        if plaus.ran:
            # plausible_ran: binary indicator
            scores["plausible_ran"] = Score(
                value=1.0,
                explanation="Plausible property testing was attempted",
            )

            # plausible_success: success rate (0.0 to 1.0)
            # If there are errors, show them; otherwise show the rate
            if plaus.errors:
                explanation = (
                    f"Plausible errors (0% success): {'; '.join(plaus.errors[:2])}"
                )
            else:
                explanation = f"Plausible success rate: {plaus.success:.1%} ({max(0, plaus.num_theorems - plaus.counterexamples)}/{plaus.num_theorems} theorems passed)"

            scores["plausible_success"] = Score(
                value=plaus.success,
                explanation=explanation,
            )

            # plausible_time: execution time
            if plaus.time is not None:
                scores["plausible_time"] = Score(
                    value=plaus.time,
                    explanation=f"Time to run plausible: {plaus.time:.2f}s",
                )

            # plausible_counterexamples: count
            if plaus.counterexamples > 0:
                scores["plausible_counterexamples"] = Score(
                    value=plaus.counterexamples,
                    explanation=f"Counterexamples found: {plaus.counterexamples}",
                )
        else:
            scores["plausible_ran"] = Score(
                value=0.0,
                explanation="Plausible property testing was not attempted (disabled or spec generation failed)",
            )

        # percent_plausible: fraction of theorems that kept 'by plausible' after selective reversion
        if self.percent_plausible is not None:
            scores["percent_plausible"] = Score(
                value=self.percent_plausible,
                explanation=f"Fraction of theorems that kept 'by plausible': {self.percent_plausible:.1%} ({int(self.percent_plausible * self.num_theorems)}/{self.num_theorems})",
            )

        return scores

    def to_wandb_metrics(self) -> dict[str, int | float | str | None]:
        """Export metrics as wandb-compatible dictionary.

        Uses model_dump() with automatic flattening of nested structures.
        Nested keys are joined with underscores (e.g., plausibility.ran -> plausibility_ran).
        Booleans are converted to integers (0/1) for wandb compatibility.

        Returns:
            Dictionary of metric names to values for wandb logging
        """
        # Get the full model as a dictionary
        data = self.model_dump()

        # Flatten nested dictionaries
        return _flatten_dict(data)
