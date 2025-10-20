"""Per-sample orchestration for dependency autoformalization."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from inspect_ai.solver import TaskState, solver, Solver, Generate

from benchmark.scaffold.dataset import Datapoint
from benchmark.scaffold.tools import utilio

from .cache import (
    CacheRecord,
    load_cached_dependency,
    persist_generated_dependency,
    read_manifest,
    record_cache_hit,
)
from .models import DependencyPayload, DependencyResult


def _payloads_from_datapoint(datapoint: Datapoint) -> list[DependencyPayload]:
    deps = datapoint.deps or []
    payloads: list[DependencyPayload] = []

    for idx, source in enumerate(deps):
        name = None
        if idx < len(datapoint.dep_names):
            name = datapoint.dep_names[idx]
        dep_name = name or f"dependency_{idx + 1}"
        payloads.append(
            DependencyPayload(
                dep_name=dep_name,
                python_source=source,
                tags=[],
                usage_example=None,
            )
        )
    return payloads


def _stub_result(payload: DependencyPayload, variant: str | None) -> DependencyResult:
    module_name = payload.lean_module_name
    lean_module = f"Fvspec.Deps.{module_name}"
    original = payload.python_source.strip()
    lean_code = (
        "namespace Fvspec.Deps\n\n"
        f"/-- Autoformalization stub for `{payload.dep_name}`. \n"
        "TODO: replace with generated Lean code. -/\n"
        "-- Original Python:\n/-\n"
        f"{original}\n"
        "-/\n\n"
        f"def {module_name}_stub : Unit := sorry\n\n"
        "end Fvspec.Deps\n"
    )
    return DependencyResult(
        lean_module=lean_module,
        lean_code=lean_code,
        variant=variant,
        status="stub",
        diagnostics="autoformalizer not yet executed",
    )


def _aggregate_lean(deps_dir: Path, manifest: list[dict[str, object]]) -> list[dict[str, str]]:
    aggregated: list[dict[str, str]] = []
    for entry in manifest:
        module = entry.get("module")
        if not isinstance(module, str):
            continue
        lean_path = deps_dir / f"{module}.lean"
        if lean_path.exists():
            aggregated.append({"module": module, "path": str(lean_path), "code": lean_path.read_text()})
    return aggregated


@solver
def depmock_setup() -> Solver:
    async def run(state: TaskState, generate: Generate) -> TaskState:
        datapoint = state.metadata.get("datapoint")
        if not isinstance(datapoint, Datapoint):
            return state

        payloads = _payloads_from_datapoint(datapoint)
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
        deps_dir = sample_output_dir / "deps"
        deps_dir.mkdir(parents=True, exist_ok=True)

        prepared_records: list[CacheRecord] = []

        for payload in payloads:
            record = load_cached_dependency(payload)
            if record is not None:
                record_cache_hit(record, sample_output_dir, source="cache")
                prepared_records.append(record)
                continue

            stub_result = _stub_result(payload, variant if isinstance(variant, str) else None)
            record = persist_generated_dependency(payload, stub_result, sample_output_dir)
            prepared_records.append(record)

        manifest = read_manifest(deps_dir)
        aggregated = _aggregate_lean(deps_dir, manifest)
        lean_text = "\n\n".join(item["code"] for item in aggregated)
        state.metadata["depmock"] = {
            "manifest": manifest,
            "aggregated": aggregated,
            "lean_text": lean_text,
            "deps_dir": str(deps_dir),
            "variant": variant,
        }
        return state

    return run
