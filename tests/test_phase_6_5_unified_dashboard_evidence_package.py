from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

import build_enterprise_unified_dashboard_evidence_package as launcher
from src.dividend_bot.enterprise_unified_dashboard_evidence_package import (
    MANIFEST_NAME,
    build_evidence_manifest,
    build_unified_dashboard_evidence_package,
    write_deterministic_evidence_package,
)


ARTIFACTS = ("acceptance.json", "cycle.json", "acceptance.html")


def _write_artifacts(results: Path) -> None:
    results.mkdir(parents=True, exist_ok=True)
    for index, name in enumerate(ARTIFACTS):
        (results / name).write_text(f"evidence-{index}\n", encoding="utf-8")


def _dependencies(results: Path, *, acceptance_status: str = "PASSED"):
    def accept(**kwargs):
        _write_artifacts(results)
        return {
            "acceptance_status": acceptance_status,
            "warnings": ["safe empty Swing journal"],
            "errors": [],
        }

    def preview(**kwargs):
        return {"path": str(results / "acceptance.html"), "verification_status": "PASSED"}

    return accept, preview


def test_verified_evidence_builds_passing_package(tmp_path: Path) -> None:
    results = tmp_path / "results"
    accept, preview = _dependencies(results)
    report = build_unified_dashboard_evidence_package(
        root_dir=tmp_path,
        artifact_names=ARTIFACTS,
        acceptance_runner=accept,
        preview_generator=preview,
    )
    assert report["package_status"] == "PASSED"
    assert report["artifact_count"] == 3
    assert Path(report["package"]["path"]).is_file()


def test_manifest_contains_size_and_sha256_for_every_file(tmp_path: Path) -> None:
    _write_artifacts(tmp_path)
    manifest, errors = build_evidence_manifest(
        results_dir=tmp_path, artifact_names=ARTIFACTS
    )
    assert errors == []
    assert manifest["artifact_count"] == 3
    assert all(len(row["sha256"]) == 64 for row in manifest["artifacts"].values())


def test_missing_artifact_fails_closed_without_zip(tmp_path: Path) -> None:
    results = tmp_path / "results"
    accept, preview = _dependencies(results)
    report = build_unified_dashboard_evidence_package(
        root_dir=tmp_path,
        artifact_names=(*ARTIFACTS, "missing.json"),
        acceptance_runner=accept,
        preview_generator=preview,
    )
    assert report["package_status"] == "FAILED"
    assert report["package"] == {}
    assert any("artifact is missing" in item for item in report["errors"])


def test_failed_acceptance_skips_preview_and_packaging(tmp_path: Path) -> None:
    results = tmp_path / "results"
    calls: list[str] = []
    accept, _ = _dependencies(results, acceptance_status="FAILED")
    def preview(**kwargs):
        calls.append("preview")
        return {}
    report = build_unified_dashboard_evidence_package(
        root_dir=tmp_path,
        artifact_names=ARTIFACTS,
        acceptance_runner=accept,
        preview_generator=preview,
    )
    assert calls == []
    assert report["package_status"] == "FAILED"
    assert report["verification_status"] == "NOT_RUN"


def test_failed_ui_verification_prevents_packaging(tmp_path: Path) -> None:
    results = tmp_path / "results"
    accept, _ = _dependencies(results)
    report = build_unified_dashboard_evidence_package(
        root_dir=tmp_path,
        artifact_names=ARTIFACTS,
        acceptance_runner=accept,
        preview_generator=lambda **kwargs: {"verification_status": "FAILED"},
    )
    assert report["package_status"] == "FAILED"
    assert report["package"] == {}


def test_package_uses_flat_safe_names_and_includes_manifest(tmp_path: Path) -> None:
    _write_artifacts(tmp_path)
    manifest, errors = build_evidence_manifest(
        results_dir=tmp_path, artifact_names=ARTIFACTS
    )
    assert errors == []
    package = write_deterministic_evidence_package(
        results_dir=tmp_path, manifest=manifest
    )
    with ZipFile(package["path"]) as archive:
        assert sorted(archive.namelist()) == sorted((*ARTIFACTS, MANIFEST_NAME))
        assert all("/" not in name and "\\" not in name for name in archive.namelist())


def test_identical_inputs_produce_identical_package_hash(tmp_path: Path) -> None:
    _write_artifacts(tmp_path)
    manifest, _ = build_evidence_manifest(
        results_dir=tmp_path, artifact_names=ARTIFACTS
    )
    first = write_deterministic_evidence_package(
        results_dir=tmp_path, manifest=manifest, package_path=tmp_path / "one.zip"
    )
    second = write_deterministic_evidence_package(
        results_dir=tmp_path, manifest=manifest, package_path=tmp_path / "two.zip"
    )
    assert first["sha256"] == second["sha256"]


def test_traversal_artifact_name_is_rejected(tmp_path: Path) -> None:
    _write_artifacts(tmp_path)
    _, errors = build_evidence_manifest(
        results_dir=tmp_path, artifact_names=("../acceptance.json",)
    )
    assert any("flat local filename" in item for item in errors)


def test_package_report_preserves_paper_only_safety(tmp_path: Path) -> None:
    results = tmp_path / "results"
    accept, preview = _dependencies(results)
    report = build_unified_dashboard_evidence_package(
        root_dir=tmp_path,
        artifact_names=ARTIFACTS,
        acceptance_runner=accept,
        preview_generator=preview,
    )
    assert report["paper_trade_mode"] is True
    assert report["live_trading_enabled"] is False
    assert report["broker_execution_enabled"] is False
    assert report["capital_movement_enabled"] is False


def test_launcher_returns_expected_exit_codes(monkeypatch, capsys) -> None:
    passing = {
        "package_status": "PASSED",
        "acceptance_status": "PASSED",
        "verification_status": "PASSED",
        "artifact_count": 13,
        "package": {"path": "evidence.zip", "sha256": "a" * 64},
        "errors": [],
        "warnings": [],
    }
    monkeypatch.setattr(
        launcher, "build_unified_dashboard_evidence_package", lambda **kwargs: passing
    )
    assert launcher.main([]) == 0
    assert "Package status: PASSED" in capsys.readouterr().out
    monkeypatch.setattr(
        launcher,
        "build_unified_dashboard_evidence_package",
        lambda **kwargs: {**passing, "package_status": "FAILED", "errors": ["failed"]},
    )
    assert launcher.main([]) == 1
