import json
from pathlib import Path
from typer import Typer, Option
from generate.templates.spec import get_variant_prompts, VariantRegistry
from generate.templates.deps import (
    get_dependency_prompts,
    DependencyVariantRegistry,
)

__all__ = [
    "get_variant_prompts",
    "VariantRegistry",
    "get_dependency_prompts",
    "DependencyVariantRegistry",
]

DATA_DIR = Path(__file__).resolve().parents[3] / "data"

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
        data: JSON file name located under benchmark/data
        variant: Prompt variant to preview
    """
    the_json = DATA_DIR / data
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
