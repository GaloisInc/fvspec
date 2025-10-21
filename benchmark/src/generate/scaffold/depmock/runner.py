"""Per-sample orchestration for dependency autoformalization."""

from __future__ import annotations

from datetime import UTC, datetime
import re
from pathlib import Path

from inspect_ai.solver import TaskState, solver, Solver, Generate

from generate.config import load_config
from generate.scaffold.dataset import Datapoint
from generate.scaffold.tools import utilio

from generate.scaffold.depmock.cache import (
    CacheRecord,
    CacheProvenance,
    compute_cache_key,
    load_cached_dependency,
    persist_generated_dependency,
    read_manifest,
    record_cache_hit,
)
from generate.scaffold.depmock.dataset import (
    DependencySampleSpec,
    payloads_from_datapoint,
)
from generate.scaffold.depmock.models import DependencyPayload, DependencyResult
from generate.scaffold.depmock.autoformalizer import (
    DependencyExecutionRequest,
    DependencyRecoverableError,
    DependencyFatalError,
)
from generate.scaffold.depmock.agent_runner import run_dependency_agent


_LEAN_IMPORT_PATTERN = re.compile(
    r"^\s*import\s+(Fvspec\.Deps\.[A-Za-z0-9_.]+)", re.MULTILINE
)

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.toml"
_CFG = load_config(_CONFIG_PATH)
_DEPMOCK_AGENT_MODEL = _CFG.agent.model
_DEPMOCK_AGENT_DISPLAY = _CFG.meta.display or "none"
_DEPMOCK_MAX_ATTEMPTS = 3


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


def _order_modules(entries: list[dict[str, str]]) -> list[dict[str, str]]:
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


def _aggregate_lean(
    deps_dir: Path, manifest: list[dict[str, object]]
) -> list[dict[str, str]]:
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
    *,
    max_attempts: int,
    model: str,
    display: str | None,
) -> dict[str, object]:
    deps_dir = sample_output_dir / "deps"
    deps_dir.mkdir(parents=True, exist_ok=True)

    prepared_records: list[CacheRecord] = []
    sample_id = sample_output_dir.name

    for index, payload in enumerate(payloads):
        record = load_cached_dependency(payload)
        if record is not None:
            record_cache_hit(record, sample_output_dir, source="cache")
            prepared_records.append(record)
            continue

        spec = DependencySampleSpec(
            payload=payload,
            cache_key=compute_cache_key(payload),
            datapoint_id=datapoint.id,
            datapoint_repo_id=datapoint.repo_id,
            datapoint_name=datapoint.pbt_name,
            dependency_index=index,
            sample_id=sample_id,
            cached=False,
        )

        diagnostics: str | None = None
        success_result: DependencyResult | None = None
        failure_error: DependencyRecoverableError | DependencyFatalError | None = None
        final_attempt = 0

        for attempt in range(1, max_attempts + 1):
            request = DependencyExecutionRequest(
                spec=spec,
                attempt=attempt,
                diagnostics=diagnostics,
            )
            try:
                success_result = run_dependency_agent(
                    request,
                    variant=variant,
                    model=model,
                    max_attempts=max_attempts,
                    display=display,
                )
            except DependencyRecoverableError as err:
                diagnostics = err.diagnostics
                failure_error = err
                success_result = None
                final_attempt = attempt
                if attempt >= max_attempts:
                    break
                continue
            except DependencyFatalError as err:
                failure_error = err
                success_result = None
                final_attempt = attempt
                break
            else:
                failure_error = None
                final_attempt = attempt
                break

        if success_result is not None:
            provenance = CacheProvenance(
                model=model,
                attempts=final_attempt,
                diagnostics=None,
            )
            record = persist_generated_dependency(
                payload,
                success_result,
                sample_output_dir,
                provenance=provenance,
            )
        else:
            failure_diagnostics = None
            if failure_error is not None:
                failure_diagnostics = failure_error.diagnostics or str(failure_error)

            stub = _stub_result(payload, variant)
            failed_result = DependencyResult(
                lean_module=stub.lean_module,
                lean_code=stub.lean_code,
                variant=stub.variant,
                status="failed",
                diagnostics=failure_diagnostics,
            )
            record = persist_generated_dependency(
                payload,
                failed_result,
                sample_output_dir,
            )

        prepared_records.append(record)

    manifest = read_manifest(deps_dir)
    aggregated = _aggregate_lean(deps_dir, manifest)
    ordered_modules = _order_modules(aggregated)
    body = "\n\n".join(item["code"] for item in ordered_modules if item["code"])
    if body:
        lean_text = f"namespace Fvspec.Deps\n\n{body}\n\nend Fvspec.Deps\n"
    else:
        lean_text = ""
    return {
        "manifest": manifest,
        "aggregated": ordered_modules,
        "lean_text": lean_text,
        "deps_dir": str(deps_dir),
        "variant": variant,
    }


@solver
def depmock_setup() -> Solver:
    """Prepare dependency payload stubs within the inspect_ai task loop."""

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
        meta = _process_payloads(
            datapoint,
            payloads,
            sample_output_dir,
            variant if isinstance(variant, str) else None,
            max_attempts=_DEPMOCK_MAX_ATTEMPTS,
            model=_DEPMOCK_AGENT_MODEL,
            display=_DEPMOCK_AGENT_DISPLAY,
        )
        state.metadata["depmock"] = meta
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
        max_attempts=_DEPMOCK_MAX_ATTEMPTS,
        model=_DEPMOCK_AGENT_MODEL,
        display=_DEPMOCK_AGENT_DISPLAY,
    )
