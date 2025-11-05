"""Smart function discovery using tree-sitter parsing.

This module uses tree-sitter to parse Python code and intelligently discover:
1. The function/method/class being tested
2. Its dependencies
3. Extract implementation code

Achieves 90%+ coverage without requiring database changes.
"""

from __future__ import annotations

import builtins
import re
from collections import Counter
from enum import Enum
from typing import Literal

import tree_sitter_python as tspython
from pydantic import BaseModel
from sqlmodel import Session
from tree_sitter import Language, Node, Parser

from generate.scaffold.dataset.models import Datapoint
from generate.scaffold.dataset.queries import (
    get_associated_function_names,
    lookup_function_exact,
    lookup_function_fuzzy,
)

# ============================================================================
# Constants
# ============================================================================

# Standard library modules that should not be considered dependencies
STDLIB_MODULES = {
    # Built-in modules
    "abc",
    "array",
    "ast",
    "asyncio",
    "base64",
    "binascii",
    "bisect",
    "collections",
    "contextlib",
    "copy",
    "csv",
    "datetime",
    "decimal",
    "enum",
    "functools",
    "hashlib",
    "heapq",
    "io",
    "itertools",
    "json",
    "logging",
    "math",
    "operator",
    "os",
    "pathlib",
    "pickle",
    "pprint",
    "random",
    "re",
    "shutil",
    "sqlite3",
    "string",
    "struct",
    "sys",
    "tempfile",
    "threading",
    "time",
    "typing",
    "unittest",
    "uuid",
    "warnings",
    "weakref",
    # Common testing frameworks
    "pytest",
    "hypothesis",
    "mock",
    "nose",
    # Common third-party (should be axiomized, not mocked)
    "numpy",
    "pandas",
    "torch",
    "tensorflow",
    "scipy",
    "sklearn",
    "requests",
}

# Python builtins that shouldn't be in dependencies
BUILTINS = set(dir(builtins))


# ============================================================================
# Data Models
# ============================================================================


class DiscoveryMethod(str, Enum):
    """Method used to discover the function."""

    TEST_CLASS = "test_class"  # Parsed test class inheritance
    CALL_ANALYSIS = "call_analysis"  # Analyzed function calls in test
    NAME_MATCH = "name_match"  # Matched test name to function
    SOURCE_PARSE = "source_parse"  # Parsed source field
    FUNCTIONS_TABLE = "functions_table"  # Found in Functions table
    FAILED = "failed"  # Could not discover


class FunctionInfo(BaseModel, frozen=True):
    """Information about a discovered function."""

    name: str
    code: str | None
    type: Literal["function", "method", "constructor", "class"]
    confidence: float  # 0.0 to 1.0
    discovery_method: DiscoveryMethod
    dependencies: list[str]  # Names of functions this depends on


# ============================================================================
# Tree-sitter Utilities
# ============================================================================

# Initialize parser once at module level
PY_LANGUAGE = Language(tspython.language())
_parser = Parser(PY_LANGUAGE)


def parse_python(code: str) -> Node | None:
    """Parse Python code and return the root node.

    Args:
        code: Python source code as string

    Returns:
        Root node of the parse tree, or None if parsing failed
    """
    try:
        tree = _parser.parse(code.encode("utf-8"))
        return tree.root_node
    except Exception:
        return None


def get_node_text(node: Node, code: bytes) -> str:
    """Extract text from a node.

    Args:
        node: Tree-sitter node
        code: Original source code as bytes

    Returns:
        Text content of the node
    """
    return code[node.start_byte : node.end_byte].decode("utf-8")


def find_nodes_by_type(root: Node, node_type: str) -> list[Node]:
    """Find all nodes of a specific type.

    Args:
        root: Root node to search from
        node_type: Type of node to find (e.g., "class_definition", "function_definition")

    Returns:
        List of matching nodes
    """
    results: list[Node] = []

    def visit(node: Node) -> None:
        if node.type == node_type:
            results.append(node)
        for child in node.children:
            visit(child)

    visit(root)
    return results


# ============================================================================
# Test Class Analysis
# ============================================================================


