from jinja2 import Environment, FileSystemLoader, Template
from pathlib import Path

from benchmark.templates.registry import VariantRegistry

# Configure Jinja2 to load templates from the filesystem
# This allows {% include %} to work for shared fragments
_templates_dir = Path(__file__).parent
env = Environment(loader=FileSystemLoader(_templates_dir))


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
    # This now supports {% include %} directives for shared fragments
    initial_template = env.from_string(variant_config.initial_template)

    # Also process system prompt to resolve any {% include %} directives
    system_template = env.from_string(variant_config.system_prompt)
    system_prompt = system_template.render()

    return system_prompt, initial_template
