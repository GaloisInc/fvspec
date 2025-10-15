import json
from pathlib import Path
from typer import Typer, Option
from benchmark.templates.prompt import get_variant_prompts
from benchmark.templates.registry import VariantRegistry

DATA = Path("data")

app = Typer()


@app.command()
def preview_prompts(
    data: str,
    variant: str = Option(
        None,
        help="Prompt variant name (e.g., 'control-functional', 'terse-functional'). If not specified, uses registry default.",
    ),
) -> None:
    """Preview prompts for the given data file and variant.

    Args:
        data: JSON file name in the data/ directory
        variant: Prompt variant to preview
    """
    the_json = DATA / data
    with open(the_json) as f:
        data_content = json.load(f)

    # Get variant name (use default if not specified)
    registry = VariantRegistry()
    variant_name = variant or registry.default_variant()

    system_prompt, initial_template = get_variant_prompts(variant_name)

    for obj in data_content:
        print(f"=== Variant: {variant_name} ===")
        print(system_prompt)
        print(initial_template.render(pbt=obj["pbt"], deps=obj["deps"]))
        print("=" * 80)


def main() -> None:
    app()
