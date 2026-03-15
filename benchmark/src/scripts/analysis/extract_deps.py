r"""Extract depth-bounded transitive dependencies for PBTs from a cloned repo.

Given a PBT and its source repo, this script resolves all code reachable from
the PBT up to a configurable call depth (default 2). It uses tree-sitter for
fast AST parsing and a lightweight import resolver to map dotted names to files
within the repo.

Architecture:
    RepoIndex    - Parses all .py files, builds {qualified_name: FuncDef} index
    ImportResolver - Resolves import aliases to repo-relative module paths
    DepExtractor   - BFS over the call graph, bounded by depth

Usage:
    uv run extract-deps /tmp/pytorch-test \
        --pbt-file caffe2/python/operator_test/segment_ops_test.py \
        --pbt-name test_sparse_lengths_mean \
        --depth 2
"""

from __future__ import annotations

import builtins
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import tree_sitter_python as tspython
import typer
from rich.console import Console
from rich.tree import Tree
from tree_sitter import Language, Node, Parser

# Python builtin names — derived from the builtins module, not hardcoded
PYTHON_BUILTINS = frozenset(dir(builtins))

app = typer.Typer(help="Extract depth-bounded dependencies for a PBT.")
console = Console()

PY_LANGUAGE = Language(tspython.language())
_parser = Parser(PY_LANGUAGE)


# No hardcoded external module list. The ImportResolver naturally returns None
# for modules not found in the repo index. This avoids false negatives when a
# repo has a package matching a common name (e.g. a `json` wrapper).

# ============================================================================
# Data models
# ============================================================================


@dataclass(frozen=True)
class FuncDef:
    """A parsed function/method/class definition."""

    name: str
    qualified_name: str  # module.ClassName.method or module.func
    code: str
    file_path: str  # repo-relative
    start_line: int
    end_line: int
    calls: list[str]  # raw call expressions found in the body
    kind: str  # "function", "method", "class"


@dataclass
class ImportEntry:
    """A resolved import statement."""

    alias: str  # name used in code (e.g. "hu", "core", "np")
    module_path: str  # dotted module (e.g. "caffe2.python.hypothesis_test_util")
    imported_name: str | None  # specific name imported, or None for module import


@dataclass
class RepoIndex:
    """Index of all Python definitions in a repository."""

    repo_root: Path
    # module_path -> {name -> FuncDef}  (module_path is dotted, e.g. "caffe2.python.core")
    modules: dict[str, dict[str, FuncDef]] = field(default_factory=dict)
    # Flat lookup: qualified_name -> FuncDef
    all_defs: dict[str, FuncDef] = field(default_factory=dict)
    # file_path (repo-relative) -> module_path
    file_to_module: dict[str, str] = field(default_factory=dict)
    # module_path -> file_path
    module_to_file: dict[str, str] = field(default_factory=dict)


# ============================================================================
# Tree-sitter helpers
# ============================================================================


def _parse(code: str) -> Node | None:
    try:
        return _parser.parse(code.encode()).root_node
    except Exception:
        return None


def _text(node: Node, src: bytes) -> str:
    return src[node.start_byte : node.end_byte].decode()


def _find(root: Node, node_type: str) -> list[Node]:
    results: list[Node] = []

    def visit(n: Node) -> None:
        if n.type == node_type:
            results.append(n)
        for c in n.children:
            visit(c)

    visit(root)
    return results


def _root_name(node: Node, src: bytes) -> str | None:
    """Extract the root name from a call target AST node.

    Walks through subscripts and nested calls to find the base identifier
    or dotted attribute. E.g.:
        baz[0]    -> baz
        qux(a=1)  -> qux
        obj.method -> obj.method
        d['key']   -> d
    """
    while node.type in ("subscript", "call"):
        # For subscript: value[key] — take value
        # For call: func(args) — take func
        if node.children:
            node = node.children[0]
        else:
            return None
    if node.type == "identifier":
        return _text(node, src)
    if node.type == "attribute":
        return _text(node, src)
    return None


def _extract_calls(body_node: Node, src: bytes) -> list[str]:
    """Extract all call target expressions from an AST subtree.

    Returns clean names (identifiers or dotted attributes), not raw text
    that might contain subscripts or nested call syntax.
    """
    calls: list[str] = []
    for call_node in _find(body_node, "call"):
        if call_node.children:
            name = _root_name(call_node.children[0], src)
            if name:
                calls.append(name)
    return calls


def _find_function_def(node: Node) -> Node | None:
    """Find the function_definition node, searching through wrappers.

    Handles: module > decorated_definition > function_definition
    or just: function_definition directly.
    """
    if node.type == "function_definition":
        return node
    for fdef in _find(node, "function_definition"):
        return fdef  # return the first one found
    return None


def _extract_parameter_names(func_node: Node, src: bytes) -> set[str]:
    """Extract parameter names from a function definition node.

    Returns all names bound as parameters (including self, cls, *args, **kwargs).
    """
    names: set[str] = set()
    fdef = _find_function_def(func_node)
    if not fdef:
        return names
    params_node = fdef.child_by_field_name("parameters")
    if not params_node:
        return names

    for child in params_node.children:
        if child.type == "identifier":
            names.add(_text(child, src))
        elif child.type in (
            "default_parameter",
            "typed_parameter",
            "typed_default_parameter",
        ):
            # The parameter name is the first identifier child
            # (child_by_field_name("name") doesn't work for all param types)
            for gc in child.children:
                if gc.type == "identifier":
                    names.add(_text(gc, src))
                    break
        elif child.type in ("list_splat_pattern", "dictionary_splat_pattern"):
            for gc in child.children:
                if gc.type == "identifier":
                    names.add(_text(gc, src))
                    break
    return names


