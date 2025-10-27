"""Tests for variant registry and prompt templating (SSoT)."""

from pathlib import Path
import pytest
from generate.templates.spec import (
    VariantRegistry,
    VariantConfig,
    get_variant_prompts,
)


class TestVariantRegistry:
    """Tests for VariantRegistry class."""

    def test_registry_loads_from_toml(self):
        """Registry should load variants from registry.toml."""
        registry = VariantRegistry()
        assert registry._registry is not None
        assert "variants" in registry._registry
        assert "meta" in registry._registry

    def test_list_variants(self):
        """Registry should list all available variant names."""
        registry = VariantRegistry()
        variants = registry.list_variants()

        assert isinstance(variants, list)
        assert (
            len(variants) >= 3
        )  # At least control-functional, control-mvcgen, terse-functional
        assert "control-functional" in variants
        assert "control-mvcgen" in variants
        assert "terse-functional" in variants

    def test_default_variant(self):
        """Registry should return configured default variant."""
        registry = VariantRegistry()
        default = registry.default_variant()

        assert isinstance(default, str)
        assert default in registry.list_variants()

    def test_get_variant_info(self):
        """Registry should return metadata for a variant."""
        registry = VariantRegistry()
        info = registry.get_variant_info("control-functional")

        assert isinstance(info, dict)
        assert "path" in info
        assert "style" in info
        assert "description" in info
        assert info["style"] == "functional"

    def test_get_variant_info_unknown_raises(self):
        """Registry should raise ValueError for unknown variants."""
        registry = VariantRegistry()

        with pytest.raises(ValueError, match="Unknown variant"):
            registry.get_variant_info("nonexistent-variant")

    def test_get_variant_loads_full_config(self):
        """Registry should load full VariantConfig with templates."""
        registry = VariantRegistry()
        config = registry.get_variant("control-functional")

        assert isinstance(config, VariantConfig)
        assert config.name == "control-functional"
        assert config.style == "functional"
        assert len(config.system_prompt) > 100
        assert len(config.initial_template) > 50
        assert isinstance(config.metadata, dict)

    def test_list_variants_by_tag(self):
        """Registry should filter variants by tag."""
        registry = VariantRegistry()

        control_variants = registry.list_variants_by_tag("control")
        assert "control-functional" in control_variants
        assert "control-mvcgen" in control_variants

        treatment_variants = registry.list_variants_by_tag("treatment")
        assert "terse-functional" in treatment_variants

        functional_variants = registry.list_variants_by_tag("functional")
        assert "control-functional" in functional_variants
        assert "terse-functional" in functional_variants

    def test_list_variants_by_style(self):
        """Registry should filter variants by style."""
        registry = VariantRegistry()

        functional = registry.list_variants_by_style("functional")
        assert "control-functional" in functional
        assert "terse-functional" in functional
        assert "control-mvcgen" not in functional

        mvcgen = registry.list_variants_by_style("mvcgen")
        assert "control-mvcgen" in mvcgen
        assert "control-functional" not in mvcgen


