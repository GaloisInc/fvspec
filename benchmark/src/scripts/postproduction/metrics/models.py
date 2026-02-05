"""Pydantic models for Lean code metrics."""

from datetime import datetime

from pydantic import BaseModel, Field


class StructureMetrics(BaseModel):
    """Code structure metrics for Lean code."""

    # Line counts
    total_lines: int = Field(description="Total lines including blank and comments")
    code_lines: int = Field(
        description="Lines containing code (excluding blank/comments)"
    )
    blank_lines: int = Field(description="Number of blank lines")
    comment_lines: int = Field(description="Number of comment lines")

    # Declaration counts
    num_axioms: int = Field(description="Number of axiom declarations")
    num_defs: int = Field(description="Number of def declarations")
    num_theorems: int = Field(description="Number of theorem declarations")
    num_lemmas: int = Field(description="Number of lemma declarations")
    num_structures: int = Field(description="Number of structure declarations")
    num_inductives: int = Field(description="Number of inductive declarations")

    # Proof quality indicators
    num_sorries: int = Field(description="Number of sorry placeholders")
    num_admits: int = Field(description="Number of admit tactics")
    num_axiomized_defs: int = Field(
        description="Definitions using axiom instead of def"
    )

    # Special constructs
    num_eval_statements: int = Field(description="Number of #eval statements")
    num_imports: int = Field(description="Number of import statements")
    num_namespace_blocks: int = Field(description="Number of namespace declarations")


class ComplexityMetrics(BaseModel):
    """Complexity metrics for Lean code."""

    # Nesting and depth
    max_nesting_depth: int = Field(
        description="Maximum nesting depth of proof terms/tactics"
    )
    avg_nesting_depth: float = Field(description="Average nesting depth")

    # Term size
    max_term_size: int = Field(description="Size of largest proof term (token count)")
    avg_term_size: float = Field(description="Average proof term size")
    total_proof_tokens: int = Field(description="Total tokens in all proof terms")

    # Proof complexity
    avg_proof_steps: float = Field(
        description="Average number of tactic steps per proof"
    )
    max_proof_steps: int = Field(description="Maximum proof steps in any single proof")

    # Dependencies
    num_dependencies: int = Field(
        description="Number of external definitions/theorems referenced"
    )
    avg_dependencies_per_decl: float = Field(
        description="Average dependencies per declaration"
    )

    # Signature complexity
    avg_param_count: float = Field(
        description="Average parameters per function/theorem"
    )
    max_param_count: int = Field(description="Maximum parameters in any declaration")

    # Halstead complexity metrics
    halstead_vocabulary: int = Field(
        description="Number of unique operators and operands (n)"
    )
    halstead_length: int = Field(
        description="Total number of operators and operands (N)"
    )
    halstead_volume: float = Field(description="Program volume (V = N × log₂(n))")
    halstead_difficulty: float = Field(
        description="Difficulty to understand/maintain (D)"
    )
    halstead_effort: float = Field(description="Effort required (E = D × V)")
    halstead_time: float = Field(description="Time to implement in seconds (T = E/18)")
    halstead_bugs: float = Field(description="Expected number of bugs (B = V/3000)")


class LeanCodeMetrics(BaseModel):
    """Complete Lean code metrics for a sample."""

    # Per-file metrics
    spec_structure: StructureMetrics | None = Field(
        default=None, description="Structure metrics for Spec.lean"
    )
    impl_structure: StructureMetrics | None = Field(
        default=None, description="Structure metrics for Impl.lean"
    )
    tests_structure: StructureMetrics | None = Field(
        default=None, description="Structure metrics for Tests.lean"
    )

    spec_complexity: ComplexityMetrics | None = Field(
        default=None, description="Complexity metrics for Spec.lean"
    )
    impl_complexity: ComplexityMetrics | None = Field(
        default=None, description="Complexity metrics for Impl.lean"
    )
    tests_complexity: ComplexityMetrics | None = Field(
        default=None, description="Complexity metrics for Tests.lean"
    )

    # Aggregate metrics
    total_lean_lines: int = Field(description="Total lines across all Lean files")
    total_sorries: int = Field(description="Total sorries across all files")
    total_axioms: int = Field(description="Total axioms across all files")


class MetricsMetadata(BaseModel):
    """Metadata about metrics computation."""

    version: str = Field(description="Metrics script version")
    timestamp: datetime = Field(description="When metrics were computed")
    computation_time_seconds: float = Field(description="Time taken to compute metrics")
    spec_available: bool = Field(description="Whether Spec.lean was present")
    impl_available: bool = Field(description="Whether Impl.lean was present")
    tests_available: bool = Field(description="Whether Tests.lean was present")
