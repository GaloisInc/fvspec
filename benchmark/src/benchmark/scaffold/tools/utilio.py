import subprocess
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

# import logfire
from benchmark import config

cfg = config.load_config()
# if cfg.meta.logging:
#     config.setup_logfire()

# Path to the Lake project template (relative to project root)
LAKE_TEMPLATE = Path(__file__).parent.parent.parent.parent.parent / "lake-template"


type SubprocessResult = tuple[str, str, int]


def run_cmd(
    cmd: list[str],
    capture_output: bool = True,
    timeout: int = 60,
    text: bool = True,
    cwd: Path | None = None,
) -> SubprocessResult:
    """
    Run a command in the shell.

    Args:
        cmd: The command to run.
        capture_output: Whether to capture stdout/stderr
        timeout: Command timeout in seconds
        text: Whether to return output as text (vs bytes)
        cwd: Working directory for the command (optional)

    Returns:
        A tuple of stdout, stderr and exitcode.
    """
    # if cfg.meta.logging:
    #     logfire.info("Running command", cmd=" ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture_output,
            timeout=timeout,
            text=text,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired:
        # logfire.info(f"Command timed out: {' '.join(cmd)}")
        return "", "Timeout", 1
    # if cfg.meta.logging:
    # logfire.info(
    #     "Command output",
    #     stdout=result.stdout,
    #     stderr=result.stderr,
    #     exitcode=result.returncode,
    # )
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
    # if cfg.meta.logging:
    #     logfire.info(msg, sample_id=sample_id, text=text)
    return f"{msg} for sample_id={sample_id}"


def get_output_filepath(
    date_time: str,
    sample_id: str,
    file_name: str,
    variant: str,
) -> Path:
    """Construct output file path in the artifacts directory structure.

    Creates a directory structure: artifacts/<date_time>__variant_<variant>/<sample_id>/<file_name>

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
    timestamped_dir = f"{date_time}__variant_{variant}"
    output_dir = root_dir / "artifacts" / timestamped_dir / sample_id
    output_dir.mkdir(parents=True, exist_ok=True)

    spec_file = output_dir / file_name
    return spec_file


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
    # if cfg.meta.logging:
    #     logfire.info(msg, spec_file=spfile, code_snippet=code)
    return f"{msg} at {spfile}"


def create_sample_workspace(
    sample_id: str, lake_template: Path = LAKE_TEMPLATE
) -> Path:
    """
    Create an isolated workspace for one sample.

    This function creates a temporary directory with a Lake project for the sample.
    The caller is responsible for cleanup via cleanup_sample_workspace().

    Advantages over global state tracking:
    - Explicit lifecycle management
    - No global state needed
    - Works naturally with parallel execution
    - Cleanup happens immediately after sample (bounded memory: O(n_parallel) not O(n_total))

    Args:
        sample_id: Unique identifier for the sample (used in tmpdir prefix)
        lake_template: Path to the Lake project template to copy

    Returns:
        Path: Temporary workspace directory containing a Lake project

    Example:
        workspace = create_sample_workspace("sample_42")
        spec_file = workspace / "Fvspec" / "Basic.lean"
        spec_file.write_text("def foo := 42")
        result = subprocess.run(["lake", "build"], cwd=workspace)
        save_artifacts(workspace, "sample_42")
        cleanup_sample_workspace(workspace)
    """
    tmpdir = Path(tempfile.mkdtemp(prefix=f"fvspec_{sample_id}_"))

    # Copy Lake project template into workspace
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
    """
    Clean up a sample workspace created by create_sample_workspace().

    Args:
        workspace: Path to the workspace directory to remove
    """
    if workspace.exists():
        try:
            shutil.rmtree(workspace)
        except Exception as e:
            # Log but don't fail on cleanup errors
            print(f"Warning: Error cleaning up workspace {workspace}: {e}")


@contextmanager
def sample_workspace(sample_id: str, lake_template: Path = LAKE_TEMPLATE):
    """
    Context manager version of sample workspace for use in with-blocks.

    Automatically creates and cleans up the workspace.

    Args:
        sample_id: Unique identifier for the sample (used in tmpdir prefix)
        lake_template: Path to the Lake project template to copy

    Yields:
        Path: Temporary workspace directory containing a Lake project

    Example:
        with sample_workspace("sample_42") as workspace:
            spec_file = workspace / "Fvspec" / "Basic.lean"
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
