"""Tests for dependency autoformalizer invocation layer."""

from collections.abc import Iterator
from typing import cast

import pytest

from generate.scaffold.formalize_impl import (
    DependencyBatchError,
    DependencyExecutionRequest,
    DependencyFatalError,
    DependencyOutcome,
    DependencyPayload,
    DependencyRecoverableError,
    DependencyResult,
    DependencySampleSpec,
    run_dependency_autoformalizer,
)


def make_spec(
    *, cached: bool = False, dep_name: str = "helpers.trim"
) -> DependencySampleSpec:
    """Construct a dependency specification for test scenarios."""
    payload = DependencyPayload(
        dep_name=dep_name,
        python_source="def trim(value: str) -> str:\n    return value.strip()",
        python_signature=None,
        python_docstring=None,
        source_hash="abc123",
        tags=tuple(),
        usage_example=None,
        lean_module=None,
    )
    return DependencySampleSpec(
        payload=payload,
        cache_key="abc123",
        datapoint_id=1,
        datapoint_repo_id=42,
        datapoint_name="spec",
        dependency_index=0,
        sample_id="00001_spec",
        cached=cached,
    )


def make_result(
    payload: DependencyPayload, variant: str | None = None
) -> DependencyResult:
    """Return a trivial Lean module used to simulate autoformalizer output."""
    return DependencyResult(
        lean_module=payload.lean_module_name,
        lean_code=(
            f"namespace Fvspec.Deps\n\n"
            f"def {payload.lean_module_name} : Nat := 0\n\n"
            "end Fvspec.Deps\n"
        ),
        variant=variant,
        status="ok",
        diagnostics=None,
    )


def test_run_dependency_autoformalizer_success() -> None:
    """A successful execution should produce a populated outcome."""
    spec = make_spec()

    def executor(request: DependencyExecutionRequest) -> DependencyResult:
        return make_result(request.spec.payload, variant="functional")

    report = run_dependency_autoformalizer(
        [spec], executor=executor, variant="functional", max_attempts=2
    )

    assert report.success is True
    assert len(report.succeeded) == 1
    outcome = report.succeeded[0]
    assert isinstance(outcome, DependencyOutcome)
    assert outcome.attempts == 1
    assert outcome.result is not None


def test_run_dependency_autoformalizer_recoverable_then_success() -> None:
    """Recoverable errors should retry until a successful attempt occurs."""
    spec = make_spec()
    attempts: Iterator[int] = iter((1, 2))

    def executor(request: DependencyExecutionRequest) -> DependencyResult:
        attempt = next(attempts, 2)
        if attempt == 1:
            raise DependencyRecoverableError(
                "Lean typecheck error", diagnostics="unknown identifier"
            )
        return make_result(request.spec.payload)

    report = run_dependency_autoformalizer(
        [spec], executor=executor, max_attempts=2, variant="functional"
    )

    assert len(report.succeeded) == 1
    assert report.succeeded[0].attempts == 2


def test_run_dependency_autoformalizer_exhaust_recoverable() -> None:
    """Exhausted retries should surface a failed outcome."""
    spec = make_spec()

    def executor(request: DependencyExecutionRequest) -> DependencyResult:
        raise DependencyRecoverableError(
            "Lean typecheck error", diagnostics="unknown identifier"
        )

    report = run_dependency_autoformalizer(
        [spec], executor=executor, max_attempts=2, variant="functional"
    )

    assert len(report.failed) == 1
    assert report.failed[0].attempts == 2
    assert report.success is False


def test_run_dependency_autoformalizer_fatal() -> None:
    """Fatal errors should propagate via a DependencyBatchError."""
    spec = make_spec()

    def executor(request: DependencyExecutionRequest) -> DependencyResult:
        raise DependencyFatalError("Missing helper module")

    with pytest.raises(DependencyBatchError) as exc:
        run_dependency_autoformalizer(
            [spec], executor=executor, max_attempts=2, variant="functional"
        )

    error = cast(DependencyBatchError, exc.value)
    report = error.report
    assert len(report.fatal) == 1
    assert report.fatal[0].status == "fatal"


def test_run_dependency_autoformalizer_skip_cached() -> None:
    """Skip-cached mode should bypass dependencies with existing cache entries."""
    cached_spec = make_spec(cached=True)
    uncached_spec = make_spec(cached=False, dep_name="helpers.bump")

    def executor(request: DependencyExecutionRequest) -> DependencyResult:
        return make_result(request.spec.payload)

    report = run_dependency_autoformalizer(
        [cached_spec, uncached_spec],
        executor=executor,
        variant="functional",
        max_attempts=1,
        skip_cached=True,
    )

    assert len(report.skipped) == 1
    assert report.skipped[0].spec.dependency_name == "helpers.trim"
    assert len(report.succeeded) == 1
