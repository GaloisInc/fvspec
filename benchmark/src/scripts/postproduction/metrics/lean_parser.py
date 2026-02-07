"""Lean code parsing and metrics extraction."""

import math
import re
from collections import Counter
from typing import Any

from scripts.postproduction.metrics.models import (
    ComplexityMetrics,
    StructureMetrics,
)


def extract_structure_metrics(lean_code: str) -> StructureMetrics:
    """Extract structure metrics from Lean code.

    Args:
        lean_code: Lean source code

    Returns:
        StructureMetrics containing line counts, declaration counts, etc.
    """
    lines = lean_code.split("\n")

    # Line counts
    total_lines = len(lines)
    blank_lines = sum(1 for line in lines if not line.strip())
    comment_lines = sum(
        1
        for line in lines
        if line.strip().startswith("--") or line.strip().startswith("/-")
    )
    code_lines = total_lines - blank_lines - comment_lines

    # Declaration counts
    num_axioms = len(re.findall(r"\baxiom\b", lean_code))
    num_defs = len(re.findall(r"\bdef\b", lean_code))
    num_theorems = len(re.findall(r"\btheorem\b", lean_code))
    num_lemmas = len(re.findall(r"\blemma\b", lean_code))
    num_structures = len(re.findall(r"\bstructure\b", lean_code))
    num_inductives = len(re.findall(r"\binductive\b", lean_code))

    # Proof quality
    num_sorries = len(re.findall(r"\bsorry\b", lean_code))
    num_admits = len(re.findall(r"\badmit\b", lean_code))

    # Count axiomized defs (axioms that look like they should be defs)
    # Pattern: axiom name : Type (without Prop)
    axiom_pattern = r"axiom\s+\w+\s*:\s*(?!.*\bProp\b)"
    num_axiomized_defs = len(re.findall(axiom_pattern, lean_code))

    # Special constructs
    num_eval_statements = len(re.findall(r"^#eval\b", lean_code, re.MULTILINE))
    num_imports = len(re.findall(r"^import\b", lean_code, re.MULTILINE))
    num_namespace_blocks = len(re.findall(r"^namespace\b", lean_code, re.MULTILINE))

    return StructureMetrics(
        total_lines=total_lines,
        code_lines=code_lines,
        blank_lines=blank_lines,
        comment_lines=comment_lines,
        num_axioms=num_axioms,
        num_defs=num_defs,
        num_theorems=num_theorems,
        num_lemmas=num_lemmas,
        num_structures=num_structures,
        num_inductives=num_inductives,
        num_sorries=num_sorries,
        num_admits=num_admits,
        num_axiomized_defs=num_axiomized_defs,
        num_eval_statements=num_eval_statements,
        num_imports=num_imports,
        num_namespace_blocks=num_namespace_blocks,
    )


def extract_complexity_metrics(lean_code: str) -> ComplexityMetrics:
    """Extract complexity metrics from Lean code.

    Args:
        lean_code: Lean source code

    Returns:
        ComplexityMetrics containing nesting, term size, dependencies, etc.
    """
    # Extract all proof blocks (between := and final closing delimiter)
    proof_blocks = _extract_proof_blocks(lean_code)

    # Nesting depth analysis
    nesting_depths = [_calculate_nesting_depth(proof) for proof in proof_blocks]
    max_nesting = max(nesting_depths) if nesting_depths else 0
    avg_nesting = sum(nesting_depths) / len(nesting_depths) if nesting_depths else 0.0

    # Term size analysis (token count)
    term_sizes = [len(re.findall(r"\S+", proof)) for proof in proof_blocks]
    max_term = max(term_sizes) if term_sizes else 0
    avg_term = sum(term_sizes) / len(term_sizes) if term_sizes else 0.0
    total_tokens = sum(term_sizes)

    # Proof steps (count tactics: by, exact, apply, simp, etc.)
    proof_steps = [_count_proof_steps(proof) for proof in proof_blocks]
    max_steps = max(proof_steps) if proof_steps else 0
    avg_steps = sum(proof_steps) / len(proof_steps) if proof_steps else 0.0

    # Dependencies (count identifiers that look like external references)
    dependencies = _extract_dependencies(lean_code)
    num_deps = len(dependencies)

    # Count total declarations to compute avg deps per decl
    total_decls = len(re.findall(r"\b(def|theorem|lemma|axiom)\b", lean_code)) or 1
    avg_deps = num_deps / total_decls

    # Parameter counts
    param_counts = _extract_parameter_counts(lean_code)
    max_params = max(param_counts) if param_counts else 0
    avg_params = sum(param_counts) / len(param_counts) if param_counts else 0.0

    # Halstead metrics
    halstead = _compute_halstead_metrics(lean_code)

    return ComplexityMetrics(
        max_nesting_depth=max_nesting,
        avg_nesting_depth=avg_nesting,
        max_term_size=max_term,
        avg_term_size=avg_term,
        total_proof_tokens=total_tokens,
        avg_proof_steps=avg_steps,
        max_proof_steps=max_steps,
        num_dependencies=num_deps,
        avg_dependencies_per_decl=avg_deps,
        avg_param_count=avg_params,
        max_param_count=max_params,
        halstead_vocabulary=int(halstead["vocabulary"]),
        halstead_length=int(halstead["length"]),
        halstead_volume=halstead["volume"],
        halstead_difficulty=halstead["difficulty"],
        halstead_effort=halstead["effort"],
        halstead_time=halstead["time"],
        halstead_bugs=halstead["bugs"],
    )


