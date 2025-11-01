"""Task definitions for running the fvspec benchmark."""

from datetime import datetime
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.solver import (
    Generate,
    Solver,
    TaskState,
    generate,
    solver,
    system_message,
    use_tools,
)

from generate.scaffold.dataset import Datapoint, mk_dataset
from generate.scaffold.depmock.agent import create_bound_dependency_tools
from generate.scaffold.depmock.dataset import payloads_from_datapoint
from generate.scaffold.depmock.runner import depmock_setup
from generate.scaffold.tools import utilio
from generate.scaffold.tools.declaration import (
    lean_lsp_mcp_tools,
    write_to_disk,
)
from generate.templates.spec import VariantRegistry, get_variant_prompts

DATA_DIR = Path(__file__).resolve().parents[3] / "data"


@solver
def workspace_setup() -> Solver:
    """Create a per-sample workspace tmpdir for Lean files and LSP integration.

    Tmpdir Lifecycle (inspect_ai phases):
    1. Setup phase (this solver): Creates tmpdir via create_sample_workspace()
       - Uses tempfile.mkdtemp() for manual lifecycle control
       - Registers in global _active_workspaces for atexit safety net
       - Stores path in state.metadata["workspace"]
    2. Solver phase: Agent writes Lean code to <workspace>/Fvspec/Spec.lean
       - MCP tools (lean_diagnostic_messages, lean_goal, etc.) access this file
    3. Cleanup phase (write_to_disk): Normal cleanup via cleanup_sample_workspace()
       - Removes tmpdir and unregisters from atexit tracking
    4. Emergency: atexit handler cleans any remaining tmpdirs on process exit

    Memory bounds: With parallelism=N, max N tmpdirs exist simultaneously

    Thread safety: create_sample_workspace() uses locks for parallel execution

    Returns:
        Solver that creates workspace and stores path in metadata
    """

    async def run(state: TaskState, generate: Generate) -> TaskState:
        # Create workspace tmpdir
        workspace = utilio.create_sample_workspace(str(state.sample_id))

        # Store workspace path in metadata for MCP tools to use
        state.metadata["workspace"] = str(workspace)

        return state

    return run


@solver
def register_dependency_tools(variant: str | None = None) -> Solver:
    """Register LSP and per-dependency autoformalization tools.

    This solver:
    1. Registers Lean LSP MCP tools (diagnostic_messages, goal, etc.)
    2. Creates one autoformalization tool per dependency in the datapoint
    3. Each dependency tool is bound to its specific payload

    When the main agent calls a dependency tool, it will:
    1. Run the dependency autoformalizer
    2. Persist the result to cache and sample directory
    3. Update Deps.lean incrementally
    4. Return success message to the agent

    Args:
        variant: Optional prompt variant for dependency translation

    Returns:
        Solver that registers all tools in TaskState
    """

    async def run(state: TaskState, generate: Generate) -> TaskState:
        # Always add LSP tools
        all_tools = lean_lsp_mcp_tools()

        # Add dependency tools if datapoint has dependencies
        datapoint = state.metadata.get("datapoint")
        if isinstance(datapoint, Datapoint):
            payloads = payloads_from_datapoint(datapoint)
            if payloads:
                dep_tools = create_bound_dependency_tools(payloads, variant=variant)
                all_tools.extend(dep_tools)

        # Set tools on state
        state.tools = all_tools

        return state

    return run


@task
def fvspec(
    datafile: str,
    variant: str | None = None,
    sample_size: int = 100,
    ranseed: int | None = 0,
    timestamp: datetime | None = None,
) -> Task:
    """A task generating the fvspec generate.

    Args:
        datafile: Path to the JSON file containing test data
        variant: Prompt variant name from registry.toml. If None, uses registry default.
        sample_size: Number of samples to draw from the dataset
        ranseed: Random seed used when sampling datapoints

        timestamp: Pre-created timestamp to use (defaults to now if None)
    """
    now = timestamp or datetime.now()

    # Resolve variant and get its style for deps consistency
    registry = VariantRegistry()
    resolved_variant = variant or registry.default_variant()
    variant_config = registry.get_variant(resolved_variant)
    deps_variant = (
        variant_config.style
    )  # Use the same style (functional/mvcgen) for deps

    # Load variant prompts
    system_prompt, _ = get_variant_prompts(variant)
    dataset = mk_dataset(
        DATA_DIR / datafile,
        now,
        variant=variant,
        sample_size=sample_size,
        ranseed=ranseed,
    )

    # Tools are registered dynamically in setup based on each sample's dependencies
    fvspec_task = Task(
        dataset=dataset,
        setup=[
            workspace_setup(),
            depmock_setup(),
            register_dependency_tools(variant=deps_variant),
        ],
        solver=[
            system_message(system_prompt),
            use_tools(),  # Uses tools registered in setup
            generate(),
        ],
        cleanup=write_to_disk,
    )

    return fvspec_task
