"""Quality assessment data models."""

import logging
import re
from enum import Enum
from typing import TYPE_CHECKING, Any, cast

from inspect_ai.scorer import Score
from inspect_ai.solver import TaskState
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from generate.scaffold.dataset import Datapoint
from generate.scaffold.formalize.plausible_runner import Plausibility
from generate.scaffold.quality_assessment.lean_parsing import (
    count_lean_properties,
    count_lean_theorems,
    detect_trivial_unit_theorems,
    detect_unit_stub_in_impl,
    extract_hypothesis_strategies,
    extract_lean_bounds,
    extract_lean_parameters,
    extract_lean_types,
)
from generate.scaffold.quality_assessment.metrics import (
    compute_assertion_coverage,
    compute_dependency_coverage,
    compute_parameter_coverage,
    compute_strategy_coverage,
    compute_type_correspondence,
)
from generate.scaffold.quality_assessment.python_parsing import (
    count_python_assertions,
    extract_dependency_names,
    extract_python_parameters,
    extract_python_types,
)
from generate.scaffold.quality_assessment.serialization import flatten_dict

if TYPE_CHECKING:
    from inspect_ai.scorer import Score


class ImplementationLevel(str, Enum):
    """Indicates what level of FUT implementation was provided to the model."""

    PROVIDED = "provided"  # Full FUT source code discovered and implemented
    SIGNATURE = "signature"  # Only type signature/stub provided (discovery failed)
    ABSENT = "absent"  # No FUT implementation (spec-only or error case)


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
    assertion_theorem_difference: int = Field(
        default=0,
        description="Difference between number of Lean theorems and Python asserts (positive = more theorems, negative = fewer theorems, zero = perfect match)",
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
        py_params = extract_python_parameters(python_pbt)
        py_types = extract_python_types(python_pbt)
        py_strategies = extract_hypothesis_strategies(python_pbt)
        py_assertions = count_python_assertions(python_pbt)
        py_dep_names = extract_dependency_names(python_deps)

        # Extract Lean structure
        lean_params = extract_lean_parameters(lean_code)
        lean_types = extract_lean_types(lean_code)
        lean_bounds = extract_lean_bounds(lean_code)
        lean_properties = count_lean_properties(lean_code)
        lean_theorems = count_lean_theorems(lean_code)

        # Compute metrics
        param_cov = compute_parameter_coverage(py_params, lean_params)
        type_corr = compute_type_correspondence(py_types, lean_types)
        strat_cov = compute_strategy_coverage(py_strategies, lean_bounds)
        assert_cov = compute_assertion_coverage(py_assertions, lean_properties)
        dep_cov = compute_dependency_coverage(py_dep_names, lean_code)
        assert_thm_diff = lean_theorems - py_assertions

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
            assertion_theorem_difference=assert_thm_diff,
            overall=overall,
        )


class Radon(BaseModel):
    """Radon code complexity metrics for Python PBT.

    These metrics are computed from the Python property-based test source code
    using the radon library and provide objective measures of code complexity.
    """

    loc: int | None = Field(None, description="Total lines of code")
    sloc: int | None = Field(
        None, description="Source lines of code (no blanks/comments)"
    )
    lloc: int | None = Field(None, description="Logical lines of code")
    comments: int | None = Field(None, description="Number of comment lines")
    blank: int | None = Field(None, description="Number of blank lines")
    multi: int | None = Field(None, description="Multi-line strings")
    single_comments: int | None = Field(None, description="Single-line comments")
    num_functions: int | None = Field(None, description="Number of functions analyzed")
    avg_complexity: float | None = Field(
        None, description="Average cyclomatic complexity"
    )
    max_complexity: int | None = Field(None, description="Maximum complexity")
    total_complexity: int | None = Field(
        None, description="Sum of function complexities"
    )
    complexity_rank: str | None = Field(None, description="Complexity rank (A-F)")
    maintainability_index: float | None = Field(
        None, description="Maintainability index (0-100)"
    )
    maintainability_rank: str | None = Field(
        None, description="Maintainability rank (A-C)"
    )
    halstead_vocabulary: int | None = Field(None, description="Halstead vocabulary")
    halstead_length: int | None = Field(None, description="Halstead length")
    halstead_volume: float | None = Field(None, description="Halstead volume")
    halstead_difficulty: float | None = Field(None, description="Halstead difficulty")
    halstead_effort: float | None = Field(None, description="Halstead effort")
    halstead_time: float | None = Field(None, description="Halstead time (seconds)")
    halstead_bugs: float | None = Field(None, description="Expected bugs")


