"""Plausible property testing integration for fvspec benchmark generation.

This module provides functionality to run the Plausible property testing framework
on generated Lean specifications to check for counterexamples.
"""

import re
import subprocess
import time
from pathlib import Path

from pydantic import BaseModel, Field


def _extract_theorem_locations(lean_code: str) -> dict[str, int]:
    r"""Extract theorem/lemma names and their declaration line numbers.

    Parses Lean code to find all theorem and lemma declarations and map
    them to their starting line numbers. This is used to attribute errors
    to specific theorems during selective plausible reversion.

    Args:
        lean_code: The Lean source code to parse

    Returns:
        Dictionary mapping theorem names to their declaration line numbers (1-indexed)

    Example:
        >>> code = "theorem foo : P := sorry\ntheorem bar : Q := sorry"
        >>> _extract_theorem_locations(code)
        {'foo': 1, 'bar': 2}
    """
    theorem_map = {}
    lines = lean_code.split("\n")
    for i, line in enumerate(lines, start=1):
        # Match theorem/lemma declarations at the start of a line (may have whitespace)
        match = re.match(r"^\s*(theorem|lemma)\s+(\w+)", line)
        if match:
            theorem_name = match.group(2)
            theorem_map[theorem_name] = i
    return theorem_map


def _get_mcp_diagnostics(spec_path: Path) -> list[str]:
    """Get diagnostic messages from Lean LSP via MCP tools.

    This function attempts to call the MCP lean_diagnostic_messages tool
    to get structured error information from the Lean Language Server.

    Args:
        spec_path: Path to the Spec.lean file to get diagnostics for

    Returns:
        List of diagnostic error messages. Empty list if MCP unavailable or no errors.

    Note:
        This is a placeholder that will need MCP integration. For now, returns
        empty list as fallback (causing full reversion on any error).
    """
    # TODO: Integrate with MCP lean_diagnostic_messages tool
    # For now, return empty list (will cause fallback to full reversion)
    # Real implementation would call:
    #   from generate.scaffold.tools.declaration import call_mcp_tool
    #   result = call_mcp_tool("lean_diagnostic_messages", {"file_path": str(spec_path)})
    #   return _parse_mcp_diagnostic_response(result)
    return []


def _map_errors_to_theorems(
    diagnostics: list[str], theorem_locations: dict[str, int]
) -> set[str]:
    """Map diagnostic error messages to theorem names.

    Parses diagnostic messages to extract line numbers, then maps those
    line numbers to theorem names using the theorem location map.

    Args:
        diagnostics: List of diagnostic error messages from LSP
        theorem_locations: Map of theorem names to line numbers

    Returns:
        Set of theorem names that have errors

    Note:
        Currently returns all theorems as failed (placeholder implementation).
        Real implementation would parse line numbers from diagnostics.
    """
    # TODO: Parse diagnostics for line numbers and map to theorems
    # Placeholder: assume all theorems failed if any diagnostics present
    if diagnostics:
        return set(theorem_locations.keys())
    return set()


def _selective_revert(
    content: str, failed_theorems: set[str], theorem_locations: dict[str, int]
) -> str:
    """Selectively revert 'by plausible' back to 'sorry' for failed theorems.

    Replaces plausible with sorry only for theorems that failed during
    plausible testing, preserving plausible for theorems that succeeded.

    Args:
        content: Lean code with all theorems using 'by plausible'
        failed_theorems: Set of theorem names that failed plausible testing
        theorem_locations: Map of theorem names to their declaration line numbers

    Returns:
        Modified Lean code with selective reversion applied

    Strategy:
        For each failed theorem, find its declaration line and replace
        the first occurrence of 'by plausible' after that line with 'sorry'.
    """
    lines = content.split("\n")

    for theorem_name in failed_theorems:
        start_line = theorem_locations.get(theorem_name)
        if start_line is None:
            continue

        # Search from theorem declaration onwards for 'by plausible'
        # (theorem body typically starts on same line or next few lines)
        for i in range(start_line - 1, min(start_line + 10, len(lines))):
            if i < len(lines) and "by plausible" in lines[i]:
                # Replace first occurrence of 'by plausible' with 'sorry'
                lines[i] = lines[i].replace("by plausible", "sorry", 1)
                break

    return "\n".join(lines)


