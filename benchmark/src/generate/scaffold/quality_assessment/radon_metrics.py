"""Radon code metrics collection for Python PBTs.

This module uses radon to collect objective code quality metrics from Python
property-based tests stored in the database:
- Cyclomatic Complexity (CC)
- Maintainability Index (MI)
- Raw metrics (LOC, SLOC, comments, blank lines)
- Halstead complexity metrics

These metrics provide additional data points for analyzing test complexity
and can be correlated with benchmark performance.
"""

from pydantic import BaseModel, Field
from radon import complexity, metrics, raw


class RadonMetrics(BaseModel):
    """Complete radon metrics for a Python code snippet.

    These metrics are computed statically from the source code and provide
    objective measures of code complexity and maintainability.
    """

    # Raw metrics
    loc: int = Field(description="Total lines of code")
    sloc: int = Field(description="Source lines of code (no blanks/comments)")
    comments: int = Field(description="Number of comment lines")
    blank: int = Field(description="Number of blank lines")
    lloc: int = Field(description="Logical lines of code")
    multi: int = Field(description="Multi-line strings")
    single_comments: int = Field(description="Single-line comments")

    # Cyclomatic complexity
    average_complexity: float = Field(
        description="Average cyclomatic complexity across functions"
    )
    max_complexity: int = Field(description="Maximum complexity of any function")
    total_complexity: int = Field(description="Sum of all function complexities")
    num_functions: int = Field(description="Number of functions analyzed")

    # Maintainability index (0-100, higher is better)
    maintainability_index: float = Field(
        description="Maintainability index (0-100, higher is better)"
    )

    # Halstead metrics
    halstead_vocabulary: int = Field(
        description="Number of unique operators and operands"
    )
    halstead_length: int = Field(description="Total number of operators and operands")
    halstead_volume: float = Field(description="Program volume")
    halstead_difficulty: float = Field(description="Difficulty to understand/maintain")
    halstead_effort: float = Field(description="Effort required to implement")
    halstead_time: float = Field(description="Time to implement (seconds)")
    halstead_bugs: float = Field(description="Expected number of bugs")

    @classmethod
    def from_code(cls, code: str) -> "RadonMetrics":
        """Compute radon metrics from Python source code.

        Args:
            code: Python source code to analyze

        Returns:
            RadonMetrics object with all computed metrics

        Raises:
            ValueError: If code cannot be parsed or analyzed
        """
        try:
            # Raw metrics
            raw_metrics = raw.analyze(code)

            # Cyclomatic complexity
            cc_results = complexity.cc_visit(code)
            if cc_results:
                complexities = [item.complexity for item in cc_results]
                avg_complexity = sum(complexities) / len(complexities)
                max_complexity = max(complexities)
                total_complexity = sum(complexities)
                num_functions = len(cc_results)
            else:
                # No functions found
                avg_complexity = 0.0
                max_complexity = 0
                total_complexity = 0
                num_functions = 0

            # Maintainability index
            mi = metrics.mi_visit(code, multi=False)

            # Halstead metrics
            halstead = metrics.h_visit(code)
            if halstead and halstead.total:
                h_total = halstead.total
                h_vocab = h_total.vocabulary
                h_length = h_total.length
                h_volume = h_total.volume
                h_difficulty = h_total.difficulty
                h_effort = h_total.effort
                h_time = h_total.time
                h_bugs = h_total.bugs
            else:
                # No operators/operands found (very simple code)
                h_vocab = 0
                h_length = 0
                h_volume = 0.0
                h_difficulty = 0.0
                h_effort = 0.0
                h_time = 0.0
                h_bugs = 0.0

            return cls(
                # Raw
                loc=raw_metrics.loc,
                sloc=raw_metrics.sloc,
                comments=raw_metrics.comments,
                blank=raw_metrics.blank,
                lloc=raw_metrics.lloc,
                multi=raw_metrics.multi,
                single_comments=raw_metrics.single_comments,
                # Cyclomatic
                average_complexity=avg_complexity,
                max_complexity=max_complexity,
                total_complexity=total_complexity,
                num_functions=num_functions,
                # Maintainability
                maintainability_index=mi,
                # Halstead
                halstead_vocabulary=h_vocab,
                halstead_length=h_length,
                halstead_volume=h_volume,
                halstead_difficulty=h_difficulty,
                halstead_effort=h_effort,
                halstead_time=h_time,
                halstead_bugs=h_bugs,
            )

        except Exception as e:
            raise ValueError(f"Failed to compute radon metrics: {e}") from e

    def complexity_rank(self) -> str:
        """Get complexity rank based on average complexity.

        Returns:
            Letter grade: A (1-5), B (6-10), C (11-20), D (21-50), F (51+)
        """
        cc = self.average_complexity
        if cc <= 5:
            return "A"
        elif cc <= 10:
            return "B"
        elif cc <= 20:
            return "C"
        elif cc <= 50:
            return "D"
        else:
            return "F"

    def maintainability_rank(self) -> str:
        """Get maintainability rank based on MI score.

        Returns:
            Letter grade: A (20-100), B (10-19), C (0-9)
        """
        mi = self.maintainability_index
        if mi >= 20:
            return "A"
        elif mi >= 10:
            return "B"
        else:
            return "C"


def compute_metrics_for_datapoint(datapoint_code: str) -> RadonMetrics | None:
    """Compute radon metrics for a datapoint's PBT code.

    Args:
        datapoint_code: The Python PBT source code

    Returns:
        RadonMetrics object, or None if analysis fails
    """
    try:
        return RadonMetrics.from_code(datapoint_code)
    except Exception:
        # Failed to analyze (syntax errors, etc.)
        return None
