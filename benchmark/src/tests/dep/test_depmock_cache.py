"""Tests for dependency cache management."""

from pathlib import Path

import pytest

from generate.scaffold.depmock import (
    DependencyPayload,
    DependencyResult,
    store_dependency_result,
    load_cached_dependency,
    write_dependency_artifact,
    persist_generated_dependency,
    record_cache_hit,
)
from generate.scaffold.depmock.cache import CacheProvenance, CacheRecord, read_manifest


@pytest.fixture
def payload() -> DependencyPayload:
    return DependencyPayload(
        dep_name="utils.normalize",
        python_source="""def normalize(x):\n    return x.strip().lower()""",
        source_hash="abc123",
        tags=("strings",),
        usage_example="normalize(' Foo ')",
    )


@pytest.fixture
def result() -> DependencyResult:
    return DependencyResult(
        lean_module="Normalize",
        lean_code="""@[simp] def normalize (s : String) : String := s.trim.lower\n""",
        variant="functional",
        status="ok",
        diagnostics=None,
    )


@pytest.fixture
def provenance() -> CacheProvenance:
    return CacheProvenance(model="anthropic/claude-sonnet", attempts=1)


def test_store_and_load_cached_dependency(tmp_path: Path, payload, result, provenance):
    cache_root = tmp_path / "cache"
    record = store_dependency_result(
        payload, result, cache_root=cache_root, provenance=provenance
    )

    assert record.lean_path.exists()
    metadata_path = record.directory / "metadata.json"
    assert metadata_path.exists()

    loaded = load_cached_dependency(payload, cache_root=cache_root)
    assert loaded is not None
    assert loaded.metadata.lean_module == result.lean_module
    assert loaded.lean_path.read_text() == result.lean_code
    assert loaded.metadata.provenance is not None
    assert loaded.metadata.provenance.model == "anthropic/claude-sonnet"


def test_write_dependency_artifact_updates_manifest(
    tmp_path: Path, payload, result, provenance
):
    cache_root = tmp_path / "cache"
    run_dir = tmp_path / "run" / "sample_001"
    run_dir.mkdir(parents=True)

    record = store_dependency_result(
        payload, result, cache_root=cache_root, provenance=provenance
    )
    target = write_dependency_artifact(record, run_dir, source="generated")

    assert target.exists()
    manifest_entries = read_manifest(run_dir / "deps")
    assert len(manifest_entries) == 1
    assert manifest_entries[0]["module"] == result.lean_module
    assert manifest_entries[0]["source"] == "generated"

    # Writing again should replace the entry instead of duplicating it
    write_dependency_artifact(record, run_dir, source="cache")
    updated_entries = read_manifest(run_dir / "deps")
    assert len(updated_entries) == 1
    assert updated_entries[0]["source"] == "cache"
    assert updated_entries[0]["model"] == "anthropic/claude-sonnet"


def test_persist_generated_dependency_writes_cache_and_run(
    tmp_path: Path, payload, result, provenance
):
    run_dir = tmp_path / "run" / "sample_002"
    run_dir.mkdir(parents=True)
    cache_root = tmp_path / "cache"

    record = persist_generated_dependency(
        payload,
        result,
        run_dir,
        cache_root=cache_root,
        provenance=provenance,
    )

    assert isinstance(record, CacheRecord)
    assert record.lean_path.exists()
    sample_file = run_dir / "deps" / f"{result.lean_module}.lean"
    assert sample_file.exists()

    manifest_entries = read_manifest(run_dir / "deps")
    assert manifest_entries[0]["source"] == "generated"


def test_record_cache_hit(tmp_path: Path, payload, result):
    cache_root = tmp_path / "cache"
    run_dir = tmp_path / "run" / "sample_003"
    run_dir.mkdir(parents=True)

    record = store_dependency_result(payload, result, cache_root=cache_root)
    record_cache_hit(record, run_dir, source="cache")

    manifest = read_manifest(run_dir / "deps")
    assert manifest[0]["cache_key"] == record.key
    assert manifest[0]["source"] == "cache"
