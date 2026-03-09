"""Tests for baselines.workspace."""

from pathlib import Path

import pytest

from baselines.workspace import (
    cleanup_workspace,
    create_workspace,
    populate_workspace,
)


@pytest.fixture
def workspace() -> Path:  # type: ignore[override]
    """Create a real workspace (requires lake-template symlink to be valid)."""
    ws = create_workspace("test_42")
    yield ws
    cleanup_workspace(ws)


class TestCreateWorkspace:
    def test_creates_directory(self, workspace: Path):
        assert workspace.exists()
        assert workspace.is_dir()

    def test_has_lakefile(self, workspace: Path):
        assert (workspace / "lakefile.toml").exists()

    def test_has_lean_toolchain(self, workspace: Path):
        tc = workspace / "lean-toolchain"
        assert tc.exists()
        assert not tc.is_symlink()

    def test_lake_packages_is_symlink(self, workspace: Path):
        packages = workspace / ".lake" / "packages"
        assert packages.is_symlink()

    def test_lake_build_is_real_dir(self, workspace: Path):
        build = workspace / ".lake" / "build"
        assert build.exists()
        assert not build.is_symlink()

    def test_fvspec_dir_exists(self, workspace: Path):
        assert (workspace / "Fvspec").is_dir()


class TestPopulateWorkspace:
    def test_writes_files(self, workspace: Path):
        populate_workspace(workspace, impl="def f := 1", spec="theorem t := sorry")
        assert (workspace / "Fvspec" / "Impl.lean").read_text() == "def f := 1"
        assert (workspace / "Fvspec" / "Spec.lean").read_text() == "theorem t := sorry"


class TestCleanupWorkspace:
    def test_removes_directory(self):
        ws = create_workspace("cleanup_test")
        assert ws.exists()
        cleanup_workspace(ws)
        assert not ws.exists()

    def test_cleanup_nonexistent_is_noop(self, tmp_path: Path):
        cleanup_workspace(tmp_path / "nonexistent")
