"""Pydantic models used by the dependency autoformalization agent."""

from __future__ import annotations

import ast
import re
from enum import Enum
from typing import Iterable, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, computed_field


class ArgumentRole(str, Enum):
    """Classification of a Python parameter position."""

    POSITIONAL_ONLY = "positional_only"
    POSITIONAL_OR_KEYWORD = "positional_or_keyword"
    VAR_POSITIONAL = "var_positional"
    KEYWORD_ONLY = "keyword_only"
    VAR_KEYWORD = "var_keyword"


class ArgumentSpec(BaseModel):
    """Normalized representation of a callable argument for prompting."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., description="Parameter identifier")
    role: ArgumentRole = Field(..., description="Calling convention for the parameter")
    annotation: str | None = Field(
        default=None, description="PEP 484 style annotation if present"
    )
    default: str | None = Field(
        default=None, description="Default value literal for the parameter"
    )

    def prompt_dict(self) -> dict[str, str | None]:
        """Convert the argument spec into a prompt-friendly dictionary."""
        return {
            "name": self.name,
            "role": self.role.value,
            "annotation": self.annotation,
            "default": self.default,
        }


class CallableSignature(BaseModel):
    """Captured signature information for a Python callable."""

    model_config = ConfigDict(frozen=True)

    text: str | None = Field(
        default=None, description="Formatted signature header for the callable"
    )
    arguments: tuple[ArgumentSpec, ...] = Field(
        default_factory=tuple,
        description="Ordered argument specification extracted from the signature",
    )
    returns_annotation: str | None = Field(
        default=None, description="Return annotation if present"
    )


class CallableKind(str, Enum):
    """High-level classification for a dependency callable."""

    FUNCTION = "function"
    ASYNC_FUNCTION = "async_function"
    METHOD = "method"
    CLASSMETHOD = "classmethod"
    STATICMETHOD = "staticmethod"
    CLASS = "class"
    UNKNOWN = "unknown"


class DependencyCallable(BaseModel):
    """Structured description of the Python callable to autoformalize."""

    model_config = ConfigDict(frozen=True)

    qualname: str = Field(
        ..., description="Fully qualified Python name for the callable"
    )
    module_path: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Python module path segments preceding the callable",
    )
    callable_name: str = Field(..., description="Unqualified callable identifier")
    kind: CallableKind = Field(..., description="Callable classification")
    signature: CallableSignature = Field(
        default_factory=CallableSignature,
        description="Signature information extracted from the Python source",
    )
    docstring: str | None = Field(
        default=None, description="Primary docstring associated with the callable"
    )
    python_source: str = Field(
        ..., description="Original Python helper code for reference"
    )

    def prompt_dict(self) -> dict[str, object]:
        """Produce a prompt-ready representation of the callable metadata."""
        return {
            "qualname": self.qualname,
            "module_path": ".".join(self.module_path),
            "module_segments": list(self.module_path),
            "callable_name": self.callable_name,
            "callable_kind": self.kind.value,
            "signature": {
                "text": self.signature.text,
                "returns_annotation": self.signature.returns_annotation,
                "arguments": [arg.prompt_dict() for arg in self.signature.arguments],
            },
            "docstring": self.docstring,
        }


class LeanArtifactSpec(BaseModel):
    """Lean module expectations for the generated dependency artifact."""

    model_config = ConfigDict(frozen=True)

    namespace: tuple[str, ...] = Field(
        default=("Fvspec", "Deps"),
        description="Namespace segments that wrap dependency modules",
    )
    module_segments: tuple[str, ...] = Field(
        ..., description="Sanitized Lean module path segments under the namespace"
    )
    module_basename: str = Field(
        ..., description="Final Lean module identifier within the namespace"
    )
    file_stem: str = Field(
        ..., description="Filename stem used when persisting the Lean module to disk"
    )

    @computed_field  # type: ignore[misc]
    @property
    def qualified_module(self) -> str:
        """Fully qualified Lean module path."""
        return ".".join((*self.namespace, self.module_basename))


def _sanitize_segment(segment: str, fallback: str = "Dependency") -> str:
    """Convert a raw module segment into a Lean-safe identifier."""
    parts = re.findall(r"[A-Za-z0-9]+", segment)
    if not parts:
        return fallback
    candidate = "".join(part.capitalize() for part in parts)
    if not candidate:
        candidate = fallback
    if not candidate[0].isalpha():
        candidate = f"M{candidate}"
    return candidate


def _sanitize_module_segments(name: str | None) -> tuple[str, ...]:
    """Sanitize a dotted module name into Lean-safe path segments."""
    if not name:
        return ("Dependency",)
    segments = [segment for segment in name.split(".") if segment]
    if not segments:
        return ("Dependency",)
    return tuple(_sanitize_segment(segment) for segment in segments)


def _lean_module_segments(dep_name: str, override: str | None) -> tuple[str, ...]:
    """Derive Lean module segments from a dependency name and optional override."""
    if override:
        override_segments = _sanitize_module_segments(override)
        return override_segments
    return _sanitize_module_segments(dep_name)


def _sanitize_identifier(name: str, fallback: str = "helper") -> str:
    """Sanitize a Python identifier into a Lean-safe lowercase name."""
    parts = re.findall(r"[A-Za-z0-9]+", name)
    if not parts:
        return fallback
    identifier = "_".join(part.lower() for part in parts if part)
    if not identifier:
        identifier = fallback
    if identifier[0].isdigit():
        identifier = f"x_{identifier}"
    return identifier


def _lean_function_name(path: tuple[str, ...], name: str) -> str:
    """Derive a Lean-friendly function name from a module path and callable name."""
    segments = [*_sanitize_module_segments(".".join(path)), _sanitize_segment(name)]
    parts = [_sanitize_identifier(segment) for segment in segments if segment]
    if not parts:
        return "dependency_fn"
    return "_".join(parts)


def _module_path_from_dep(dep_name: str) -> tuple[str, ...]:
    """Split a fully qualified dependency name into module path segments."""
    segments = [segment for segment in dep_name.split(".") if segment]
    if len(segments) <= 1:
        return ()
    return tuple(segments[:-1])


def _callable_name_from_dep(dep_name: str) -> str:
    """Return the final segment of a dependency name."""
    segments = [segment for segment in dep_name.split(".") if segment]
    if not segments:
        return "dependency"
    return segments[-1]


def _unparse(node: ast.AST | None) -> str | None:
    """Best effort conversion from AST to source."""
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except AttributeError:
        return None


def _format_argument(
    arg: ast.arg,
    *,
    role: ArgumentRole,
    default: ast.AST | None,
) -> tuple[str, ArgumentSpec]:
    annotation = _unparse(arg.annotation)
    default_str = _unparse(default)
    prefix = ""
    if role is ArgumentRole.VAR_POSITIONAL:
        prefix = "*"
    elif role is ArgumentRole.VAR_KEYWORD:
        prefix = "**"

    name = f"{prefix}{arg.arg}"
    segment = name
    if annotation:
        segment += f": {annotation}"
    if default_str is not None:
        segment += f" = {default_str}"

    spec = ArgumentSpec(
        name=arg.arg,
        role=role,
        annotation=annotation,
        default=default_str,
    )
    return segment, spec


def _format_signature(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> CallableSignature:
    """Build a normalized signature for a function-like AST node."""
    args = node.args
    pieces: list[str] = []
    specs: list[ArgumentSpec] = []

    positional: list[ast.arg] = list(args.posonlyargs) + list(args.args)
    defaults = list(args.defaults)
    defaults_start = len(positional) - len(defaults)

    for idx, arg in enumerate(args.posonlyargs):
        positional_idx = idx
        default = (
            defaults[positional_idx - defaults_start]
            if positional_idx >= defaults_start
            else None
        )
        segment, spec = _format_argument(
            arg, role=ArgumentRole.POSITIONAL_ONLY, default=default
        )
        pieces.append(segment)
        specs.append(spec)

    if args.posonlyargs:
        pieces.append("/")

    for idx, arg in enumerate(args.args):
        positional_idx = len(args.posonlyargs) + idx
        default = (
            defaults[positional_idx - defaults_start]
            if positional_idx >= defaults_start
            else None
        )
        segment, spec = _format_argument(
            arg, role=ArgumentRole.POSITIONAL_OR_KEYWORD, default=default
        )
        pieces.append(segment)
        specs.append(spec)

    if args.vararg:
        segment, spec = _format_argument(
            args.vararg, role=ArgumentRole.VAR_POSITIONAL, default=None
        )
        pieces.append(segment)
        specs.append(spec)

    if args.kwonlyargs:
        if not args.vararg:
            pieces.append("*")
        for idx, kw_arg in enumerate(args.kwonlyargs):
            default = args.kw_defaults[idx] if idx < len(args.kw_defaults) else None
            segment, spec = _format_argument(
                kw_arg, role=ArgumentRole.KEYWORD_ONLY, default=default
            )
            pieces.append(segment)
            specs.append(spec)

    if args.kwarg:
        segment, spec = _format_argument(
            args.kwarg, role=ArgumentRole.VAR_KEYWORD, default=None
        )
        pieces.append(segment)
        specs.append(spec)

    signature_text = f"{node.name}({', '.join(pieces)})"
    returns_annotation = _unparse(node.returns)
    if returns_annotation:
        signature_text += f" -> {returns_annotation}"

    return CallableSignature(
        text=signature_text,
        arguments=tuple(specs),
        returns_annotation=returns_annotation,
    )


def _iter_decorators(decorators: Iterable[ast.expr] | None) -> Iterable[ast.expr]:
    """Yield decorator expressions if present."""
    return decorators or ()


def _decorator_basename(expr: ast.expr) -> str:
    """Extract the final identifier from a decorator expression."""
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        return expr.attr
    return ""


def _detect_callable_kind(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
) -> CallableKind:
    """Infer the callable classification from the AST node."""
    if isinstance(node, ast.ClassDef):
        return CallableKind.CLASS

    kind = (
        CallableKind.ASYNC_FUNCTION
        if isinstance(node, ast.AsyncFunctionDef)
        else CallableKind.FUNCTION
    )

    decorator_names = {
        name.lower()
        for name in (
            _decorator_basename(dec) for dec in _iter_decorators(node.decorator_list)
        )
        if name
    }

    if "staticmethod" in decorator_names:
        return CallableKind.STATICMETHOD
    if "classmethod" in decorator_names:
        return CallableKind.CLASSMETHOD

    if node.args.args:
        first_param = node.args.args[0].arg
        if first_param in {"self", "cls"}:
            return CallableKind.METHOD

    return kind


class _ReceiverUsage(BaseModel):
    """Attributes accessed on a method receiver."""

    model_config = ConfigDict(frozen=True)

    attributes: tuple[str, ...]
    mutates: bool


class _ReceiverUsageVisitor(ast.NodeVisitor):
    """Collect attribute usages and mutations on a receiver symbol."""

    def __init__(self, receiver_name: str) -> None:
        self.receiver_name = receiver_name
        self._attributes: set[str] = set()
        self._mutates = False

    def _is_receiver_attribute(self, node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == self.receiver_name
        )

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if self._is_receiver_attribute(node):
            self._attributes.add(node.attr)
            if isinstance(node.ctx, (ast.Store, ast.Del)):
                self._mutates = True
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if self._check_target(target):
                self._mutates = True
        self.generic_visit(node.value)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        if self._check_target(node.target):
            self._mutates = True
        self.generic_visit(node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.target and self._check_target(node.target):
            self._mutates = True
        if node.value:
            self.generic_visit(node.value)

    def _check_target(self, node: ast.AST) -> bool:
        if self._is_receiver_attribute(node):
            attr_node = cast(ast.Attribute, node)
            self._attributes.add(attr_node.attr)
            return True
        return False

    def result(self) -> _ReceiverUsage:
        return _ReceiverUsage(
            attributes=tuple(sorted(self._attributes)),
            mutates=self._mutates,
        )


def _analyze_receiver_usage(
    node: ast.FunctionDef | ast.AsyncFunctionDef, receiver_name: str
) -> tuple[tuple[str, ...], bool]:
    """Inspect method body to gather receiver attribute access information."""
    visitor = _ReceiverUsageVisitor(receiver_name)
    for stmt in node.body:
        visitor.visit(stmt)
    usage = visitor.result()
    return usage.attributes, usage.mutates


class _CallableAnalysis(BaseModel):
    """Internal representation of parsed callable metadata."""

    model_config = ConfigDict(frozen=True)

    kind: CallableKind
    signature: CallableSignature
    docstring: str | None
    receiver_name: str | None
    receiver_attributes: tuple[str, ...]
    mutates_receiver: bool


class NormalizationStrategy(str, Enum):
    """Strategies for representing Python callables in Lean prompts."""

    AS_IS = "as_is"
    FLATTEN_METHOD = "flatten_method"
    STRUCTURE_METHOD = "structure_method"


class NormalizationPlan(BaseModel):
    """Decision record describing how to normalize a dependency callable."""

    model_config = ConfigDict(frozen=True)

    strategy: NormalizationStrategy = Field(
        ..., description="Selected normalization approach"
    )
    receiver_name: str | None = Field(
        default=None, description="Original receiver parameter name if applicable"
    )
    receiver_alias: str | None = Field(
        default=None,
        description="Suggested Lean identifier for the receiver argument or instance",
    )
    function_basename: str = Field(
        ..., description="Python callable name (sans module path)"
    )
    lean_helper_name: str = Field(
        ..., description="Lean-friendly helper/function name to implement"
    )
    struct_name: str | None = Field(
        default=None, description="Suggested Lean structure name for receiver modelling"
    )
    struct_fields: tuple[str, ...] = Field(
        default_factory=tuple, description="Attributes accessed on the receiver"
    )
    mutates_receiver: bool = Field(
        default=False, description="Whether the method mutates receiver state"
    )
    notes: str | None = Field(default=None, description="Human-readable rationale")

    def prompt_dict(self) -> dict[str, object]:
        """Convert plan into plain types for prompt rendering."""
        return {
            "strategy": self.strategy.value,
            "receiver_name": self.receiver_name,
            "receiver_alias": self.receiver_alias,
            "function_basename": self.function_basename,
            "lean_helper_name": self.lean_helper_name,
            "struct_name": self.struct_name,
            "struct_fields": list(self.struct_fields),
            "mutates_receiver": self.mutates_receiver,
            "notes": self.notes,
        }


def _analyze_python_callable(source: str) -> _CallableAnalysis:
    """Parse Python source to infer callable metadata."""
    try:
        module = ast.parse(source)
    except SyntaxError:
        return _CallableAnalysis(
            kind=CallableKind.UNKNOWN,
            signature=CallableSignature(),
            docstring=None,
            receiver_name=None,
            receiver_attributes=tuple(),
            mutates_receiver=False,
        )

    target = next(
        (
            node
            for node in module.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ),
        None,
    )
    if target is None:
        return _CallableAnalysis(
            kind=CallableKind.UNKNOWN,
            signature=CallableSignature(),
            docstring=None,
            receiver_name=None,
            receiver_attributes=tuple(),
            mutates_receiver=False,
        )

    if isinstance(target, ast.ClassDef):
        bases: list[str] = []
        for base in target.bases:
            base_text = _unparse(base)
            if base_text:
                bases.append(base_text)
        base_clause = f"({', '.join(bases)})" if bases else ""
        signature_text = f"class {target.name}{base_clause}"
        signature = CallableSignature(text=signature_text, arguments=tuple())
    else:
        signature = _format_signature(target)

    docstring = ast.get_docstring(target)
    kind = _detect_callable_kind(target)

    receiver_name: str | None = None
    receiver_attributes: tuple[str, ...] = tuple()
    mutates_receiver = False

    if (
        kind in {CallableKind.METHOD, CallableKind.CLASSMETHOD}
        and signature.arguments
        and signature.arguments[0].name
    ):
        receiver_name = signature.arguments[0].name
        receiver_attributes, mutates_receiver = _analyze_receiver_usage(
            target, receiver_name
        )

    return _CallableAnalysis(
        kind=kind,
        signature=signature,
        docstring=docstring,
        receiver_name=receiver_name,
        receiver_attributes=receiver_attributes,
        mutates_receiver=mutates_receiver,
    )


def _receiver_alias(name: str | None) -> str | None:
    """Suggest a Lean identifier for the receiver reference."""
    if name is None:
        return None
    lowered = name.lower()
    if lowered == "self":
        return "inst"
    if lowered == "cls":
        return "clsInst"
    return name


def _candidate_struct_name(module_path: tuple[str, ...], callable_name: str) -> str:
    """Choose a canonical Lean structure name for a receiver."""
    if module_path:
        return _sanitize_segment(module_path[-1])
    return _sanitize_segment(callable_name)


def _build_normalization_plan(
    module_path: tuple[str, ...],
    callable_name: str,
    analysis: _CallableAnalysis,
) -> NormalizationPlan:
    """Derive the normalization plan for a dependency callable."""
    lean_helper_name = _lean_function_name(module_path, callable_name)
    receiver_alias = _receiver_alias(analysis.receiver_name)

    if analysis.kind not in {CallableKind.METHOD, CallableKind.CLASSMETHOD}:
        return NormalizationPlan(
            strategy=NormalizationStrategy.AS_IS,
            receiver_name=None,
            receiver_alias=None,
            function_basename=callable_name,
            lean_helper_name=lean_helper_name,
            notes="Callable is already a standalone function.",
        )

    if analysis.receiver_name is None:
        return NormalizationPlan(
            strategy=NormalizationStrategy.AS_IS,
            receiver_name=None,
            receiver_alias=None,
            function_basename=callable_name,
            lean_helper_name=lean_helper_name,
            notes="Method lacks an explicit receiver; treat as standalone.",
        )

    if analysis.receiver_attributes:
        struct_name = _candidate_struct_name(module_path, callable_name)
        note = "Model receiver state via a Lean structure."
        if analysis.mutates_receiver:
            note += " Method mutates the receiver; return the updated structure."
        else:
            note += " Method only reads receiver state."
        return NormalizationPlan(
            strategy=NormalizationStrategy.STRUCTURE_METHOD,
            receiver_name=analysis.receiver_name,
            receiver_alias=receiver_alias,
            function_basename=callable_name,
            lean_helper_name=lean_helper_name,
            struct_name=struct_name,
            struct_fields=analysis.receiver_attributes,
            mutates_receiver=analysis.mutates_receiver,
            notes=note,
        )

    return NormalizationPlan(
        strategy=NormalizationStrategy.FLATTEN_METHOD,
        receiver_name=analysis.receiver_name,
        receiver_alias=receiver_alias,
        function_basename=callable_name,
        lean_helper_name=lean_helper_name,
        struct_name=None,
        struct_fields=tuple(),
        mutates_receiver=analysis.mutates_receiver,
        notes="Receiver state unused; flatten the method into a helper function.",
    )


class DependencyPayload(BaseModel):
    """Input payload describing a Python dependency snippet to autoformalize."""

    model_config = ConfigDict(frozen=True)

    dep_name: str = Field(..., description="Fully qualified dependency name")
    python_source: str = Field(..., description="Original Python helper code")
    python_signature: str | None = Field(
        default=None, description="Optional pre-extracted Python signature"
    )
    python_docstring: str | None = Field(
        default=None, description="Inline docstring associated with the dependency"
    )
    source_hash: str | None = Field(
        default=None, description="Stable hash for cache lookups"
    )
    tags: tuple[str, ...] = Field(
        default_factory=tuple, description="Contextual tags from the dataset"
    )
    usage_example: str | None = Field(
        default=None, description="Representative usage pulled from the dataset"
    )
    lean_module: str | None = Field(
        default=None,
        description="Optional Lean module override (otherwise derived from dep name)",
    )

    @computed_field  # type: ignore[misc]
    @property
    def callable(self) -> DependencyCallable:
        """Normalized callable metadata extracted from the Python helper."""
        analysis = _analyze_python_callable(self.python_source)
        module_path = _module_path_from_dep(self.dep_name)
        callable_name = _callable_name_from_dep(self.dep_name)
        signature_text = self.python_signature or analysis.signature.text
        signature = CallableSignature(
            text=signature_text,
            arguments=analysis.signature.arguments,
            returns_annotation=analysis.signature.returns_annotation,
        )
        docstring = self.python_docstring or analysis.docstring
        return DependencyCallable(
            qualname=self.dep_name or callable_name,
            module_path=module_path,
            callable_name=callable_name,
            kind=analysis.kind,
            signature=signature,
            docstring=docstring,
            python_source=self.python_source,
        )

    @computed_field  # type: ignore[misc]
    @property
    def normalization(self) -> NormalizationPlan:
        """Normalization strategy for the dependency callable."""
        analysis = _analyze_python_callable(self.python_source)
        module_path = _module_path_from_dep(self.dep_name)
        callable_name = _callable_name_from_dep(self.dep_name)
        return _build_normalization_plan(module_path, callable_name, analysis)

    @computed_field  # type: ignore[misc]
    @property
    def artifact(self) -> LeanArtifactSpec:
        """Lean artifact information expected from the agent."""
        segments = _lean_module_segments(self.dep_name, self.lean_module)
        module_basename = "".join(segments)
        file_stem = module_basename or "Dependency"
        return LeanArtifactSpec(
            namespace=("Fvspec", "Deps"),
            module_segments=segments,
            module_basename=module_basename,
            file_stem=file_stem,
        )

    @computed_field  # type: ignore[misc]
    @property
    def lean_module_name(self) -> str:
        """Lean module identifier used in prompts and caching."""
        return self.artifact.module_basename

    def prompt_context(self) -> dict[str, object]:
        """Prepare a dictionary for Jinja template rendering."""
        callable_dict = self.callable.prompt_dict()
        signature_dict = cast(dict[str, object], callable_dict["signature"])
        signature_text = signature_dict["text"]
        if signature_text is None and self.python_signature:
            signature_text = self.python_signature
        arguments = signature_dict["arguments"]
        normalization_plan = self.normalization.prompt_dict()
        return {
            "dep_name": self.dep_name,
            "python_source": self.python_source,
            "python_signature": signature_text,
            "python_docstring": callable_dict["docstring"],
            "source_hash": self.source_hash or "unknown",
            "tags": list(self.tags),
            "usage_example": self.usage_example,
            "dep_module": self.lean_module_name,
            "callable": callable_dict,
            "module_path": callable_dict["module_path"],
            "module_segments": callable_dict["module_segments"],
            "callable_kind": callable_dict["callable_kind"],
            "callable_signature": signature_text,
            "callable_arguments": arguments,
            "normalization": normalization_plan,
            "normalization_strategy": normalization_plan["strategy"],
            "lean_helper_name": normalization_plan["lean_helper_name"],
            "normalization_notes": normalization_plan["notes"],
            "lean_namespace": ".".join(self.artifact.namespace),
            "lean_namespace_segments": list(self.artifact.namespace),
            "lean_module_segments": list(self.artifact.module_segments),
            "lean_module_qualified": self.artifact.qualified_module,
            "lean_file_stem": self.artifact.file_stem,
        }


class DependencyResult(BaseModel):
    """Result metadata emitted by the autoformalization agent."""

    model_config = ConfigDict(frozen=True)

    lean_module: str = Field(..., description="Lean module file/base name")
    lean_code: str = Field(..., description="Generated Lean source code")
    variant: str | None = Field(default=None, description="Prompt variant used")
    status: Literal["ok", "failed", "stub"] = Field(
        default="ok", description="Outcome of the generation attempt"
    )
    diagnostics: str | None = Field(
        default=None, description="Diagnostics returned by Lean, if any"
    )
