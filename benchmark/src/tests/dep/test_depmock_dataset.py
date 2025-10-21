"""Tests for dependency dataset utilities."""

from datetime import UTC, datetime
from typing import Any, cast

import pytest

from generate.scaffold.dataset import Datapoint
from generate.scaffold.depmock.dataset import (
    build_dependency_dataset,
    payloads_from_datapoint,
    scan_dependencies,
)
from generate.scaffold.depmock.models import DependencyPayload


@pytest.fixture
def datapoint() -> Datapoint:
    return Datapoint(
        id=1,
        repo_id=111,
        pbt_name="spec",
        pbt="def test(): pass",
        dep_names=["helpers.trim", "helpers.bump"],
        deps=[
            "def trim(value: str) -> str:\n    return value.strip()",
            "def bump(x: int) -> int:\n    return x + 1",
        ],
        source="repo/spec.py",
        summary=None,
        hash="hash1",
        summary_vector=None,
    )


def test_payloads_from_datapoint(datapoint: Datapoint) -> None:
    payloads = payloads_from_datapoint(datapoint)
    assert len(payloads) == 2
    assert payloads[0].dep_name == "helpers.trim"
    assert payloads[1].dep_name == "helpers.bump"


def test_scan_dependencies_dedupe(datapoint: Datapoint) -> None:
    duplicate_dp = datapoint.model_copy(update={"id": 2})

    specs = scan_dependencies([datapoint, duplicate_dp], skip_cached=False, dedupe=True)
    assert len(specs) == 2
    assert {spec.cache_key for spec in specs} == {
        specs[0].cache_key,
        specs[1].cache_key,
    }


def test_scan_dependencies_skip_cached(datapoint: Datapoint) -> None:
    def cache_lookup(payload: DependencyPayload) -> bool:
        return payload.dep_name == "helpers.bump"

    specs = scan_dependencies(
        [datapoint],
        skip_cached=True,
        dedupe=False,
        cache_lookup=cache_lookup,
    )
    assert len(specs) == 1
    assert specs[0].dependency_name == "helpers.trim"


def test_build_dependency_dataset_batches(datapoint: Datapoint) -> None:
    specs = scan_dependencies([datapoint], skip_cached=False, dedupe=False)
    date_time = datetime(2025, 1, 1, 12, 0, 0)

    dataset = build_dependency_dataset(
        specs, date_time=date_time, variant="functional", batch_size=1
    )
    assert len(dataset) == 2

    first = dataset[0]
    metadata = cast(dict[str, Any], first.metadata)
    batch = cast(dict[str, Any], metadata["batch"])
    assert batch["index"] == 0
    assert metadata["variant"] == "functional"
    assert isinstance(metadata["payload"], DependencyPayload)
    assert metadata["date_time"] == "2025-01-01T12-00-00"


def test_build_dependency_dataset_empty() -> None:
    dataset = build_dependency_dataset([], date_time=datetime.now(UTC), variant=None)
    assert len(dataset) == 0
