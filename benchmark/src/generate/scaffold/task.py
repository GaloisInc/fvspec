"""Task definitions for running the fvspec benchmark."""

from datetime import datetime
from pathlib import Path
from inspect_ai import Task, task
from inspect_ai.solver import (
    generate,
    use_tools,
    system_message,
    solver,
    Generate,
    Solver,
    TaskState,
)
from generate.scaffold.tools.declaration import (
    lean_lsp_mcp_tools,
    write_to_disk,
)
from generate.scaffold.tools import utilio
from generate.scaffold.dataset import mk_dataset
from generate.templates.spec import get_variant_prompts, VariantRegistry
from generate.scaffold.depmock.runner import depmock_setup
from generate.scaffold.depmock.agent import autoformalize_dependency_tool

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


@task
def fvspec(
    datafile: str,
    variant: str | None = None,
    sample_size: int = 100,
    ranseed: int | None = 0,
    skip_index: bool = False,
    timestamp: datetime | None = None,
) -> Task:
    """A task generating the fvspec generate.

    Args:
        datafile: Path to the JSON file containing test data
        variant: Prompt variant name from registry.toml. If None, uses registry default.
        sample_size: Number of samples to draw from the dataset
        ranseed: Random seed used when sampling datapoints
        skip_index: Skip using index file and use reservoir sampling
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
        skip_index=skip_index,
    )

    # MCP tools are always enabled - they provide objectively better LSP integration
    tools = lean_lsp_mcp_tools() + [autoformalize_dependency_tool(variant=deps_variant)]

    fvspec_task = Task(
        dataset=dataset,
        setup=[workspace_setup(), depmock_setup()],
        solver=[
            system_message(system_prompt),
            use_tools(tools),
            generate(),
        ],
        cleanup=write_to_disk,
    )

    return fvspec_task
