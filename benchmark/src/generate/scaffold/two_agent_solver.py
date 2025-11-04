"""Two-agent solver that generates implementations then specifications."""

from pathlib import Path

from inspect_ai.solver import (
    Generate,
    Solver,
    TaskState,
    solver,
)

from generate.scaffold.dataset import Datapoint
from generate.scaffold.formalize_impl import (
    FunctionImplPayload,
    function_impl_agent,
)
from generate.scaffold.formalize_spec import (
    SpecPayload,
    spec_generation_agent,
)
from generate.scaffold.formalize_spec.validator import extract_signatures
from generate.scaffold.function_discovery import lookup_function_exact


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
        # Get workspace and datapoint
        workspace_path = state.metadata.get("workspace")
        if not workspace_path:
            return state

        workspace = Path(workspace_path)
        datapoint = state.metadata.get("datapoint")
        if not isinstance(datapoint, Datapoint):
            return state

        # Determine function name from PBT
        # Simple heuristic: test_foo → foo, test_bar_baz → bar_baz
        function_name = datapoint.name
        if function_name.startswith("test_"):
            function_name = function_name[5:]

        # Try to discover function code
        db_session = state.metadata.get("db_session")
        function_code = None
        if db_session:
            result = lookup_function_exact(db_session, datapoint.repo_id, function_name)
            if result:
                function_code = result.code

        # Phase 1: Generate implementation for function under test
        impl_payload = FunctionImplPayload(
            pbt_code=datapoint.code,
            pbt_name=datapoint.name,
            function_name=function_name,
            function_code=function_code,
            dependencies={},  # TODO: integrate with dependency system
            variant=impl_variant or "control-functional",
        )

        impl_result = await function_impl_agent(impl_payload, workspace)

        # Store impl result in metadata
        state.metadata["impl_result"] = impl_result.model_dump()

        # Write Impl.lean if successful
        impl_file = workspace / "Fvspec" / "Impl.lean"
        if impl_result.success and impl_result.lean_code:
            impl_file.write_text(impl_result.lean_code)

        # Phase 2: Extract signatures from Impl.lean
        impl_signatures = {}
        if impl_file.exists():
            impl_code = impl_file.read_text()
            impl_signatures = extract_signatures(impl_code)

        # Store signatures for debugging
        state.metadata["impl_signatures"] = impl_signatures

        # Phase 3: Generate specifications with signatures
        spec_payload = SpecPayload(
            pbt_code=datapoint.code,
            pbt_name=datapoint.name,
            function_name=function_name,
            impl_signatures=impl_signatures,
            variant=spec_variant or impl_variant or "control-functional",
        )

        spec_result = await spec_generation_agent(spec_payload, workspace)

        # Store spec result in metadata for quality assessment
        state.metadata["spec_result"] = spec_result.model_dump()

        # Write spec to workspace
        if spec_result.success and spec_result.lean_code:
            spec_file = workspace / "Fvspec" / "Spec.lean"
            spec_file.write_text(spec_result.lean_code)

        return state

    return run  # type: ignore[return-value]
