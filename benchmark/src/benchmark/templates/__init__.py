import json
from pathlib import Path
from typer import Typer, Option
from benchmark.config import PromptStyle
from benchmark.templates.prompt import get_system_prompt, initial

DATA = Path("data")

app = Typer()


@app.command()
def preview_prompts(
    data: str,
    style: PromptStyle = Option(
        PromptStyle.FUNCTIONAL,
        help="Prompt style: 'functional' (FVAPPS) or 'mvcgen' (imperative)",
    ),
) -> None:
    """Preview prompts for the given data file and style.

    Args:
        data: JSON file name in the data/ directory
        style: Prompt style to preview
    """
    the_json = DATA / data
    with open(the_json) as f:
        data_content = json.load(f)

    system_prompt = get_system_prompt(style)

    for obj in data_content:
        print(f"=== Style: {style} ===")
        print(system_prompt.render())
        print(initial.render(pbt=obj["pbt"], deps=obj["deps"]))
        print("=" * 80)


def main() -> None:
    app()