def _extract_proof_blocks(lean_code: str) -> list[str]:
    """Extract proof blocks from Lean code.

    Looks for patterns like:
    - theorem/lemma name : type := proof
    - def name : type := body

    Returns:
        List of proof/body strings
    """
    # Pattern: declaration followed by := and content until next declaration or end
    pattern = r"(?:theorem|lemma|def)\s+\w+[^:]*:[^:]*:=\s*([^(?:theorem|lemma|def|axiom|structure|inductive)]+)"
    matches = re.findall(pattern, lean_code, re.DOTALL)
    return [m.strip() for m in matches]


def _calculate_nesting_depth(code_block: str) -> int:
    """Calculate maximum nesting depth based on parentheses/brackets.

    Args:
        code_block: Code block to analyze

    Returns:
        Maximum nesting depth
    """
    max_depth = 0
    current_depth = 0

    # Count opening and closing delimiters
    for char in code_block:
        if char in "([{⟨":
            current_depth += 1
            max_depth = max(max_depth, current_depth)
        elif char in ")]}⟩":
            current_depth = max(0, current_depth - 1)

    return max_depth


def _count_proof_steps(proof_block: str) -> int:
    """Count tactic steps in a proof block.

    Args:
        proof_block: Proof text

    Returns:
        Number of tactic invocations

    Note:
        In the fvspec benchmark, most proofs use `sorry` placeholders rather than
        actual tactic proofs, so this metric typically returns low values. The full
        tactic list is included for forward compatibility should the benchmark
        evolve to include complete proofs.
    """
    # Common Lean tactics
    tactics = [
        r"\bby\b",
        r"\bexact\b",
        r"\bapply\b",
        r"\bsimp\b",
        r"\brw\b",
        r"\brewrite\b",
        r"\bintro\b",
        r"\bcases\b",
        r"\binduction\b",
        r"\bsplit\b",
        r"\bleft\b",
        r"\bright\b",
        r"\brefl\b",
        r"\btrivial\b",
        r"\bdecide\b",
        r"\brfl\b",
        r"\bsorry\b",
        r"\badmit\b",
        r"\bplausible\b",
    ]

    total_steps = 0
    for tactic_pattern in tactics:
        total_steps += len(re.findall(tactic_pattern, proof_block))

    return total_steps


def _extract_dependencies(lean_code: str) -> set[str]:
    """Extract unique external identifiers referenced in code.

    Args:
        lean_code: Lean source code

    Returns:
        Set of dependency identifiers (qualified names)
    """
    # Match qualified identifiers: Foo.Bar.baz or List.map
    # Exclude common keywords
    keywords = {
        "def",
        "theorem",
        "lemma",
        "axiom",
        "structure",
        "inductive",
        "Type",
        "Prop",
        "Nat",
        "Int",
        "String",
        "List",
        "Array",
        "Option",
    }

    pattern = r"\b([A-Z]\w*(?:\.\w+)+)\b"
    matches = re.findall(pattern, lean_code)

    # Filter out keywords and keep only qualified names
    dependencies = {match for match in matches if match.split(".")[0] not in keywords}

    return dependencies


def _extract_parameter_counts(lean_code: str) -> list[int]:
    """Extract parameter counts for all declarations.

    Args:
        lean_code: Lean source code

    Returns:
        List of parameter counts (one per declaration)
    """
    param_counts = []

    # Pattern: declaration with parameters in parentheses
    # Example: theorem foo (x : Nat) (y z : Int) (h : x > 0) : Prop
    decl_pattern = r"(?:def|theorem|lemma|axiom)\s+\w+\s*((?:\([^)]+\))*)"

    for match in re.finditer(decl_pattern, lean_code):
        param_section = match.group(1)

        # Count parameter groups (each parenthesized section)
        # Count individual parameters: (x y z : Type) has 3 params
        params_in_decl = 0

        # Find all parenthesized parameter groups
        param_groups = re.findall(r"\(([^)]+)\)", param_section)

        for group in param_groups:
            # Extract parameter names before the colon
            # Pattern: x y z : Type
            before_colon = group.split(":")[0] if ":" in group else group
            param_names = before_colon.strip().split()
            params_in_decl += len(param_names)

        param_counts.append(params_in_decl)

    return param_counts


