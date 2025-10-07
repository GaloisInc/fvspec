"""Generate the benchmark"""

from inspect_ai import eval
from benchmark.config import load_config  # , setup_logfire
from benchmark.scaffold.task import fvspec
from typer import Typer

cfg = load_config()
# if cfg.meta.logging:
#     setup_logfire()

app = Typer()


@app.command()
def generate(datafile: str = "scrapedtests.json", no_mcp: bool = False) -> None:
    """Evaluate the fvspec benchmark.

    Args:
        datafile: Path to the JSON file containing test data
        no_mcp: Disable Lean LSP MCP tools (use simple generate instead)
    """
    eval(fvspec(datafile, use_mcp=not no_mcp), model=cfg.agent.model)


def main() -> None:
    app()
