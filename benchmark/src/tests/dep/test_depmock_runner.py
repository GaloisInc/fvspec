"""Tests for depmock setup orchestration."""

from pathlib import Path

from generate.scaffold.depmock.runner import (
    run_depmock_for_sample,
    _aggregate_lean,
    _order_modules,
)
from generate.scaffold.dataset import Datapoint


def test_depmock_setup_generates_stub(monkeypatch, tmp_path: Path):
    """Verify depmock scaffolding writes stubs and manifest entries."""
    monkeypatch.setenv("DEPMOCK_CACHE_ROOT", str(tmp_path / "cache"))

    def fake_sample_dir(_dt: str, sample_id: str, _variant: str) -> Path:
        path = tmp_path / "artifacts" / sample_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    from generate.scaffold.tools import utilio

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
    payloads = meta.get("payloads")
    assert isinstance(payloads, list) and payloads
    assert payloads[0]["dep_name"] == "helper"

    deps_dir = tmp_path / "artifacts" / "00001_test" / "deps"
    manifest_path = deps_dir / "manifest.jsonl"
    assert manifest_path.exists()
    deps_lean = deps_dir / "Helper.lean"
    assert deps_lean.exists()
    file_text = deps_lean.read_text()
    assert "Autoformalization stub" in file_text
    assert "namespace" not in file_text


def test_order_modules_respects_import_dependencies(tmp_path: Path) -> None:
    """Ordered modules should reflect dependencies discovered in Lean imports."""
    deps_dir = tmp_path / "deps"
    deps_dir.mkdir(parents=True)

    (deps_dir / "First.lean").write_text("def firstValue : Nat := 1\n")
    (deps_dir / "Second.lean").write_text(
        "import Fvspec.Deps.First\n\ndef secondValue : Nat := firstValue + 1\n"
    )

    manifest = [
        {"module": "Second"},
        {"module": "First"},
    ]

    aggregated = _aggregate_lean(deps_dir, manifest)
    ordered = _order_modules(aggregated)

    assert [entry["module"] for entry in ordered] == ["First", "Second"]
