"""Utility helpers for managing benchmark workspaces and filesystem I/O."""

import atexit
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from threading import Lock

from generate.config import ARTIFACTS_DIR, LAKE_TEMPLATE_DIR, load_config

cfg = load_config()

# Path to the Lake project template (relative to project root)
LAKE_TEMPLATE = LAKE_TEMPLATE_DIR


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
        tmpdir_base = ARTIFACTS_DIR / ".tmp"
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


def model_slug(model: str) -> str:
    """Derive a filesystem-safe slug from a model identifier.

    Strips provider prefix (e.g. "anthropic/") so that
    "anthropic/claude-sonnet-4-6" becomes "claude-sonnet-4-6".
    """
    return model.split("/")[-1]


def mk_run_path(
    date_time: str,
    model: str,
    ranseed: int | None = None,
    start_idx: int | None = None,
    end_idx: int | None = None,
) -> str:
    """Construct run directory name for artifacts.

    Args:
        date_time: Timestamp string (e.g., "2025-11-06T12-01-34")
        model: Model slug (e.g., "claude-sonnet-4-6")
        ranseed: Random seed used for sampling (optional)
        start_idx: Starting index for sequential sampling (optional)
        end_idx: Ending index for sequential sampling (optional)

    Returns:
        Run directory name in format:
        - With indices: "2025-11-06T12-01-34__idx0-1000__claude-sonnet-4-6"
        - With ranseed: "2025-11-06T12-01-34__s4__claude-sonnet-4-6"
        - Without either: "2025-11-06T12-01-34__claude-sonnet-4-6"

    Examples:
        >>> mk_run_path("2025-11-06T12-01-34", "claude-sonnet-4-6", ranseed=4)
        '2025-11-06T12-01-34__s4__claude-sonnet-4-6'
        >>> mk_run_path("2025-11-06T12-01-34", "claude-sonnet-4-6")
        '2025-11-06T12-01-34__claude-sonnet-4-6'
        >>> mk_run_path("2025-11-06T12-01-34", "claude-sonnet-4-6", start_idx=0, end_idx=1000)
        '2025-11-06T12-01-34__idx0-1000__claude-sonnet-4-6'
        >>> mk_run_path("2025-11-06T12-01-34", "claude-sonnet-4-6", start_idx=1000, end_idx=2000)
        '2025-11-06T12-01-34__idx1000-2000__claude-sonnet-4-6'
    """
    # Sequential mode: include indices in path
    if start_idx is not None or end_idx is not None:
        start_str = str(start_idx) if start_idx is not None else "0"
        end_str = str(end_idx) if end_idx is not None else "end"
        return f"{date_time}__idx{start_str}-{end_str}__{model}"
    # Random sampling mode: include ranseed
    elif ranseed is not None:
        return f"{date_time}__s{ranseed}__{model}"
    # No sampling parameters
    else:
        return f"{date_time}__{model}"


