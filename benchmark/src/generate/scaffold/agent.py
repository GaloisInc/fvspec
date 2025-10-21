from inspect_ai.tool import mcp_server_stdio, mcp_tools
from generate.scaffold.tools.declaration import lean_compile


def get_lean_mcp_tools():
    """Get Lean LSP MCP tools for use in the agent.

    Selected tools appropriate for specification generation:
    - lean_run_code: Compile/check independent code snippets
    - lean_diagnostic_messages: Get errors/warnings/infos for generated code
    - lean_hover_info: Get documentation on types/terms for better specifications
    - lean_goal: Check proof goals to understand what's needed
    - lean_completions: Auto-completion for correct syntax/identifiers
    - lean_multi_attempt: Try multiple type signatures/declarations

    Note: Proof-finding tools (leansearch, loogle, state_search, hammer) are
    excluded since we generate specs with 'sorry' rather than complete proofs.
    """
    lean_server = mcp_server_stdio(
        name="lean-lsp", command="uvx", args=["lean-lsp-mcp"]
    )

    # Return both the local lean_compile tool and MCP tools
    return [
        lean_compile(),
        mcp_tools(
            lean_server,
            # https://github.com/oOo0oOo/lean-lsp-mcp
            tools=[
                "lean_run_code",
                "lean_diagnostic_messages",
                "lean_hover_info",
                "lean_goal",
                "lean_completions",
                "lean_multi_attempt",
            ],
        ),
    ]
