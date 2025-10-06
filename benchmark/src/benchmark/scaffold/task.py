import datetime
from pathlib import Path
from inspect_ai import Task, task
from inspect_ai.agent import react
from inspect_ai.tool import mcp_server_stdio
from inspect_ai.solver import generate, use_tools, system_message
from benchmark.scaffold.tools.declaration import lean_compile, write_to_disk
from benchmark.scaffold.dataset import mk_dataset
from benchmark.templates.prompt import system

SYSTEM_PROMPT = system.render()
DATA = Path("..") / "data"


@task
def fvspec(datafile: str) -> Task:
    """
    A task generating the fvspec benchmark.
    """
    fvspec_task = Task(
        dataset=mk_dataset(DATA / datafile, datetime.datetime.now()),
        solver=[
            system_message(SYSTEM_PROMPT),
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
        dataset=[Sample("Help me write lean code that compiles and can be proved using tools.")],
        solver=react(tools=[lean_server]),
    )
