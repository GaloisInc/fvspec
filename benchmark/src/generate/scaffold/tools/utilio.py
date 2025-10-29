"""Utility helpers for managing benchmark workspaces and filesystem I/O."""

import atexit
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from threading import Lock

from generate import config

cfg = config.load_config()

# Path to the Lake project template (relative to project root)
LAKE_TEMPLATE = Path(__file__).parent.parent.parent.parent.parent / "lake-template"


type SubprocessResult = tuple[str, str, int]


# Global registry for tracking active workspace tmpdirs (for atexit cleanup)
_active_workspaces: set[Path] = set()
_workspace_lock = Lock()


def _cleanup_all_workspaces() -> None:
    """Emergency cleanup of all active workspaces on process exit.

    This is registered as an atexit handler to ensure tmpdir cleanup even if:
    - Process crashes or receives SIGTERM
    - inspect_ai cleanup phase doesn't run
    - Exceptions occur during normal cleanup

    Note: This is a safety net. Normal cleanup happens in write_to_disk().
    """
    with _workspace_lock:
        for workspace in list(_active_workspaces):
            if workspace.exists():
                try:
                    shutil.rmtree(workspace)
                except Exception:
                    # Silently fail on atexit - process is exiting anyway
                    pass

        # Also clean up the artifacts/.tmp parent directory if empty
        tmpdir_base = (
            Path(__file__).parent.parent.parent.parent.parent / "artifacts" / ".tmp"
        )
        if tmpdir_base.exists():
            try:
                tmpdir_base.rmdir()  # Only removes if empty
            except OSError:
                # Directory not empty or other error - that's fine
                pass


# Register the emergency cleanup handler
atexit.register(_cleanup_all_workspaces)


