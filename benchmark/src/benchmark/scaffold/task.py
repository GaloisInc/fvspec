import datetime
from pathlib import Path
from inspect_ai import Task, task
from inspect_ai.solver import generate, use_tools, system_message
from benchmark.scaffold.tools.declaration import lean_compile, write_to_disk
from benchmark.scaffold.dataset import mk_dataset
from benchmark.templates.prompt import get_variant_prompts

DATA = Path("..") / "data"


@task
def fvspec(
    datafile: str,
    use_mcp: bool = False,
    variant: str | None = None,
    sample_size: int = 100,
) -> Task:
    """
    A task generating the fvspec benchmark.

    Args:
        datafile: Path to the JSON file containing test data
        use_mcp: If True, use Lean LSP MCP tools in addition to lean_compile
        variant: Prompt variant name from registry.toml. If None, uses registry default.
        sample_size: Number of samples to draw from the dataset
    """
    now = datetime.datetime.now()

    # Load variant prompts (will use registry default if variant is None)
    system_prompt, _ = get_variant_prompts(variant)
    dataset = mk_dataset(DATA / datafile, now, variant=variant, sample_size=sample_size)

    if use_mcp:
        from benchmark.scaffold.agent import get_lean_mcp_tools

        fvspec_task = Task(
            dataset=dataset,
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
            solver=[
                system_message(system_prompt),
                use_tools([lean_compile()]),
                generate(),
            ],
            cleanup=write_to_disk,
        )

    return fvspec_task