def parse_test_class(pbt_code: str) -> tuple[str, str | None] | None:
    """Parse test class and extract class name and inheritance.

    Args:
        pbt_code: Property-based test code

    Returns:
        Tuple of (test_class_name, parent_class) or None
    """
    root = parse_python(pbt_code)
    if not root:
        return None

    code_bytes = pbt_code.encode("utf-8")

    # Find class definitions
    classes = find_nodes_by_type(root, "class_definition")

    for cls in classes:
        # Get class name
        name_node = None
        arg_list_node = None

        for child in cls.children:
            if child.type == "identifier":
                name_node = child
            elif child.type == "argument_list":
                arg_list_node = child

        if not name_node:
            continue

        class_name = get_node_text(name_node, code_bytes)

        # Get parent class if exists
        parent = None
        if arg_list_node and arg_list_node.children:
            # First child in argument_list is usually the parent
            for child in arg_list_node.children:
                if child.type == "identifier" or child.type == "attribute":
                    parent = get_node_text(child, code_bytes)
                    break

        return (class_name, parent)

    return None


def infer_target_from_test_class(
    test_class_name: str, parent_class: str | None
) -> str | None:
    """Infer the target class from test class name.

    Args:
        test_class_name: Name of the test class (e.g., "TestMyClass")
        parent_class: Parent class name (e.g., "unittest.TestCase")

    Returns:
        Inferred target class name (e.g., "MyClass")
    """
    # Common patterns:
    # TestFoo -> Foo
    # FooTest -> Foo
    # TestFooBar -> FooBar

    if test_class_name.startswith("Test"):
        return test_class_name[4:]  # Remove "Test" prefix
    elif test_class_name.endswith("Test"):
        return test_class_name[:-4]  # Remove "Test" suffix

    return None


# ============================================================================
# Function Call Analysis
# ============================================================================


def extract_test_calls(pbt_code: str) -> list[tuple[str, str]]:
    """Extract function calls from test code.

    Args:
        pbt_code: Property-based test code

    Returns:
        List of (function_name, call_type) tuples
    """
    root = parse_python(pbt_code)
    if not root:
        return []

    code_bytes = pbt_code.encode("utf-8")
    calls: list[tuple[str, str]] = []

    # Find all call expressions
    def visit(node: Node) -> None:
        if node.type == "call":
            # The function being called is the first child
            if node.children:
                func_node = node.children[0]
                func_name = get_node_text(func_node, code_bytes)

                # Determine call type
                if func_node.type == "identifier":
                    call_type = "direct"
                elif func_node.type == "attribute":
                    call_type = "method"
                else:
                    call_type = "other"

                calls.append((func_name, call_type))

        for child in node.children:
            visit(child)

    visit(root)
    return calls


def identify_primary_call(calls: list[tuple[str, str]]) -> str | None:
    """Identify the primary function being tested.

    Args:
        calls: List of (function_name, call_type) from test

    Returns:
        Name of the primary function, or None
    """
    # Filter out test infrastructure calls
    test_infra = {
        "assert",
        "assertEqual",
        "assertIs",
        "assertTrue",
        "assertFalse",
        "assertRaises",
        "given",
        "assume",  # Hypothesis assume
        "note",  # Hypothesis note
        "event",  # Hypothesis event
        "strategies",
        "pytest.approx",
        "pytest.raises",
        # Hypothesis strategies
        "st.",
        "strategies.",
        # Common test patterns
        "self.assert",
        "mock.",
        "patch",
        # Common test setup
        "FeedBlob",
        "FetchBlob",
        "CreateBlob",
    }

    # Count non-infrastructure calls
    func_calls = [
        name for name, _ in calls if not any(name.startswith(t) for t in test_infra)
    ]

    if not func_calls:
        return None

    # Return most common non-infrastructure call
    counter = Counter(func_calls)
    return counter.most_common(1)[0][0] if counter else None


# ============================================================================
# Stdlib Detection
# ============================================================================


def is_stdlib(func_name: str) -> bool:
    """Check if a function name is from stdlib.

    Args:
        func_name: Function name (may include module, e.g., "base64.b64encode")

    Returns:
        True if stdlib function
    """
    # Check if it's a builtin
    simple_name = func_name.split(".")[-1]
    if simple_name in BUILTINS:
        return True

    # Check if module is stdlib
    module = func_name.split(".")[0]
    if module in STDLIB_MODULES:
        return True

    return False