def _extract_local_vars(func_node: Node, src: bytes) -> set[str]:
    """Extract locally assigned variable names from a function body.

    This catches loop vars, with-statement vars, assignment targets, etc.
    """
    names: set[str] = set()
    fdef = _find_function_def(func_node)
    body = fdef.child_by_field_name("body") if fdef else None
    if not body:
        return names

    for assign in _find(body, "assignment"):
        left = assign.child_by_field_name("left")
        if not left:
            continue
        if left.type == "identifier":
            names.add(_text(left, src))
        elif left.type == "pattern_list":
            # Tuple unpacking: a, b = expr
            for child in left.children:
                if child.type == "identifier":
                    names.add(_text(child, src))

    for for_node in _find(body, "for_statement"):
        left = for_node.child_by_field_name("left")
        if left and left.type == "identifier":
            names.add(_text(left, src))

    for with_clause in _find(body, "with_clause"):
        for child in with_clause.children:
            if child.type == "as_pattern":
                alias = child.child_by_field_name("alias")
                if alias and alias.type == "identifier":
                    names.add(_text(alias, src))

    return names


def _extract_references(body_node: Node, src: bytes) -> list[str]:
    """Extract dotted attribute accesses that aren't call targets.

    Catches things like `hu.gcs` (a module-level dict used as **hu.gcs).
    """
    refs: list[str] = []
    for attr_node in _find(body_node, "attribute"):
        # Skip if this attribute is the target of a call (already captured)
        if attr_node.parent and attr_node.parent.type == "call":
            continue
        refs.append(_text(attr_node, src))
    return refs


def _extract_type_annotations(func_node: Node, src: bytes) -> list[str]:
    """Extract type names from function parameter and return annotations.

    Catches things like `circ: Circuit` or `-> bool`.
    """
    types: list[str] = []
    fdef = _find_function_def(func_node)
    if not fdef:
        return types

    # Check parameter annotations
    params = fdef.child_by_field_name("parameters")
    if params:
        for param in params.children:
            if param.type in ("typed_parameter", "typed_default_parameter"):
                type_node = param.child_by_field_name("type")
                if type_node:
                    types.append(_text(type_node, src))

    # Check return type
    return_type = fdef.child_by_field_name("return_type")
    if return_type:
        types.append(_text(return_type, src))

    return types


def _extract_bare_identifiers(body_node: Node, src: bytes) -> list[str]:
    """Extract bare identifier references used as values (not call targets).

    Catches things like `storage_factories` passed as an argument, or
    `test_file_name` used in an expression. These are module-level variables
    or constants that the BFS should try to resolve.
    """
    refs: list[str] = []
    for id_node in _find(body_node, "identifier"):
        name = _text(id_node, src)
        parent = id_node.parent
        if not parent:
            continue
        # Skip if this identifier is:
        # - a function/class name being defined
        if parent.type in ("function_definition", "class_definition"):
            if id_node == parent.child_by_field_name("name"):
                continue
        # - a parameter name
        if parent.type in (
            "parameters",
            "default_parameter",
            "typed_parameter",
            "typed_default_parameter",
        ):
            continue
        # - the function part of a call (already captured by _extract_calls)
        if parent.type == "call" and id_node == parent.children[0]:
            continue
        # - an import name
        if parent.type in (
            "import_statement",
            "import_from_statement",
            "aliased_import",
            "dotted_name",
        ):
            continue
        # - part of a dotted attribute (handled by _extract_references)
        if parent.type == "attribute":
            continue
        # - an assignment target
        if parent.type == "assignment" and id_node == parent.child_by_field_name(
            "left"
        ):
            continue
        # - a keyword argument name (e.g. deadline=None)
        if parent.type == "keyword_argument":
            kw_name = parent.child_by_field_name("name")
            if kw_name and id_node == kw_name:
                continue
        # - a decorator name
        if parent.type == "decorator":
            continue

        refs.append(name)
    return refs


def _extract_decorator_names(func_node: Node, src: bytes) -> set[str]:
    """Extract decorator names from a function definition.

    Returns the root identifier of each decorator (e.g. `given` from `@given(...)`,
    `settings` from `@settings(deadline=None)`). These are framework names that
    should be excluded from global search to avoid false positives like matching
    `sympy.stats.rv.given` when the decorator is `hypothesis.given`.
    """
    names: set[str] = set()
    for dec_node in _find(func_node, "decorator"):
        for child in dec_node.children:
            if child.type == "identifier":
                names.add(_text(child, src))
            elif child.type == "call" and child.children:
                root = _root_name(child.children[0], src)
                if root:
                    # Take just the first part (e.g. "given" from "given")
                    names.add(root.split(".")[0])
            elif child.type == "attribute":
                # e.g. @pytest.mark.parametrize — take "pytest"
                parts = _text(child, src).split(".")
                if parts:
                    names.add(parts[0])
    return names


# ============================================================================
# Index building
# ============================================================================


def _file_to_module_path(file_path: str) -> str:
    """Convert repo-relative file path to dotted module path.

    caffe2/python/core.py         -> caffe2.python.core
    caffe2/python/__init__.py     -> caffe2.python
    src/mypackage/utils.py        -> src.mypackage.utils
    """
    p = file_path.removesuffix(".py")
    if p.endswith("/__init__"):
        p = p.removesuffix("/__init__")
    return p.replace("/", ".")


