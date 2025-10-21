"""Tests for A/B testing and compare-variants command."""

from typer.testing import CliRunner
from generate import app
from generate.templates.spec import VariantRegistry


class TestCompareVariantsLogic:
    """Tests for compare-variants subcommand logic."""

    def test_compare_variants_auto_selects_control_and_treatment(self, mocker):
        """compare-variants with no args should auto-select control and treatment variants."""
        mock_fvspec = mocker.patch("generate.fvspec")
        mock_eval_set = mocker.patch("generate.eval_set")

        runner = CliRunner()

        # Run the command
        result = runner.invoke(app, ["compare-variants"])

        # Should succeed
        assert result.exit_code == 0

        # Should have called fvspec for multiple variants
        assert mock_fvspec.call_count >= 2

        # Should have called eval_set
        assert mock_eval_set.called

    def test_compare_variants_with_explicit_variants(self, mocker):
        """compare-variants should accept explicit variant names."""
        mock_fvspec = mocker.patch("generate.fvspec")
        _mock_eval_set = mocker.patch("generate.eval_set")

        runner = CliRunner()

        result = runner.invoke(
            app,
            [
                "compare-variants",
                "--variant",
                "control-functional",
                "--variant",
                "terse-functional",
            ],
        )

        assert result.exit_code == 0
        # Should have called fvspec exactly twice (once per variant)
        assert mock_fvspec.call_count == 2

        # Check that fvspec was called with correct variants
        calls = [c[1] for c in mock_fvspec.call_args_list]
        variant_args = [c.get("variant") for c in calls]
        assert "control-functional" in variant_args
        assert "terse-functional" in variant_args

    def test_compare_variants_passes_options_to_tasks(self, mocker):
        """compare-variants should pass options like --no-mcp to task creation."""
        mock_fvspec = mocker.patch("generate.fvspec")
        _mock_eval_set = mocker.patch("generate.eval_set")

        runner = CliRunner()

        result = runner.invoke(
            app,
            [
                "compare-variants",
                "--variant",
                "control-functional",
                "--variant",
                "control-mvcgen",
                "--no-mcp",
            ],
        )

        assert result.exit_code == 0

        # Should have passed use_mcp=False to fvspec
        calls = mock_fvspec.call_args_list
        for call_args in calls:
            _, kwargs = call_args
            assert kwargs.get("use_mcp") is False

    def test_compare_variants_creates_log_dir(self, mocker):
        """compare-variants should create a timestamped log directory."""
        _mock_fvspec = mocker.patch("generate.fvspec")
        mock_eval_set = mocker.patch("generate.eval_set")

        runner = CliRunner()

        result = runner.invoke(
            app,
            [
                "compare-variants",
                "--variant",
                "control-functional",
                "--variant",
                "terse-functional",
            ],
        )

        assert result.exit_code == 0

        # eval_set should have been called with log_dir argument
        assert mock_eval_set.called
        call_kwargs = mock_eval_set.call_args[1]
        assert "log_dir" in call_kwargs

        log_dir = call_kwargs["log_dir"]
        assert "comparison_" in log_dir
        assert "artifacts" in log_dir


class TestCompareVariantsValidation:
    """Tests for compare-variants input validation."""

    def test_compare_variants_requires_at_least_two_variants(self):
        """compare-variants should error if only 1 variant provided."""
        runner = CliRunner()

        result = runner.invoke(
            app, ["compare-variants", "--variant", "control-functional"]
        )

        # Should print error message
        assert "Error" in result.output or "2 variants" in result.output.lower()

    def test_compare_variants_accepts_more_than_two_variants(self, mocker):
        """compare-variants should work with 3+ variants."""
        mock_fvspec = mocker.patch("generate.fvspec")
        _mock_eval_set = mocker.patch("generate.eval_set")

        runner = CliRunner()

        result = runner.invoke(
            app,
            [
                "compare-variants",
                "--variant",
                "control-functional",
                "--variant",
                "control-mvcgen",
                "--variant",
                "terse-functional",
            ],
        )

        assert result.exit_code == 0
        assert mock_fvspec.call_count == 3


