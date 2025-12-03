"""Load dependency prompt bundles for autoformalization variants."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, Template
from pydantic import BaseModel, ConfigDict

from generate.templates.impl.registry import DependencyVariantRegistry


class DependencyPromptBundle(BaseModel):
    """Group of prompts used by the dependency autoformalization subagent."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    system_prompt: str
    translate_template: Template
    refine_template: Template


_templates_dir = Path(__file__).parent
_env = Environment(loader=FileSystemLoader(_templates_dir))


def get_dependency_prompts(variant: str | None = None) -> DependencyPromptBundle:
    """Load system/translate/refine prompts for the given dependency variant."""
    registry = DependencyVariantRegistry()
    variant_name = variant or registry.default_variant()
    if variant_name == "default":
        variant_name = registry.default_variant()

    variant_config = registry.get_variant(variant_name)

    system_prompt = _env.from_string(variant_config.system_prompt).render()
    translate_template = _env.from_string(variant_config.translate_template)
    refine_template = _env.from_string(variant_config.refine_template)

    return DependencyPromptBundle(
        system_prompt=system_prompt,
        translate_template=translate_template,
        refine_template=refine_template,
    )


def get_impl_function_prompts(variant: str | None = None) -> tuple[str, Template]:
    """Load system/user prompts for function implementation generation.

    Loads dedicated function implementation prompts from impl/variants/{variant}/function_system.prompt.template

    Args:
        variant: Implementation variant name (functional or mvcgen)

    Returns:
        Tuple of (system_prompt, user_template)
    """
    # Use DependencyVariantRegistry just to get the variant list
    registry = DependencyVariantRegistry()
    variant_name = variant or registry.default_variant()
    if variant_name == "default":
        variant_name = registry.default_variant()

    # Load the dedicated function system prompt (not dependency prompt!)
    variant_path = _templates_dir / "variants" / variant_name
    function_system_prompt_path = variant_path / "function_system.prompt.template"

    if not function_system_prompt_path.exists():
        raise FileNotFoundError(
            f"Function system prompt not found at {function_system_prompt_path} "
            f"for variant '{variant_name}'"
        )

    system_prompt = _env.from_string(function_system_prompt_path.read_text()).render()

    # Load user template from fragment file
    user_template_path = (
        _templates_dir / "common" / "fragments" / "function_user.prompt.template"
    )

    if not user_template_path.exists():
        raise FileNotFoundError(
            f"Function user prompt not found at {user_template_path}"
        )

    user_template = _env.from_string(user_template_path.read_text())

    return system_prompt, user_template