def _index_file(repo_root: Path, rel_path: str) -> dict[str, FuncDef]:
    """Parse a single .py file and extract all definitions."""
    full_path = repo_root / rel_path
    try:
        src_text = full_path.read_text(errors="replace")
    except (OSError, UnicodeDecodeError):
        return {}

    root = _parse(src_text)
    if not root:
        return {}

    src = src_text.encode()
    module = _file_to_module_path(rel_path)
    defs: dict[str, FuncDef] = {}

    def process_node(
        node: Node,
        parent_name: str | None = None,
        decorated_wrapper: Node | None = None,
    ) -> None:
        # Unwrap decorated definitions — but preserve the full decorated node
        # so we capture decorator calls (e.g. @given(inputs=hu.strategy()))
        if node.type == "decorated_definition":
            for child in node.children:
                if child.type in ("function_definition", "class_definition"):
                    # Pass the outer decorated_definition as wrapper so we
                    # can capture the full text and decorator calls
                    process_node(child, parent_name, decorated_wrapper=node)
            return

        if node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            if not name_node:
                return
            name = _text(name_node, src)
            qname = (
                f"{module}.{parent_name}.{name}" if parent_name else f"{module}.{name}"
            )
            # Include calls from both the function body AND any decorators
            outer = decorated_wrapper if decorated_wrapper else node
            calls = _extract_calls(outer, src)
            defs[name if not parent_name else f"{parent_name}.{name}"] = FuncDef(
                name=name,
                qualified_name=qname,
                code=_text(outer, src),  # include decorator in code
                file_path=rel_path,
                start_line=outer.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                calls=calls,
                kind="method" if parent_name else "function",
            )
            # Don't recurse into nested functions for top-level index
            # (they're captured in the parent's code)

        elif node.type == "class_definition":
            name_node = node.child_by_field_name("name")
            if not name_node:
                return
            class_name = _text(name_node, src)
            # Index the class itself
            calls = _extract_calls(node, src)
            defs[class_name] = FuncDef(
                name=class_name,
                qualified_name=f"{module}.{class_name}",
                code=_text(node, src),
                file_path=rel_path,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                calls=calls,
                kind="class",
            )
            # Index methods and class-level assignments
            body = node.child_by_field_name("body")
            if body:
                for child in body.children:
                    process_node(child, parent_name=class_name)
                    # Also capture class-level assignments (e.g. klass = ZoneInfo)
                    if child.type == "expression_statement":
                        for assign_child in child.children:
                            if assign_child.type == "assignment":
                                left = assign_child.child_by_field_name("left")
                                if left and left.type == "identifier":
                                    attr_name = _text(left, src)
                                    key = f"{class_name}.{attr_name}"
                                    defs[key] = FuncDef(
                                        name=attr_name,
                                        qualified_name=f"{module}.{key}",
                                        code=_text(child, src),
                                        file_path=rel_path,
                                        start_line=child.start_point[0] + 1,
                                        end_line=child.end_point[0] + 1,
                                        calls=_extract_calls(child, src),
                                        kind="assignment",
                                    )

        # Also capture module-level assignments that look like constants/dicts
        # e.g. `gcs = dict(...)` which is a common pattern
        elif node.type == "expression_statement" and parent_name is None:
            # Check for assignment
            for child in node.children:
                if child.type == "assignment":
                    left = child.child_by_field_name("left")
                    if left and left.type == "identifier":
                        name = _text(left, src)
                        defs[name] = FuncDef(
                            name=name,
                            qualified_name=f"{module}.{name}",
                            code=_text(node, src),
                            file_path=rel_path,
                            start_line=node.start_point[0] + 1,
                            end_line=node.end_point[0] + 1,
                            calls=_extract_calls(node, src),
                            kind="assignment",
                        )

    for child in root.children:
        process_node(child)

    return defs


def build_repo_index(repo_root: Path) -> RepoIndex:
    """Walk all .py files and build the complete index."""
    index = RepoIndex(repo_root=repo_root)
    py_files = sorted(repo_root.rglob("*.py"))

    for py_file in py_files:
        rel = str(py_file.relative_to(repo_root))
        # Skip venvs, build dirs, etc.
        if any(
            part.startswith(".")
            or part
            in ("venv", "env", "build", "dist", "node_modules", "__pycache__", ".git")
            for part in rel.split("/")
        ):
            continue

        module = _file_to_module_path(rel)
        defs = _index_file(repo_root, rel)
        if defs:
            index.modules[module] = defs
            index.file_to_module[rel] = module
            index.module_to_file[module] = rel
            for local_name, funcdef in defs.items():
                index.all_defs[funcdef.qualified_name] = funcdef

    return index


# ============================================================================
# Import resolution
# ============================================================================


def _resolve_relative_import(
    rel_text: str, source_module: str | None
) -> str | None:
    """Resolve a relative import like '..base' to an absolute module path.

    Args:
        rel_text: The relative import text (e.g. '..', '..base', '.')
        source_module: The dotted module path of the file containing the import
                       (e.g. 'src.nextline_rdb.models.tests.test_repr_val')
    Returns:
        Absolute dotted module path, or None if unresolvable.
    """
    if not source_module:
        return None

    # Count leading dots
    dots = 0
    for ch in rel_text:
        if ch == ".":
            dots += 1
        else:
            break
    suffix = rel_text[dots:]  # e.g. 'base' from '..base', '' from '..'

    # Go up `dots` levels from the source module's package
    parts = source_module.split(".")
    # The source file itself is at the last part; going up 1 = its package
    if dots > len(parts):
        return None
    base_parts = parts[: len(parts) - dots]

    if suffix:
        return ".".join(base_parts + [suffix]) if base_parts else suffix
    return ".".join(base_parts) if base_parts else None


