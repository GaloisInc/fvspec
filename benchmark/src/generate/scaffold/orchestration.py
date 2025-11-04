"""Two-agent orchestration for fvspec benchmark.

Architecture:
1. Implementation Agent: Generates function implementations (zero sorry required)
2. Specification Agent: Generates theorem statements (with sorry for proofs)

The orchestration runs both agents sequentially, passing type signatures between them.
"""

from datetime import datetime
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.solver import Generate, Solver, TaskState, solver

from generate.scaffold.dataset import Datapoint, mk_dataset
from generate.scaffold.dataset.connection import get_session
from generate.scaffold.dataset.function_discovery import lookup_function_exact
from generate.scaffold.formalize.impl import (
    FunctionImplPayload,
    function_impl_agent,
)
from generate.scaffold.formalize.spec import (
    SpecPayload,
    spec_generation_agent,
)
from generate.scaffold.formalize.spec.validator import extract_signatures
from generate.scaffold.tools import utilio
from generate.scaffold.tools.declaration import write_to_disk
from generate.templates.spec import VariantRegistry

DATA_DIR = Path(__file__).resolve().parents[3] / "data"


@solver
def workspace_setup() -> Solver:
    """Create a per-sample workspace tmpdir for Lean files and LSP integration.

    Tmpdir Lifecycle:
    1. Setup phase: Creates tmpdir via create_sample_workspace()
    2. Solver phase: Agents write Lean code to workspace
    3. Cleanup phase: write_to_disk removes tmpdir

    Thread safety: Uses locks for parallel execution

    Returns:
        Solver that creates workspace and stores path in metadata
    """

    async def run(state: TaskState, generate: Generate) -> TaskState:
        workspace = utilio.create_sample_workspace(str(state.sample_id))
        state.metadata["workspace"] = str(workspace)
        return state

    return run


@solver
def pass_session_to_state(db_path: Path) -> Solver:
    """Inject database session into task state for function discovery.

    Args:
        db_path: Path to the pbts_full.db SQLite database

    Returns:
        Solver that stores db session in metadata
    """

    async def run(state: TaskState, generate: Generate) -> TaskState:
        # Create session and store in metadata for function discovery
        session = get_session(db_path)
        state.metadata["db_session"] = session
        return state

    return run


@solver
def orchestrate_subagents(variant: str | None = None) -> Solver:
    """Orchestrate impl agent then spec agent sequentially.

    Flow:
    1. Discover function code from database (if available)
    2. Generate function implementation → Impl.lean (zero sorry)
    3. Extract type signatures from Impl.lean
    4. Generate theorem statements → Spec.lean (with sorry)

    Args:
        variant: Prompt variant for both agents (functional/mvcgen style)

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

        # Determine function name from PBT name
        # Heuristic: test_foo → foo, test_bar_baz → bar_baz
        function_name = datapoint.name
        if function_name.startswith("test_"):
            function_name = function_name[5:]

        # Try to discover function code from database
        db_session = state.metadata.get("db_session")
        function_code = None
        if db_session:
            result = lookup_function_exact(db_session, datapoint.repo_id, function_name)
            if result:
                function_code = result.code

        # Phase 1: Generate implementation for function under test
        # Map spec variant to impl variant style (control-functional → functional)
        spec_variant_name = variant or "control-functional"
        spec_registry = VariantRegistry()
        spec_variant = spec_registry.get_variant(spec_variant_name)
        impl_variant = spec_variant.style  # Extract style: functional or mvcgen

        impl_payload = FunctionImplPayload(
            pbt_code=datapoint.code,
            pbt_name=datapoint.name,
            function_name=function_name,
            function_code=function_code,
            dependencies={},  # Dependencies handled separately if needed
            variant=impl_variant,
        )

        impl_result = await function_impl_agent(impl_payload, workspace)

        # Store impl result in metadata for quality assessment
        state.metadata["impl_result"] = impl_result.model_dump()

        # Write Impl.lean if successful
        impl_file = workspace / "Fvspec" / "Impl.lean"
        if impl_result.success and impl_result.lean_code:
            impl_file.write_text(impl_result.lean_code)

        # Phase 2: Extract type signatures from Impl.lean
        impl_signatures = {}
        if impl_file.exists():
            impl_code = impl_file.read_text()
            impl_signatures = extract_signatures(impl_code)

        # Store signatures for debugging and quality assessment
        state.metadata["impl_signatures"] = impl_signatures

        # Phase 3: Generate theorem statements with signatures
        spec_payload = SpecPayload(
            pbt_code=datapoint.code,
            pbt_name=datapoint.name,
            function_name=function_name,
            impl_signatures=impl_signatures,
            variant=spec_variant_name,
        )

        spec_result = await spec_generation_agent(spec_payload, workspace)

        # Store spec result in metadata for quality assessment
        state.metadata["spec_result"] = spec_result.model_dump()

        # Write Spec.lean if successful
        if spec_result.success and spec_result.lean_code:
            spec_file = workspace / "Fvspec" / "Spec.lean"
            spec_file.write_text(spec_result.lean_code)

        return state

    return run  # type: ignore[return-value]


@task
def fvspec(
    datafile: str,
    variant: str | None = None,
    sample_size: int = 100,
    ranseed: int | None = 0,
    timestamp: datetime | None = None,
) -> Task:
    """Create fvspec benchmark task with two-agent architecture.

    Args:
        datafile: Path to pbts_full.db database file
        variant: Prompt variant name from registry.toml (functional/mvcgen style)
        sample_size: Number of samples to draw from the dataset
        ranseed: Random seed used when sampling datapoints
        timestamp: Pre-created timestamp (defaults to now if None)

    Returns:
        Task configured with two-agent orchestration
    """
    now = timestamp or datetime.now()

    # Resolve variant to get consistent style for both agents
    registry = VariantRegistry()
    resolved_variant = variant or registry.default_variant()

    # Load dataset
    db_path = DATA_DIR / datafile
    dataset = mk_dataset(
        db_path,
        now,
        variant=resolved_variant,
        sample_size=sample_size,
        ranseed=ranseed,
    )

    # Two-agent architecture: impl → spec
    return Task(
        dataset=dataset,
        setup=[
            workspace_setup(),
            pass_session_to_state(db_path),
        ],
        solver=[
            orchestrate_subagents(variant=resolved_variant),
        ],
        cleanup=write_to_disk,
    )
