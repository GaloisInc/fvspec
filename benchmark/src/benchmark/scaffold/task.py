from pathlib import Path
from inspect_ai import Task, task
from inspect_ai.solver import generate, use_tools, system_message
from benchmark.scaffold.tools.declaration import lean_compile, write_code_to_disk, write_problem_to_disk
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
        dataset=mk_dataset(DATA / datafile),
        solver=[
            system_message(SYSTEM_PROMPT),
            use_tools([write_problem_to_disk(), lean_compile(), write_code_to_disk()]),
            generate(),
        ],
    )

    return fvspec_task