def parse_imports(code: str, source_module: str | None = None) -> list[ImportEntry]:
    """Parse import statements from Python code.

    Args:
        code: Python source code.
        source_module: Optional dotted module path for resolving relative imports.
    """
    root = _parse(code)
    if not root:
        return []

    src = code.encode()
    imports: list[ImportEntry] = []

    for node in root.children:
        if node.type == "import_statement":
            # import caffe2.python.core
            # import numpy as np
            for child in node.children:
                if child.type == "dotted_name":
                    module_path = _text(child, src)
                    alias = module_path.split(".")[-1]
                    imports.append(
                        ImportEntry(
                            alias=alias, module_path=module_path, imported_name=None
                        )
                    )
                elif child.type == "aliased_import":
                    name_node = child.child_by_field_name("name")
                    alias_node = child.child_by_field_name("alias")
                    if name_node:
                        module_path = _text(name_node, src)
                        alias = (
                            _text(alias_node, src)
                            if alias_node
                            else module_path.split(".")[-1]
                        )
                        imports.append(
                            ImportEntry(
                                alias=alias, module_path=module_path, imported_name=None
                            )
                        )

        elif node.type == "import_from_statement":
            # from caffe2.python import core, workspace
            # from .. import repr_val  (relative)
            module_node = node.child_by_field_name("module_name")
            if not module_node:
                continue

            # Handle relative imports (module_node.type == "relative_import")
            raw_text = _text(module_node, src)
            if module_node.type == "relative_import":
                module_path = _resolve_relative_import(raw_text, source_module)
                if not module_path:
                    continue
            else:
                module_path = raw_text

            for child in node.children:
                if child.type == "dotted_name" and child != module_node:
                    name = _text(child, src)
                    imports.append(
                        ImportEntry(
                            alias=name, module_path=module_path, imported_name=name
                        )
                    )
                elif child.type == "aliased_import":
                    name_node = child.child_by_field_name("name")
                    alias_node = child.child_by_field_name("alias")
                    if name_node:
                        name = _text(name_node, src)
                        alias = _text(alias_node, src) if alias_node else name
                        imports.append(
                            ImportEntry(
                                alias=alias, module_path=module_path, imported_name=name
                            )
                        )

    return imports


def _resolve_module(module_path: str, index: RepoIndex) -> str | None:
    """Try to find a module in the repo index, handling package vs module ambiguity."""
    if module_path in index.modules:
        return module_path

    # Try as a package (module/__init__.py)
    for mod in index.modules:
        if mod == module_path or mod.startswith(module_path + "."):
            return mod

    # Try partial suffix matching (handles cases where repo root isn't the package root)
    for mod in index.modules:
        if mod.endswith(module_path) or mod.endswith("." + module_path):
            return mod

    # Try suffix-based package matching: if module_path is "X.Y" and the index
    # has "prefix.X.Y.submod", match it. This handles src-layout repos where
    # `import X.Y` maps to `client/X/X/Y/_submod.py` indexed as `client.X.X.Y._submod`.
    suffix = "." + module_path + "."
    for mod in index.modules:
        if suffix in mod:
            return mod

    return None


