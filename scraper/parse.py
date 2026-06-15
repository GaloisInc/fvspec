import ast
import os

import astor
from typing import Dict, List, Set, Tuple


def get_hyp_imports(a: ast.Module) -> str:
    w = ast.Module([], type_ignores=[])
    for node in a.body:
        if isinstance(node, ast.ImportFrom) and node.module == "hypothesis":
            w.body.append(node)
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "hypothesis":
                    w.body.append(node)
                    break
    unparsed = ast.unparse(w)
    if unparsed != "":
        return unparsed + "\n"
    return ""


def get_full_function_name(node: ast.AST) -> str:
    """Recursively retrieve the full function name from an AST node."""
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        return get_full_function_name(node.value) + "." + node.attr
    return ""


def unparse_decorator(decorator: ast.AST) -> str:
    """Unparse a decorator to a string."""
    if isinstance(decorator, ast.Call):
        func_name = get_full_function_name(decorator.func)
        args = [ast.unparse(arg) for arg in decorator.args]
        kwargs = [f"{kw.arg}={ast.unparse(kw.value)}" for kw in decorator.keywords]
        all_args = ", ".join(args + kwargs)
        return f"{func_name}({all_args})"
    return ""


def find_pbt_functions(tree: ast.Module) -> List[Tuple[str, str]]:
    """Extract PBT functions from code, returning a list of (name, code) tuples."""
    functions = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            decorator_code = ""
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call):
                    full_func_name = get_full_function_name(decorator.func)
                    if "given" in full_func_name.split("."):
                        decorator_code = "@" + unparse_decorator(decorator)
            if decorator_code:
                function_code = decorator_code + "\n" + astor.to_source(node)
                functions.append((node.name, function_code))
    return functions


def find_pbt_function_names(code: str) -> List[str]:
    """Extract the PBT function names from a given block of code"""
    tree = ast.parse(code)
    functions = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for decorator in node.decorator_list:
                try:
                    # notably, our heuristic for determining if a function definition is
                    # a hypothesis function definition is if it has the decorator "given"
                    if (
                        isinstance(decorator, ast.Call)
                        and isinstance(decorator.func, ast.Name)
                        and decorator.func.id == "given"
                    ):
                        functions.append(node.name)
                        break
                except Exception:
                    # this will be hit if we have no decorators
                    continue
    return functions


# I imagine there is some ub here, if there are multiple functions with the same name
# but the code this replaces did the same thing so.
def get_all_functions(tree: ast.Module):
    funs: Dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            funs[node.name] = ast.unparse(node)
    return funs


def get_called_function_names(func_name: str, tree: ast.Module) -> Set[str]:
    """Find all function names called within the given function's body."""
    called_functions = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            for sub_node in ast.walk(node):
                if isinstance(sub_node, ast.Call) and isinstance(
                    sub_node.func, ast.Name
                ):
                    called_functions.add(sub_node.func.id)
    return called_functions


def extract_pbts_with_context(
    directory: str,
) -> List[Tuple[str, List[str], str, List[str], str]]:
    """Extracts all PBTs from a project, then acquires the minimum amount of context for the PBT."""
    pbts = set()
    pbt_deps: Dict[str, Set[str]] = {}
    functions: Dict[str, str] = {}  # track function names to function definitions
    function_deps: Dict[
        str, Set[str]
    ] = {}  # track function names to called functions called within the function
    function_files: Dict[str, str] = {}  # track function names to file paths
    file_imports: Dict[str, str] = {}

    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    try:
                        content = f.read()
                        clean_path = file_path.replace(directory, "")
                        tree = ast.parse(content)

                        funs = get_all_functions(tree)
                        func_names = funs.keys()
                        file_imports[clean_path] = get_hyp_imports(tree)
                        pbts.update(find_pbt_functions(tree))
                        for func_name in func_names:
                            try:
                                # This is very inefficient since we walk the AST a ton,
                                # but since the AST parser in python is very performant
                                # (and because this seems to run decently fast for large repos such as numpy)
                                # it is fine for now
                                called_funcs = get_called_function_names(
                                    func_name, tree
                                )
                                functions[func_name] = funs[func_name]
                                function_deps[func_name] = called_funcs
                                function_files[func_name] = clean_path
                            except Exception as e:
                                print(
                                    f"While parsing {func_name} in {clean_path}, got {e}"
                                )
                                continue
                    except Exception as e:
                        print(f"While parsing {file_path}, got {e}")
                        continue

    for name, pbt in pbts:
        pbt_deps[name] = set()
    # Now, we want to get _all_ dependent functions such that we can add them as context
    prog_defs = set(functions.keys()) - set(pbts)
    for name, pbt in pbts:
        try:
            deps = set()
            # todo: reparsing is slow
            new_deps = set(get_called_function_names(name, ast.parse(pbt)))
            deps = new_deps.union(deps)
            to_add = new_deps.copy()

            while to_add != set():  # while there are things to add...
                proc = set()
                for func in to_add:
                    if func in function_deps:
                        proc = proc.union(set(function_deps[func]))

                to_add = proc - deps
                deps = deps.union(proc)

            deps = deps.intersection(prog_defs)
            pbt_deps[name] = deps
        except Exception as e:
            print(f"Error unk_1: {e} for {name}")

    # create the object
    full_pbt_deps = []
    for pbts, deps in pbt_deps.items():
        try:
            full_pbt_deps.append(
                (
                    pbts,
                    list(deps),
                    file_imports[function_files[pbts]] + functions[pbts],
                    [functions[dep] for dep in deps],
                    function_files[pbts],
                )
            )
        except Exception as e:
            print(f"Error adding {pbts} to output: {e}")

    return full_pbt_deps


def generate_dataset_from_project(project_dir):
    pbts_with_context = extract_pbts_with_context(project_dir)
    dataset = []

    for pbt_name, dep_names, pbt, deps, file in pbts_with_context:
        try:
            dataset.append(
                [
                    pbt_name,
                    pbt,
                    list(dep_names) if isinstance(dep_names, set) else dep_names,
                    [list(dep) if isinstance(dep, set) else dep for dep in deps],
                    file,
                ]
            )
        except Exception as e:
            print(f"Error mapping in generate_dataset_from_project for {pbt_name}: {e}")

    return dataset
