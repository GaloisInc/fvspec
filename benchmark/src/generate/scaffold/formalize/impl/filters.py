"""Filters for cleaning impl agent output.

This module handles impl agent hallucinations where specs are generated
alongside implementations. The primary defense is stripping spec namespaces
before storing results.
"""

import re


def strip_spec_namespace(lean_code: str) -> str:
    """Remove Fvspec.Spec namespace and contents from Lean code.

    This handles impl agent hallucinations where specs are generated
    alongside implementations. We strip them before storing the result.

    The function removes:
    - The entire "namespace Fvspec.Spec ... end Fvspec.Spec" block
    - Any content within that namespace (theorems, lemmas, etc.)

    Args:
        lean_code: Raw Lean code possibly containing Spec namespace

    Returns:
        Lean code with Spec namespace section removed

    Examples:
        >>> code = '''namespace Fvspec.Impl
        ... def foo := 1
        ... end Fvspec.Impl
        ...
        ... namespace Fvspec.Spec
        ... theorem bar : True := sorry
        ... end Fvspec.Spec'''
        >>> result = strip_spec_namespace(code)
        >>> "theorem bar" in result
        False
        >>> "def foo" in result
        True
    """
    # Pattern: Match from "namespace Fvspec.Spec" to its matching "end Fvspec.Spec"
    # Handles both with and without "open" statements and other content
    # Uses non-greedy matching to handle multiple namespace blocks
    pattern = r"namespace\s+Fvspec\.Spec\b.*?end\s+Fvspec\.Spec\b"

    cleaned = re.sub(pattern, "", lean_code, flags=re.DOTALL)

    # Clean up excessive blank lines (3+ newlines → 2 newlines)
    cleaned = re.sub(r"\n\s*\n\s*\n+", "\n\n", cleaned)

    # Clean up leading/trailing whitespace
    cleaned = cleaned.strip()

    return cleaned


def strip_spec_keywords(lean_code: str) -> str:
    """Remove specification keywords (theorem, lemma, example, axiom, sorry) from Lean code.

    This strips individual theorem/lemma/example/axiom declarations and sorry placeholders
    that may appear inside the Impl namespace (hallucinations). It complements
    strip_spec_namespace which removes entire Spec namespace blocks.

    The function removes:
    - Individual theorem/lemma/example/axiom declarations
    - Standalone sorry placeholders
    - Their associated doc comments (if present)

    Args:
        lean_code: Lean code possibly containing spec keywords

    Returns:
        Lean code with spec keywords removed

    Examples:
        >>> code = '''namespace Fvspec.Impl
        ... def foo := 1
        ... example : True := trivial
        ... end Fvspec.Impl'''
        >>> result = strip_spec_keywords(code)
        >>> "example" not in result
        True
        >>> "def foo" in result
        True
    """
    # Pattern: Match doc comment (optional) + theorem/lemma/example declaration
    # Matches multi-line declarations up to the next top-level keyword or end of namespace

    # First, handle doc comments immediately before spec keywords
    # Pattern: /-- ... -/ followed by theorem/lemma/example/axiom
    docstring_pattern = r"/--.*?-/\s*(?=(?:theorem|lemma|example|axiom)\s+)"
    cleaned = re.sub(docstring_pattern, "", lean_code, flags=re.DOTALL)

    # Now remove the spec keyword declarations themselves
    # Match from keyword to the next top-level keyword (def/structure/etc) or namespace end
    # This is conservative - stops at next definition to avoid over-removing
    spec_keywords = ["theorem", "lemma", "example", "axiom"]

    for keyword in spec_keywords:
        # Pattern matches: keyword name ... up to next top-level keyword or "end" or EOF
        # Uses lookahead to preserve the next definition
        # Added \Z to catch keywords at end of file (fixes bug where EOF declarations weren't removed)
        pattern = rf"^[ \t]*{keyword}\s+.*?(?=(?:^[ \t]*(?:def|structure|inductive|class|instance|abbrev|theorem|lemma|example|axiom)\s+)|(?:^end\s+)|(?:\Z))"
        cleaned = re.sub(pattern, "", cleaned, flags=re.MULTILINE | re.DOTALL)

    # Also remove standalone "sorry" placeholders (not part of larger declarations)
    # Pattern: Line with just "sorry" (possibly with whitespace)
    sorry_pattern = r"^[ \t]*sorry[ \t]*$"
    cleaned = re.sub(sorry_pattern, "", cleaned, flags=re.MULTILINE)

    # Clean up excessive blank lines (3+ newlines → 2 newlines)
    cleaned = re.sub(r"\n\s*\n\s*\n+", "\n\n", cleaned)

    # Clean up leading/trailing whitespace
    cleaned = cleaned.strip()

    return cleaned


