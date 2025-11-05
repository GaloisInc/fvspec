"""Plausible property testing integration for fvspec benchmark generation.

This module provides functionality to run the Plausible property testing framework
on generated Lean specifications to check for counterexamples.
"""

import re
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field


class Plausibility(BaseModel):
    """Results from running Plausible property testing on a specification.

    This model captures whether plausible ran successfully, found counterexamples,
    and any errors encountered during execution.
    """

    ran: bool = Field(
        default=False,
        description="Whether plausible was attempted (may be disabled in config)",
    )
    success: bool | None = Field(
        default=None,
        description="True if no counterexamples found, False if counterexamples found, None if couldn't run",
    )
    time: float | None = Field(
        default=None, description="Time taken to run plausible in seconds"
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Compilation errors or instance synthesis failures",
    )
    counterexamples: int = Field(
        default=0, description="Number of counterexamples found by plausible"
    )


def run_plausible(
    spec_path: Path, workspace_path: Path, timeout: int = 60
) -> Plausibility:
    """Run plausible property testing on a Lean specification.

    This function:
    1. Reads the Spec.lean file
    2. Replaces all occurrences of 'sorry' with 'plausible'
    3. Overwrites the Spec.lean file with the plausible version
    4. Runs 'lake build' to compile and execute plausible tests
    5. Parses the output for success/failure/errors

    Note: This overwrites the spec file with plausible instead of sorry.
    The artifacts will contain the plausible version, not the sorry version.

    Args:
        spec_path: Path to the Spec.lean file
        workspace_path: Path to the workspace directory containing lakefile
        timeout: Maximum time in seconds to wait for lake build

    Returns:
        Plausibility object with test results
    """
    import time

    # Read spec content
    try:
        spec_content = spec_path.read_text()
    except Exception as e:
        return Plausibility(
            ran=True, success=None, errors=[f"Failed to read spec file: {e}"]
        )

    # Check if spec contains sorry (nothing to replace if not)
    if "sorry" not in spec_content:
        return Plausibility(
            ran=True,
            success=None,
            errors=["No 'sorry' found in spec to replace with 'plausible'"],
        )

    # Replace sorry with plausible (FVAPPS approach)
    spec_plausible = spec_content.replace("sorry", "plausible")

    # Overwrite the main Spec.lean file with plausible version
    try:
        spec_path.write_text(spec_plausible)
    except Exception as e:
        return Plausibility(
            ran=True, success=None, errors=[f"Failed to write spec file: {e}"]
        )

    # Run lake build with timeout
    start_time = time.time()
    try:
        result = subprocess.run(
            ["lake", "build", spec_path.name],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed_time = time.time() - start_time

        # Parse results
        return _parse_plausible_output(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            elapsed_time=elapsed_time,
        )

    except subprocess.TimeoutExpired:
        elapsed_time = time.time() - start_time

        return Plausibility(
            ran=True,
            success=None,
            time=elapsed_time,
            errors=[f"Plausible execution timed out after {timeout} seconds"],
        )
    except Exception as e:
        return Plausibility(
            ran=True, success=None, errors=[f"Failed to execute lake build: {e}"]
        )


def _parse_plausible_output(
    returncode: int, stdout: str, stderr: str, elapsed_time: float
) -> Plausibility:
    """Parse the output from lake build to extract plausible results.

    Plausible output patterns:
    - Success: "Success" or no errors (returncode 0)
    - Counterexample: "Found a counter-example!" with details
    - Instance error: "Failed to create a `testable` instance" or similar synthesis errors

    Args:
        returncode: Exit code from lake build
        stdout: Standard output
        stderr: Standard error
        elapsed_time: Time taken to run

    Returns:
        Plausibility object with parsed results
    """
    combined_output = stdout + "\n" + stderr

    # Check for counterexamples
    counterexample_matches = re.findall(
        r"Found a counter-example!", combined_output, re.IGNORECASE
    )
    num_counterexamples = len(counterexample_matches)

    # Check for instance synthesis errors
    instance_errors = []
    if (
        "Failed to create" in combined_output
        or "failed to synthesize" in combined_output
    ):
        instance_errors.append(
            "Failed to synthesize typeclass instances (Testable, Arbitrary, Decidable)"
        )

    # Check for other compilation errors
    compilation_errors = []
    if "error:" in combined_output.lower() and returncode != 0:
        # Extract error lines (simplified - could be more sophisticated)
        error_lines = [
            line.strip()
            for line in combined_output.split("\n")
            if "error:" in line.lower()
        ]
        compilation_errors.extend(error_lines[:5])  # Limit to first 5 errors

    all_errors = instance_errors + compilation_errors

    # Determine success
    if returncode == 0 and num_counterexamples == 0:
        # Compiled successfully with no counterexamples
        success = True
    elif num_counterexamples > 0:
        # Found counterexamples - plausible works but property may be wrong
        success = False
    else:
        # Compilation failed or other errors
        success = None

    return Plausibility(
        ran=True,
        success=success,
        time=elapsed_time,
        errors=all_errors,
        counterexamples=num_counterexamples,
    )