def get_output_filepath(
    date_time: str,
    sample_id: str,
    file_name: str,
    model: str,
    ranseed: int | None = None,
    start_idx: int | None = None,
    end_idx: int | None = None,
) -> Path:
    """Construct output file path in the artifacts directory structure.

    Creates a directory structure: artifacts/runs/<run_path>/<sample_id>/<file_name>

    The function locates the project root by searching for pyproject.toml.

    Args:
        date_time: Timestamp string for the benchmark run
        sample_id: Unique identifier for the sample
        file_name: Name of the output file (e.g., 'Spec.lean', 'qa.json')
        model: Model slug (e.g., "claude-sonnet-4-6")
        ranseed: Random seed used for sampling (optional, included in path when provided)
        start_idx: Starting index for sequential sampling (optional)
        end_idx: Ending index for sequential sampling (optional)

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

    # Create directory name using mk_run_path
    run_path = mk_run_path(date_time, model, ranseed, start_idx, end_idx)

    output_dir = root_dir / "artifacts" / "runs" / run_path / sample_id
    output_dir.mkdir(parents=True, exist_ok=True)

    spec_file = output_dir / file_name
    return spec_file


def get_sample_output_dir(
    date_time: str,
    sample_id: str,
    model: str,
    ranseed: int | None = None,
    start_idx: int | None = None,
    end_idx: int | None = None,
) -> Path:
    """Return the artifact directory for a given sample."""
    path = get_output_filepath(
        date_time, sample_id, "Spec.lean", model, ranseed, start_idx, end_idx
    )
    sample_dir = path.parent
    sample_dir.mkdir(parents=True, exist_ok=True)
    return sample_dir


def cleanup_empty_sample_dirs(log_dir: Path) -> None:
    """Remove empty sample subdirectories from a run directory.

    This cleans up artifacts from inspect_ai's directory structure where it
    pre-creates sample subdirectories that may remain empty if samples are
    skipped or written to a different location (e.g., with ranseed in path).

    Args:
        log_dir: Path to the run directory (e.g., artifacts/runs/<timestamp>__<variant>)
    """
    if not log_dir.exists() or not log_dir.is_dir():
        return

    for item in log_dir.iterdir():
        if item.is_dir():
            # Check if directory is empty (no files, only empty subdirs)
            try:
                contents = list(item.rglob("*"))
                # Filter to only files (not directories)
                files = [c for c in contents if c.is_file()]
                if not files:
                    # Directory has no files, remove it
                    import shutil

                    shutil.rmtree(item)
            except (PermissionError, OSError):
                # Skip directories we can't access/remove
                pass


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
    3. Lake template copied with symlinked .lake/packages/ to reduce disk I/O
    4. Used during sample execution (workspace_setup → solver → write_to_disk)
    5. Cleaned up in write_to_disk() cleanup phase (normal path)
    6. If cleanup fails, atexit handler ensures removal on process exit (safety net)

    Memory bounds: With parallelism=N, max N tmpdirs exist simultaneously
    (O(parallelism) not O(total_samples))

    Thread safety: Uses _workspace_lock for registry access in parallel execution

    Lake Build Strategy:
    - Symlinks .lake/packages/ to template (read-only shared deps, ~6GB)
    - Creates empty .lake/build/ per workspace (avoids build races)
    - Skips Fvspec/ directory (agents create their own files there)
    - Resolves lean-toolchain symlink to absolute copy (prevents dangling)
    - Disk usage: O(1) per workspace instead of O(6GB) per workspace

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
    tmpdir_base = ARTIFACTS_DIR / ".tmp"
    tmpdir_base.mkdir(parents=True, exist_ok=True)

    tmpdir = Path(tempfile.mkdtemp(prefix=f"fvspec_{sample_id}_", dir=tmpdir_base))

    # Register for atexit cleanup (safety net)
    with _workspace_lock:
        _active_workspaces.add(tmpdir)

    # Copy template structure (without .lake and Fvspec — we set those up separately)
    if not lake_template.exists():
        raise FileNotFoundError(
            f"Lake template not found at {lake_template}. "
            "Run 'lake init' to create the template first."
        )

    for item in lake_template.iterdir():
        if item.name in (".lake", "Fvspec"):
            continue
        dest = tmpdir / item.name
        if item.is_dir():
            shutil.copytree(item, dest, symlinks=True)
        else:
            shutil.copy2(item, dest)

    # Set up .lake: symlink packages (read-only deps), own build dir (avoids races)
    lake_dir = tmpdir / ".lake"
    lake_dir.mkdir()
    (lake_dir / "packages").symlink_to((lake_template / ".lake" / "packages").resolve())
    (lake_dir / "build").mkdir()

    # Resolve lean-toolchain symlink to absolute copy (prevents dangling symlinks)
    toolchain_link = tmpdir / "lean-toolchain"
    if toolchain_link.is_symlink():
        target = toolchain_link.resolve()
        toolchain_link.unlink()
        shutil.copy2(target, toolchain_link)

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
