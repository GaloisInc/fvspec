"""Load prompt templates for unified formalization agent."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, Template

from generate.templates.formalize.registry import FormalizationVariantRegistry

# Configure Jinja2 to load templates from the filesystem
_templates_dir = Path(__file__).parent
env = Environment(loader=FileSystemLoader(_templates_dir))


def get_formalization_prompts(
    variant_name: str | None = None,
) -> tuple[str, Template]:
    """Load system and initial prompts for a specific formalization variant.

    Args:
        variant_name: Name of the variant to load. If None, uses default.

    Returns:
        Tuple of (system_prompt_text, initial_prompt_template)
    """
    registry = FormalizationVariantRegistry()

    if variant_name is None:
        variant_name = registry.default_variant()

    variant_config = registry.get_variant(variant_name)

    # Process Jinja2 includes in both prompts
    initial_template = env.from_string(variant_config.initial_template)
    system_template = env.from_string(variant_config.system_prompt)
    system_prompt = system_template.render()

    return system_prompt, initial_template
