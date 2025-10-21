"""Dependency autoformalization toolkit."""

from .models import (
    ArgumentRole,
    ArgumentSpec,
    CallableKind,
    CallableSignature,
    DependencyCallable,
    DependencyPayload,
    DependencyResult,
    NormalizationPlan,
    NormalizationStrategy,
    LeanArtifactSpec,
)
from .agent import dependency_autoformalizer, autoformalize_dependency_tool
from .cache import (
    CacheRecord,
    compute_cache_key,
    load_cached_dependency,
    persist_generated_dependency,
    record_cache_hit,
    store_dependency_result,
    write_dependency_artifact,
    read_manifest,
    clear_cache,
)
from .runner import depmock_setup, run_depmock_for_sample

__all__ = [
    "DependencyPayload",
    "DependencyResult",
    "ArgumentRole",
    "ArgumentSpec",
    "CallableSignature",
    "CallableKind",
    "DependencyCallable",
    "NormalizationPlan",
    "NormalizationStrategy",
    "LeanArtifactSpec",
    "dependency_autoformalizer",
    "autoformalize_dependency_tool",
    "CacheRecord",
    "compute_cache_key",
    "load_cached_dependency",
    "persist_generated_dependency",
    "record_cache_hit",
    "store_dependency_result",
    "write_dependency_artifact",
    "read_manifest",
    "clear_cache",
    "depmock_setup",
    "run_depmock_for_sample",
]
