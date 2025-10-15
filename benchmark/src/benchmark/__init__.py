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
    display: str = Option(
        None,
        help="Display mode: full, conversation, rich, plain, log, none. Overrides config.toml.",
    ),
    parallelism: int = Option(
        None,
        help="Number of samples to evaluate in parallel. Overrides config.toml.",
    ),
) -> None:
    """Evaluate the fvspec benchmark.

    Args:
        datafile: Path to the JSON file containing test data
        no_mcp: Disable Lean LSP MCP tools (use simple generate instead)
        style: Prompt style override (defaults to config.toml setting)
        display: Display mode override
        parallelism: Parallelism override
    """
    # Use CLI args if provided, otherwise use config
    prompt_style = style if style is not None else cfg.prompt.style
    display_mode = display if display is not None else cfg.meta.display
    max_samples = parallelism if parallelism is not None else cfg.meta.parallelism

    eval(
        fvspec(datafile, use_mcp=not no_mcp, style=prompt_style),
        model=cfg.agent.model,
        display=display_mode,
        max_samples=max_samples,
    )


def main() -> None:
    app()
