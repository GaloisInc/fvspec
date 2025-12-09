"""Dataset utilities for dependency payload creation."""

from __future__ import annotations

from sqlmodel import Session

from generate.scaffold.dataset import Datapoint
from generate.scaffold.dataset.function_discovery import discover_function_code
from generate.scaffold.formalize.impl.models import DependencyPayload


def payloads_from_datapoint(
    datapoint: Datapoint, session: Session | None = None
) -> list[DependencyPayload]:
    """Convert a dataset datapoint into dependency payloads.

    Creates payloads for:
    1. Discovered function under test (if session provided and confidence >= 0.5)
    2. All explicit dependencies in datapoint.deps (with source code)

    Args:
        datapoint: The datapoint containing test and dependency information
        session: Optional database session for function discovery

    Returns:
        List of dependency payloads (discovered function first, then dependencies)
    """
    deps = datapoint.get_deps()
    dep_names = datapoint.get_dep_names()
    payloads: list[DependencyPayload] = []

    # Priority 1: Discover function under test
    if session is not None:
        function_info = discover_function_code(datapoint, session)
        if function_info and function_info.code and function_info.confidence >= 0.5:
            payloads.append(
                DependencyPayload(
                    dep_name=function_info.name,
                    python_source=function_info.code,
                    python_signature=None,
                    python_docstring=None,
                    source_hash=None,
                    tags=(
                        "function_under_test",
                        function_info.discovery_method.value,
                    ),
                    usage_example=datapoint.code,  # PBT shows usage
                    confidence=function_info.confidence,
                    discovery_method=function_info.discovery_method.value,
                    lean_module=None,
                )
            )

    # Priority 2: Add explicit dependencies (these have source code)
    for idx, source in enumerate(deps):
        dep_name = dep_names[idx] if idx < len(dep_names) else f"dependency_{idx + 1}"
        payloads.append(
            DependencyPayload(
                dep_name=dep_name,
                python_source=source,
                python_signature=None,
                python_docstring=None,
                source_hash=None,
                tags=("explicit_dependency",),
                usage_example=None,
                lean_module=None,
            )
        )

    return payloads
