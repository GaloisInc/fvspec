"""Cache management for dependency autoformalization outputs."""

from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import json
from pydantic import BaseModel, Field

from generate.scaffold.depmock.models import (
    DependencyPayload,
    DependencyResult,
)

CACHE_SCHEMA_VERSION = 3


def _find_project_root(start: Path | None = None) -> Path:
    """Locate the project root (directory containing pyproject.toml)."""
    current = start or Path.cwd()
    while not (current / "pyproject.toml").exists():
        if current == current.parent:
            raise FileNotFoundError(
                "Could not locate project root (missing pyproject.toml)"
            )
        current = current.parent
    return current


def _cache_root() -> Path:
    override = os.environ.get("DEPMOCK_CACHE_ROOT")
    if override:
        root = Path(override)
    else:
        root = _find_project_root() / "artifacts" / "depcache"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _sample_deps_dir(run_sample_dir: Path) -> Path:
    deps_dir = run_sample_dir / "deps"
    deps_dir.mkdir(parents=True, exist_ok=True)
    return deps_dir


def compute_cache_key(payload: DependencyPayload) -> str:
    """Compute a stable cache key for a dependency payload."""
    if payload.source_hash:
        return payload.source_hash
    digest = hashlib.sha256(payload.python_source.encode("utf-8")).hexdigest()
    return digest


class CacheProvenance(BaseModel):
    """Provenance metadata for generated dependency artifacts."""

    model: str | None = None
    run_id: str | None = None
    attempts: int | None = None
    diagnostics: str | None = None
    generated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class CacheMetadata(BaseModel):
    """Metadata persisted alongside cached Lean modules."""

    dep_name: str
    lean_module: str
    source_hash: str
    variant: str | None = None
    status: Literal["ok", "failed", "stub"] = "ok"
    diagnostics: str | None = None
    schema_version: int = Field(default=CACHE_SCHEMA_VERSION)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    provenance: CacheProvenance | None = None


@dataclass(frozen=True)
class CacheRecord:
    """A cached dependency artifact."""

    key: str
    directory: Path
    lean_path: Path
    metadata: CacheMetadata

    def to_manifest_entry(
        self, source: Literal["cache", "generated"]
    ) -> dict[str, object]:
        """Convert the cache record into a manifest entry for run artifacts."""
        return {
            "module": self.metadata.lean_module,
            "dep_name": self.metadata.dep_name,
            "source": source,
            "cache_key": self.key,
            "variant": self.metadata.variant,
            "source_hash": self.metadata.source_hash,
            "status": self.metadata.status,
            "diagnostics": self.metadata.diagnostics,
            "cache_path": str(self.lean_path),
            "timestamp": datetime.now(UTC).isoformat(),
            "model": self.metadata.provenance.model
            if self.metadata.provenance
            else None,
            "generated_at": (
                self.metadata.provenance.generated_at
                if self.metadata.provenance
                else self.metadata.created_at
            ),
        }


def _entry_dir(key: str, root: Path | None = None) -> Path:
    base = root or _cache_root()
    entry = base / key
    entry.mkdir(parents=True, exist_ok=True)
    return entry


def store_dependency_result(
    payload: DependencyPayload,
    result: DependencyResult,
    *,
    cache_root: Path | None = None,
    provenance: CacheProvenance | None = None,
) -> CacheRecord:
    """Persist a dependency result to the global cache."""
    key = compute_cache_key(payload)
    entry = _entry_dir(key, cache_root)
    lean_path = entry / f"{result.lean_module}.lean"
    lean_path.write_text(result.lean_code)

    metadata = CacheMetadata(
        dep_name=payload.dep_name,
        lean_module=result.lean_module,
        source_hash=key,
        variant=result.variant,
        status=result.status,
        diagnostics=result.diagnostics,
        provenance=provenance,
    )
    (entry / "metadata.json").write_text(metadata.model_dump_json(indent=2))
    return CacheRecord(key=key, directory=entry, lean_path=lean_path, metadata=metadata)


def load_cached_dependency(
    payload: DependencyPayload, *, cache_root: Path | None = None
) -> CacheRecord | None:
    """Load a cached dependency result if it exists."""
    key = compute_cache_key(payload)
    base = cache_root or _cache_root()
    entry = base / key
    metadata_path = entry / "metadata.json"
    if not metadata_path.exists():
        return None
    metadata = CacheMetadata.model_validate_json(metadata_path.read_text())
    if metadata.schema_version < CACHE_SCHEMA_VERSION:
        return None
    lean_path = entry / f"{metadata.lean_module}.lean"
    if not lean_path.exists():
        return None
    return CacheRecord(key=key, directory=entry, lean_path=lean_path, metadata=metadata)


def clear_cache(cache_root: Path | None = None) -> Path:
    """Delete all cached dependency artifacts."""
    root = cache_root or _cache_root()
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _manifest_path(deps_dir: Path) -> Path:
    return deps_dir / "manifest.jsonl"


def read_manifest(deps_dir: Path) -> list[dict[str, object]]:
    """Read manifest entries, deduplicating by module (last entry wins)."""
    path = _manifest_path(deps_dir)
    if not path.exists():
        return []

    entries: list[dict[str, object]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                entries.append(entry)
    except FileNotFoundError:
        return []

    merged: dict[str, dict[str, object]] = {}
    order: list[str] = []
    for entry in entries:
        module = entry.get("module")
        if not isinstance(module, str):
            continue
        if module in merged:
            order.remove(module)
        order.append(module)
        merged[module] = entry
    return [merged[module] for module in order]


def _append_manifest_entry(deps_dir: Path, entry: dict[str, object]) -> None:
    path = _manifest_path(deps_dir)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry))
        fh.write("\n")


def write_dependency_artifact(
    record: CacheRecord,
    run_sample_dir: Path,
    *,
    source: Literal["cache", "generated"],
) -> Path:
    """Copy a cached dependency Lean file into a run directory and update manifest."""
    deps_dir = _sample_deps_dir(run_sample_dir)
    target = deps_dir / f"{record.metadata.lean_module}.lean"
    shutil.copy2(record.lean_path, target)

    entry = record.to_manifest_entry(source=source)
    _append_manifest_entry(deps_dir, entry)
    return target


def persist_generated_dependency(
    payload: DependencyPayload,
    result: DependencyResult,
    run_sample_dir: Path,
    *,
    cache_root: Path | None = None,
    provenance: CacheProvenance | None = None,
) -> CacheRecord:
    """Persist a freshly generated dependency to cache and run artifact directory."""
    record = store_dependency_result(
        payload,
        result,
        cache_root=cache_root or _cache_root(),
        provenance=provenance,
    )
    write_dependency_artifact(record, run_sample_dir, source="generated")
    return record


def record_cache_hit(
    record: CacheRecord, run_sample_dir: Path, *, source: Literal["cache", "generated"]
) -> Path:
    """Copy a cache record into the run directory without creating a new cache entry."""
    return write_dependency_artifact(record, run_sample_dir, source=source)
