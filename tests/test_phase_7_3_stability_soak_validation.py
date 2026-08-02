from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import validate_enterprise_stability_soak as launcher
from src.dividend_bot.enterprise_stability_soak_validation import (
    append_stability_sample,
    capture_and_validate_stability_soak,
    capture_stability_sample,
    read_stability_samples,
    validate_stability_samples,
)


def _sample(timestamp: datetime, *, status: str = "PASSED") -> dict:
    return {
        "captured_at_utc": timestamp.isoformat().replace("+00:00", "Z"),
        "sample_status": status,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
    }


def _passing_samples() -> list[dict]:
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    return [_sample(start + timedelta(hours=28 * index)) for index in range(7)]


def _write_evidence(results: Path) -> None:
    results.mkdir(parents=True, exist_ok=True)
    safety = {
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
    }
    documents = {
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
    }
    for name, payload in documents.items():
        (results / name).write_text(json.dumps(payload), encoding="utf-8")


def test_seven_day_passing_history_passes() -> None:
    report = validate_stability_samples(_passing_samples())
    assert report["soak_status"] == "PASSED"
    assert report["sample_count"] == 7
    assert report["duration_hours"] == 168.0


def test_short_history_is_in_progress_not_failed() -> None:
    report = validate_stability_samples(_passing_samples()[:3])
    assert report["soak_status"] == "IN_PROGRESS"
    assert report["errors"] == []
    assert len(report["warnings"]) == 2


def test_failed_operational_sample_fails_soak() -> None:
    samples = _passing_samples()
    samples[3]["sample_status"] = "FAILED"
    report = validate_stability_samples(samples)
    assert report["soak_status"] == "FAILED"
    assert any("sample failed" in item for item in report["errors"])


def test_unsafe_sample_fails_soak() -> None:
    samples = _passing_samples()
    samples[2]["live_trading_enabled"] = True
    report = validate_stability_samples(samples)
    assert report["soak_status"] == "FAILED"
    assert any("safety fields failed" in item for item in report["errors"])


def test_excessive_sampling_gap_fails_completed_history() -> None:
    samples = _passing_samples()
    samples[-1]["captured_at_utc"] = "2026-08-12T00:00:00Z"
    report = validate_stability_samples(samples)
    assert report["soak_status"] == "FAILED"
    assert any("gap exceeds" in item for item in report["errors"])


def test_duplicate_or_invalid_timestamps_fail() -> None:
    samples = _passing_samples()
    samples[1]["captured_at_utc"] = samples[0]["captured_at_utc"]
    samples[2]["captured_at_utc"] = "not-a-time"
    report = validate_stability_samples(samples)
    assert report["soak_status"] == "FAILED"
    assert any("timestamps must be unique" in item for item in report["errors"])
    assert any("timestamp is invalid" in item for item in report["errors"])


def test_capture_reads_statuses_without_exposing_environment(tmp_path: Path) -> None:
    _write_evidence(tmp_path)
    sample = capture_stability_sample(
        results_dir=tmp_path, captured_at_utc="2026-08-01T00:00:00Z"
    )
    assert sample["sample_status"] == "PASSED"
    assert sample["environment_values_exposed"] is False
    assert sample["hardening_status"] == "READY_WITH_WARNINGS"


def test_missing_evidence_creates_failed_sample(tmp_path: Path) -> None:
    sample = capture_stability_sample(results_dir=tmp_path)
    assert sample["sample_status"] == "FAILED"
    assert any("report is missing" in item for item in sample["errors"])


def test_jsonl_persistence_and_reports(tmp_path: Path) -> None:
    _write_evidence(tmp_path)
    log = tmp_path / "samples.jsonl"
    append_stability_sample(log, _sample(datetime(2026, 8, 1, tzinfo=timezone.utc)))
    samples, errors = read_stability_samples(log)
    assert len(samples) == 1
    assert errors == []
    report = capture_and_validate_stability_soak(
        results_dir=tmp_path,
        captured_at_utc="2026-08-02T00:00:00Z",
        minimum_samples=2,
        minimum_duration_hours=0,
    )
    assert Path(report["output_paths"]["json"]).is_file()
    assert Path(report["output_paths"]["markdown"]).is_file()
    assert report["environment_values_exposed"] is False


def test_launcher_exit_codes(monkeypatch, capsys) -> None:
    base = {
        "sample_count": 1,
        "minimum_samples": 7,
        "duration_hours": 0,
        "minimum_duration_hours": 168,
        "errors": [],
        "warnings": ["in progress"],
    }
    monkeypatch.setattr(
        launcher,
        "capture_and_validate_stability_soak",
        lambda **kwargs: {**base, "soak_status": "IN_PROGRESS"},
    )
    assert launcher.main([]) == 0
    assert "Soak status: IN_PROGRESS" in capsys.readouterr().out
    monkeypatch.setattr(
        launcher,
        "capture_and_validate_stability_soak",
        lambda **kwargs: {**base, "soak_status": "FAILED", "errors": ["failed"]},
    )
    assert launcher.main([]) == 1
