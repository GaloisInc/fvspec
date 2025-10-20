"""Tests for depmock setup orchestration."""

from pathlib import Path

from benchmark.scaffold.depmock.runner import run_depmock_for_sample
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

    meta = run_depmock_for_sample(
        datapoint,
        date_time="2025-01-01T00-00-00",
        variant="control-functional",
        sample_id="00001_test",
        path_variant="control-functional",
    )
    assert meta is not None
    assert meta["manifest"], "expected manifest entries"
    lean_text = meta.get("lean_text")
    assert isinstance(lean_text, str)
    assert "namespace Fvspec.Deps" in lean_text
    assert "helper" in lean_text

    deps_dir = tmp_path / "artifacts" / "00001_test" / "deps"
    manifest_path = deps_dir / "manifest.jsonl"
    assert manifest_path.exists()
    deps_lean = deps_dir / "Helper.lean"
    assert deps_lean.exists()
    file_text = deps_lean.read_text()
    assert "Autoformalization stub" in file_text
    assert "namespace" not in file_text
