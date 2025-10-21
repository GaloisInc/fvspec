"""Task definitions for running the fvspec benchmark."""

from datetime import datetime
from pathlib import Path
from inspect_ai import Task, task
from inspect_ai.solver import generate, use_tools, system_message
from generate.scaffold.tools.declaration import lean_compile, write_to_disk
from generate.scaffold.dataset import mk_dataset
from generate.templates.spec import get_variant_prompts
from generate.scaffold.depmock.runner import depmock_setup

DATA_DIR = Path(__file__).resolve().parents[3] / "data"


@task
def fvspec(
    datafile: str,
    use_mcp: bool = False,
    variant: str | None = None,
    sample_size: int = 100,
    ranseed: int | None = 0,
) -> Task:
    """A task generating the fvspec generate.

    Args:
        datafile: Path to the JSON file containing test data
        use_mcp: If True, use Lean LSP MCP tools in addition to lean_compile
        variant: Prompt variant name from registry.toml. If None, uses registry default.
        sample_size: Number of samples to draw from the dataset
        ranseed: Random seed used when sampling datapoints
    """
    now = datetime.now()

    # Load variant prompts (will use registry default if variant is None)
    system_prompt, _ = get_variant_prompts(variant)
    dataset = mk_dataset(
        DATA_DIR / datafile,
        now,
        variant=variant,
        sample_size=sample_size,
        ranseed=ranseed,
    )

    if use_mcp:
        from generate.scaffold.agent import get_lean_mcp_tools

        fvspec_task = Task(
            dataset=dataset,
            setup=[depmock_setup()],
            solver=[
                system_message(system_prompt),
                use_tools(get_lean_mcp_tools()),
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
                use_tools([lean_compile()]),
                generate(),
            ],
            cleanup=write_to_disk,
        )

    return fvspec_task
