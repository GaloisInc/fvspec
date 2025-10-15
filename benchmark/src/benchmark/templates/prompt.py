from jinja2 import Environment, PackageLoader, Template

from benchmark.templates.registry import VariantRegistry

env = Environment(loader=PackageLoader("benchmark"))


def get_variant_prompts(variant_name: str | None = None) -> tuple[str, Template]:
    """Load system and initial prompts for a specific variant.

    Args:
        variant_name: Name of the variant to load. If None, uses default from registry.

    Returns:
        Tuple of (system_prompt_text, initial_prompt_template)

    Raises:
        ValueError: If variant name is not found in registry
        FileNotFoundError: If variant files are missing
    """
    registry = VariantRegistry()

    if variant_name is None:
        variant_name = registry.default_variant()

    variant_config = registry.get_variant(variant_name)

    # Create a Jinja2 template from the initial prompt string
    initial_template = env.from_string(variant_config.initial_template)

    return variant_config.system_prompt, initial_template
