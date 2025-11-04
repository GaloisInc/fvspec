"""Validation utilities for spec generation agent."""

from __future__ import annotations

import re

from generate.scaffold.formalize_spec.models import SpecValidation


def validate_spec_output(lean_code: str, diagnostics: str) -> SpecValidation:
    """Validate spec agent output.

    Checks:
    1. Code compiles (no type errors in diagnostics)
    2. Has theorem/def/lemma statements
    3. Has sorry (tracked but NOT required - sorry is GOOD for specs!)

    Args:
        lean_code: Generated Lean specification code
        diagnostics: Output from lean_diagnostic_messages LSP tool

    Returns:
        Validation result with status and errors
    """
    # Check for type errors in diagnostics
    has_errors = bool(re.search(r"\berror:", diagnostics, re.IGNORECASE))

    # Check for theorem/def/lemma statements
    has_statements = bool(
        re.search(r"\b(theorem|def|lemma|axiom|structure|inductive)\b", lean_code)
    )

    # Check for sorry (this is EXPECTED and GOOD for specs!)
    has_sorry = bool(re.search(r"\bsorry\b", lean_code))

    # Collect errors
    errors: list[str] = []
    if has_errors:
        errors.append("Code has type errors")
    if not has_statements:
        errors.append("No theorem/def statements found")

    # Valid if: compiles AND has statements
    # Note: has_sorry is NOT required for validity, but we track it
    valid = not has_errors and has_statements

    return SpecValidation(
        compiles=not has_errors,
        has_statements=has_statements,
        has_sorry=has_sorry,
        valid=valid,
        errors=errors,
    )


def extract_signatures(impl_lean: str) -> dict[str, str]:
    """Extract function signatures from Impl.lean.

    Parses lines like:
        def foo (x : Nat) : Nat := ...
        theorem bar (x : Bool) : x = x := ...
        structure Baz where ...

    Returns dict mapping function name to signature string:
        {"foo": "def foo (x : Nat) : Nat", ...}

    Args:
        impl_lean: Lean implementation code

    Returns:
        Dictionary mapping function names to their signatures
    """
    signatures: dict[str, str] = {}

    # Split into lines and process each
    lines = impl_lean.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Look for keyword at start of line
        match = re.match(
            r"^(def|theorem|lemma|structure|inductive|class|axiom)\s+(\w+)(.*)",
            line,
        )

        if match:
            keyword = match.group(1)
            name = match.group(2)
            rest = match.group(3)

            # Accumulate signature until we hit := or where
            sig_parts = [rest]

            # Check if := is already on the same line
            if ":=" not in rest:
                i += 1
                while i < len(lines):
                    next_line = lines[i].strip()
                    # Stop if we hit := or where or a new declaration
                    if (
                        ":=" in next_line
                        or next_line.startswith("where")
                        or next_line.startswith("|")
                    ):
                        break
                    if re.match(
                        r"^(def|theorem|lemma|structure|inductive|class|axiom)\s",
                        next_line,
                    ):
                        break
                    sig_parts.append(next_line)
                    i += 1
            else:
                i += 1

            # Build full signature
            full_sig_text = " ".join(sig_parts)
            full_sig_text = " ".join(full_sig_text.split())  # Clean whitespace

            # Only include if there's a type signature (contains :)
            if ":" in full_sig_text:
                # Extract just up to := if present
                if ":=" in full_sig_text:
                    full_sig_text = full_sig_text[: full_sig_text.index(":=")].strip()

                signatures[name] = f"{keyword} {name} {full_sig_text}"
            elif keyword in ("structure", "inductive", "class"):
                # These don't always have : before where
                signatures[name] = f"{keyword} {name}"
            else:
                i += 1
                continue

        i += 1

    return signatures
