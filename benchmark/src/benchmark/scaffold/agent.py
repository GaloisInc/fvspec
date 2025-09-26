from inspect_ai.solver import basic_agent, solver
from inspect_ai.solver.tool import mcp_tools
from generate.scaffold.tool import lean_tool
from generate.scaffold.task import lean_server


@solver
def lean_agent(max_attempts: int = 5):
    return basic_agent(
        tools=[
            lean_tool(),
            mcp_tools(
                lean_server,
                # https://github.com/oOo0oOo/lean-lsp-mcp
                tools=[
                    "lean_diagnostic_messages",
                    "lean_completions",
                    "lean_multi_attempt",
                ],
            ),
        ],
        max_attempts=max_attempts,
    )
