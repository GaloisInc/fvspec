"""Smart function discovery using tree-sitter parsing.

This module uses tree-sitter to parse Python code and intelligently discover:
1. The function/method/class being tested
2. Its dependencies
3. Extract implementation code

Searches the datapoint's embedded dependencies instead of a database.
"""

from __future__ import annotations

import builtins
import re
from collections import Counter
from enum import Enum
from typing import Literal

import tree_sitter_python as tspython
from pydantic import BaseModel
from tree_sitter import Language, Node, Parser

from generate.scaffold.dataset.models import Datapoint, Dependency

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
    """Parse Python code and return the root node."""
    try:
        tree = _parser.parse(code.encode("utf-8"))
        return tree.root_node
    except Exception:
        return None


def get_node_text(node: Node, code: bytes) -> str:
    """Extract text from a node."""
    return code[node.start_byte : node.end_byte].decode("utf-8")


def find_nodes_by_type(root: Node, node_type: str) -> list[Node]:
    """Find all nodes of a specific type."""
    results: list[Node] = []

    def visit(node: Node) -> None:
        if node.type == node_type:
            results.append(node)
        for child in node.children:
            visit(child)

    visit(root)
    return results


# ============================================================================
# Dependency Search Helpers
# ============================================================================


def _find_dependency_by_name(deps: list[Dependency], name: str) -> Dependency | None:
    """Find a dependency by exact name match."""
    for dep in deps:
        if dep.name == name:
            return dep
        if dep.qualified_name and dep.qualified_name == name:
            return dep
    return None


def _find_dependency_fuzzy(deps: list[Dependency], name: str) -> Dependency | None:
    """Find a dependency by fuzzy name match (prefix/contains)."""
    name_lower = name.lower()
    # Try prefix match
    for dep in deps:
        if dep.name.lower().startswith(name_lower):
            return dep
    # Try contains match
    for dep in deps:
        if name_lower in dep.name.lower():
            return dep
    return None


# ============================================================================
# Test Class Analysis
# ============================================================================


def parse_test_class(pbt_code: str) -> tuple[str, str | None] | None:
    """Parse test class and extract class name and inheritance."""
    root = parse_python(pbt_code)
    if not root:
        return None

    code_bytes = pbt_code.encode("utf-8")
    classes = find_nodes_by_type(root, "class_definition")

    for cls in classes:
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

        parent = None
        if arg_list_node and arg_list_node.children:
            for child in arg_list_node.children:
                if child.type == "identifier" or child.type == "attribute":
                    parent = get_node_text(child, code_bytes)
                    break

        return (class_name, parent)

    return None


def infer_target_from_test_class(
    test_class_name: str, parent_class: str | None
) -> str | None:
    """Infer the target class from test class name."""
    if test_class_name.startswith("Test"):
        return test_class_name[4:]
    elif test_class_name.endswith("Test"):
        return test_class_name[:-4]
    return None


# ============================================================================
# Function Call Analysis
# ============================================================================


def extract_test_calls(pbt_code: str) -> list[tuple[str, str]]:
    """Extract function calls from test code."""
    root = parse_python(pbt_code)
    if not root:
        return []

    code_bytes = pbt_code.encode("utf-8")
    calls: list[tuple[str, str]] = []

    def visit(node: Node) -> None:
        if node.type == "call":
            if node.children:
                func_node = node.children[0]
                func_name = get_node_text(func_node, code_bytes)

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
    """Identify the primary function being tested."""
    test_infra = {
        "assert",
        "assertEqual",
        "assertIs",
        "assertTrue",
        "assertFalse",
        "assertRaises",
        "given",
        "assume",
        "note",
        "event",
        "strategies",
        "pytest.approx",
        "pytest.raises",
        "st.",
        "strategies.",
        "self.assert",
        "mock.",
        "patch",
        "FeedBlob",
        "FetchBlob",
        "CreateBlob",
    }

    func_calls = [
        name for name, _ in calls if not any(name.startswith(t) for t in test_infra)
    ]

    if not func_calls:
        return None

    counter = Counter(func_calls)
    return counter.most_common(1)[0][0] if counter else None


# ============================================================================
# Stdlib Detection
# ============================================================================


def is_stdlib(func_name: str) -> bool:
    """Check if a function name is from stdlib."""
    simple_name = func_name.split(".")[-1]
    if simple_name in BUILTINS:
        return True

    module = func_name.split(".")[0]
    if module in STDLIB_MODULES:
        return True

    return False


# ============================================================================
# Main Discovery Function
# ============================================================================


def discover_function_code(
    pbt: Datapoint,
) -> FunctionInfo | None:
    """Discover the function under test using multiple strategies.

    Searches the datapoint's embedded dependencies instead of a database.

    Args:
        pbt: Property-based test datapoint

    Returns:
        FunctionInfo if discovered with highest confidence, None otherwise

    Strategy cascade (prioritized by confidence):
    1. Test class inheritance → match in dependencies
    2. Primary function call → match in dependencies
    3. Test name extraction → match in dependencies
    """
    candidates: list[FunctionInfo] = []
    deps = pbt.dependencies

    # Strategy 1: Parse test class inheritance
    if class_info := parse_test_class(pbt.code):
        test_class_name, parent_class = class_info
        if target_name := infer_target_from_test_class(test_class_name, parent_class):
            if dep := _find_dependency_by_name(deps, target_name):
                candidates.append(
                    FunctionInfo(
                        name=dep.name,
                        code=dep.code,
                        type="class",
                        confidence=0.8,
                        discovery_method=DiscoveryMethod.TEST_CLASS,
                        dependencies=[],
                    )
                )

    # Strategy 2: Parse test method calls
    if calls := extract_test_calls(pbt.code):
        if main_call := identify_primary_call(calls):
            if not is_stdlib(main_call):
                simple_name = main_call.split(".")[-1]

                # Try exact match by simple name
                if dep := _find_dependency_by_name(deps, simple_name):
                    candidates.append(
                        FunctionInfo(
                            name=dep.name,
                            code=dep.code,
                            type="function",
                            confidence=0.7,
                            discovery_method=DiscoveryMethod.CALL_ANALYSIS,
                            dependencies=[],
                        )
                    )
                # Try full qualified name
                elif dep := _find_dependency_by_name(deps, main_call):
                    candidates.append(
                        FunctionInfo(
                            name=dep.name,
                            code=dep.code,
                            type="function",
                            confidence=0.75,
                            discovery_method=DiscoveryMethod.CALL_ANALYSIS,
                            dependencies=[],
                        )
                    )

    # Strategy 3: Extract from test name
    if match := re.match(r"test_(\w+)", pbt.name):
        func_name = match.group(1)
        # Try exact match first
        if dep := _find_dependency_by_name(deps, func_name):
            candidates.append(
                FunctionInfo(
                    name=dep.name,
                    code=dep.code,
                    type="function",
                    confidence=0.6,
                    discovery_method=DiscoveryMethod.NAME_MATCH,
                    dependencies=[],
                )
            )
        # Try fuzzy match
        elif dep := _find_dependency_fuzzy(deps, func_name):
            candidates.append(
                FunctionInfo(
                    name=dep.name,
                    code=dep.code,
                    type="function",
                    confidence=0.5,
                    discovery_method=DiscoveryMethod.NAME_MATCH,
                    dependencies=[],
                )
            )

    # Return highest confidence candidate
    if candidates:
        candidates.sort(key=lambda x: x.confidence, reverse=True)
        return candidates[0]

    return None
