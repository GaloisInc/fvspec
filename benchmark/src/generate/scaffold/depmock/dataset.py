"""Dataset and batching utilities for dependency autoformalization."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from datetime import datetime
from pathlib import Path

from inspect_ai.dataset import MemoryDataset, Sample
from pydantic import BaseModel, ConfigDict

from generate.scaffold.dataset import Datapoint
from generate.scaffold.depmock.cache import compute_cache_key, load_cached_dependency
from generate.scaffold.depmock.models import DependencyPayload


def payloads_from_datapoint(datapoint: Datapoint) -> list[DependencyPayload]:
    """Convert a dataset datapoint into dependency payloads.

    Creates payloads for:
    1. All explicit dependencies in datapoint.deps (with source code)
    2. All functions in datapoint.pbt_functions (to be inferred from test)
       Note: DB model doesn't have pbt_functions, so this is empty for now

    Args:
        datapoint: The datapoint containing test and dependency information

    Returns:
        List of dependency payloads
    """
    deps = datapoint.get_deps()
    dep_names = datapoint.get_dep_names()
    payloads: list[DependencyPayload] = []

    # Add explicit dependencies first (these have source code)
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

    # Add all functions from pbt_functions (no source code - infer from test)
    # Note: DB model doesn't currently have this field, defaults to empty
    pbt_functions = getattr(datapoint, "pbt_functions", []) or []
    for func_name in pbt_functions:
        # Skip if already in explicit dependencies
        if func_name in dep_names:
            continue

        # Create payload with test as context (model will infer implementation)
        payloads.append(
            DependencyPayload(
                dep_name=func_name,
                python_source=datapoint.code,  # Pass test as context
                python_signature=None,
                python_docstring=None,
                source_hash=None,
                tags=("pbt_function",),
                usage_example=datapoint.code,
                lean_module=None,
            )
        )

    return payloads


class DependencySampleSpec(BaseModel):
    """Metadata describing a dependency autoformalization task."""

    model_config = ConfigDict(frozen=True)

    payload: DependencyPayload
    cache_key: str
    datapoint_id: int
    datapoint_repo_id: int
    datapoint_name: str
    dependency_index: int
    sample_id: str
    cached: bool

    @property
    def dependency_name(self) -> str:
        """Return the dependency name."""
        return self.payload.dep_name


CacheLookup = Callable[[DependencyPayload], bool]


def scan_dependencies(
    datapoints: Iterable[Datapoint],
    *,
    skip_cached: bool = True,
    dedupe: bool = True,
    cache_root: Path | None = None,
    cache_lookup: CacheLookup | None = None,
) -> list[DependencySampleSpec]:
    """Scan datapoints and produce dependency tasks.

    Args:
        datapoints: Iterable of scraped datapoints.
        skip_cached: If True, omit dependencies already present in the cache.
        dedupe: If True, only keep the first occurrence of a dependency (by cache key).
        cache_root: Optional cache root override used for lookup.
        cache_lookup: Optional override used for cache existence checks (for testing).

    Returns:
        Ordered list of dependency sample specifications.
    """

    def is_cached(payload: DependencyPayload) -> bool:
        if cache_lookup is not None:
            return cache_lookup(payload)
        return load_cached_dependency(payload, cache_root=cache_root) is not None

    seen_keys: set[str] = set()
    specs: list[DependencySampleSpec] = []

    for datapoint in datapoints:
        payloads = payloads_from_datapoint(datapoint)
        sample_id = f"{datapoint.id:05d}_{datapoint.name}"

        for index, payload in enumerate(payloads):
            cache_key = compute_cache_key(payload)
            cached = is_cached(payload)
            if skip_cached and cached:
                continue
            if dedupe and cache_key in seen_keys:
                continue

            seen_keys.add(cache_key)
            specs.append(
                DependencySampleSpec(
                    payload=payload,
                    cache_key=cache_key,
                    datapoint_id=datapoint.id,
                    datapoint_repo_id=datapoint.repo_id,
                    datapoint_name=datapoint.name,
                    dependency_index=index,
                    sample_id=sample_id,
                    cached=cached,
                )
            )

    return specs


def build_dependency_dataset(
    specs: Sequence[DependencySampleSpec],
    *,
    date_time: datetime,
    variant: str | None,
    batch_size: int | None = None,
) -> MemoryDataset:
    """Create an inspect_ai dataset from dependency specifications."""
    if not specs:
        return MemoryDataset([])

    effective_batch_size = batch_size or len(specs)
    date_time_str = date_time.strftime("%Y-%m-%dT%H-%M-%S")

    samples: list[Sample] = []

    for global_index, spec in enumerate(specs):
        batch_index = global_index // effective_batch_size
        batch_position = global_index % effective_batch_size

        metadata = {
            "payload": spec.payload,
            "cache_key": spec.cache_key,
            "dep_name": spec.dependency_name,
            "dependency_index": spec.dependency_index,
            "datapoint_id": spec.datapoint_id,
            "datapoint_repo_id": spec.datapoint_repo_id,
            "datapoint_name": spec.datapoint_name,
            "sample_id": spec.sample_id,
            "date_time": date_time_str,
            "variant": variant,
            "cached": spec.cached,
            "batch": {
                "index": batch_index,
                "position": batch_position,
                "size": effective_batch_size,
                "global_index": global_index,
            },
        }

        sample_id = f"{spec.cache_key}:{spec.dependency_index}"
        samples.append(Sample(input="", metadata=metadata, id=sample_id))

    return MemoryDataset(samples)
