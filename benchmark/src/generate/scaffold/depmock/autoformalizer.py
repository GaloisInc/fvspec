"""Invocation layer for dependency autoformalization."""

from __future__ import annotations

from datetime import UTC, datetime
import logging
from typing import Callable, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field

from generate.scaffold.depmock.dataset import (
    DependencySampleSpec,
    build_dependency_dataset,
)
from generate.scaffold.depmock.models import DependencyResult


class DependencyInvocationError(RuntimeError):
    """Base exception for dependency autoformalizer failures."""

    def __init__(self, message: str, *, diagnostics: str | None = None) -> None:
        """Initialise the error with an optional diagnostics payload."""
        super().__init__(message)
        self.diagnostics = diagnostics


class DependencyRecoverableError(DependencyInvocationError):
    """Error indicating the attempt can be retried (e.g., Lean diagnostics)."""


class DependencyFatalError(DependencyInvocationError):
    """Error indicating the dependency cannot be processed in the current run."""


class DependencyExecutionRequest(BaseModel):
    """Execution request for a dependency autoformalizer attempt."""

    model_config = ConfigDict(frozen=True)

    spec: DependencySampleSpec
    attempt: int = 1
    diagnostics: str | None = None


class DependencyOutcome(BaseModel):
    """Outcome of a dependency autoformalizer attempt."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    spec: DependencySampleSpec
    status: Literal["success", "failed", "fatal", "skipped"]
    attempts: int
    result: DependencyResult | None = None
    diagnostics: str | None = None
    error: DependencyInvocationError | None = None

    @property
    def cache_key(self) -> str:
        """Return the dependency cache key."""
        return self.spec.cache_key


class DependencyRunReport(BaseModel):
    """Summary report for dependency autoformalization run."""

    model_config = ConfigDict(frozen=True)

    started_at: datetime
    completed_at: datetime
    variant: str | None
    total: int
    outcomes: tuple[DependencyOutcome, ...]
    metadata: dict[str, object] = Field(default_factory=dict)

    @property
    def succeeded(self) -> tuple[DependencyOutcome, ...]:
        """Return outcomes that completed successfully."""
        return tuple(
            outcome for outcome in self.outcomes if outcome.status == "success"
        )

    @property
    def failed(self) -> tuple[DependencyOutcome, ...]:
        """Return outcomes that exhausted recoverable attempts."""
        return tuple(outcome for outcome in self.outcomes if outcome.status == "failed")

    @property
    def fatal(self) -> tuple[DependencyOutcome, ...]:
        """Return outcomes that encountered unrecoverable errors."""
        return tuple(outcome for outcome in self.outcomes if outcome.status == "fatal")

    @property
    def skipped(self) -> tuple[DependencyOutcome, ...]:
        """Return outcomes that were skipped due to cached artifacts."""
        return tuple(
            outcome for outcome in self.outcomes if outcome.status == "skipped"
        )

    @property
    def success(self) -> bool:
        """Return True when all dependencies succeeded."""
        return not self.failed and not self.fatal


class DependencyBatchError(RuntimeError):
    """Raised when fatal dependency errors occur during the run."""

    def __init__(self, message: str, report: DependencyRunReport) -> None:
        """Store the fatal error message together with the generated report."""
        super().__init__(message)
        self.report = report


DependencyExecutor = Callable[[DependencyExecutionRequest], DependencyResult]


def run_dependency_autoformalizer(
    specs: Sequence[DependencySampleSpec],
    *,
    executor: DependencyExecutor,
    variant: str | None = None,
    max_attempts: int = 3,
    skip_cached: bool = True,
    dataset_batch_size: int | None = None,
    metadata: dict[str, object] | None = None,
    stop_on_fatal: bool = True,
) -> DependencyRunReport:
    """Run the dependency autoformalizer over provided specifications.

    Args:
        specs: Sequence of dependency sample specifications to process.
        executor: Callable that performs a single autoformalizer attempt.
        variant: Optional prompt variant identifier for reporting.
        max_attempts: Maximum attempts per dependency when recoverable errors occur.
        skip_cached: Whether to treat cached dependencies as skipped outcomes.
        dataset_batch_size: Optional batch size recorded in metadata; used when building inspect_ai datasets.
        metadata: Optional additional metadata attached to the run report.
        stop_on_fatal: Whether to raise an exception when a fatal error is encountered.

    Returns:
        DependencyRunReport describing the run outcomes.
    """
    logger = logging.getLogger("generate.depmock.autoformalizer")
    started_at = datetime.now(UTC)
    outcomes: list[DependencyOutcome] = []

    for spec in specs:
        # Skip cached dependencies if requested
        if skip_cached and spec.cached:
            outcomes.append(
                DependencyOutcome(
                    spec=spec,
                    status="skipped",
                    attempts=0,
                    result=None,
                    diagnostics=None,
                )
            )
            continue

        diagnostics: str | None = None
        attempt = 0
        outcome: DependencyOutcome | None = None

        while attempt < max_attempts:
            attempt += 1
            request = DependencyExecutionRequest(
                spec=spec, attempt=attempt, diagnostics=diagnostics
            )

            try:
                result = executor(request)
            except DependencyRecoverableError as err:
                diagnostics = err.diagnostics
                logger.warning(
                    "Recoverable autoformalizer error for %s (attempt %d/%d): %s",
                    spec.dependency_name,
                    attempt,
                    max_attempts,
                    err,
                )
                if attempt >= max_attempts:
                    outcome = DependencyOutcome(
                        spec=spec,
                        status="failed",
                        attempts=attempt,
                        result=None,
                        diagnostics=diagnostics,
                        error=err,
                    )
                else:
                    continue
            except DependencyFatalError as err:
                logger.error(
                    "Fatal autoformalizer error for %s: %s",
                    spec.dependency_name,
                    err,
                )
                outcome = DependencyOutcome(
                    spec=spec,
                    status="fatal",
                    attempts=attempt,
                    result=None,
                    diagnostics=err.diagnostics,
                    error=err,
                )
                break
            else:
                outcome = DependencyOutcome(
                    spec=spec,
                    status="success",
                    attempts=attempt,
                    result=result,
                    diagnostics=None,
                    error=None,
                )
                break

        if outcome is None:
            # This happens when attempts exhausted without setting outcome (should not occur)
            outcome = DependencyOutcome(
                spec=spec,
                status="failed",
                attempts=attempt,
                result=None,
                diagnostics=diagnostics,
                error=None,
            )
        outcomes.append(outcome)

    completed_at = datetime.now(UTC)
    run_metadata = dict(metadata or {})
    dataset = build_dependency_dataset(
        specs,
        date_time=started_at,
        variant=variant,
        batch_size=dataset_batch_size,
    )
    run_metadata.setdefault("dataset_size", len(dataset))
    run_metadata.setdefault("batch_size", dataset_batch_size)

    report = DependencyRunReport(
        started_at=started_at,
        completed_at=completed_at,
        variant=variant,
        total=len(specs),
        outcomes=tuple(outcomes),
        metadata=run_metadata,
    )

    if stop_on_fatal and report.fatal:
        raise DependencyBatchError(
            f"Fatal dependency errors encountered ({len(report.fatal)} failure(s)).",
            report,
        )

    return report
