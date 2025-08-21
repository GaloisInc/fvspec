import subprocess
from pathlib import Path
import logfire
from generate import config

cfg = config.load_config()
if cfg.meta.logging:
    config.setup_logfire()


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
    if cfg.meta.logging:
        logfire.info("Running command", cmd=" ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture_output,
            timeout=timeout,
            text=text,
        )
    except subprocess.TimeoutExpired:
        logfire.info(f"Command timed out: {' '.join(cmd)}")
        return "", "Timeout", 1
    if cfg.meta.logging:
        logfire.info(
            "Command output",
            stdout=result.stdout,
            stderr=result.stderr,
            exitcode=result.returncode,
        )
    return result.stdout, result.stderr, result.returncode


def no_code_block_found(sample_id: str, text: str) -> str:
    """Considered effectful just because logging"""
    msg = "No <code> block found"
    if cfg.meta.logging:
        logfire.info(msg, sample_id=sample_id, text=text)
    return f"{msg} for sample_id={sample_id}"


def get_output_filepath(sample_id: str) -> Path:
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

    # Create artifacts/spec/<sample_id> relative to the project root
    output_dir = root_dir / "artifacts" / "spec" / sample_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write out to Spec.lean
    spec_file = output_dir / "Spec.lean"
    return spec_file


def writeit(spfile: Path, code: str) -> str:
    with spfile.open("w", encoding="utf-8") as the_file:
        the_file.write(code)
    msg = "Code block written to disk"
    if cfg.meta.logging:
        logfire.info(msg, spec_file=spfile, code_snippet=code)
    return f"{msg} at {spfile}"