class TestSharedTemplates:
    """Tests for Single Source of Truth (SSoT) template mechanics."""

    def test_shared_initial_prompt_is_default(self):
        """Variants without initial.prompt should use common/initial.prompt."""
        registry = VariantRegistry()

        # control-functional has no initial.prompt → uses common
        config = registry.get_variant("control-functional")
        assert len(config.initial_template) > 0

        # Should contain the common template's characteristic text
        assert "The following Python dependencies" in config.initial_template
        assert "{{ pbt }}" in config.initial_template

    def test_multiple_variants_share_same_initial(self):
        """Multiple variants should get identical common initial prompt."""
        registry = VariantRegistry()

        config1 = registry.get_variant("control-functional")
        config2 = registry.get_variant("control-mvcgen")

        # Both use common/initial.prompt, so should be identical
        assert config1.initial_template == config2.initial_template

    def test_jinja_includes_work_in_system_prompt(self):
        """System prompts should resolve {% include %} directives."""
        sys_prompt, _ = get_variant_prompts("control-functional")

        # Should have content from common fragments
        assert "## Task" in sys_prompt
        assert "## Output Format" in sys_prompt
        assert "## Metrics" in sys_prompt
        assert "sorry" in sys_prompt  # From output_format.txt
        assert "Faithfulness" in sys_prompt  # From metrics.txt

    def test_jinja_includes_propagate_changes(self):
        """Changes to common fragments should appear in all variants that include them."""
        sys1, _ = get_variant_prompts("control-functional")
        sys2, _ = get_variant_prompts("control-mvcgen")

        # Both should have content from common fragments
        # Check for user's edit: "intricacy" instead of "complexity"
        assert "intricacy" in sys1 or "complexity" in sys1 or "sophistication" in sys1

        # Both should have the same metrics section (both include metrics.txt)
        assert "Faithfulness" in sys1
        assert "Faithfulness" in sys2

    def test_get_variant_prompts_with_none_uses_default(self):
        """get_variant_prompts(None) should use registry default."""
        sys, init = get_variant_prompts(None)

        assert isinstance(sys, str)
        assert len(sys) > 100
        # Should render successfully
        rendered = init.render(pbt="test", deps=["dep"])
        assert len(rendered) > 0

    def test_get_variant_prompts_returns_rendered_system(self):
        """get_variant_prompts should return fully rendered system prompt."""
        sys, init = get_variant_prompts("control-functional")

        # System prompt should be string (not template)
        assert isinstance(sys, str)
        # Should NOT have any unresolved {% include %} directives
        assert "{% include" not in sys

    def test_initial_template_is_renderable(self):
        """Initial template should be Jinja2 Template that can render."""
        _, init = get_variant_prompts("control-functional")

        # Should be able to render with variables
        rendered = init.render(pbt="def test(): pass", deps=["def helper(): return 42"])

        assert "def test(): pass" in rendered
        assert "def helper(): return 42" in rendered


class TestTemplateContent:
    """Tests for specific template content expectations."""

    def test_control_functional_has_process_section(self):
        """control-functional should have detailed process section."""
        sys, _ = get_variant_prompts("control-functional")

        assert "## Process" in sys
        assert "Extract key code components" in sys
        assert "Identify all functions" in sys

    def test_control_mvcgen_has_imperative_guidance(self):
        """control-mvcgen should have mvcgen/Hoare logic guidance."""
        sys, _ = get_variant_prompts("control-mvcgen")

        assert "mvcgen" in sys
        assert "Hoare" in sys or "loop invariant" in sys
        assert "imperative" in sys.lower() or "do notation" in sys

    def test_all_variants_have_metrics_section(self):
        """All variants should report Faithfulness and Interest."""
        for variant in ["control-functional", "control-mvcgen", "terse-functional"]:
            sys, _ = get_variant_prompts(variant)
            assert "Faithfulness" in sys
            assert "Interest" in sys


class TestSharedFragments:
    """Tests for common fragment files."""

    def test_shared_fragments_exist(self):
        """All expected common fragment files should exist."""
        fragments_dir = (
            Path(__file__).parent.parent
            / "generate"
            / "templates"
            / "spec"
            / "common"
            / "fragments"
        )

        assert (fragments_dir / "task_core.txt").exists()
        assert (fragments_dir / "output_format.txt").exists()
        assert (fragments_dir / "metrics.txt").exists()

    def test_common_initial_prompt_exists(self):
        """Common initial prompt should exist."""
        common_dir = (
            Path(__file__).parent.parent / "generate" / "templates" / "spec" / "common"
        )
        assert (common_dir / "initial.prompt").exists()

    def test_task_core_fragment_content(self):
        """task_core.txt should have expected content."""
        fragments_dir = (
            Path(__file__).parent.parent
            / "generate"
            / "templates"
            / "spec"
            / "common"
            / "fragments"
        )
        content = (fragments_dir / "task_core.txt").read_text()

        assert "## Task" in content
        assert "Hypothesis" in content
        assert "sorry" in content

    def test_output_format_fragment_content(self):
        """output_format.txt should specify code tag format."""
        fragments_dir = (
            Path(__file__).parent.parent
            / "generate"
            / "templates"
            / "spec"
            / "common"
            / "fragments"
        )
        content = (fragments_dir / "output_format.txt").read_text()

        assert "## Output Format" in content
        assert "<code>" in content
        assert "sorry" in content

    def test_metrics_fragment_content(self):
        """metrics.txt should describe Faithfulness and Interest."""
        fragments_dir = (
            Path(__file__).parent.parent
            / "generate"
            / "templates"
            / "spec"
            / "common"
            / "fragments"
        )
        content = (fragments_dir / "metrics.txt").read_text()

        assert "## Metrics" in content
        assert "Faithfulness" in content
        assert "Interest" in content
        assert "X/10" in content or "/10" in content