def validate_impl_only(lean_code: str) -> tuple[bool, str | None]:
    r"""Validate that code contains only Impl namespace, no specs.

    Checks for:
    - Fvspec.Spec namespace (should have been filtered)
    - Theorem/lemma keywords (forbidden in impl code)

    Args:
        lean_code: Lean code to validate

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if code passes validation
        - error_message: None if valid, otherwise description of violation

    Examples:
        >>> code = "namespace Fvspec.Impl\ndef foo := 1\nend Fvspec.Impl"
        >>> is_valid, error = validate_impl_only(code)
        >>> is_valid
        True
        >>> code_with_theorem = "namespace Fvspec.Impl\ntheorem bar : True := sorry\nend Fvspec.Impl"
        >>> is_valid, error = validate_impl_only(code_with_theorem)
        >>> is_valid
        False
    """
    # Check for Spec namespace (indicates filtering failed)
    if "namespace Fvspec.Spec" in lean_code:
        return False, "Code contains Fvspec.Spec namespace (should be impl only)"

    # Check for forbidden specification keywords
    # Use word boundaries to avoid false positives in comments/strings
    forbidden_keywords = [
        (r"\btheorem\s+", "theorem"),
        (r"\blemma\s+", "lemma"),
        (r"\bexample\s+", "example"),
        (r"\baxiom\s+", "axiom"),
        (r"\bsorry\b", "sorry"),  # sorry often appears without trailing whitespace
    ]

    for pattern, keyword in forbidden_keywords:
        if re.search(pattern, lean_code):
            return (
                False,
                f"Code contains forbidden keyword: {keyword} (use def for implementations)",
            )

    return True, None


def extract_impl_only(lean_code: str) -> str:
    """Extract only the Impl namespace section from Lean code.

    This is more aggressive than strip_spec_namespace - it actively extracts
    the Impl section rather than just removing Spec sections. Use this when
    you want to be absolutely certain only impl code remains.

    Args:
        lean_code: Raw Lean code possibly containing multiple namespaces

    Returns:
        Only the Fvspec.Impl namespace content, or original code if no Impl namespace found

    Examples:
        >>> code = '''namespace Fvspec.Impl
        ... def foo := 1
        ... end Fvspec.Impl
        ...
        ... namespace Fvspec.Spec
        ... theorem bar : True := sorry
        ... end Fvspec.Spec'''
        >>> result = extract_impl_only(code)
        >>> "def foo" in result
        True
        >>> "theorem bar" in result
        False
    """
    # Pattern: Extract from "namespace Fvspec.Impl" to its matching "end Fvspec.Impl"
    pattern = r"(namespace\s+Fvspec\.Impl\b.*?end\s+Fvspec\.Impl\b)"

    match = re.search(pattern, lean_code, flags=re.DOTALL)

    if match:
        impl_section = match.group(1)
        # Clean up excessive blank lines
        impl_section = re.sub(r"\n\s*\n\s*\n+", "\n\n", impl_section)
        return impl_section.strip()

    # No Impl namespace found - return original code
    # (might be a fragment without namespace declarations)
    return lean_code.strip()