def extract_all_metrics(
    spec_code: str | None = None,
    impl_code: str | None = None,
    tests_code: str | None = None,
) -> dict[str, Any]:
    """Extract all metrics from Lean code files.

    Args:
        spec_code: Spec.lean content
        impl_code: Impl.lean content
        tests_code: Tests.lean content

    Returns:
        Dict with structure and complexity metrics for each file
    """
    result: dict[str, Any] = {}

    if spec_code:
        result["spec_structure"] = extract_structure_metrics(spec_code)
        result["spec_complexity"] = extract_complexity_metrics(spec_code)

    if impl_code:
        result["impl_structure"] = extract_structure_metrics(impl_code)
        result["impl_complexity"] = extract_complexity_metrics(impl_code)

    if tests_code:
        result["tests_structure"] = extract_structure_metrics(tests_code)
        result["tests_complexity"] = extract_complexity_metrics(tests_code)

    # Compute aggregate metrics
    total_lines = 0
    total_sorries = 0
    total_axioms = 0

    for code in [spec_code, impl_code, tests_code]:
        if code:
            metrics = extract_structure_metrics(code)
            total_lines += metrics.total_lines
            total_sorries += metrics.num_sorries
            total_axioms += metrics.num_axioms

    result["total_lean_lines"] = total_lines
    result["total_sorries"] = total_sorries
    result["total_axioms"] = total_axioms

    return result


def _compute_halstead_metrics(lean_code: str) -> dict[str, float]:
    """Compute Halstead complexity metrics for Lean code.

    Halstead metrics measure the complexity based on operators and operands:
    - Vocabulary (n): unique operators + unique operands
    - Length (N): total operators + total operands
    - Volume (V): N × log₂(n)
    - Difficulty (D): (n1/2) × (N2/n2)
    - Effort (E): D × V
    - Time (T): E / 18 seconds
    - Bugs (B): V / 3000

    Args:
        lean_code: Lean source code

    Returns:
        Dict with Halstead metrics
    """
    # Define Lean operators (keywords, symbols, punctuation that perform operations)
    operators = {
        # Keywords
        "def",
        "theorem",
        "lemma",
        "axiom",
        "structure",
        "inductive",
        "match",
        "with",
        "if",
        "then",
        "else",
        "let",
        "in",
        "fun",
        "λ",
        "forall",
        "∀",
        "exists",
        "∃",
        "by",
        "have",
        "show",
        "calc",
        "sorry",
        "admit",
        # Tactics
        "exact",
        "apply",
        "simp",
        "rw",
        "rewrite",
        "intro",
        "intros",
        "cases",
        "induction",
        "split",
        "left",
        "right",
        "refl",
        "rfl",
        "trivial",
        "decide",
        "plausible",
        # Operators
        "→",
        "->",
        "←",
        "<-",
        "∧",
        "∨",
        "¬",
        "=",
        "≠",
        "<",
        ">",
        "≤",
        "≥",
        "+",
        "-",
        "*",
        "/",
        "%",
        "^",
        ":=",
        ":",
        "|",
        "||",
        "&&",
        "!",
        ".",
        ",",
        ";",
        # Delimiters (also operators)
        "(",
        ")",
        "[",
        "]",
        "{",
        "}",
        "⟨",
        "⟩",
    }

    # Tokenize code: split on whitespace and common delimiters
    # This is a simplified tokenization - not a full Lean lexer
    token_pattern = (
        r"[a-zA-Z_][a-zA-Z0-9_']*|[→←∀∃∧∨¬≠≤≥⟨⟩]|:=|->|<-|[()[\]{}.,;:+\-*/%^=<>|!]|\S+"
    )
    tokens = re.findall(token_pattern, lean_code)

    # Separate operators and operands
    operator_counts = Counter()
    operand_counts = Counter()

    for token in tokens:
        if token in operators:
            operator_counts[token] += 1
        elif token.strip() and not token.startswith("--"):  # Skip comments
            # Consider as operand (identifiers, literals, etc.)
            operand_counts[token] += 1

    # Halstead metrics
    n1 = len(operator_counts)  # Unique operators
    n2 = len(operand_counts)  # Unique operands
    N1 = sum(operator_counts.values())  # Total operators
    N2 = sum(operand_counts.values())  # Total operands

    n = n1 + n2  # Vocabulary
    N = N1 + N2  # Length

    # Compute derived metrics
    if n > 0 and n2 > 0:
        volume = N * math.log2(n)
        difficulty = (n1 / 2) * (N2 / n2) if n2 > 0 else 0.0
        effort = difficulty * volume
        time = effort / 18  # Time in seconds
        bugs = volume / 3000  # Expected bugs
    else:
        # Empty or trivial code
        volume = 0.0
        difficulty = 0.0
        effort = 0.0
        time = 0.0
        bugs = 0.0

    return {
        "vocabulary": n,
        "length": N,
        "volume": volume,
        "difficulty": difficulty,
        "effort": effort,
        "time": time,
        "bugs": bugs,
    }