def run_cmd(
    cmd: list[str],
    capture_output: bool = True,
    timeout: int = 60,
    text: bool = True,
    cwd: Path | None = None,
) -> SubprocessResult:
    """Run a command in the shell.

    Args:
        cmd: The command to run.
        capture_output: Whether to capture stdout/stderr
        timeout: Command timeout in seconds
        text: Whether to return output as text (vs bytes)
        cwd: Working directory for the command (optional)

    Returns:
        A tuple of stdout, stderr and exitcode.
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture_output,
            timeout=timeout,
            text=text,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired:
        return "", "Timeout", 1
    return result.stdout, result.stderr, result.returncode


def no_code_block_found(sample_id: str, text: str) -> str:
    """Generate error message when no code block is found in model output.

    Args:
        sample_id: The sample identifier
        text: The model output text that was searched

    Returns:
        A formatted error message string
    """
    msg = "No <code> block found"
    return f"{msg} for sample_id={sample_id}"


def get_output_filepath(
    date_time: str,
    sample_id: str,
    file_name: str,
    variant: str,
) -> Path:
    """Construct output file path in the artifacts directory structure.

    Creates a directory structure: artifacts/runs/<date_time>__<variant>/<sample_id>/<file_name>

    The function locates the project root by searching for pyproject.toml.

    Args:
        date_time: Timestamp string for the benchmark run
        sample_id: Unique identifier for the sample
        file_name: Name of the output file (e.g., 'Spec.lean', 'qa.json')
        variant: Prompt variant name

    Returns:
        Path to the output file

    Raises:
        FileNotFoundError: If pyproject.toml cannot be found in parent directories
    """
    # Find the project root (directory containing pyproject.toml)
    current_dir = Path.cwd()
    root_dir = current_dir

    # Walk up the directory tree until we find pyproject.toml or hit the filesystem root
    while not (root_dir / "pyproject.toml").exists():
        if root_dir == root_dir.parent:  # We've reached the filesystem root
            raise FileNotFoundError(
                "Error: Could not find project root (directory with pyproject.toml)"
            )
        root_dir = root_dir.parent

    # Create directory name based on variant
    timestamped_dir = f"{date_time}__{variant}"
    output_dir = root_dir / "artifacts" / "runs" / timestamped_dir / sample_id
    output_dir.mkdir(parents=True, exist_ok=True)

    spec_file = output_dir / file_name
    return spec_file


def get_sample_output_dir(
    date_time: str,
    sample_id: str,
    variant: str,
) -> Path:
    """Return the artifact directory for a given sample."""
    path = get_output_filepath(date_time, sample_id, "Spec.lean", variant)
    sample_dir = path.parent
    sample_dir.mkdir(parents=True, exist_ok=True)
    return sample_dir


def writeit(spfile: Path, code: str) -> str:
    """Write content to a file.

    Args:
        spfile: Path to the output file
        code: Content to write to the file

    Returns:
        A success message with the file path
    """
    with spfile.open("w", encoding="utf-8") as the_file:
        the_file.write(code)
    msg = "Code block written to disk"
    return f"{msg} at {spfile}"


def create_sample_workspace(
    sample_id: str, lake_template: Path = LAKE_TEMPLATE
) -> Path:
    """Create an isolated workspace tmpdir for one sample.

    Tmpdir Lifecycle:
    1. Created in artifacts/.tmp/ (on main disk, not /tmp tmpfs) to avoid quota issues
    2. Registered in global _active_workspaces for atexit cleanup safety net
    3. Lake template copied (EXCLUDING .lake/ to avoid disk quota issues)
    4. Used during sample execution (workspace_setup → solver → write_to_disk)
    5. Cleaned up in write_to_disk() cleanup phase (normal path)
    6. If cleanup fails, atexit handler ensures removal on process exit (safety net)

    Memory bounds: With parallelism=N, max N tmpdirs exist simultaneously
    (O(parallelism) not O(total_samples))

    Thread safety: Uses _workspace_lock for registry access in parallel execution

    Lake Build Strategy:
    - Copies .lake/ from template (6GB cached artifacts per workspace)
    - Safe because tmpdir is on main disk (3.7TB available) not /tmp (32GB tmpfs)
    - With parallelism=10: 10 × 6GB = 60GB (manageable)
    - No rebuilds needed (much faster than rebuilding mathlib from scratch)

    Args:
        sample_id: Unique identifier for the sample (used in tmpdir prefix)
        lake_template: Path to the Lake project template to copy

    Returns:
        Path: Temporary workspace directory containing a Lake project with cache

    Raises:
        FileNotFoundError: If lake_template doesn't exist

    Example:
        # Normal usage in inspect_ai task
        workspace = create_sample_workspace("sample_42")
        state.metadata["workspace"] = str(workspace)
        # ... sample executes ...
        # cleanup_sample_workspace(workspace) called in write_to_disk()
    """
    # Use custom tmpdir location to avoid /tmp (tmpfs) disk quota issues
    # Default to project's artifacts/.tmp to use main disk instead of RAM-based /tmp
    # __file__ = .../benchmark/src/generate/scaffold/tools/utilio.py
    # Need 5 parents to get to benchmark/ directory
    tmpdir_base = (
        Path(__file__).parent.parent.parent.parent.parent / "artifacts" / ".tmp"
    )
    tmpdir_base.mkdir(parents=True, exist_ok=True)

    tmpdir = Path(tempfile.mkdtemp(prefix=f"fvspec_{sample_id}_", dir=tmpdir_base))

    # Register for atexit cleanup (safety net)
    with _workspace_lock:
        _active_workspaces.add(tmpdir)

    # Copy Lake project template into workspace (including .lake/ for cached builds)
    # Now safe because workspaces are on main disk (artifacts/.tmp/) not /tmp tmpfs
    if lake_template.exists():
        for item in lake_template.iterdir():
            if item.is_dir():
                shutil.copytree(item, tmpdir / item.name, dirs_exist_ok=True)
            else:
                shutil.copy2(item, tmpdir / item.name)
    else:
        raise FileNotFoundError(
            f"Lake template not found at {lake_template}. "
            "Run 'lake init' to create the template first."
        )

    return tmpdir


def cleanup_sample_workspace(workspace: Path) -> None:
    """Clean up a sample workspace created by create_sample_workspace().

    This is the normal cleanup path, called in write_to_disk() after sample
    completes. Removes the tmpdir and unregisters it from atexit tracking.

    If this fails, the atexit handler will attempt cleanup on process exit.

    Thread safety: Uses _workspace_lock for registry access in parallel execution

    Args:
        workspace: Path to the workspace directory to remove
    """
    # Unregister from atexit tracking (normal cleanup succeeded)
    with _workspace_lock:
        _active_workspaces.discard(workspace)

    if workspace.exists():
        try:
            shutil.rmtree(workspace)
        except Exception as e:
            # Log but don't fail on cleanup errors
            # atexit handler will retry on process exit
            print(f"Warning: Error cleaning up workspace {workspace}: {e}")


@contextmanager
def sample_workspace(sample_id: str, lake_template: Path = LAKE_TEMPLATE):
    """Context manager version of sample workspace for use in with-blocks.

    Automatically creates and cleans up the workspace.

    Args:
        sample_id: Unique identifier for the sample (used in tmpdir prefix)
        lake_template: Path to the Lake project template to copy

    Yields:
        Path: Temporary workspace directory containing a Lake project

    Example:
        with sample_workspace("sample_42") as workspace:
            spec_file = workspace / "Fvspec" / "Spec.lean"
            spec_file.write_text("def foo := 42")
            result = subprocess.run(["lake", "build"], cwd=workspace)
            save_artifacts(workspace, "sample_42")
        # Tmpdir automatically cleaned up here
    """
    workspace = create_sample_workspace(sample_id, lake_template)
    try:
        yield workspace
    finally:
        cleanup_sample_workspace(workspace)
