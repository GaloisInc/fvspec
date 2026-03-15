"""Tests for variant registry and prompt templating."""

import pytest

from generate.templates.formalize import (
    FormalizationVariantConfig,
    FormalizationVariantRegistry,
    get_formalization_prompts,
)


class TestFormalizationVariantRegistry:
    """Tests for FormalizationVariantRegistry class."""

    def test_registry_loads_from_toml(self):
        """Registry should load variants from registry.toml."""
        registry = FormalizationVariantRegistry()
        assert registry._registry is not None
        assert "variants" in registry._registry
        assert "meta" in registry._registry

    def test_list_variants(self):
        """Registry should list all available variant names."""
        registry = FormalizationVariantRegistry()
        variants = registry.list_variants()

        assert isinstance(variants, list)
        assert len(variants) >= 1
        assert "control-functional" in variants

    def test_default_variant(self):
        """Registry should return configured default variant."""
        registry = FormalizationVariantRegistry()
        default = registry.default_variant()

        assert isinstance(default, str)
        assert default in registry.list_variants()
        assert default == "control-functional"

    def test_get_variant_info(self):
        """Registry should return metadata for a variant."""
        registry = FormalizationVariantRegistry()
        info = registry.get_variant_info("control-functional")

        assert isinstance(info, dict)
        assert "path" in info
        assert "style" in info
        assert "description" in info
        assert info["style"] == "functional"

    def test_get_variant_info_unknown_raises(self):
        """Registry should raise ValueError for unknown variants."""
        registry = FormalizationVariantRegistry()

        with pytest.raises(ValueError, match="Unknown variant"):
            registry.get_variant_info("nonexistent-variant")

    def test_get_variant_loads_full_config(self):
        """Registry should load full config with templates."""
        registry = FormalizationVariantRegistry()
        config = registry.get_variant("control-functional")

        assert isinstance(config, FormalizationVariantConfig)
        assert config.name == "control-functional"
        assert config.style == "functional"
        assert len(config.system_prompt) > 100
        assert len(config.initial_template) > 50
        assert isinstance(config.metadata, dict)

    def test_list_variants_by_tag(self):
        """Registry should filter variants by tag."""
        registry = FormalizationVariantRegistry()

        control_variants = registry.list_variants_by_tag("control")
        assert "control-functional" in control_variants

        functional_variants = registry.list_variants_by_tag("functional")
        assert "control-functional" in functional_variants

    def test_list_variants_by_style(self):
        """Registry should filter variants by style."""
        registry = FormalizationVariantRegistry()

        functional = registry.list_variants_by_style("functional")
        assert "control-functional" in functional


class TestFormalizationTemplates:
    """Tests for formalization template mechanics."""

    def test_system_prompt_has_key_sections(self):
        """System prompt should have implementation and spec instructions."""
        sys_prompt, _ = get_formalization_prompts("control-functional")

        assert isinstance(sys_prompt, str)
        assert "Impl.lean" in sys_prompt
        assert "Spec.lean" in sys_prompt
        assert "sorry" in sys_prompt
        assert "Fvspec.Impl" in sys_prompt
        assert "Fvspec.Spec" in sys_prompt

    def test_system_prompt_resolves_includes(self):
        """System prompt should have no unresolved {% include %} directives."""
        sys_prompt, _ = get_formalization_prompts("control-functional")
        assert "{% include" not in sys_prompt

    def test_initial_template_is_renderable(self):
        """Initial template should render with expected context."""
        _, init = get_formalization_prompts("control-functional")

        rendered = init.render(
            pbt_code="def test(): pass",
            function_name="add",
            function_code="def add(x, y): return x + y",
            pbt_summary="Test addition",
            dependencies={"helper": "def helper (x : Nat) : Nat"},
        )

        assert "def test(): pass" in rendered
        assert "def add(x, y): return x + y" in rendered
        assert "Test addition" in rendered
        assert "def helper (x : Nat) : Nat" in rendered

    def test_initial_template_handles_none_function_code(self):
        """Initial template should handle None function_code gracefully."""
        _, init = get_formalization_prompts("control-functional")

        rendered = init.render(
            pbt_code="def test(): pass",
            function_name="add",
            function_code=None,
            pbt_summary=None,
            dependencies={},
        )

        assert "def test(): pass" in rendered
        assert "source code was not found" in rendered

    def test_get_formalization_prompts_with_none_uses_default(self):
        """get_formalization_prompts(None) should use registry default."""
        sys, init = get_formalization_prompts(None)

        assert isinstance(sys, str)
        assert len(sys) > 100
        rendered = init.render(
            pbt_code="test",
            function_name="add",
            function_code=None,
            pbt_summary=None,
            dependencies={},
        )
        assert len(rendered) > 0


class TestFormalizationFragments:
    """Tests for common fragment files."""

    def test_shared_fragments_exist(self):
        """All expected common fragment files should exist."""
        from generate.config import TEMPLATES_DIR

        fragments_dir = TEMPLATES_DIR / "formalize" / "common" / "fragments"

        assert (fragments_dir / "lsp_tools.prompt").exists()
        assert (fragments_dir / "output_format.prompt").exists()

    def test_common_initial_prompt_exists(self):
        """Common initial prompt should exist."""
        from generate.config import TEMPLATES_DIR

        common_dir = TEMPLATES_DIR / "formalize" / "common"
        assert (common_dir / "initial.prompt.template").exists()
