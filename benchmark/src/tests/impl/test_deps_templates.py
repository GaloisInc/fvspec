"""Tests for dependency autoformalization prompt variants."""

from generate.scaffold.formalize.impl import DependencyPayload
from generate.templates.impl import (
    DependencyPromptBundle,
    DependencyVariantRegistry,
    get_dependency_prompts,
)


def _example_payload() -> DependencyPayload:
    return DependencyPayload(
        dep_name="config.normalize",
        python_source=(
            "def normalize(value: str, *, trim: bool = True) -> str:\n"
            '    """Coerce strings to lowercase with optional trimming."""\n'
            "    result = value.lower()\n"
            "    if trim:\n"
            "        return result.strip()\n"
            "    return result\n"
        ),
        source_hash="abc123",
        tags=("strings", "io-free"),
        usage_example="normalize(' Example ', trim=False)",
    )


def test_dependency_registry_lists_variants() -> None:
    """Ensure all expected dependency prompt variants are registered."""
    registry = DependencyVariantRegistry()
    variants = registry.list_variants()
    assert "functional" in variants
    assert "mvcgen" in variants


def test_dependency_registry_default() -> None:
    """Verify the default dependency prompt variant is functional."""
    registry = DependencyVariantRegistry()
    assert registry.default_variant() == "functional"


def test_functional_prompts_render() -> None:
    """Functional prompts should include helper details and normalization plan."""
    payload = _example_payload()
    context = payload.prompt_context()

    bundle = get_dependency_prompts("functional")
    assert isinstance(bundle, DependencyPromptBundle)
    assert "Lean 4" in bundle.system_prompt

    rendered = bundle.translate_template.render(**context)
    assert payload.artifact.qualified_module in rendered
    assert "Guidelines:" in rendered
    assert "Normalization plan" in rendered
    assert payload.normalization.lean_helper_name in rendered


def test_functional_prompt_structure_strategy() -> None:
    """Functional prompts should describe structure-based normalization when needed."""
    payload = DependencyPayload(
        dep_name="Counter.increment",
        python_source=(
            "def increment(self, delta: int = 1):\n"
            "    self.count += delta\n"
            "    return self.count\n"
        ),
        source_hash=None,
    )
    context = payload.prompt_context()
    bundle = get_dependency_prompts("functional")
    rendered = bundle.translate_template.render(**context)
    assert "Lean structure" in rendered
    assert "Counter" in rendered
    assert "count" in rendered


def test_mvcgen_prompts_render() -> None:
    """Mvcgen prompts should highlight imperative guidance and normalization plan."""
    payload = _example_payload()
    context = payload.prompt_context()

    bundle = get_dependency_prompts("mvcgen")
    rendered = bundle.translate_template.render(**context)
    assert "Hoare" in rendered or "vcg" in rendered
    assert payload.artifact.qualified_module in rendered
    assert "Normalization plan" in rendered


def test_dependency_tags_filter() -> None:
    """Tag filtering should surface functional and mvcgen variants."""
    registry = DependencyVariantRegistry()
    default_variants = registry.list_variants_by_tag("default")
    assert "functional" in default_variants
    mvcgen_variants = registry.list_variants_by_tag("mvcgen")
    assert "mvcgen" in mvcgen_variants