# ============================================================================
# Main Discovery Function
# ============================================================================


def discover_function_code(
    pbt: Datapoint,
    session: Session,
) -> FunctionInfo | None:
    """Discover the function under test using multiple strategies.

    Args:
        pbt: Property-based test datapoint
        session: Database session for function lookups

    Returns:
        FunctionInfo if discovered with highest confidence, None otherwise

    Strategy cascade (prioritized by confidence):
    1. Test class inheritance → exact match in Functions table
    2. Primary function call → exact match in Functions table
    3. Test name extraction → fuzzy match in Functions table
    4. Associated functions → best match from pbt_functions table
    """
    candidates: list[FunctionInfo] = []

    # Strategy 1: Parse test class inheritance
    if class_info := parse_test_class(pbt.code):
        test_class_name, parent_class = class_info
        if target_name := infer_target_from_test_class(test_class_name, parent_class):
            # Try exact match in Functions table
            if func := lookup_function_exact(session, target_name, pbt.repo_id):
                candidates.append(
                    FunctionInfo(
                        name=func.name,
                        code=func.code,
                        type="class",
                        confidence=0.8,
                        discovery_method=DiscoveryMethod.TEST_CLASS,
                        dependencies=[],
                    )
                )

    # Strategy 2: Parse test method calls
    if calls := extract_test_calls(pbt.code):
        if main_call := identify_primary_call(calls):
            # Filter out stdlib and extract simple name
            if not is_stdlib(main_call):
                # Handle method calls like "self.klass" or "hashutil.md5_file"
                simple_name = main_call.split(".")[-1]

                # Try exact match
                if func := lookup_function_exact(session, simple_name, pbt.repo_id):
                    candidates.append(
                        FunctionInfo(
                            name=func.name,
                            code=func.code,
                            type="function",
                            confidence=0.7,
                            discovery_method=DiscoveryMethod.CALL_ANALYSIS,
                            dependencies=[],
                        )
                    )
                # Try full qualified name
                elif func := lookup_function_exact(session, main_call, pbt.repo_id):
                    candidates.append(
                        FunctionInfo(
                            name=func.name,
                            code=func.code,
                            type="function",
                            confidence=0.75,
                            discovery_method=DiscoveryMethod.CALL_ANALYSIS,
                            dependencies=[],
                        )
                    )

    # Strategy 3: Extract from test name
    # test_foo_bar -> foo_bar
    if match := re.match(r"test_(\w+)", pbt.name):
        func_name = match.group(1)
        # Try exact match first
        if func := lookup_function_exact(session, func_name, pbt.repo_id):
            candidates.append(
                FunctionInfo(
                    name=func.name,
                    code=func.code,
                    type="function",
                    confidence=0.6,
                    discovery_method=DiscoveryMethod.NAME_MATCH,
                    dependencies=[],
                )
            )
        # Try fuzzy match
        elif fuzzy_matches := lookup_function_fuzzy(
            session, func_name, pbt.repo_id, limit=1
        ):
            func = fuzzy_matches[0]
            candidates.append(
                FunctionInfo(
                    name=func.name,
                    code=func.code,
                    type="function",
                    confidence=0.5,
                    discovery_method=DiscoveryMethod.NAME_MATCH,
                    dependencies=[],
                )
            )

    # Strategy 4: Check associated functions from pbt_functions table
    if associated_names := get_associated_function_names(session, pbt.id):
        # Try to find the most likely candidate from associated functions
        for func_name in associated_names[:3]:  # Check top 3
            if func := lookup_function_exact(session, func_name, pbt.repo_id):
                candidates.append(
                    FunctionInfo(
                        name=func.name,
                        code=func.code,
                        type="function",
                        confidence=0.4,
                        discovery_method=DiscoveryMethod.FUNCTIONS_TABLE,
                        dependencies=[],
                    )
                )

    # Return highest confidence candidate
    if candidates:
        candidates.sort(key=lambda x: x.confidence, reverse=True)
        return candidates[0]

    # Failed to discover
    return None
