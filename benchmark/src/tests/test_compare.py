"""Tests for A/B testing and compare-variants command."""

from typer.testing import CliRunner

from generate import app
from generate.templates.formalize import FormalizationVariantRegistry as VariantRegistry


class TestCompareVariantsLogic:
    """Tests for compare-variants subcommand logic."""

    def test_compare_variants_requires_at_least_two_variants(self):
        """compare-variants should error if only 1 variant provided."""
        runner = CliRunner()

        result = runner.invoke(
            app, ["compare-variants", "--variant", "control-functional"]
        )

        # Should print error message
        assert "Error" in result.output or "2 variants" in result.output.lower()


class TestCompareVariantsIntegration:
    """Integration tests for compare-variants with real registry."""

    def test_registry_has_control_variant(self):
        """Registry should have at least one control variant."""
        registry = VariantRegistry()

        all_variants = registry.list_variants()
        selected = []
        for v in all_variants:
            info = registry.get_variant_info(v)
            tags = info.get("tags", [])
            if "control" in tags:
                selected.append(v)

        assert len(selected) >= 1
        assert "control-functional" in selected


class TestCLIHelp:
    """Tests for CLI help text and documentation."""

    def test_compare_variants_help_text(self):
        """compare-variants --help should describe A/B testing."""
        runner = CliRunner()
        result = runner.invoke(app, ["compare-variants", "--help"])

        assert result.exit_code == 0
        assert "A/B testing" in result.output or "compar" in result.output.lower()
        assert "variant" in result.output.lower()

    def test_main_help_shows_subcommand(self):
        """Main help should list compare-variants subcommand."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "compare-variants" in result.output

    def test_list_variants_flag_works(self):
        """--list-variants should display available variants."""
        runner = CliRunner()
        result = runner.invoke(app, ["--list-variants"])

        assert result.exit_code == 0
        assert "control-functional" in result.output
