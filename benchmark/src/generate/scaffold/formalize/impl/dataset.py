"""Dataset utilities for dependency payload creation."""

from __future__ import annotations

from generate.scaffold.dataset import Datapoint
from generate.scaffold.dataset.function_discovery import FunctionInfo
from generate.scaffold.formalize.impl.models import DependencyPayload

# Test infrastructure names that should not be formalized as dependencies.
# These are Hypothesis, pytest, unittest, and framework helpers that appear
# in deps due to broken upstream extraction.
KNOWN_TEST_INFRA = {
    "given",
    "settings",
    "assume",
    "note",
    "event",  # Hypothesis
    "fixture",
    "parametrize",
    "mark",  # pytest
    "setUp",
    "tearDown",
    "setUpClass",
    "tearDownClass",  # unittest
    "serial",  # Caffe2
}


def payloads_from_datapoint(
    datapoint: Datapoint,
    function_info: FunctionInfo | None = None,
) -> list[DependencyPayload]:
    """Convert a dataset datapoint into dependency payloads.

    Creates payloads for:
    1. Discovered function under test (if function_info provided and confident)
    2. All explicit dependencies in datapoint.deps (with source code),
       excluding known test infrastructure names.

    Args:
        datapoint: The datapoint containing test and dependency information
        function_info: Pre-discovered function info (avoids redundant discovery call)

    Returns:
        List of dependency payloads (discovered function first, then dependencies)
    """
    deps = datapoint.get_deps()
    dep_names = datapoint.get_dep_names()
    payloads: list[DependencyPayload] = []

    # Priority 1: Add discovered function under test
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

        # Skip known test infrastructure deps
        if dep_name in KNOWN_TEST_INFRA:
            continue

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
