from __future__ import annotations

import json
from pathlib import Path

import validate_enterprise_deployment_handoff as launcher
from src.dividend_bot.enterprise_deployment_handoff import (
    REQUIRED_REPORTS,
    build_deployment_handoff,
    build_and_write_deployment_handoff,
    detect_environment,
)


SAFETY = {
    "paper_trade_mode": True,
    "live_trading_enabled": False,
    "broker_execution_enabled": False,
    "capital_movement_enabled": False,
    "reporting_only": True,
}


def _reports(root: Path, *, soak: str = "PASSED", release: str = "READY") -> Path:
    results = root / "results"
    results.mkdir()
    statuses = {
        "evidence_package": "PASSED",
        "hardening": "READY_WITH_WARNINGS",
        "recovery": "PASSED",
        "soak": soak,
        "release": release,
    }
    for name, (filename, field, _) in REQUIRED_REPORTS.items():
        (results / filename).write_text(
            json.dumps({**SAFETY, field: statuses[name]}), encoding="utf-8"
        )
    return results


def test_windows_defaults_to_local() -> None:
    assert detect_environment(env={}, system_name="Windows") == "LOCAL"


def test_explicit_digitalocean_marker_wins() -> None:
    assert detect_environment(
        env={"TRADE_BOT_DEPLOYMENT_ENV": "digitalocean"}, system_name="Windows"
    ) == "DIGITALOCEAN"


def test_missing_local_reports_blocks_handoff(tmp_path: Path) -> None:
    report = build_deployment_handoff(
        root_dir=tmp_path, env={}, system_name="Windows"
    )
    assert report["handoff_status"] == "BLOCKED"
    assert report["local_validation_ready"] is False
    assert report["production_validation_ready"] is False


def test_local_passed_prerequisites_are_local_ready(tmp_path: Path) -> None:
    results = _reports(tmp_path)
    report = build_deployment_handoff(
        root_dir=tmp_path, results_dir=results, env={}, system_name="Windows"
    )
    assert report["handoff_status"] == "LOCAL_READY"
    assert report["local_validation_ready"] is True
    assert report["production_validation_ready"] is False
    assert any("Deploy" in item for item in report["next_actions"])


def test_digitalocean_requires_variables_without_exposing_values(tmp_path: Path) -> None:
    results = _reports(tmp_path)
    report = build_deployment_handoff(
        root_dir=tmp_path,
        results_dir=results,
        env={"TRADE_BOT_DEPLOYMENT_ENV": "DIGITALOCEAN"},
        system_name="Linux",
    )
    assert report["handoff_status"] == "BLOCKED"
    assert "SENDGRID_API_KEY" in report["deployment_variables"]["missing"]
    assert report["deployment_variables"]["values_exposed"] is False
    assert "DIGITALOCEAN" not in json.dumps(report.get("environment", ""))


def test_digitalocean_all_gates_pass_is_ready(tmp_path: Path) -> None:
    results = _reports(tmp_path)
    env = {
        "TRADE_BOT_DEPLOYMENT_ENV": "DIGITALOCEAN",
        "REPORT_RECIPIENT": "configured",
        "SENDGRID_API_KEY": "configured",
        "SENDGRID_FROM_EMAIL": "configured",
    }
    report = build_deployment_handoff(
        root_dir=tmp_path, results_dir=results, env=env, system_name="Linux"
    )
    assert report["handoff_status"] == "READY"
    assert report["production_validation_ready"] is True
    assert "configured" not in json.dumps(report)


def test_incomplete_production_soak_is_not_ready(tmp_path: Path) -> None:
    results = _reports(tmp_path, soak="IN_PROGRESS", release="IN_PROGRESS")
    env = {
        "TRADE_BOT_DEPLOYMENT_ENV": "DIGITALOCEAN",
        "REPORT_RECIPIENT": "set",
        "SENDGRID_API_KEY": "set",
        "SENDGRID_FROM_EMAIL": "set",
    }
    report = build_deployment_handoff(
        root_dir=tmp_path, results_dir=results, env=env, system_name="Linux"
    )
    assert report["production_validation_ready"] is False
    assert any("seven-day" in item for item in report["next_actions"])


def test_writer_and_launcher_exit_codes(tmp_path: Path, monkeypatch, capsys) -> None:
    results = _reports(tmp_path)
    report = build_and_write_deployment_handoff(
        root_dir=tmp_path, results_dir=results
    )
    assert Path(report["output_path"]).is_file()
    monkeypatch.setattr(
        launcher,
        "build_and_write_deployment_handoff",
        lambda **kwargs: {
            "environment": "LOCAL",
            "handoff_status": "LOCAL_READY",
            "local_validation_ready": True,
            "production_validation_ready": False,
            "next_actions": [],
            "blockers": [],
        },
    )
    assert launcher.main([]) == 0
    assert "Handoff status: LOCAL_READY" in capsys.readouterr().out