class ImportResolver:
    """Resolves dotted names to FuncDefs using import context."""

    def __init__(self, imports: list[ImportEntry], index: RepoIndex) -> None:
        """Build resolver from import entries and repo index."""
        self.imports = imports
        self.index = index
        # alias -> (resolved_module, imported_name_or_none)
        self._cache: dict[str, tuple[str | None, str | None]] = {}
        # Track unresolvable imports so we can report them
        self.unresolvable: list[ImportEntry] = []
        for imp in imports:
            resolved_mod = _resolve_module(imp.module_path, index)
            if imp.imported_name:
                # `from X import Y` — alias Y might be a submodule or a name in X
                # First check if it's a submodule
                sub_mod = _resolve_module(
                    f"{imp.module_path}.{imp.imported_name}", index
                )
                if sub_mod:
                    self._cache[imp.alias] = (sub_mod, None)
                elif resolved_mod:
                    self._cache[imp.alias] = (resolved_mod, imp.imported_name)
                else:
                    self.unresolvable.append(imp)
            else:
                # `import X` or `import X as Y`
                if resolved_mod:
                    self._cache[imp.alias] = (resolved_mod, None)
                else:
                    self.unresolvable.append(imp)

    def resolve(self, dotted_name: str) -> FuncDef | None:
        """Resolve a dotted call expression to a FuncDef.

        Examples:
            "core.CreateOperator" → look up alias "core" → module caffe2.python.core
                                    → look up "CreateOperator" in that module
            "hu.sparse_lengths_tensor" → alias "hu" → caffe2.python.hypothesis_test_util
                                        → "sparse_lengths_tensor"
            "np.zeros" → alias "np" → external (numpy) → None
            "self.assertReferenceChecks" → needs class context (handled separately)
        """
        parts = dotted_name.split(".")

        # Direct name (no dots) — might be a from-import
        if len(parts) == 1:
            name = parts[0]
            if name in self._cache:
                mod_path, imported_name = self._cache[name]
                if mod_path and imported_name:
                    # `from X import Y` — Y is a name in module X
                    mod_defs = self.index.modules.get(mod_path, {})
                    return mod_defs.get(imported_name)
                elif mod_path and not imported_name:
                    # `import X as name` — name IS the module, not useful alone
                    return None
            # Try unresolvable imports — `from X import Y` where X wasn't found
            for imp in self.unresolvable:
                if imp.alias == name and imp.imported_name:
                    target_mod = imp.module_path
                    # Search repo modules matching the original module path
                    # Use both prefix and suffix matching (handles src-layout repos
                    # where e.g. `from pkg._utils import f` maps to `src.pkg._utils`)
                    for mod_path, mod_defs in self.index.modules.items():
                        if (
                            mod_path == target_mod
                            or mod_path.startswith(target_mod + ".")
                            or mod_path.endswith(target_mod)
                            or mod_path.endswith("." + target_mod)
                        ):
                            if imp.imported_name in mod_defs:
                                return mod_defs[imp.imported_name]
                    # Also try as a submodule
                    sub = f"{target_mod}.{imp.imported_name}"
                    for mod_path, mod_defs in self.index.modules.items():
                        if (
                            mod_path == sub
                            or mod_path.startswith(sub + ".")
                            or mod_path.endswith(sub)
                            or mod_path.endswith("." + sub)
                        ):
                            if mod_defs:
                                return next(iter(mod_defs.values()))
            return None

        # Dotted name — first part is the alias
        alias = parts[0]
        rest = parts[1:]

        if alias == "self":
            # Can't resolve without class context — return None
            # Caller must handle self-resolution separately
            return None

        if alias in self._cache:
            mod_path, imported_name = self._cache[alias]
            if not mod_path:
                return None

            if imported_name:
                # alias is a name in the module. rest is attributes on that name.
                # e.g. `from X import Cls` then `Cls.method`
                # Look for Cls.method in module
                mod_defs = self.index.modules.get(mod_path, {})
                lookup_name = ".".join([imported_name] + list(rest))
                if lookup_name in mod_defs:
                    return mod_defs[lookup_name]
                # Try just the last part as a method
                if len(rest) == 1 and f"{imported_name}.{rest[0]}" in mod_defs:
                    return mod_defs[f"{imported_name}.{rest[0]}"]
                return None
            else:
                # alias is the module itself
                # e.g. `import caffe2.python.core as core` then `core.CreateOperator`
                mod_defs = self.index.modules.get(mod_path, {})
                # Try the full rest as a name
                lookup = ".".join(rest)
                if lookup in mod_defs:
                    return mod_defs[lookup]
                # Try just the last element
                if rest[-1] in mod_defs:
                    return mod_defs[rest[-1]]
                return None

        # Try matching progressively longer prefixes of the dotted name
        # against module paths in the index. Handles `import X.Y` where
        # the call site uses the full path `X.Y.Z` (Python makes the full
        # dotted path accessible via the root name after `import X.Y`).
        # Search ALL matching modules (not just the first) because the target
        # name may be in a sibling submodule (e.g. `X.Y._git.Git` when
        # `_resolve_module("X.Y")` first finds `X.Y._code`).
        for i in range(len(parts) - 1, 0, -1):
            prefix = ".".join(parts[:i])
            remaining = parts[i:]
            lookup = ".".join(remaining)
            last = remaining[-1]
            for mod_path, mod_defs in self.index.modules.items():
                if not (
                    mod_path == prefix
                    or mod_path.startswith(prefix + ".")
                    or mod_path.endswith(prefix)
                    or mod_path.endswith("." + prefix)
                    or ("." + prefix + ".") in mod_path
                ):
                    continue
                if lookup in mod_defs:
                    return mod_defs[lookup]
                if last in mod_defs:
                    return mod_defs[last]

        # Last resort: the alias might be an unresolved import that maps to a
        # top-level package in the repo. e.g. `import aaanalysis as aa` where
        # the repo has aaanalysis/__init__.py. Try matching the *original*
        # module path from the import against repo modules.
        for imp in self.unresolvable:
            if imp.alias == alias:
                # Try the original module path as a prefix search
                target_mod = imp.module_path
                for mod_path, mod_defs in self.index.modules.items():
                    if mod_path == target_mod or mod_path.startswith(target_mod + "."):
                        # Found the package — look for the attr in it
                        lookup = ".".join(rest)
                        if lookup in mod_defs:
                            return mod_defs[lookup]
                        if rest[-1] in mod_defs:
                            return mod_defs[rest[-1]]
                # Also try if imported_name is set (from X import Y as alias)
                if imp.imported_name:
                    target = f"{imp.module_path}.{imp.imported_name}"
                    for mod_path, mod_defs in self.index.modules.items():
                        if mod_path == target or mod_path.startswith(target + "."):
                            lookup = ".".join(rest)
                            if lookup in mod_defs:
                                return mod_defs[lookup]
                            if rest[-1] in mod_defs:
                                return mod_defs[rest[-1]]

        return None


# ============================================================================
# Class context resolution (for self.method calls)
# ============================================================================


def _find_class_for_method(
    method_name: str, file_path: str, index: RepoIndex, file_imports: list[ImportEntry]
) -> FuncDef | None:
    """Resolve self.method by searching the class hierarchy.

    Strategy:
    1. Find the class in the test file that contains the method
    2. If not found, check parent classes (single-level inheritance)
    """
    module = index.file_to_module.get(file_path)
    if not module:
        return None

    mod_defs = index.modules.get(module, {})

    # Check all classes in this module for the method
    for local_name, funcdef in mod_defs.items():
        if funcdef.kind == "class":
            # Check if this class has the method
            class_method_key = f"{funcdef.name}.{method_name}"
            if class_method_key in mod_defs:
                return mod_defs[class_method_key]

    # Check parent classes via imports
    # Parse the file to find class definitions and their bases
    file_path_full = index.repo_root / file_path
    try:
        src_text = file_path_full.read_text(errors="replace")
    except (OSError, UnicodeDecodeError):
        return None

    root = _parse(src_text)
    if not root:
        return None

    src = src_text.encode()
    resolver = ImportResolver(file_imports, index)

    for cls_node in _find(root, "class_definition"):
        # Check superclasses
        superclasses_node = cls_node.child_by_field_name("superclasses")
        if not superclasses_node:
            continue

        for child in superclasses_node.children:
            if child.type in ("identifier", "attribute"):
                parent_name = _text(child, src)
                # Try to resolve parent class
                parent_def = resolver.resolve(parent_name)
                if parent_def and parent_def.kind == "class":
                    # Look for method in parent's module
                    parent_module = parent_def.qualified_name.rsplit(".", 1)[0]
                    parent_mod_defs = index.modules.get(parent_module, {})
                    method_key = f"{parent_def.name}.{method_name}"
                    if method_key in parent_mod_defs:
                        return parent_mod_defs[method_key]

    return None