class QualityAssessment(BaseModel):
    """Quality assessment metrics for a generated Lean specification."""

    sample_id: int
    sample_name: str
    datetime: str
    variant: str = Field(description="Prompt variant name")
    model: str
    git_commit: str | None = Field(
        None, description="Repo git commit hash at generation time"
    )
    token_usage: int = Field(
        description="Total tokens used (aggregate for backward compatibility)"
    )
    token_usage_breakdown: list[dict[str, Any]] | None = Field(
        default=None,
        description="Per-subagent token usage breakdown with function names. Each entry contains: subagent, function_name (for impl agents), tokens_spent, num_toolcalls",
    )
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
    has_unit_stub: bool = Field(
        default=False,
        description="Whether implementation is a Unit stub (discovery failed)",
    )
    num_trivial_unit_theorems: int = Field(
        default=0,
        ge=0,
        description="Number of trivial theorems asserting Unit functions equal ()",
    )
    has_eval_statements: bool = Field(
        default=False,
        description="Whether any #eval statements were detected in Impl.lean",
    )
    num_eval_statements: int = Field(
        default=0,
        ge=0,
        description="Number of #eval statements found in Impl.lean",
    )
    impl_eval_stripped: bool = Field(
        default=False,
        description="Whether #eval was stripped from Impl.lean due to build failures (uncomputable)",
    )
    # Radon code complexity metrics for the Python PBT
    radon: Radon | None = Field(None, description="Code complexity metrics")
    # Function discovery metadata
    function_discovery: dict[str, Any] | None = Field(
        default=None,
        description="Function discovery metadata: method, confidence, name resolution",
    )

    @classmethod
    def from_task_state(cls, state: TaskState) -> "QualityAssessment":
        """Extract quality metrics from a completed task state."""
        datapoint = cast(Datapoint, state.metadata.get("datapoint"))
        date_time = cast(str, state.metadata.get("date_time"))
        variant = cast(str, state.metadata.get("variant"))
        lines_pbt = datapoint.code.count("\n")

        # Extract spec result from store (set by spec agent with compilation checks)
        spec_result_data = state.store.get("spec_result")
        if isinstance(spec_result_data, dict):
            spec_sig_success = spec_result_data.get(
                "success", False
            ) and spec_result_data.get("compiles", False)
            code_snippet = spec_result_data.get("lean_code") or ""
        elif spec_result_data is not None:
            spec_sig_success = spec_result_data.success and spec_result_data.compiles
            code_snippet = spec_result_data.lean_code or ""
        else:
            # No spec_result in store — compilation was never verified.
            # Mark as failed rather than guessing from message content.
            logger.warning(
                f"No spec_result in store for sample {datapoint.id} — "
                "marking spec_sig_success=False"
            )
            spec_sig_success = False
            code_snippet = ""

        # Extract code metrics from spec code
        if code_snippet:
            num_sorries = code_snippet.count("sorry")
            num_theorems = count_lean_theorems(code_snippet)
            lines_code = code_snippet.count("\n")
            percent_lines_added = (lines_code - lines_pbt) / lines_pbt
        else:
            num_sorries = 0
            num_theorems = 0
            lines_code = 0
            percent_lines_added = 0.0

        # Check impl autoformalization status
        impl_result_data = state.store.get("impl_result")
        impl_autoform_success = False  # Default to False (no impl or failed)
        impl_eval_stripped = False  # Default to False (no stripping needed)
        if impl_result_data:
            # impl_result may be dict or FunctionImplResult object
            if isinstance(impl_result_data, dict):
                # Check both success (generation) and compiles (validation)
                impl_autoform_success = impl_result_data.get(
                    "success", False
                ) and impl_result_data.get("compiles", False)
                # Extract whether #eval was stripped
                impl_eval_stripped = impl_result_data.get("has_eval_stripped", False)
            else:
                # FunctionImplResult object
                impl_autoform_success = (
                    impl_result_data.success and impl_result_data.compiles
                )
                impl_eval_stripped = impl_result_data.has_eval_stripped

        # Overall success: spec compiled AND (no impl OR impl compiled)
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
            except (SyntaxError, ValueError, AttributeError, KeyError) as e:
                # If structural analysis fails, continue without it
                logger.warning(
                    f"Structural faithfulness analysis failed for sample {datapoint.id}: {e}"
                )
                pass

        # Extract plausibility metrics from store
        plausibility = state.store.get("plausibility", Plausibility())
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

        # Extract implementation level from store
        implementation_level_str = state.store.get(
            "implementation_level", ImplementationLevel.ABSENT.value
        )
        # Convert string to enum
        try:
            implementation_level = ImplementationLevel(implementation_level_str)
        except ValueError as e:
            logger.warning(
                f"Invalid implementation level '{implementation_level_str}' for sample {datapoint.id}: {e}"
            )
            implementation_level = ImplementationLevel.ABSENT

        # Check if @given is actually invoked in the PBT code
        # Look for @given decorator usage (handles various formatting)
        # Matches: @given(...), @given (...), @st.given(...), @hypothesis.given(...)
        pbt_code = datapoint.code
        actually_invokes_given = bool(
            re.search(
                r"@(?:st\.|hypothesis\.)?given\s*\(",
                pbt_code,
            )
        )

        # Detect Unit stubbing patterns (implementation discovery failure)
        # Check if impl has Unit stub
        impl_code_str = state.store.get("impl_code", "")
        has_unit_stub = detect_unit_stub_in_impl(impl_code_str)

        # Count trivial Unit theorems in spec
        num_trivial_unit_theorems = 0
        if code_snippet:
            num_trivial_unit_theorems = detect_trivial_unit_theorems(code_snippet)

        # Extract function discovery metadata from store
        function_discovery = state.store.get("function_discovery")

        # Read radon metrics from embedded datapoint metrics
        radon_obj = None
        if datapoint.metrics is not None:
            m = datapoint.metrics
            radon_obj = Radon(
                loc=m.loc,
                sloc=m.sloc,
                lloc=m.lloc,
                comments=m.comments,
                avg_complexity=m.avg_complexity,
                max_complexity=m.max_complexity,
                maintainability_index=m.maintainability_index,
                halstead_difficulty=m.halstead_difficulty,
                halstead_effort=m.halstead_effort,
            )

        # Extract #eval violation metrics from metadata
        # Only spec violations are tracked (impl #eval usage is now encouraged)
        spec_eval_violations = state.metadata.get("spec_eval_violations", [])
        has_eval_statements = len(spec_eval_violations) > 0
        num_eval_statements = len(spec_eval_violations)

        # Build token_usage_breakdown from store
        token_breakdown = []

        # Add FUT impl token usage
        impl_fut_usage = state.store.get("impl_fut_token_usage")
        if impl_fut_usage:
            token_breakdown.append(impl_fut_usage)

        # Add all dependency impl token usages
        dep_usages = state.store.get("dep_token_usages", [])
        token_breakdown.extend(dep_usages)

        # Add spec token usage
        spec_usage = state.store.get("spec_token_usage")
        if spec_usage:
            token_breakdown.append(spec_usage)

        return cls(
            sample_id=datapoint.id,
            sample_name=datapoint.name,
            datetime=date_time,
            variant=variant,
            model=state.output.model,
            git_commit=state.metadata.get("git_commit"),
            token_usage=state.token_usage,
            token_usage_breakdown=token_breakdown if token_breakdown else None,
            time=state.output.time if state.output.time is not None else 0.0,
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
            num_fns_impl=state.store.get("num_fns_impl", 1),  # Default to 1 (FUT only)
            percent_lines_added=percent_lines_added,
            faithfulness_subjective=faithfulness_subj,
            interest_subjective=interest_subj,
            structural_faithfulness=structural,
            plausibility=plausibility,
            percent_plausible=percent_plausible,
            impl_autoform_success=impl_autoform_success,
            spec_sig_success=spec_sig_success,
            implementation_level=implementation_level,
            actually_invokes_given=actually_invokes_given,
            has_unit_stub=has_unit_stub,
            num_trivial_unit_theorems=num_trivial_unit_theorems,
            has_eval_statements=has_eval_statements,
            num_eval_statements=num_eval_statements,
            impl_eval_stripped=impl_eval_stripped,
            # Radon metrics (None if not found in database)
            radon=radon_obj,
            # Function discovery metadata
            function_discovery=function_discovery,
        )

    def to_inspect_scores(self) -> dict[str, "Score"]:
        """Export metrics as inspect_ai Score objects for viewer.

        Returns:
            Dictionary mapping score names to Score objects
        """
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
            scores["assertion_theorem_difference"] = Score(
                value=sf.assertion_theorem_difference,
                explanation=f"Difference between Lean theorems and Python asserts: {sf.assertion_theorem_difference} (zero is perfect, positive = more theorems, negative = fewer theorems)",
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

        # Unit stubbing detection metrics
        scores["has_unit_stub"] = Score(
            value=1.0 if self.has_unit_stub else 0.0,
            explanation="Implementation is a Unit stub (discovery failed)"
            if self.has_unit_stub
            else "Implementation has proper type signature",
        )

        if self.num_trivial_unit_theorems > 0:
            scores["num_trivial_unit_theorems"] = Score(
                value=self.num_trivial_unit_theorems,
                explanation=f"Trivial Unit theorems detected: {self.num_trivial_unit_theorems}/{self.num_theorems} (inflates plausibility without verification value)",
            )

        # #eval violation metrics
        scores["has_eval_statements"] = Score(
            value=1.0 if self.has_eval_statements else 0.0,
            explanation=f"#eval statements detected in Impl.lean: {self.num_eval_statements} statement(s) (expected for computability testing)"
            if self.has_eval_statements
            else "No #eval statements in implementation (unusual; #eval is expected for computability testing)",
        )

        if self.num_eval_statements > 0:
            scores["num_eval_statements"] = Score(
                value=self.num_eval_statements,
                explanation=f"#eval statements found: {self.num_eval_statements} (expected for computability testing)",
            )

        # #eval stripping metric (indicates uncomputable implementation)
        scores["impl_eval_stripped"] = Score(
            value=1.0 if self.impl_eval_stripped else 0.0,
            explanation="#eval statements were stripped due to build failures (uncomputable)"
            if self.impl_eval_stripped
            else "Implementation is computable (no #eval stripping needed)",
        )

        return scores

    def to_wandb_metrics(self) -> dict[str, int | float | str | None]:
        """Export metrics as wandb-compatible dictionary.

        Uses model_dump() with automatic flattening of nested structures.
        Nested keys are joined with underscores (e.g., plausibility.ran -> plausibility_ran).
        Booleans are converted to integers (0/1) for wandb compatibility.

        Special handling for token_usage_breakdown to log per-agent metrics.

        Returns:
            Dictionary of metric names to values for wandb logging
        """
        # Get the full model as a dictionary
        data = self.model_dump()

        # Extract token_usage_breakdown before flattening for custom handling
        token_breakdown = data.pop("token_usage_breakdown", None)

        # Flatten nested dictionaries
        metrics = flatten_dict(data)

        # Add per-agent token usage metrics if available
        if token_breakdown:
            for agent_usage in token_breakdown:
                subagent = agent_usage["subagent"]

                # For impl agents, include function name in key for per-function tracking
                if subagent.startswith("impl"):
                    func_name = agent_usage.get("function_name", "unknown")
                    key_prefix = f"{subagent}/{func_name}"
                else:
                    key_prefix = subagent

                # Log individual agent metrics with nested keys
                metrics[f"token_usage/{key_prefix}"] = agent_usage["tokens_spent"]
                metrics[f"toolcalls/{key_prefix}"] = agent_usage["num_toolcalls"]

            # Also log aggregate counts by agent type for easier analysis
            impl_total = sum(
                a["tokens_spent"]
                for a in token_breakdown
                if a["subagent"].startswith("impl")
            )
            spec_total = sum(
                a["tokens_spent"] for a in token_breakdown if a["subagent"] == "spec"
            )

            if impl_total > 0:
                metrics["token_usage/impl_total"] = impl_total
            if spec_total > 0:
                metrics["token_usage/spec"] = spec_total

        return metrics
