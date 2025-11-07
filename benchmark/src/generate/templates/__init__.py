"""CLI helpers for previewing benchmark prompt templates."""

from typer import Option, Typer

from generate.config import DATA_DIR, load_config
from generate.scaffold.dataset.connection import get_session
from generate.scaffold.dataset.queries import sample_datapoints
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
DEFAULT_DATASET = "pbts_full.db"


@app.command()
def preview_prompts(
    data: str = Option(
        DEFAULT_DATASET,
        "--data",
        "-d",
        help="Dataset SQLite database file under benchmark/data (default: pbts_full.db).",
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
    """Preview prompts for the given database and variant.

    Randomly samples from the SQLite database.

    Args:
        data: SQLite database file name located under benchmark/data
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

    db_path = DATA_DIR / data

    # Sample datapoints from database
    with get_session(db_path) as session:
        datapoints = sample_datapoints(session, actual_sample_size, actual_ranseed)

    if prompt_type.lower() == "deps":
        from generate.scaffold.formalize.impl.models import (
            DependencyPayload,
        )  # local import to avoid circular dependency

        registry = DependencyVariantRegistry()
        variant_name = variant or registry.default_variant()
        prompts = get_dependency_prompts(variant_name)

        for datapoint in datapoints:
            dep_sources = datapoint.get_deps()
            dep_names = datapoint.get_dep_names()
            if not dep_sources:
                continue

            for index, source in enumerate(dep_sources):
                dep_name = (
                    dep_names[index]
                    if index < len(dep_names)
                    else f"{datapoint.name}_{index}"
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

        for datapoint in datapoints:
            # Infer function name from test name (remove test_ prefix)
            function_name = datapoint.name.replace("test_", "").replace("Test", "")

            # Prepare template context (matching spec agent context)
            context = {
                "pbt_code": datapoint.code,
                "pbt_name": datapoint.name,
                "function_name": function_name,
                "impl_signatures": {},  # Empty for preview (no impl available yet)
            }

            print(f"=== Spec Variant: {variant_name} ===")
            print(system_prompt)
            print(initial_template.render(**context))
            print("=" * 80)


def main() -> None:
    app()
