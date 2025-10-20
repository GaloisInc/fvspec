"""Tests for depmock setup orchestration."""

import asyncio
from pathlib import Path

from inspect_ai.model import ModelName
from inspect_ai.solver import TaskState

from benchmark.scaffold.depmock.runner import depmock_setup
from benchmark.scaffold.dataset import Datapoint


def test_depmock_setup_generates_stub(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("DEPMOCK_CACHE_ROOT", str(tmp_path / "cache"))

    def fake_sample_dir(_dt: str, sample_id: str, _variant: str) -> Path:
        path = tmp_path / "artifacts" / sample_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    from benchmark.scaffold.tools import utilio

    monkeypatch.setattr(utilio, "get_sample_output_dir", fake_sample_dir)

    datapoint = Datapoint(
        id=1,
        repo_id=1,
        pbt_name="test",
        pbt="def test(): pass",
        dep_names=["helper"],
        deps=["def helper():\n    return 1"],
        source="/tmp/test.py",
        summary="",
        hash="hash123",
        summary_vector=None,
    )

    state = TaskState(
        model=ModelName("mock/model"),
        sample_id="00001_test",
        epoch=0,
        input="",
        messages=[],
        metadata={
            "datapoint": datapoint,
            "date_time": "2025-01-01T00-00-00",
            "variant": "control-functional",
        },
    )

    async def runner() -> TaskState:
        async def dummy_generate(*args, **kwargs):  # pragma: no cover - unused
            return state

        solver = depmock_setup()
        return await solver(state, dummy_generate)

    new_state = asyncio.run(runner())

    meta = new_state.metadata.get("depmock")
    assert meta is not None
    assert meta["manifest"], "expected manifest entries"
    assert "helper" in meta["lean_text"], "stub Lean text should mention helper"

    deps_dir = tmp_path / "artifacts" / "00001_test" / "deps"
    manifest_path = deps_dir / "manifest.jsonl"
    assert manifest_path.exists()
    deps_lean = (tmp_path / "artifacts" / "00001_test" / "deps" / "Fvspec.Deps.Helper.lean")
    assert deps_lean.exists()
    assert "Autoformalization stub" in deps_lean.read_text()
