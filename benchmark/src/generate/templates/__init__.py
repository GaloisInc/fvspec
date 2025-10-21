"""CLI helpers for previewing benchmark prompt templates."""

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
DEFAULT_DATASET = "scrapedtests.json"


@app.command()
def preview_prompts(
    data: str = Option(
        DEFAULT_DATASET,
        "--data",
        "-d",
        help="Dataset JSON file under benchmark/data (default: scrapedtests.json).",
    ),
    variant: str = Option(
        None,
        help="Prompt variant name (e.g., 'control-functional', 'terse-functional'). If not specified, uses registry default.",
    ),
    prompt_type: str = Option(
        "spec",
        "--prompt-type",
        "-t",
        help="Which prompt family to preview: 'spec' (default) or 'deps'.",
    ),
) -> None:
    """Preview prompts for the given data file and variant.

    Args:
        data: JSON file name located under benchmark/data
        variant: Prompt variant to preview
        prompt_type: Which prompt family to preview ('spec' or 'deps')
    """
    the_json = DATA_DIR / data
    with open(the_json) as f:
        data_content = json.load(f)

    if prompt_type.lower() == "deps":
        from generate.scaffold.depmock.models import (
            DependencyPayload,
        )  # local import to avoid circular dependency

        registry = DependencyVariantRegistry()
        variant_name = variant or registry.default_variant()
        prompts = get_dependency_prompts(variant_name)

        for obj in data_content:
            dep_sources = obj.get("deps") or []
            dep_names = obj.get("dep_names") or []
            if not dep_sources:
                continue

            for index, source in enumerate(dep_sources):
                dep_name = (
                    dep_names[index]
                    if index < len(dep_names)
                    else f"{obj.get('pbt_name', 'dependency')}_{index}"
                )
                payload = DependencyPayload(
                    dep_name=dep_name or f"dependency_{index}",
                    python_source=source,
                )
                rendered = prompts.translate_template.render(payload.prompt_context())
                print(f"=== Dependency Variant: {variant_name} :: {dep_name} ===")
                print(prompts.system_prompt)
                print(rendered)
                print("=" * 80)
    else:
        # Default to specification prompts
        registry = VariantRegistry()
        variant_name = variant or registry.default_variant()

        system_prompt, initial_template = get_variant_prompts(variant_name)

        for obj in data_content:
            print(f"=== Spec Variant: {variant_name} ===")
            print(system_prompt)
            print(initial_template.render(pbt=obj["pbt"], deps=obj["deps"]))
            print("=" * 80)


def main() -> None:
    app()
