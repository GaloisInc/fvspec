import subprocess
from pathlib import Path

# import logfire
from benchmark import config

cfg = config.load_config()
# if cfg.meta.logging:
#     config.setup_logfire()


type SubprocessResult = tuple[str, str, int]


def run_cmd(
    cmd: list[str], capture_output: bool = True, timeout: int = 60, text: bool = True
) -> SubprocessResult:
    """
    Run a command in the shell.

    Args:
        cmd: The command to run.

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
    date_time: str, sample_id: str, file_name: str, style: str = "functional"
) -> Path:
    """Construct output file path in the artifacts directory structure.

    Creates a directory structure: artifacts/<date_time>_<style>/<sample_id>/<file_name>
    The function locates the project root by searching for pyproject.toml.

    Args:
        date_time: Timestamp string for the benchmark run
        sample_id: Unique identifier for the sample
        file_name: Name of the output file (e.g., 'Spec.lean', 'QA.json')
        style: Verification style (functional or mvcgen)

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

    # Create artifacts/<date_time>_<style>/<sample_id> relative to the project root
    timestamped_dir = f"{date_time}_{style}"
    output_dir = root_dir / "artifacts" / timestamped_dir / sample_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write out to Spec.lean
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
