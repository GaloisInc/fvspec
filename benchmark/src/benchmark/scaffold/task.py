from pathlib import Path
from inspect_ai import Task, task
from inspect_ai.solver import generate, use_tools, system_message
from generate.scaffold.tools.declaration import lean_compile, write_code_to_disk
from generate.scaffold.dataset import mk_dataset
from generate.templates.prompt import system

SYSTEM_PROMPT = system.render()
DATA = Path("data")


@task
def fvspec(datafile: str) -> Task:
    """
    A task generating the fvspec benchmark.
    """
    fvspec_task = Task(
        dataset=mk_dataset(DATA / datafile),
        solver=[
            system_message(SYSTEM_PROMPT),
            use_tools([lean_compile(), write_code_to_disk()]),
            generate(),
        ],
    )

    return fvspec_task
