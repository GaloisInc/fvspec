"""Per-sample workspace lifecycle for Lean projects.

Adapted from benchmark/src/generate/scaffold/tools/utilio.py.
"""

import atexit
import shutil
import tempfile
from pathlib import Path
from threading import Lock

LAKE_TEMPLATE = Path(__file__).parents[2] / "lake-template"
ARTIFACTS_DIR = Path(__file__).parents[2] / "artifacts"

# Global registry for tracking active workspace tmpdirs (for atexit cleanup)
_active_workspaces: set[Path] = set()
_workspace_lock = Lock()


def _cleanup_all_workspaces() -> None:
    """Emergency cleanup of all active workspaces on process exit."""
    with _workspace_lock:
        for workspace in list(_active_workspaces):
            if workspace.exists():
                try:
                    shutil.rmtree(workspace)
                except Exception:
                    pass

        tmpdir_base = ARTIFACTS_DIR / ".tmp"
        if tmpdir_base.exists():
            try:
                tmpdir_base.rmdir()
            except Exception:
                pass


atexit.register(_cleanup_all_workspaces)


def create_workspace(sample_id: str) -> Path:
    """Create an isolated workspace tmpdir for one sample.

    Copies lake-template, symlinks .lake/packages/ for shared deps,
    creates Fvspec/ directory, and writes Impl.lean + Spec.lean.

    Args:
        sample_id: Unique identifier for the sample

    Returns:
        Path to temporary workspace directory
    """
    tmpdir_base = ARTIFACTS_DIR / ".tmp"
    tmpdir_base.mkdir(parents=True, exist_ok=True)

    tmpdir = Path(tempfile.mkdtemp(prefix=f"fvspec_{sample_id}_", dir=tmpdir_base))

    with _workspace_lock:
        _active_workspaces.add(tmpdir)

    if not LAKE_TEMPLATE.exists():
        raise FileNotFoundError(
            f"Lake template not found at {LAKE_TEMPLATE}. "
            "Ensure the lake-template symlink is valid."
        )

    # Copy template structure (skip .lake and Fvspec — set up separately)
    for item in LAKE_TEMPLATE.iterdir():
        if item.name in (".lake", "Fvspec"):
            continue
        dest = tmpdir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, symlinks=True)
        else:
            shutil.copy2(item, dest)

    # Set up .lake: symlink packages (read-only shared deps), own build dir
    lake_dir = tmpdir / ".lake"
    lake_dir.mkdir()
    (lake_dir / "packages").symlink_to((LAKE_TEMPLATE / ".lake" / "packages").resolve())
    (lake_dir / "build").mkdir()

    # Resolve lean-toolchain symlink to absolute copy
    toolchain_link = tmpdir / "lean-toolchain"
    if toolchain_link.is_symlink():
        target = toolchain_link.resolve()
        toolchain_link.unlink()
        shutil.copy2(target, toolchain_link)

    # Create Fvspec directory for agent files
    (tmpdir / "Fvspec").mkdir()

    return tmpdir


def populate_workspace(workspace: Path, impl: str, spec: str) -> None:
    """Write Impl.lean and Spec.lean into the workspace.

    Args:
        workspace: Path to the workspace tmpdir
        impl: Lean implementation code
        spec: Lean specification code (with sorry placeholders)
    """
    fvspec_dir = workspace / "Fvspec"
    fvspec_dir.mkdir(exist_ok=True)
    (fvspec_dir / "Impl.lean").write_text(impl)
    (fvspec_dir / "Spec.lean").write_text(spec)


def cleanup_workspace(workspace: Path) -> None:
    """Clean up a sample workspace."""
    if workspace.exists():
        shutil.rmtree(workspace)
    with _workspace_lock:
        _active_workspaces.discard(workspace)
