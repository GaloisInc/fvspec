from inspect_ai.solver import basic_agent, solver
from generate.scaffold.tool import lean_tool


# file is currently dead code
@solver
def lean_agent(max_attempts: int = 5):
    return basic_agent(
        tools=[lean_tool()],
        max_attempts=max_attempts,
    )
