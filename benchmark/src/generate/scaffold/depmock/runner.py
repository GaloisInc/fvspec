"""Per-sample orchestration for dependency autoformalization."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from inspect_ai.solver import Generate, Solver, TaskState, solver

from generate.scaffold.dataset import JSONLDatapoint as Datapoint
from generate.scaffold.depmock.cache import (
    CacheRecord,
    _cache_root,
    load_cached_dependency,
    store_dependency_result,
)
from generate.scaffold.depmock.dataset import payloads_from_datapoint
from generate.scaffold.depmock.models import DependencyPayload, DependencyResult
from generate.scaffold.tools import utilio

_LEAN_IMPORT_PATTERN = re.compile(
    r"^\s*import\s+(Fvspec\.Deps\.[A-Za-z0-9_.]+)", re.MULTILINE
)


def _extract_module_dependencies(
    module: str, code: str, available: set[str]
) -> set[str]:
    """Extract dependency modules appearing in Lean import statements."""
    dependencies: set[str] = set()
    for match in _LEAN_IMPORT_PATTERN.findall(code):
        if match.startswith("Fvspec.Deps."):
            candidate = match.removeprefix("Fvspec.Deps.")
        else:
            continue
        # When the candidate contains namespace separators, take the final segment
        # because manifest modules are stored as sanitized basenames.
        basename = candidate.split(".")[-1]
        if basename != module and basename in available:
            dependencies.add(basename)
    return dependencies


def order_dependency_modules(entries: list[dict[str, str]]) -> list[dict[str, str]]:
    """Topologically order Lean modules according to internal import graph."""
    modules = {
        entry["module"]: entry
        for entry in entries
        if isinstance(entry.get("module"), str)
    }
    available = set(modules.keys())
    dependency_graph = {
        module: _extract_module_dependencies(module, entry.get("code", ""), available)
        for module, entry in modules.items()
    }

    ordered: list[dict[str, str]] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def dfs(node: str) -> None:
        if node in visited:
            return
        if node in visiting:
            raise ValueError(f"Cycle detected involving module '{node}'")
        visiting.add(node)
        for dep in dependency_graph.get(node, set()):
            dfs(dep)
        visiting.remove(node)
        visited.add(node)
        ordered.append(modules[node])

    try:
        for module_name in modules:
            dfs(module_name)
    except ValueError:
        # Fall back to original order if a cycle is encountered.
        return entries

    return ordered


def _stub_result(payload: DependencyPayload, variant: str | None) -> DependencyResult:
    module_name = payload.lean_module_name
    original = payload.python_source.strip()
    lean_code = (
        f"/-- Autoformalization stub for `{payload.dep_name}`.\n"
        "TODO: replace with generated Lean code. -/\n"
        "-- Original Python:\n/-\n"
        f"{original}\n"
        "-/\n\n"
        f"def {module_name}_stub : Unit := ()\n"
    )
    return DependencyResult(
        lean_module=module_name,
        lean_code=lean_code,
        variant=variant,
        status="stub",
        diagnostics="autoformalizer not yet executed",
    )


def aggregate_dependency_modules(
    deps_dir: Path, manifest: list[dict[str, object]]
) -> list[dict[str, str]]:
    """Load Lean module sources listed in the manifest from the deps directory."""
    aggregated: list[dict[str, str]] = []
    for entry in manifest:
        module = entry.get("module")
        if not isinstance(module, str):
            continue
        lean_path = deps_dir / f"{module}.lean"
        if lean_path.exists():
            aggregated.append(
                {
                    "module": module,
                    "path": str(lean_path),
                    "code": lean_path.read_text().strip(),
                }
            )
    return aggregated


def _process_payloads(
    datapoint: Datapoint,
    payloads: list[DependencyPayload],
    sample_output_dir: Path,
    variant: str | None,
) -> dict[str, object]:
    prepared_records: list[CacheRecord] = []
    payload_dumps: list[dict[str, object]] = []

    # Load or generate records for each payload
    for payload in payloads:
        record = load_cached_dependency(payload)
        if record is None:
            stub_result = _stub_result(payload, variant)
            record = store_dependency_result(
                payload,
                stub_result,
                cache_root=_cache_root(),
                provenance=None,
            )

        prepared_records.append(record)
        payload_dumps.append(payload.model_dump())

    # Build aggregated modules directly from records in memory
    aggregated: list[dict[str, str]] = []
    manifest: list[dict[str, object]] = []

    for record in prepared_records:
        lean_code = record.lean_path.read_text().strip()
        aggregated.append(
            {
                "module": record.metadata.lean_module,
                "path": str(record.lean_path),
                "code": lean_code,
            }
        )
        manifest.append(record.to_manifest_entry(source="cache"))

    # Order modules by dependencies
    ordered_modules = order_dependency_modules(aggregated)
    body = "\n\n".join(item["code"] for item in ordered_modules if item["code"])
    if body:
        lean_text = f"namespace Fvspec.Deps\n\n{body}\n\nend Fvspec.Deps\n"
    else:
        lean_text = ""

    # Write consolidated Deps.lean to sample output directory
    deps_lean_file = sample_output_dir / "Deps.lean"
    deps_lean_file.write_text(lean_text if lean_text else "-- No dependencies\n")

    # Write manifest to sample output directory (not in deps/ subdirectory)
    manifest_file = sample_output_dir / "deps_manifest.jsonl"
    with manifest_file.open("w", encoding="utf-8") as f:
        for entry in manifest:
            f.write(json.dumps(entry) + "\n")

    return {
        "manifest": manifest,
        "aggregated": ordered_modules,
        "lean_text": lean_text,
        "deps_lean_file": str(deps_lean_file),
        "manifest_file": str(manifest_file),
        "variant": variant,
        "payloads": payload_dumps,
    }


@solver
def depmock_setup() -> Solver:
    """Prepare dependency directories and metadata within the inspect_ai task loop.

    This solver no longer creates stub implementations. Instead, it:
    1. Creates the deps/ directory structure
    2. Initializes an empty Deps.lean
    3. Stores dependency metadata for tools to use later

    The actual dependency formalization happens when the agent calls the
    per-dependency tools registered by register_dependency_tools().
    """

    async def run(state: TaskState, generate: Generate) -> TaskState:
        datapoint = state.metadata.get("datapoint")
        if not isinstance(datapoint, Datapoint):
            return state

        payloads = payloads_from_datapoint(datapoint)
        if not payloads:
            state.metadata["depmock"] = {"manifest": [], "lean_text": ""}
            return state

        date_time = state.metadata.get("date_time")
        variant = state.metadata.get("variant") or state.metadata.get("prompt_variant")
        if not isinstance(date_time, str):
            date_time = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")

        sample_output_dir = utilio.get_sample_output_dir(
            date_time, str(state.sample_id), variant or "default"
        )

        # Create deps/ directory
        deps_dir = sample_output_dir / "deps"
        deps_dir.mkdir(parents=True, exist_ok=True)

        # Initialize empty Deps.lean (will be populated as tools are called)
        deps_lean_file = sample_output_dir / "Deps.lean"
        deps_lean_file.write_text(
            "-- Dependencies will be added here as they are formalized\n"
        )

        # Store metadata for later use
        state.metadata["depmock"] = {
            "manifest": [],
            "lean_text": "",
            "deps_dir": str(deps_dir),
            "variant": variant,
            "payload_count": len(payloads),
        }

        return state

    return run


def run_depmock_for_sample(
    datapoint: Datapoint,
    *,
    date_time: str,
    variant: str | None = None,
    sample_id: str | None = None,
    path_variant: str | None = None,
) -> dict[str, object]:
    """Run depmock processing for a single datapoint outside the task loop."""
    payloads = payloads_from_datapoint(datapoint)
    sample_id_str = sample_id or f"{datapoint.id:05d}_{datapoint.pbt_name}"
    sample_output_dir = utilio.get_sample_output_dir(
        date_time, sample_id_str, path_variant or variant or "default"
    )

    if not payloads:
        return {
            "manifest": [],
            "aggregated": [],
            "lean_text": "",
            "deps_dir": str(sample_output_dir / "deps"),
            "variant": variant,
        }

    return _process_payloads(
        datapoint,
        payloads,
        sample_output_dir,
        variant,
    )