def _resolve_self_attribute(
    attr_name: str,
    file_path: str,
    index: RepoIndex,
    file_imports: list[ImportEntry],
) -> FuncDef | None:
    """Resolve self.X where X is set in __init__/setUp as self.X = SomeClass(...)."""
    module = index.file_to_module.get(file_path)
    if not module:
        return None

    mod_defs = index.modules.get(module, {})

    # Look for __init__ and setUp methods in all classes in the file
    for local_name, funcdef in mod_defs.items():
        if funcdef.kind != "method":
            continue
        if funcdef.name not in ("__init__", "setUp", "setUpClass"):
            continue

        # Parse the method body looking for self.<attr_name> = <expr>
        root = _parse(funcdef.code)
        if not root:
            continue
        src = funcdef.code.encode()

        for assign_node in _find(root, "assignment"):
            left = assign_node.child_by_field_name("left")
            right = assign_node.child_by_field_name("right")
            if not left or not right:
                continue
            if left.type != "attribute":
                continue
            left_text = _text(left, src)
            if left_text != f"self.{attr_name}":
                continue

            # Found it! Now resolve the RHS expression using AST
            rhs_name = _root_name(right, src)
            if not rhs_name:
                continue

            # Try to resolve via imports
            resolver = ImportResolver(file_imports, index)
            resolved = resolver.resolve(rhs_name)
            if resolved:
                return resolved

            # Try local defs
            if rhs_name in mod_defs:
                return mod_defs[rhs_name]

    return None


# ============================================================================
# Dependency extraction (BFS)
# ============================================================================


def _extract_class_init_calls(
    class_code: str, file_path: str, index: RepoIndex
) -> list[str]:
    """Extract calls only from a class's __init__ and class-level statements.

    Avoids the method explosion problem where a large class (e.g. pandas Index
    with 300+ methods) produces hundreds of depth-2 deps. Instead, we only
    capture constructor dependencies and class-level assignments/base classes.
    """
    root = _parse(class_code)
    if not root:
        return []
    src = class_code.encode()
    calls: list[str] = []

    for cls_node in _find(root, "class_definition"):
        # Extract base class references
        superclasses = cls_node.child_by_field_name("superclasses")
        if superclasses:
            for child in superclasses.children:
                if child.type in ("identifier", "attribute"):
                    calls.append(_text(child, src))

        body = cls_node.child_by_field_name("body")
        if not body:
            continue

        for child in body.children:
            # Class-level assignments and expressions (not method defs)
            if child.type in ("expression_statement", "assignment"):
                calls.extend(_extract_calls(child, src))
                calls.extend(_extract_bare_identifiers(child, src))
            # Only __init__ method body
            elif child.type in ("function_definition", "decorated_definition"):
                fdef = _find_function_def(child)
                if fdef:
                    name_node = fdef.child_by_field_name("name")
                    if name_node and _text(name_node, src) == "__init__":
                        calls.extend(_extract_calls(child, src))
                        calls.extend(_extract_references(child, src))
                        calls.extend(_extract_bare_identifiers(child, src))

    return calls


@dataclass
class DepResult:
    """Result of dependency extraction."""

    name: str
    qualified_name: str
    code: str
    file_path: str
    depth: int
    kind: str
    resolution: str  # how it was resolved


