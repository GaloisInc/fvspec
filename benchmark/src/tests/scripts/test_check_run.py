"""Tests for the check-run script."""

from pathlib import Path

from scripts.check_run import (
    CompilationResult,
    find_latest_run,
    find_sample_dirs,
)


class TestFindLatestRun:
    """Tests for finding the latest run directory."""

    def test_find_latest_run_empty_dir(self, tmp_path: Path) -> None:
        """Test with empty artifacts directory."""
        result = find_latest_run(tmp_path)
        assert result is None

    def test_find_latest_run_single(self, tmp_path: Path) -> None:
        """Test with single run directory."""
        run_dir = tmp_path / "2025-10-29T21-14-12__control-functional"
        run_dir.mkdir(parents=True)

        result = find_latest_run(tmp_path)
        assert result == run_dir

    def test_find_latest_run_multiple(self, tmp_path: Path) -> None:
        """Test that latest run is selected from multiple runs."""
        run1 = tmp_path / "2025-10-28T21-12-45__control-functional"
        run2 = tmp_path / "2025-10-29T21-14-12__control-functional"
        run3 = tmp_path / "2025-10-29T21-34-17__terse-functional"

        run1.mkdir(parents=True)
        run2.mkdir(parents=True)
        run3.mkdir(parents=True)

        result = find_latest_run(tmp_path)
        # Should return the most recent (run3)
        assert result == run3

    def test_find_latest_run_nonexistent(self) -> None:
        """Test with nonexistent directory."""
        result = find_latest_run(Path("/nonexistent"))
        assert result is None


class TestFindSampleDirs:
    """Tests for finding sample directories."""

    def test_find_sample_dirs_empty(self, tmp_path: Path) -> None:
        """Test with empty run directory."""
        result = find_sample_dirs(tmp_path)
        assert result == []

    def test_find_sample_dirs_all_samples(self, tmp_path: Path) -> None:
        """Test finding all samples in a run."""
        # Create sample directories (note: use __ not _)
        sample1 = tmp_path / "00307__test_mul"
        sample2 = tmp_path / "00645__test_soft_label"
        sample1.mkdir()
        sample2.mkdir()

        # Create a non-sample directory (should be ignored)
        (tmp_path / "deps").mkdir()

        result = find_sample_dirs(tmp_path)
        assert len(result) == 2
        assert sample1 in result
        assert sample2 in result

    def test_find_sample_dirs_specific_ids(self, tmp_path: Path) -> None:
        """Test finding specific sample IDs."""
        sample1 = tmp_path / "00307__test_mul"
        sample2 = tmp_path / "00645__test_soft_label"
        sample3 = tmp_path / "06576__test_reduce_scatter"
        sample1.mkdir()
        sample2.mkdir()
        sample3.mkdir()

        result = find_sample_dirs(tmp_path, sample_ids=["00307", "06576"])
        assert len(result) == 2
        assert sample1 in result
        assert sample3 in result
        assert sample2 not in result

    def test_find_sample_dirs_no_match(self, tmp_path: Path) -> None:
        """Test with sample IDs that don't exist."""
        sample1 = tmp_path / "00307__test_mul"
        sample1.mkdir()

        result = find_sample_dirs(tmp_path, sample_ids=["99999"])
        assert result == []

    def test_find_sample_dirs_sorted(self, tmp_path: Path) -> None:
        """Test that results are sorted by sample ID."""
        sample3 = tmp_path / "06576__test_reduce_scatter"
        sample1 = tmp_path / "00307__test_mul"
        sample2 = tmp_path / "00645__test_soft_label"

        # Create in non-sorted order
        sample3.mkdir()
        sample1.mkdir()
        sample2.mkdir()

        result = find_sample_dirs(tmp_path)
        assert len(result) == 3
        # Should be sorted by name
        assert result[0].name == "00307__test_mul"
        assert result[1].name == "00645__test_soft_label"
        assert result[2].name == "06576__test_reduce_scatter"


class TestCompilationResult:
    """Tests for CompilationResult structure."""

    def test_compilation_result_success(self, tmp_path: Path) -> None:
        """Test successful compilation result."""
        result = CompilationResult(
            sample_id="00307",
            sample_path=tmp_path,
            success=True,
            duration_seconds=1.5,
        )

        assert result.sample_id == "00307"
        assert result.success is True
        assert result.duration_seconds == 1.5
        assert result.error_message is None
        assert result.missing_files is None

    def test_compilation_result_failure_with_error(self, tmp_path: Path) -> None:
        """Test failed compilation with error message."""
        result = CompilationResult(
            sample_id="00645",
            sample_path=tmp_path,
            success=False,
            duration_seconds=2.3,
            error_message="type mismatch at 'rfl'",
        )

        assert result.sample_id == "00645"
        assert result.success is False
        assert result.duration_seconds == 2.3
        assert result.error_message == "type mismatch at 'rfl'"
        assert result.missing_files is None

    def test_compilation_result_missing_files(self, tmp_path: Path) -> None:
        """Test compilation result with missing files."""
        result = CompilationResult(
            sample_id="06576",
            sample_path=tmp_path,
            success=False,
            duration_seconds=0.1,
            missing_files=["Spec.lean"],
        )

        assert result.sample_id == "06576"
        assert result.success is False
        assert result.missing_files == ["Spec.lean"]
