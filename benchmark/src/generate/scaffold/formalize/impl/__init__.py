"""Dependency autoformalization toolkit."""

from generate.scaffold.formalize.impl.agent import (
    autoformalize_dependency_tool,
    create_bound_dependency_tools,
    dependency_autoformalizer,
)
from generate.scaffold.formalize.impl.agent_runner import run_dependency_agent
from generate.scaffold.formalize.impl.autoformalizer import (
    DependencyBatchError,
    DependencyExecutionRequest,
    DependencyFatalError,
    DependencyInvocationError,
    DependencyOutcome,
    DependencyRecoverableError,
    DependencyRunReport,
    run_dependency_autoformalizer,
)
from generate.scaffold.formalize.impl.cache import (
    CacheRecord,
    clear_cache,
    compute_cache_key,
    load_cached_dependency,
    persist_generated_dependency,
    read_manifest,
    record_cache_hit,
    store_dependency_result,
    write_dependency_artifact,
)
from generate.scaffold.formalize.impl.dataset import (
    DependencySampleSpec,
    build_dependency_dataset,
    payloads_from_datapoint,
    scan_dependencies,
)
from generate.scaffold.formalize.impl.function_agent import (
    FunctionImplPayload,
    FunctionImplResult,
    function_impl_agent,
)
from generate.scaffold.formalize.impl.models import (
    ArgumentRole,
    ArgumentSpec,
    CallableKind,
    CallableSignature,
    DependencyCallable,
    DependencyPayload,
    DependencyResult,
    LeanArtifactSpec,
    NormalizationPlan,
    NormalizationStrategy,
)
from generate.scaffold.formalize.impl.runner import (
    aggregate_impl_modules,
    formalize_impl_setup,
    order_dependency_modules,
    run_formalize_impl_for_sample,
)

__all__ = [
    "DependencyPayload",
    "DependencyResult",
    "FunctionImplPayload",
    "FunctionImplResult",
    "function_impl_agent",
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
    "create_bound_dependency_tools",
    "run_dependency_agent",
    "CacheRecord",
    "compute_cache_key",
    "load_cached_dependency",
    "persist_generated_dependency",
    "record_cache_hit",
    "store_dependency_result",
    "write_dependency_artifact",
    "read_manifest",
    "clear_cache",
    "DependencySampleSpec",
    "payloads_from_datapoint",
    "scan_dependencies",
    "build_dependency_dataset",
    "DependencyInvocationError",
    "DependencyRecoverableError",
    "DependencyFatalError",
    "DependencyExecutionRequest",
    "DependencyOutcome",
    "DependencyRunReport",
    "DependencyBatchError",
    "run_dependency_autoformalizer",
    "formalize_impl_setup",
    "run_formalize_impl_for_sample",
    "aggregate_impl_modules",
    "order_dependency_modules",
]