def extract_dependencies(
    pbt_code: str,
    pbt_file: str,  # repo-relative path
    index: RepoIndex,
    max_depth: int = 2,
) -> list[DepResult]:
    """BFS over the call graph from a PBT, bounded by depth.

    Depth 0: the PBT itself (not included in output)
    Depth 1: everything the PBT calls
    Depth 2: everything those callees call
    """
    # Read the full source file for import context
    full_path = index.repo_root / pbt_file
    try:
        file_src = full_path.read_text(errors="replace")
    except (OSError, UnicodeDecodeError):
        console.print(f"[red]Cannot read {pbt_file}[/red]")
        return []

    file_module = index.file_to_module.get(pbt_file)
    file_imports = parse_imports(file_src, source_module=file_module)
    resolver = ImportResolver(file_imports, index)

    collected: dict[str, DepResult] = {}  # qualified_name -> DepResult
    # Queue: (calls_to_resolve, depth, source_file for self-resolution)
    queue: list[tuple[list[str], int, str, list[ImportEntry]]] = []

    # Extract calls from the PBT code itself
    pbt_root = _parse(pbt_code)
    if not pbt_root:
        console.print("[red]Failed to parse PBT code[/red]")
        return []

    pbt_bytes = pbt_code.encode()
    # Find the actual function node for type annotation extraction
    # (may be wrapped in decorated_definition at the top level)
    pbt_func_node = pbt_root
    for child in pbt_root.children:
        if child.type in ("decorated_definition", "function_definition"):
            pbt_func_node = child
            break

    initial_calls = (
        _extract_calls(pbt_root, pbt_bytes)
        + _extract_references(pbt_root, pbt_bytes)
        + _extract_bare_identifiers(pbt_root, pbt_bytes)
        + _extract_type_annotations(pbt_func_node, pbt_bytes)
    )
    queue.append((initial_calls, 1, pbt_file, file_imports))

    # Compute local names (parameters + local vars + decorator names) for the
    # PBT to avoid false-positive global search matches. Decorator names like
    # `given`, `example`, `settings` are framework names that should never
    # resolve via global search to unrelated repo functions.
    #
    # Exception: parameters that are ALSO call targets in the body are likely
    # pytest fixtures (dependency-injected by name), not true local bindings.
    # Exclude them so they can resolve via global search to conftest.py etc.
    param_names = _extract_parameter_names(pbt_root, pbt_bytes)
    call_targets = set(_extract_calls(pbt_root, pbt_bytes))
    called_params = param_names & call_targets
    local_names = (
        (param_names - called_params)
        | _extract_local_vars(pbt_root, pbt_bytes)
        | _extract_decorator_names(pbt_root, pbt_bytes)
    )

    while queue:
        calls, depth, context_file, context_imports = queue.pop(0)
        if depth > max_depth:
            continue

        context_resolver = (
            ImportResolver(context_imports, index)
            if context_imports is not file_imports
            else resolver
        )
        context_module = index.file_to_module.get(context_file, "")
        context_local_defs = index.modules.get(context_module, {})

        for call_expr in calls:
            # Skip builtins and obvious non-targets
            simple = call_expr.strip()
            if not simple or simple in PYTHON_BUILTINS or simple in ("_", "__"):
                continue

            # At depth 1, skip names that are the PBT's own parameters or
            # local variables (tree-sitter-derived, not hardcoded)
            if depth == 1 and simple in local_names:
                continue

            resolved: FuncDef | None = None
            resolution_method = ""

            parts = simple.split(".")

            # 1. Try self.method resolution
            if parts[0] == "self" and len(parts) == 2:
                method_name = parts[1]
                resolved = _find_class_for_method(
                    method_name, context_file, index, context_imports
                )
                resolution_method = "self_method"

                # If not found as a method, try as a class attribute
                # (e.g. self.klass set in setUp)
                if not resolved:
                    resolved = _resolve_self_attribute(
                        method_name, context_file, index, context_imports
                    )
                    resolution_method = "self_attribute"

            # 2. Try import-based resolution
            if not resolved:
                resolved = context_resolver.resolve(simple)
                resolution_method = "import"

            # 3. Try local (same-file) lookup
            if not resolved and parts[0] in context_local_defs:
                resolved = context_local_defs[parts[0]]
                resolution_method = "local"

            # 4. Try global index search as last resort
            #    Skip names that are: builtins, parameters, or local variables
            #    (all derived from the grammar, not a hardcoded list).
            #    Prefer unique matches; for multiple matches, pick the one
            #    closest to the context file's package.
            if not resolved and len(parts) == 1:
                name = parts[0]
                if name not in local_names and name not in PYTHON_BUILTINS:
                    candidates: list[FuncDef] = []
                    for mod_d in index.modules.values():
                        if name in mod_d:
                            candidates.append(mod_d[name])
                    if len(candidates) == 1:
                        resolved = candidates[0]
                        resolution_method = "global_search"
                    elif len(candidates) > 1:
                        # Disambiguate: prefer candidate sharing the longest
                        # common module prefix with the context file
                        ctx_mod = index.file_to_module.get(context_file, "")
                        best = None
                        best_score = -1
                        for cand in candidates:
                            cmod = cand.qualified_name.rsplit(".", 1)[0]
                            # Score = length of common prefix parts
                            cp = ctx_mod.split(".")
                            cm = cmod.split(".")
                            score = 0
                            for a, b in zip(cp, cm):
                                if a == b:
                                    score += 1
                                else:
                                    break
                            if score > best_score:
                                best_score = score
                                best = cand
                        if best and best_score > 0:
                            resolved = best
                            resolution_method = "global_search"

            if resolved and resolved.qualified_name not in collected:
                collected[resolved.qualified_name] = DepResult(
                    name=resolved.name,
                    qualified_name=resolved.qualified_name,
                    code=resolved.code,
                    file_path=resolved.file_path,
                    depth=depth,
                    kind=resolved.kind,
                    resolution=resolution_method,
                )

                # Enqueue this def's calls for deeper traversal
                if depth < max_depth:
                    # Parse imports from the resolved def's file for context
                    dep_file = resolved.file_path
                    dep_full_path = index.repo_root / dep_file
                    try:
                        dep_file_src = dep_full_path.read_text(errors="replace")
                        dep_module = index.file_to_module.get(dep_file)
                        dep_imports = parse_imports(
                            dep_file_src, source_module=dep_module
                        )
                    except (OSError, UnicodeDecodeError):
                        dep_imports = context_imports

                    # For classes, only extract calls from __init__ to avoid
                    # method explosion (e.g. pandas Index with 300+ methods).
                    # The class itself is already captured; we just need its
                    # constructor dependencies.
                    if resolved.kind == "class":
                        dep_calls = _extract_class_init_calls(
                            resolved.code, dep_file, index
                        )
                    else:
                        dep_root = _parse(resolved.code)
                        if dep_root:
                            dep_bytes = resolved.code.encode()
                            dep_calls = (
                                _extract_calls(dep_root, dep_bytes)
                                + _extract_references(dep_root, dep_bytes)
                                + _extract_bare_identifiers(dep_root, dep_bytes)
                            )
                        else:
                            dep_calls = []
                    if dep_calls:
                        queue.append(
                            (dep_calls, depth + 1, dep_file, dep_imports)
                        )

    return sorted(collected.values(), key=lambda d: (d.depth, d.qualified_name))


# ============================================================================
# CLI
# ============================================================================


def _print_tree(deps: list[DepResult]) -> None:
    """Pretty-print dependency tree."""
    tree = Tree("[bold]PBT Dependencies[/bold]")
    depth_branches: dict[int, Tree] = {}

    for d in [1, 2, 3]:
        items = [dep for dep in deps if dep.depth == d]
        if items:
            branch = tree.add(f"[bold cyan]Depth {d}[/bold cyan] ({len(items)} items)")
            depth_branches[d] = branch
            for dep in items:
                kind_color = {
                    "function": "green",
                    "method": "yellow",
                    "class": "magenta",
                    "assignment": "blue",
                }.get(dep.kind, "white")
                branch.add(
                    f"[{kind_color}]{dep.kind}[/{kind_color}] "
                    f"[bold]{dep.name}[/bold] "
                    f"[dim]({dep.file_path}:{dep.resolution})[/dim]"
                )

    console.print(tree)


