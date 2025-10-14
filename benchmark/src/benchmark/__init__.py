"""Generate the benchmark"""

from inspect_ai import eval
from benchmark.config import load_config, PromptStyle  # , setup_logfire
from benchmark.scaffold.task import fvspec
from typer import Typer, Option

cfg = load_config()
# if cfg.meta.logging:
#     setup_logfire()

app = Typer()


@app.command()
def generate(
    datafile: str = "scrapedtests.json",
    no_mcp: bool = False,
    style: PromptStyle = Option(
        None,
        help="Prompt style: 'functional' (FVAPPS) or 'mvcgen' (imperative). Overrides config.toml.",
    ),
) -> None:
    """Evaluate the fvspec benchmark.

    Args:
        datafile: Path to the JSON file containing test data
        no_mcp: Disable Lean LSP MCP tools (use simple generate instead)
        style: Prompt style override (defaults to config.toml setting)
    """
    # Use CLI arg if provided, otherwise use config
    prompt_style = style if style is not None else cfg.prompt.style
    eval(
        fvspec(datafile, use_mcp=not no_mcp, style=prompt_style),
        model=cfg.agent.model,
        display=cfg.meta.display,
        max_samples=cfg.meta.parallelism,
    )


def main() -> None:
    app()
