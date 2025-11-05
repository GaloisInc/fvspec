"""CLI helpers for previewing benchmark prompt templates."""

import json
import random

import jsonlines
from typer import Option, Typer

from generate.config import DATA_DIR, load_config
from generate.templates.impl import (
    DependencyVariantRegistry,
    get_dependency_prompts,
)
from generate.templates.models import Prompt
from generate.templates.spec import VariantRegistry, get_variant_prompts

__all__ = [
    "get_variant_prompts",
    "VariantRegistry",
    "get_dependency_prompts",
    "DependencyVariantRegistry",
    "Prompt",
]

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
    sample_size: int | None = Option(
        None,
        "--sample-size",
        "-n",
        help="Number of samples to randomly select. If not specified, uses value from config.toml (default: 100).",
    ),
    ranseed: int | None = Option(
        None,
        "--ranseed",
        help="Random seed for sampling. If not specified, uses value from config.toml (default: 0).",
    ),
) -> None:
    """Preview prompts for the given data file and variant.

    Randomly samples from the dataset using reservoir sampling.

    Args:
        data: JSONL file name located under benchmark/data
        variant: Prompt variant to preview
        prompt_type: Which prompt family to preview ('spec' or 'deps')
        sample_size: Number of samples to randomly select
        ranseed: Random seed for deterministic sampling
    """
    # Load config for defaults
    config = load_config()

    # Use CLI args if provided, otherwise fall back to config
    actual_sample_size = (
        sample_size if sample_size is not None else config.dataset.sample_size
    )
    actual_ranseed = ranseed if ranseed is not None else config.dataset.ranseed

    the_jsonl = DATA_DIR / data
    index_file = DATA_DIR / f"{data}.index"

    # Use indexed sampling if available (fast), otherwise reservoir sampling (slow)
    rng = random.Random(actual_ranseed)

    if index_file.exists():
        # Fast path: indexed sampling
        with open(index_file) as f:
            index_data = json.load(f)
            offsets = index_data["offsets"]

        total_lines = len(offsets)
        selected_indices = rng.sample(
            range(total_lines), min(actual_sample_size, total_lines)
        )

        data_content = []
        with open(the_jsonl, "rb") as f:
            for idx in sorted(selected_indices):
                f.seek(offsets[idx])
                line = f.readline().decode("utf-8")
                data_content.append(json.loads(line))
    else:
        # Slow path: reservoir sampling (reads entire file)
        reservoir: list[dict] = []
        with jsonlines.open(the_jsonl) as reader:
            for idx, obj in enumerate(reader):
                if idx < actual_sample_size:
                    reservoir.append(obj)
                else:
                    # Reservoir sampling: randomly replace elements
                    j = rng.randint(0, idx)
                    if j < actual_sample_size:
                        reservoir[j] = obj
        data_content = reservoir

    if prompt_type.lower() == "deps":
        from generate.scaffold.formalize.impl.models import (
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
