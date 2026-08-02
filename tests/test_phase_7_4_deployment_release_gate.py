from __future__ import annotations

import json
from pathlib import Path

import validate_enterprise_deployment_release as launcher
from src.dividend_bot.enterprise_deployment_release_gate import (
    build_documentation_freeze_manifest,
    validate_and_write_deployment_release,
    validate_deployment_release,
)


FREEZE_FILES = ("docs/architecture.md", "src/host.py")


def _populate(root: Path, *, soak_status: str = "PASSED") -> Path:
    for name in FREEZE_FILES:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"frozen {name}\n", encoding="utf-8")
    results = root / "results"
    results.mkdir()
    safety = {
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
    }
    reports = {
        "enterprise_unified_dashboard_evidence_package.json": {
            **safety,
            "package_status": "PASSED",
            "acceptance_status": "PASSED",
            "verification_status": "PASSED",
        },
        "enterprise_production_hardening_audit.json": {
            **safety,
            "hardening_status": "READY_WITH_WARNINGS",
        },
        "enterprise_backup_recovery_validation.json": {
            **safety,
            "recovery_status": "PASSED",
            "restore_test_status": "PASSED",
        },
        "enterprise_stability_soak_validation.json": {
            **safety,
            "soak_status": soak_status,
        },
    }
    for name, payload in reports.items():
        (results / name).write_text(json.dumps(payload), encoding="utf-8")
    return results


def test_all_passed_evidence_is_ready(tmp_path: Path) -> None:
    results = _populate(tmp_path)
    report = validate_deployment_release(
        root_dir=tmp_path, results_dir=results, freeze_files=FREEZE_FILES
    )
    assert report["release_status"] == "READY"
    assert report["documentation_frozen"] is True
    assert report["errors"] == []


def test_incomplete_soak_is_in_progress_not_blocked(tmp_path: Path) -> None:
    results = _populate(tmp_path, soak_status="IN_PROGRESS")
    report = validate_deployment_release(
        root_dir=tmp_path, results_dir=results, freeze_files=FREEZE_FILES
    )
    assert report["release_status"] == "IN_PROGRESS"
    assert report["errors"] == []
    assert any("soak is still in progress" in item for item in report["warnings"])


def test_failed_soak_blocks_release(tmp_path: Path) -> None:
    results = _populate(tmp_path, soak_status="FAILED")
    report = validate_deployment_release(
        root_dir=tmp_path, results_dir=results, freeze_files=FREEZE_FILES
    )
    assert report["release_status"] == "BLOCKED"
    assert any("soak_status=FAILED" in item for item in report["errors"])


def test_failed_recovery_or_acceptance_blocks_release(tmp_path: Path) -> None:
    results = _populate(tmp_path)
    recovery_path = results / "enterprise_backup_recovery_validation.json"
    recovery = json.loads(recovery_path.read_text(encoding="utf-8"))
    recovery["restore_test_status"] = "FAILED"
    recovery_path.write_text(json.dumps(recovery), encoding="utf-8")
    report = validate_deployment_release(
        root_dir=tmp_path, results_dir=results, freeze_files=FREEZE_FILES
    )
    assert report["release_status"] == "BLOCKED"
    assert any("restore_test_status=FAILED" in item for item in report["errors"])


def test_unsafe_report_blocks_release(tmp_path: Path) -> None:
    results = _populate(tmp_path)
    package_path = results / "enterprise_unified_dashboard_evidence_package.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    package["live_trading_enabled"] = True
    package_path.write_text(json.dumps(package), encoding="utf-8")
    report = validate_deployment_release(
        root_dir=tmp_path, results_dir=results, freeze_files=FREEZE_FILES
    )
    assert report["release_status"] == "BLOCKED"
    assert any("live_trading_enabled must be False" in item for item in report["errors"])


def test_freeze_manifest_records_size_and_sha256(tmp_path: Path) -> None:
    _populate(tmp_path)
    manifest, errors = build_documentation_freeze_manifest(
        root_dir=tmp_path, freeze_files=FREEZE_FILES
    )
    assert errors == []
    assert manifest["freeze_status"] == "FROZEN"
    assert manifest["file_count"] == 2
    assert all(len(row["sha256"]) == 64 for row in manifest["files"].values())


def test_missing_or_unsafe_freeze_file_blocks_release(tmp_path: Path) -> None:
    results = _populate(tmp_path)
    report = validate_deployment_release(
        root_dir=tmp_path,
        results_dir=results,
        freeze_files=(*FREEZE_FILES, "../outside"),
    )
    assert report["release_status"] == "BLOCKED"
    assert report["documentation_frozen"] is False
    assert any("freeze path is unsafe" in item for item in report["errors"])


def test_missing_gate_report_blocks_release(tmp_path: Path) -> None:
    results = _populate(tmp_path)
    (results / "enterprise_stability_soak_validation.json").unlink()
    report = validate_deployment_release(
        root_dir=tmp_path, results_dir=results, freeze_files=FREEZE_FILES
    )
    assert report["release_status"] == "BLOCKED"
    assert any("report is missing" in item for item in report["errors"])


def test_gate_writes_validation_and_freeze_outputs(tmp_path: Path) -> None:
    results = _populate(tmp_path)
    report = validate_and_write_deployment_release(
        root_dir=tmp_path, results_dir=results, freeze_files=FREEZE_FILES
    )
    assert Path(report["output_paths"]["json"]).is_file()
    assert Path(report["output_paths"]["markdown"]).is_file()
    assert Path(report["output_paths"]["freeze_manifest"]).is_file()
    assert len(report["freeze_manifest_sha256"]) == 64


def test_launcher_exit_codes(monkeypatch, capsys) -> None:
    base = {
        "soak_status": "PASSED",
        "documentation_freeze_status": "FROZEN",
        "freeze_file_count": 12,
        "errors": [],
        "warnings": [],
    }
    monkeypatch.setattr(
        launcher,
        "validate_and_write_deployment_release",
        lambda **kwargs: {**base, "release_status": "READY"},
    )
    assert launcher.main([]) == 0
    assert "Release status: READY" in capsys.readouterr().out
    monkeypatch.setattr(
        launcher,
        "validate_and_write_deployment_release",
        lambda **kwargs: {**base, "release_status": "BLOCKED", "errors": ["failed"]},
    )
    assert launcher.main([]) == 1
