"""Tests for dependency autoformalization prompt variants."""

from benchmark.templates.deps import (
    DependencyVariantRegistry,
    get_dependency_prompts,
    DependencyPromptBundle,
)


def test_dependency_registry_lists_variants() -> None:
    registry = DependencyVariantRegistry()
    variants = registry.list_variants()
    assert "baseline" in variants


def test_dependency_registry_default() -> None:
    registry = DependencyVariantRegistry()
    assert registry.default_variant() in registry.list_variants()


def test_get_dependency_prompts_returns_bundle() -> None:
    bundle = get_dependency_prompts()
    assert isinstance(bundle, DependencyPromptBundle)
    assert "Lean 4 engineer" in bundle.system_prompt

    rendered = bundle.translate_template.render(
        dep_name="helper",
        source_hash="abc",
        dep_module="Helper",
        python_source="def helper(): return 1",
        tags=[],
        usage_example=None,
    )
    assert "Fvspec.Deps.Helper" in rendered


def test_dependency_tags_filter() -> None:
    registry = DependencyVariantRegistry()
    tagged = registry.list_variants_by_tag("default")
    assert "baseline" in tagged