class TestCompareVariantsIntegration:
    """Integration tests for compare-variants with real registry."""

    def test_auto_selection_includes_both_control_and_treatment(self):
        """Auto-selection should pick up both control and treatment variants."""
        registry = VariantRegistry()

        # Get all control and treatment variants
        all_variants = registry.list_variants()
        selected = []
        for v in all_variants:
            info = registry.get_variant_info(v)
            tags = info.get("tags", [])
            if "control" in tags or "treatment" in tags:
                selected.append(v)

        # Should have at least one control and one treatment
        control_count = sum(
            1
            for v in selected
            if "control" in registry.get_variant_info(v).get("tags", [])
        )
        treatment_count = sum(
            1
            for v in selected
            if "treatment" in registry.get_variant_info(v).get("tags", [])
        )

        assert control_count >= 1
        assert treatment_count >= 1
        assert len(selected) >= 2

    def test_compare_variants_with_real_variants(self, mocker):
        """Compare-variants should work with actual variant names from registry."""
        mock_fvspec = mocker.patch("generate.fvspec")
        _mock_eval_set = mocker.patch("generate.eval_set")

        runner = CliRunner()
        registry = VariantRegistry()

        # Get real variant names
        variants = registry.list_variants()[:2]  # Take first two

        result = runner.invoke(
            app,
            ["compare-variants", "--variant", variants[0], "--variant", variants[1]],
        )

        assert result.exit_code == 0
        assert mock_fvspec.call_count == 2


class TestTaskCreation:
    """Tests for task instance creation in compare-variants."""

    def test_creates_one_task_per_variant(self, mocker):
        """Should create exactly one task instance per variant."""
        mock_fvspec = mocker.patch("generate.fvspec")
        _mock_eval_set = mocker.patch("generate.eval_set")

        runner = CliRunner()

        runner.invoke(
            app,
            [
                "compare-variants",
                "--variant",
                "control-functional",
                "--variant",
                "terse-functional",
            ],
        )

        # Should call fvspec twice (once per variant)
        assert mock_fvspec.call_count == 2

    def test_tasks_have_different_variants(self, mocker):
        """Each task should be created with a different variant."""
        mock_fvspec = mocker.patch("generate.fvspec")
        _mock_eval_set = mocker.patch("generate.eval_set")

        runner = CliRunner()

        runner.invoke(
            app,
            [
                "compare-variants",
                "--variant",
                "control-functional",
                "--variant",
                "control-mvcgen",
            ],
        )

        # Get the variant arguments from each call
        calls = mock_fvspec.call_args_list
        variants = [c[1]["variant"] for c in calls]

        # Should have both variants, no duplicates
        assert len(variants) == 2
        assert "control-functional" in variants
        assert "control-mvcgen" in variants

    def test_all_tasks_passed_to_eval_set(self, mocker):
        """All task instances should be passed to eval_set as a list."""
        mock_fvspec = mocker.patch("generate.fvspec")
        mock_eval_set = mocker.patch("generate.eval_set")

        runner = CliRunner()

        # Make fvspec return mock tasks
        mock_task1 = mocker.MagicMock(name="task1")
        mock_task2 = mocker.MagicMock(name="task2")
        mock_fvspec.side_effect = [mock_task1, mock_task2]

        runner.invoke(
            app,
            [
                "compare-variants",
                "--variant",
                "control-functional",
                "--variant",
                "terse-functional",
            ],
        )

        # eval_set should have been called with list of tasks
        assert mock_eval_set.called
        call_args = mock_eval_set.call_args[0]
        tasks_arg = call_args[0]

        # Should be a list containing both tasks
        assert isinstance(tasks_arg, list)
        assert len(tasks_arg) == 2


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
        assert "control-mvcgen" in result.output
        assert "terse-functional" in result.output
