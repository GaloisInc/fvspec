"""Tests for formalize_impl setup orchestration."""

from pathlib import Path

from generate.scaffold.dataset import Datapoint
from generate.scaffold.formalize.impl.runner import (
    aggregate_impl_modules,
    order_dependency_modules,
    run_formalize_impl_for_sample,
)


def test_formalize_impl_setup_generates_stub(monkeypatch, tmp_path: Path):
    """Verify formalize_impl scaffolding writes stubs and manifest entries."""
    monkeypatch.setenv("IMPL_CACHE_ROOT", str(tmp_path / "cache"))

    def fake_sample_dir(_dt: str, sample_id: str, _variant: str) -> Path:
        path = tmp_path / "artifacts" / sample_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    from generate.scaffold.tools import utilio

    monkeypatch.setattr(utilio, "get_sample_output_dir", fake_sample_dir)

    datapoint = Datapoint(
        id=1,
        repo_id=1,
        name="test",
        code="def test(): pass",
        dep_names='["helper"]',
        deps='["def helper():\\n    return 1"]',
        source="/tmp/test.py",
        summary="",
        hash="hash123",
        summary_vector=None,
    )

    meta = run_formalize_impl_for_sample(
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
    assert "namespace Fvspec.Impl" in lean_text
    assert "helper" in lean_text
    payloads = meta.get("payloads")
    assert isinstance(payloads, list)
    assert payloads
    assert payloads[0]["dep_name"] == "helper"

    # Check that consolidated Impl.lean was written to sample output directory
    sample_dir = tmp_path / "artifacts" / "00001_test"
    impl_lean_file = sample_dir / "Impl.lean"
    assert impl_lean_file.exists()
    impl_content = impl_lean_file.read_text()
    assert "namespace Fvspec.Impl" in impl_content
    assert "helper" in impl_content.lower()

    # Check that manifest was written to sample output directory (not in impl/ subdirectory)
    manifest_path = sample_dir / "impl_manifest.jsonl"
    assert manifest_path.exists()

    # Verify no impl/ subdirectory was created
    impl_dir = sample_dir / "impl"
    assert not impl_dir.exists()


def test_order_modules_respects_import_dependencies(tmp_path: Path) -> None:
    """Ordered modules should reflect dependencies discovered in Lean imports."""
    impl_dir = tmp_path / "impl"
    impl_dir.mkdir(parents=True)

    (impl_dir / "First.lean").write_text("def firstValue : Nat := 1\n")
    (impl_dir / "Second.lean").write_text(
        "import Fvspec.Impl.First\n\ndef secondValue : Nat := firstValue + 1\n"
    )

    manifest = [
        {"module": "Second"},
        {"module": "First"},
    ]

    aggregated = aggregate_impl_modules(impl_dir, manifest)
    ordered = order_dependency_modules(aggregated)

    assert [entry["module"] for entry in ordered] == ["First", "Second"]