class Plausibility(BaseModel):
    """Results from running Plausible property testing on a specification.

    This model captures whether plausible ran successfully, found counterexamples,
    and any errors encountered during execution.
    """

    ran: bool = Field(
        default=False,
        description="Whether plausible was attempted (may be disabled in config)",
    )
    success: float = Field(
        default=0.0,
        description="Success rate: (num_theorems - counterexamples) / num_theorems (0.0 if errors)",
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
    num_theorems: int = Field(
        default=0, description="Number of theorems tested by plausible"
    )


def _check_testability(spec_content: str) -> tuple[bool, list[str]]:
    """Check if a spec contains patterns that make it untestable with Plausible.

    Plausible cannot test:
    1. Existential quantifiers (∃) - can't be falsified
    2. Opaque custom types without Arbitrary instances

    Args:
        spec_content: The Lean spec source code

    Returns:
        Tuple of (is_testable, reasons_untestable)
        - is_testable: False if untestable patterns detected
        - reasons_untestable: List of reasons why it's untestable
    """
    reasons = []

    # Check for existential quantifiers
    if "∃" in spec_content or "Exists" in spec_content:
        # Count how many theorems have existentials
        # Use DOTALL to match across newlines since theorems can be multiline
        existential_pattern = re.compile(
            r"(theorem|lemma)\s+\w+[^:]*:(.*?):=.*?sorry",
            re.MULTILINE | re.DOTALL,
        )
        # Find all theorem bodies and check if they contain existentials
        theorem_bodies = existential_pattern.findall(spec_content)
        existential_theorems = [
            body for _, body in theorem_bodies if "∃" in body or "Exists" in body
        ]
        if existential_theorems:
            reasons.append(
                f"Contains {len(existential_theorems)} theorem(s) with existential quantifiers (∃) which Plausible cannot test"
            )

    # Check for custom opaque types commonly generated by spec agent
    # These types appear in function signatures but lack Arbitrary instances
    opaque_type_patterns = [
        (r"\bValue\b", "Value"),
        (r"\bQTensor\b", "QTensor"),
        (r"\bFTensor\b", "FTensor"),
        (
            r"\bTensor\b(?!Metadata)",
            "Tensor",
        ),  # Exclude TensorMetadata which might have deriving
    ]

    for pattern, type_name in opaque_type_patterns:
        # Check if type is used in theorem signatures
        theorem_with_type = re.search(
            rf"(theorem|lemma)\s+\w+[^:]*:.*{pattern}", spec_content, re.MULTILINE
        )
        if theorem_with_type:
            # Check if it has deriving Arbitrary or a separate instance
            has_arbitrary = re.search(
                rf"(structure|inductive)\s+{type_name}.*deriving.*Arbitrary",
                spec_content,
                re.DOTALL,
            ) or re.search(rf"instance.*Arbitrary\s+{type_name}", spec_content)
            if not has_arbitrary:
                reasons.append(
                    f"Contains opaque type '{type_name}' without Arbitrary instance"
                )

    is_testable = len(reasons) == 0
    return is_testable, reasons


def run_plausible(
    spec_path: Path, workspace_path: Path, timeout: int = 60, num_theorems: int = 0
) -> Plausibility:
    """Run plausible property testing on a Lean specification with selective reversion.

    This function:
    1. Reads the Spec.lean file and checks if it's testable
    2. If untestable (existentials, opaque types), skips plausible with explanation
    3. Otherwise: Extracts theorem locations
    4. Replaces all occurrences of 'sorry' with 'by plausible'
    5. Overwrites the Spec.lean file with the plausible version
    6. Runs 'lake build' to compile and execute plausible tests
    7. On errors: Gets diagnostics and identifies which theorems failed
    8. Selectively reverts failed theorems back to 'sorry'
    9. Parses the output for success/failure/errors

    The final artifact contains 'by plausible' for successful theorems and
    'sorry' for theorems that failed plausible testing (compilation errors,
    instance synthesis failures, counterexamples, etc.).

    Args:
        spec_path: Path to the Spec.lean file
        workspace_path: Path to the workspace directory containing lakefile
        timeout: Maximum time in seconds to wait for lake build
        num_theorems: Number of theorems in the spec (for success rate calculation)

    Returns:
        Plausibility object with test results
    """
    # Phase 1: Read spec content and check testability
    try:
        spec_content = spec_path.read_text()
    except (OSError, UnicodeDecodeError) as e:
        return Plausibility(
            ran=True, success=0.0, errors=[f"Failed to read spec file: {e}"]
        )

    # Phase 1.5: Check if spec is testable with Plausible
    is_testable, untestable_reasons = _check_testability(spec_content)
    if not is_testable:
        # Skip plausible entirely - spec contains untestable patterns
        return Plausibility(
            ran=False,
            success=0.0,
            errors=[
                "Skipped plausible: spec contains untestable patterns",
                *untestable_reasons,
            ],
            num_theorems=num_theorems,
        )

    # Phase 2: Check if spec contains sorry (nothing to replace if not)
    if "sorry" not in spec_content:
        return Plausibility(
            ran=True,
            success=0.0,
            errors=["No 'sorry' found in spec to replace with 'plausible'"],
        )

    # Extract theorem locations before replacement (for selective reversion later)
    theorem_locations = _extract_theorem_locations(spec_content)

    # Phase 2: Replace sorry with plausible (FVAPPS approach)
    # Handle both `... := sorry` and `... := by sorry` (both need `... := by plausible`)
    spec_plausible = spec_content
    # First replace `:= by sorry` with `:= by plausible`
    spec_plausible = re.sub(
        r":=\s+by\s+sorry(?=\W|$)", ":= by plausible", spec_plausible
    )
    # Then replace remaining `:= sorry` with `:= by plausible`
    spec_plausible = re.sub(r":=\s+sorry(?=\W|$)", ":= by plausible", spec_plausible)

    # Overwrite the main Spec.lean file with plausible version
    try:
        spec_path.write_text(spec_plausible)
    except OSError as e:
        return Plausibility(
            ran=True, success=0.0, errors=[f"Failed to write spec file: {e}"]
        )

    # Phase 3: Run lake build with timeout
    start_time = time.time()
    try:
        result = subprocess.run(
            ["lake", "build"],
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed_time = time.time() - start_time

        # Phase 4: Selective reversion on errors
        # If build failed, try to identify which theorems caused failures
        # and revert only those back to sorry
        if result.returncode != 0:
            # Get diagnostics from MCP (if available)
            diagnostics = _get_mcp_diagnostics(spec_path)

            # Map errors to specific theorems
            failed_theorems = _map_errors_to_theorems(diagnostics, theorem_locations)

            # If we identified specific failed theorems, selectively revert them
            # Otherwise, revert all theorems (fallback behavior)
            if failed_theorems and failed_theorems != set(theorem_locations.keys()):
                # Partial failure: selectively revert only failed theorems
                spec_final = _selective_revert(
                    spec_plausible, failed_theorems, theorem_locations
                )
            else:
                # Total failure or couldn't identify specific failures: revert all
                spec_final = spec_content  # Revert to original (all sorry)

            # Write the final version with selective reversion
            try:
                spec_path.write_text(spec_final)
            except OSError:
                # Non-fatal: continue with results even if reversion fails
                pass

        # Phase 5: Parse results
        return _parse_plausible_output(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            elapsed_time=elapsed_time,
            num_theorems=num_theorems,
        )

    except subprocess.TimeoutExpired:
        elapsed_time = time.time() - start_time

        # On timeout, revert everything to sorry
        try:
            spec_path.write_text(spec_content)
        except OSError:
            # Non-fatal: continue with results even if reversion fails
            pass

        return Plausibility(
            ran=True,
            success=0.0,
            time=elapsed_time,
            errors=[f"Plausible execution timed out after {timeout} seconds"],
        )
    except (OSError, ValueError) as e:
        # On other errors, revert everything to sorry
        try:
            spec_path.write_text(spec_content)
        except OSError:
            # Non-fatal: continue with results even if reversion fails
            pass

        return Plausibility(
            ran=True, success=0.0, errors=[f"Failed to execute lake build: {e}"]
        )


def _parse_plausible_output(
    returncode: int,
    stdout: str,
    stderr: str,
    elapsed_time: float,
    num_theorems: int = 0,
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
        num_theorems: Number of theorems in the spec (for success rate calculation)

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
        compilation_errors.extend(error_lines)

    all_errors = instance_errors + compilation_errors

    # Determine success rate
    if returncode != 0 or all_errors or num_theorems == 0:
        # Compilation failed, other errors, or no theorems to test - treat as 0% success
        success_rate = 0.0
    else:
        # Compute success rate: (theorems passed) / (total theorems)
        # theorems passed = num_theorems - num_counterexamples
        success_rate = (num_theorems - num_counterexamples) / num_theorems

    return Plausibility(
        ran=True,
        success=success_rate,
        time=elapsed_time,
        errors=all_errors,
        counterexamples=num_counterexamples,
        num_theorems=num_theorems,
    )