@app.command()
def main(
    repo_path: Path = typer.Argument(..., help="Path to cloned repository root."),
    pbt_file: str = typer.Option(
        ..., help="Repo-relative path to the PBT's source file."
    ),
    pbt_name: str = typer.Option(..., help="Name of the PBT function/method."),
    depth: int = typer.Option(2, help="Maximum call depth to follow."),
    output_json: Path | None = typer.Option(
        None, "--json", help="Write results to JSON."
    ),
) -> None:
    """Extract depth-bounded dependencies for a PBT."""
    repo_path = repo_path.resolve()
    if not repo_path.is_dir():
        console.print(f"[red]Not a directory: {repo_path}[/red]")
        raise typer.Exit(1)

    # Build index
    console.print(f"[bold]Indexing {repo_path.name}...[/bold]")
    index = build_repo_index(repo_path)
    n_modules = len(index.modules)
    n_defs = len(index.all_defs)
    console.print(f"  Indexed {n_modules:,} modules, {n_defs:,} definitions")

    # Find the PBT
    module = index.file_to_module.get(pbt_file)
    if not module:
        console.print(f"[red]File not indexed: {pbt_file}[/red]")
        console.print("  Available files with similar name:")
        for f in index.file_to_module:
            if pbt_name in f or pbt_file.split("/")[-1] in f:
                console.print(f"    {f}")
        raise typer.Exit(1)

    mod_defs = index.modules.get(module, {})

    # Find the PBT def — might be a method (Class.method) or a function
    pbt_def: FuncDef | None = None
    for local_name, fdef in mod_defs.items():
        if fdef.name == pbt_name:
            pbt_def = fdef
            break

    if not pbt_def:
        console.print(f"[red]PBT '{pbt_name}' not found in {pbt_file}[/red]")
        console.print(f"  Available definitions: {list(mod_defs.keys())[:20]}")
        raise typer.Exit(1)

    console.print(
        f"  Found PBT: [bold]{pbt_def.qualified_name}[/bold] ({pbt_def.kind})"
    )

    # Extract dependencies
    console.print(f"[bold]Extracting dependencies (depth={depth})...[/bold]")
    deps = extract_dependencies(pbt_def.code, pbt_file, index, max_depth=depth)

    if not deps:
        console.print("[yellow]No dependencies found.[/yellow]")
        raise typer.Exit(0)

    _print_tree(deps)

    # Summary
    console.print(f"\n[bold]Total: {len(deps)} dependencies[/bold]")
    by_kind = {}
    for dep in deps:
        by_kind[dep.kind] = by_kind.get(dep.kind, 0) + 1
    for kind, count in sorted(by_kind.items()):
        console.print(f"  {kind}: {count}")

    unresolved_calls = []
    pbt_root = _parse(pbt_def.code)
    if pbt_root:
        all_calls = _extract_calls(pbt_root, pbt_def.code.encode())
        resolved_names = {d.name for d in deps}
        for call in all_calls:
            parts = call.split(".")
            last = parts[-1]
            if (
                last not in resolved_names
                and call not in PYTHON_BUILTINS
                and last not in PYTHON_BUILTINS
            ):
                unresolved_calls.append(call)
    if unresolved_calls:
        console.print("\n[yellow]Unresolved calls from PBT:[/yellow]")
        for c in sorted(set(unresolved_calls)):
            console.print(f"  [dim]{c}[/dim]")

    # JSON output
    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "pbt_name": pbt_name,
            "pbt_file": pbt_file,
            "pbt_qualified_name": pbt_def.qualified_name,
            "depth": depth,
            "dependencies": [
                {
                    "name": d.name,
                    "qualified_name": d.qualified_name,
                    "code": d.code,
                    "file_path": d.file_path,
                    "depth": d.depth,
                    "kind": d.kind,
                    "resolution": d.resolution,
                }
                for d in deps
            ],
        }
        output_json.write_text(json.dumps(data, indent=2))
        console.print(f"\n[green]Wrote {output_json}[/green]")


def clone_repo(
    url: str,
    dest: Path,
    timeout_seconds: int = 120,
    depth: int = 1,
    sparse_paths: list[str] | None = None,
) -> bool:
    """Clone a repo with a timeout. Returns True on success, False on failure.

    Uses shallow clone (--depth 1) by default for speed.
    Optionally uses sparse checkout to only fetch specific paths.
    """
    if dest.exists():
        return True

    cmd = ["git", "clone", "--depth", str(depth), url, str(dest)]

    try:
        subprocess.run(
            cmd,
            timeout=timeout_seconds,
            capture_output=True,
            check=True,
        )
    except subprocess.TimeoutExpired:
        console.print(f"[red]Clone timed out after {timeout_seconds}s: {url}[/red]")
        # Clean up partial clone
        if dest.exists():
            import shutil

            shutil.rmtree(dest)
        return False
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Clone failed: {url}[/red]")
        console.print(f"  stderr: {e.stderr.decode()[:200]}")
        if dest.exists():
            import shutil

            shutil.rmtree(dest)
        return False

    # Set up sparse checkout if requested
    if sparse_paths:
        try:
            subprocess.run(
                ["git", "sparse-checkout", "init", "--cone"],
                cwd=dest,
                capture_output=True,
                check=True,
            )
            subprocess.run(
                ["git", "sparse-checkout", "set"] + sparse_paths,
                cwd=dest,
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError:
            pass  # Non-fatal — we still have the full shallow clone

    return True


if __name__ == "__main__":
    app()
