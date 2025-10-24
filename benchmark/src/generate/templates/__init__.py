"""CLI helpers for previewing benchmark prompt templates."""

import jsonlines
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
DEFAULT_DATASET = "pbts.jsonl"


@app.command()
def preview_prompts(
    data: str = Option(
        DEFAULT_DATASET,
        "--data",
        "-d",
        help="Dataset JSONL file under benchmark/data (default: pbts.jsonl).",
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
    limit: int = Option(
        5,
        "--limit",
        "-n",
        help="Maximum number of samples to preview (default: 5). Use -1 for unlimited (WARNING: 116GB file!).",
    ),
) -> None:
    """Preview prompts for the given data file and variant.

    Args:
        data: JSONL file name located under benchmark/data
        variant: Prompt variant to preview
        prompt_type: Which prompt family to preview ('spec' or 'deps')
        limit: Maximum number of samples to preview
    """
    the_jsonl = DATA_DIR / data

    # Stream the file and only load the requested number of samples
    # limit == -1 means unlimited (load all)
    data_content: list[dict] = []
    with jsonlines.open(the_jsonl) as reader:
        for idx, obj in enumerate(reader):
            if limit != -1 and idx >= limit:
                break
            data_content.append(obj)

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
