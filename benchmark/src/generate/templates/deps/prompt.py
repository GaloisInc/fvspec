"""Load dependency prompt bundles for autoformalization variants."""

from dataclasses import dataclass
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, Template

from generate.templates.deps.registry import DependencyVariantRegistry


@dataclass(frozen=True)
class DependencyPromptBundle:
    """Group of prompts used by the dependency autoformalization subagent."""

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
