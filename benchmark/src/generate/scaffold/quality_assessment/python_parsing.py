"""Python AST-based parsing utilities for quality assessment."""

import ast


def extract_python_parameters(code: str) -> list[str]:
    """Extract parameter names from Python function definition."""
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Get parameter names (excluding 'self')
                params = [arg.arg for arg in node.args.args if arg.arg != "self"]
                return params
    except SyntaxError:
        pass
    return []


def extract_python_types(code: str) -> dict[str, str]:
    """Extract parameter types from Python function annotations."""
    types = {}
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for arg in node.args.args:
                    if arg.arg != "self" and arg.annotation:
                        # Get type annotation as string
                        if isinstance(arg.annotation, ast.Name):
                            types[arg.arg] = arg.annotation.id
                        elif isinstance(arg.annotation, ast.Subscript):
                            # Handle list[int], etc.
                            if isinstance(arg.annotation.value, ast.Name):
                                types[arg.arg] = arg.annotation.value.id
    except SyntaxError:
        pass
    return types


def count_python_assertions(code: str) -> int:
    """Count assert statements in Python code."""
    try:
        tree = ast.parse(code)
        count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Assert):
                count += 1
        return count
    except SyntaxError:
        pass
    return 0


def extract_dependency_names(deps: list[str]) -> list[str]:
    """Extract function/class names from dependency definitions."""
    names = []
    for dep in deps:
        try:
            tree = ast.parse(dep)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    names.append(node.name)
        except SyntaxError:
            pass
    return names
