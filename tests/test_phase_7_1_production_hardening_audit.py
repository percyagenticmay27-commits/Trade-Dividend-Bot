from __future__ import annotations

import hashlib
import json
from pathlib import Path

import audit_enterprise_production_hardening as launcher
from src.dividend_bot.enterprise_production_hardening_audit import (
    REQUIRED_DEPLOYMENT_FILES,
    audit_and_write_production_hardening,
    audit_production_hardening,
)


def _populate(root: Path, *, package_status: str = "PASSED") -> Path:
    for name in REQUIRED_DEPLOYMENT_FILES:
        (root / name).write_text("paper only\n", encoding="utf-8")
    results = root / "results"
    results.mkdir()
    package = results / "enterprise-unified-dashboard-evidence-package.zip"
    package.write_bytes(b"verified package")
    digest = hashlib.sha256(package.read_bytes()).hexdigest()
    report = {
        "package_status": package_status,
        "acceptance_status": "PASSED",
        "verification_status": "PASSED",
        "package": {"path": str(package), "sha256": digest},
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
    }
    (results / "enterprise_unified_dashboard_evidence_package.json").write_text(
        json.dumps(report), encoding="utf-8"
    )
    return results


def _environment() -> dict[str, str]:
    return {
        "SENDGRID_API_KEY": "configured",
        "SENDGRID_FROM_EMAIL": "configured",
        "REPORT_RECIPIENT": "configured",
    }


def test_complete_baseline_is_ready_with_restore_warning(tmp_path: Path) -> None:
    results = _populate(tmp_path)
    report = audit_production_hardening(
        root_dir=tmp_path, results_dir=results, environment=_environment()
    )
    assert report["hardening_status"] == "READY_WITH_WARNINGS"
    assert report["errors"] == []
    assert report["package_expected_sha256"] == report["package_actual_sha256"]


def test_missing_required_deployment_file_blocks_readiness(tmp_path: Path) -> None:
    results = _populate(tmp_path)
    (tmp_path / "run_daily_paper_cycle.py").unlink()
    report = audit_production_hardening(
        root_dir=tmp_path, results_dir=results, environment=_environment()
    )
    assert report["hardening_status"] == "BLOCKED"
    assert any("Required deployment file is missing" in item for item in report["errors"])


def test_deployment_local_launcher_is_warning_not_blocker(tmp_path: Path) -> None:
    results = _populate(tmp_path)
    report = audit_production_hardening(
        root_dir=tmp_path, results_dir=results, environment=_environment()
    )
    assert any("run_dividend_bot.sh" in item for item in report["warnings"])
    assert report["errors"] == []


def test_missing_environment_is_reported_without_exposing_values(tmp_path: Path) -> None:
    results = _populate(tmp_path)
    report = audit_production_hardening(
        root_dir=tmp_path, results_dir=results, environment={}
    )
    assert report["environment_values_exposed"] is False
    assert report["environment_configuration"]["SENDGRID_API_KEY"] is False
    assert all("configured" not in item for item in report["warnings"])


def test_failed_evidence_package_blocks_readiness(tmp_path: Path) -> None:
    results = _populate(tmp_path, package_status="FAILED")
    report = audit_production_hardening(
        root_dir=tmp_path, results_dir=results, environment=_environment()
    )
    assert report["hardening_status"] == "BLOCKED"
    assert "Evidence package status must be PASSED: FAILED" in report["errors"]


def test_package_hash_mismatch_blocks_readiness(tmp_path: Path) -> None:
    results = _populate(tmp_path)
    package = results / "enterprise-unified-dashboard-evidence-package.zip"
    package.write_bytes(b"tampered")
    report = audit_production_hardening(
        root_dir=tmp_path, results_dir=results, environment=_environment()
    )
    assert report["hardening_status"] == "BLOCKED"
    assert any("SHA-256 does not match" in item for item in report["errors"])


def test_unsafe_package_safety_flag_blocks_readiness(tmp_path: Path) -> None:
    results = _populate(tmp_path)
    path = results / "enterprise_unified_dashboard_evidence_package.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["broker_execution_enabled"] = True
    path.write_text(json.dumps(payload), encoding="utf-8")
    report = audit_production_hardening(
        root_dir=tmp_path, results_dir=results, environment=_environment()
    )
    assert report["hardening_status"] == "BLOCKED"
    assert any("broker_execution_enabled must be False" in item for item in report["errors"])


def test_recovery_components_are_reported(tmp_path: Path) -> None:
    results = _populate(tmp_path)
    report = audit_production_hardening(
        root_dir=tmp_path, results_dir=results, environment=_environment()
    )
    recovery = report["recovery_readiness"]
    assert recovery["backup_script_present"] is True
    assert recovery["health_check_present"] is True
    assert recovery["log_rotation_present"] is True
    assert recovery["restore_test_status"] == "NOT_YET_EXECUTED"



def _write_recovery(results: Path, *, status: str = "PASSED") -> None:
    (results / "enterprise_backup_recovery_validation.json").write_text(
        json.dumps({
            "recovery_status": status,
            "restore_test_status": status,
            "source_files_unchanged": status == "PASSED",
        }),
        encoding="utf-8",
    )


def test_passed_recovery_evidence_removes_restore_warning(tmp_path: Path) -> None:
    results = _populate(tmp_path)
    _write_recovery(results)
    report = audit_production_hardening(
        root_dir=tmp_path, results_dir=results, environment=_environment()
    )
    assert report["recovery_readiness"]["recovery_status"] == "PASSED"
    assert report["recovery_readiness"]["restore_test_status"] == "PASSED"
    assert not any(
        "not yet been executed" in item for item in report["warnings"]
    )
    assert report["errors"] == []


def test_failed_recovery_evidence_blocks_hardening(tmp_path: Path) -> None:
    results = _populate(tmp_path)
    _write_recovery(results, status="FAILED")
    report = audit_production_hardening(
        root_dir=tmp_path, results_dir=results, environment=_environment()
    )
    assert report["hardening_status"] == "BLOCKED"
    assert any(
        "Recovery validation status must be PASSED" in item
        for item in report["errors"]
    )

def test_audit_writes_json_and_markdown_reports(tmp_path: Path) -> None:
    results = _populate(tmp_path)
    report = audit_and_write_production_hardening(
        root_dir=tmp_path, results_dir=results, environment=_environment()
    )
    assert Path(report["output_paths"]["json"]).is_file()
    markdown = Path(report["output_paths"]["markdown"]).read_text(encoding="utf-8")
    assert "# Enterprise Production Hardening Baseline" in markdown
    assert "Environment values exposed: False" in markdown


def test_launcher_exit_codes(monkeypatch, capsys) -> None:
    base = {
        "package_status": "PASSED",
        "package_expected_sha256": "a",
        "package_actual_sha256": "a",
        "errors": [],
        "warnings": [],
    }
    monkeypatch.setattr(
        launcher,
        "audit_and_write_production_hardening",
        lambda **kwargs: {**base, "hardening_status": "READY_WITH_WARNINGS"},
    )
    assert launcher.main([]) == 0
    assert "Hardening status: READY_WITH_WARNINGS" in capsys.readouterr().out
    monkeypatch.setattr(
        launcher,
        "audit_and_write_production_hardening",
        lambda **kwargs: {**base, "hardening_status": "BLOCKED", "errors": ["failed"]},
    )
    assert launcher.main([]) == 1
