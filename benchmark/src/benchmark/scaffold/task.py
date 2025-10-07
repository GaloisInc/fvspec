import datetime
from pathlib import Path
from inspect_ai import Task, task
from inspect_ai.agent import react
from inspect_ai.dataset import Sample
from inspect_ai.tool import mcp_server_stdio
from inspect_ai.solver import generate, use_tools, system_message
from benchmark.scaffold.tools.declaration import lean_compile, write_to_disk
from benchmark.scaffold.dataset import mk_dataset
from benchmark.templates.prompt import get_system_prompt, PromptStyle

DATA = Path("..") / "data"


@task
def fvspec(
    datafile: str, use_mcp: bool = False, style: PromptStyle = "functional"
) -> Task:
    """
    A task generating the fvspec benchmark.

    Args:
        datafile: Path to the JSON file containing test data
        use_mcp: If True, use Lean LSP MCP tools in addition to lean_compile
        style: Prompt style - "functional" (FVAPPS) or "mvcgen" (imperative)
    """
    # Load the appropriate system prompt based on style
    system_prompt = get_system_prompt(style).render()

    # Create dataset with style metadata
    now = datetime.datetime.now()
    dataset = mk_dataset(DATA / datafile, now, style=style)

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


@task
def lean_task():
    lean_server = mcp_server_stdio(
        name="lean-lsp", command="uvx", args=["lean-lsp-mcp"]
    )

    return Task(
        dataset=[
            Sample(
                "Help me write lean code that compiles and can be proved using tools."
            )
        ],
        solver=react(tools=[lean_server]),
    )
