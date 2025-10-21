"""Unit tests for temporary workspace management.

These tests verify the tmpdir-related functionality used for isolating
Lake project builds during benchmark evaluation.
"""

from pathlib import Path

import pytest

from generate.scaffold.tools.utilio import (
    create_sample_workspace,
    cleanup_sample_workspace,
    sample_workspace,
)


@pytest.fixture
def mock_lake_template(tmp_path):
    """Create a mock Lake project template for testing."""
    template = tmp_path / "test-lake-template"
    template.mkdir()

    # Create minimal Lake project structure
    (template / "lakefile.toml").write_text(
        'name = "fvspec"\nversion = "0.1.0"\ndefaultTargets = ["Fvspec"]'
    )
    (template / "lake-manifest.json").write_text("{}")

    # Create Fvspec directory structure mirroring the real template
    fvspec_dir = template / "Fvspec"
    fvspec_dir.mkdir()
    (fvspec_dir / "Basic.lean").write_text("-- Placeholder spec\nimport Fvspec.Deps")
    (fvspec_dir / "Deps.lean").write_text("-- Placeholder deps")
    (template / "Fvspec.lean").write_text(
        "-- Auto-generated entry point\nimport Fvspec.Deps\nimport Fvspec.Basic"
    )

    return template


def test_create_sample_workspace_creates_directory(mock_lake_template):
    """Verify create_sample_workspace creates a temporary directory."""
    workspace = create_sample_workspace("sample_001", lake_template=mock_lake_template)

    try:
        assert workspace.exists()
        assert workspace.is_dir()
        assert "fvspec_sample_001" in workspace.name
    finally:
        cleanup_sample_workspace(workspace)


def test_create_sample_workspace_copies_template(mock_lake_template):
    """Verify the Lake template is copied into the workspace."""
    workspace = create_sample_workspace("sample_002", lake_template=mock_lake_template)

    try:
        # Verify Lake project files were copied
        assert (workspace / "lakefile.toml").exists()
        assert (workspace / "lake-manifest.json").exists()
        assert (workspace / "Fvspec").is_dir()
        assert (workspace / "Fvspec" / "Basic.lean").exists()

        # Verify content was copied correctly
        content = (workspace / "Fvspec" / "Basic.lean").read_text()
        assert "import Fvspec.Deps" in content
    finally:
        cleanup_sample_workspace(workspace)


def test_create_sample_workspace_raises_on_missing_template():
    """Verify error when template doesn't exist."""
    nonexistent = Path("/nonexistent/path/to/template")

    with pytest.raises(FileNotFoundError, match="Lake template not found"):
        create_sample_workspace("sample_003", lake_template=nonexistent)


def test_cleanup_sample_workspace_removes_directory(mock_lake_template):
    """Verify cleanup removes the workspace directory."""
    workspace = create_sample_workspace("sample_004", lake_template=mock_lake_template)
    assert workspace.exists()

    cleanup_sample_workspace(workspace)

    assert not workspace.exists()


def test_cleanup_sample_workspace_handles_nonexistent_path():
    """Verify cleanup doesn't crash on nonexistent path."""
    nonexistent = Path("/tmp/fvspec_nonexistent_xyz123")

    # Should not raise
    cleanup_sample_workspace(nonexistent)


def test_cleanup_sample_workspace_handles_errors(capsys):
    """Verify cleanup doesn't crash even if errors occur during removal."""
    # Create a path that might cause issues (but actually test that cleanup works)
    # Note: chmod 0o000 doesn't prevent owner from removing files on most systems,
    # so this test mainly verifies cleanup doesn't crash on edge cases
    fake_path = Path("/tmp/fvspec_test_nonexistent_xyz")

    # This should not crash even though directory doesn't exist
    cleanup_sample_workspace(fake_path)

    # No assertion needed - if we got here without exception, test passed


def test_sample_workspace_context_manager_creates_and_cleans_up(mock_lake_template):
    """Verify context manager creates workspace and cleans up on exit."""
    workspace_path = None

    with sample_workspace("sample_006", lake_template=mock_lake_template) as workspace:
        workspace_path = workspace
        assert workspace.exists()
        assert (workspace / "lakefile.toml").exists()

    # After context exit, workspace should be cleaned up
    assert workspace_path is not None
    assert not workspace_path.exists()


def test_sample_workspace_context_manager_cleans_up_on_exception(mock_lake_template):
    """Verify context manager cleans up even when exception is raised."""
    workspace_path = None

    with pytest.raises(ValueError, match="test error"):
        with sample_workspace(
            "sample_007", lake_template=mock_lake_template
        ) as workspace:
            workspace_path = workspace
            assert workspace.exists()
            raise ValueError("test error")

    # Workspace should still be cleaned up after exception
    assert workspace_path is not None
    assert not workspace_path.exists()


def test_workspace_can_write_lean_files(mock_lake_template):
    """Verify we can write Lean files to the workspace."""
    with sample_workspace("sample_008", lake_template=mock_lake_template) as workspace:
        spec_file = workspace / "Fvspec" / "Basic.lean"
        lean_code = """-- Generated spec
def add (x y : Nat) : Nat := sorry

theorem test_add (x y : Nat) : add x y = add y x := by sorry
"""
        spec_file.write_text(lean_code)

        # Verify file was written
        assert spec_file.exists()
        content = spec_file.read_text()
        assert "def add" in content
        assert "theorem test_add" in content


def test_multiple_workspaces_are_isolated(mock_lake_template):
    """Verify multiple workspaces don't interfere with each other."""
    workspace1 = create_sample_workspace(
        "sample_009a", lake_template=mock_lake_template
    )
    workspace2 = create_sample_workspace(
        "sample_009b", lake_template=mock_lake_template
    )

    try:
        # Workspaces should be in different directories
        assert workspace1 != workspace2
        assert workspace1.exists()
        assert workspace2.exists()

        # Write different content to each
        (workspace1 / "test1.txt").write_text("workspace1")
        (workspace2 / "test2.txt").write_text("workspace2")

        # Verify isolation
        assert (workspace1 / "test1.txt").exists()
        assert not (workspace1 / "test2.txt").exists()
        assert (workspace2 / "test2.txt").exists()
        assert not (workspace2 / "test1.txt").exists()
    finally:
        cleanup_sample_workspace(workspace1)
        cleanup_sample_workspace(workspace2)


def test_workspace_prefix_includes_sample_id(mock_lake_template):
    """Verify workspace directory name includes sample ID for debugging."""
    with sample_workspace(
        "test_sample_123", lake_template=mock_lake_template
    ) as workspace:
        assert "fvspec_test_sample_123" in workspace.name
