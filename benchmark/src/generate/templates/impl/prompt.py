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

    This is a simplified version for the function under test.
    For now, reuses dependency variant system prompt with a custom user template.

    Args:
        variant: Implementation variant name

    Returns:
        Tuple of (system_prompt, user_template)
    """
    registry = DependencyVariantRegistry()
    variant_name = variant or registry.default_variant()
    if variant_name == "default":
        variant_name = registry.default_variant()

    variant_config = registry.get_variant(variant_name)

    system_prompt = _env.from_string(variant_config.system_prompt).render()

    # Simple user template for function implementation
    user_template_text = """You are translating a Python function into a complete Lean 4 implementation.

## Python Test
```python
{{ pbt_code }}
```

## Function to Implement
Function name: `{{ function_name }}`

{% if function_code %}
## Original Python Code
```python
{{ function_code }}
```
{% endif %}

{% if dependencies %}
## Available Dependencies
The following dependencies are already implemented:
{% for name, sig in dependencies.items() %}
- {{ sig }}
{% endfor %}
{% endif %}

## Task
Generate a complete Lean 4 implementation of `{{ function_name }}`:
1. Must be fully implemented (ZERO sorry - we need computable code!)
2. Must match the semantics shown in the test
3. Use `Fvspec.Impl` namespace
4. Can use available dependencies if needed

Output your implementation in <code>...</code> tags."""

    user_template = _env.from_string(user_template_text)

    return system_prompt, user_template
