"""Task definitions for running the fvspec benchmark."""

from datetime import datetime
from pathlib import Path
from inspect_ai import Task, task
from inspect_ai.solver import generate, use_tools, system_message
from generate.scaffold.tools.declaration import (
    lean_compile,
    lean_lsp_mcp,
    write_to_disk,
)
from generate.scaffold.dataset import mk_dataset
from generate.templates.spec import get_variant_prompts, VariantRegistry
from generate.scaffold.depmock.runner import depmock_setup
from generate.scaffold.depmock.agent import autoformalize_dependency_tool

DATA_DIR = Path(__file__).resolve().parents[3] / "data"


@task
def fvspec(
    datafile: str,
    use_mcp: bool = False,
    variant: str | None = None,
    sample_size: int = 100,
    ranseed: int | None = 0,
    skip_index: bool = False,
    timestamp: datetime | None = None,
) -> Task:
    """A task generating the fvspec generate.

    Args:
        datafile: Path to the JSON file containing test data
        use_mcp: If True, use Lean LSP MCP tools in addition to lean_compile
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

    if use_mcp:
        fvspec_task = Task(
            dataset=dataset,
            setup=[depmock_setup()],
            solver=[
                system_message(system_prompt),
                use_tools(
                    lean_lsp_mcp()
                    + [autoformalize_dependency_tool(variant=deps_variant)]
                ),
                generate(),
            ],
            cleanup=write_to_disk,
        )
    else:
        fvspec_task = Task(
            dataset=dataset,
            setup=[depmock_setup()],
            solver=[
                system_message(system_prompt),
                use_tools(
                    [
                        lean_compile(),
                        autoformalize_dependency_tool(variant=deps_variant),
                    ]
                ),
                generate(),
            ],
            cleanup=write_to_disk,
        )

    return fvspec_task
