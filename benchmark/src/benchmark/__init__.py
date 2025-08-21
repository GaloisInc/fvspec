"""Generate the benchmark"""

from inspect_ai import eval
from generate.config import load_config, setup_logfire
from generate.scaffold.task import fvspec
from typer import Typer

cfg = load_config()
if cfg.meta.logging:
    setup_logfire()

app = Typer()


@app.command()
def evaluate_fvspec(datafile: str = "scrapedtests.json"):
    """Evaluate the fvspec benchmark."""
    eval(fvspec(datafile), model=cfg.agent.model)


def main():
    app()
