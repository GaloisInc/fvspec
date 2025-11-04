"""Two-agent solver that generates implementations then specifications."""

from pathlib import Path

from inspect_ai.solver import (
    Generate,
    Solver,
    TaskState,
    solver,
)

from generate.scaffold.formalize_spec.runner import run_spec_agent
from generate.scaffold.formalize_spec.validator import extract_signatures


@solver  # type: ignore[misc]
def two_agent_orchestration(
    impl_variant: str | None = None, spec_variant: str | None = None
) -> Solver:
    """Orchestrate impl agent then spec agent sequentially.

    Flow:
    1. Generate implementations (function under test) → Impl.lean
    2. Extract function signatures from Impl.lean
    3. Generate theorem statements with signatures → Spec.lean

    Args:
        impl_variant: Variant for implementation generation (functional/mvcgen)
        spec_variant: Variant for spec generation (uses same if not specified)

    Returns:
        Solver that orchestrates both agents
    """

    async def run(state: TaskState, generate_fn: Generate) -> TaskState:
        # Phase 1: Generate implementations
        # TODO: This needs to generate the function under test implementation
        # For now, we'll skip to Phase 2 since impl is handled by dependency tools

        # Phase 2: Extract signatures from Impl.lean (if it exists)
        workspace_path = state.metadata.get("workspace")
        if not workspace_path:
            # No workspace, can't proceed
            return state

        workspace = Path(workspace_path)
        impl_file = workspace / "Fvspec" / "Impl.lean"

        impl_signatures = {}
        if impl_file.exists():
            impl_code = impl_file.read_text()
            impl_signatures = extract_signatures(impl_code)

        # Store signatures for spec agent
        state.metadata["impl_signatures"] = impl_signatures

        # Phase 3: Generate specifications with signatures
        datapoint = state.metadata.get("datapoint")
        if datapoint:
            variant = spec_variant or impl_variant
            result = await run_spec_agent(
                datapoint,
                impl_signatures,
                variant or "control-functional",
                workspace,
            )

            # Store spec result in metadata for quality assessment
            state.metadata["spec_result"] = result.model_dump()

            # Write spec to workspace
            if result.success and result.lean_code:
                spec_file = workspace / "Fvspec" / "Spec.lean"
                spec_file.write_text(result.lean_code)

        return state

    return run  # type: ignore[return-value]
