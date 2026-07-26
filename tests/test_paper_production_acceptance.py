from __future__ import annotations

import json
from pathlib import Path

from src.dividend_bot.paper_production_acceptance import (
    BROKER_EXECUTION_ENABLED,
    LIVE_TRADING_ENABLED,
    PAPER_TRADE_MODE,
    build_acceptance_report,
    write_acceptance_report,
)


def _populate_required_files(root: Path) -> None:
    files = {
        "results/enterprise_dividend_dashboard.json": json.dumps({"status": "READY"}),
        "results/enterprise_dividend_dashboard.md": "# Dashboard\n",
        "results/html/index.html": "<html>portal</html>",
        "results/html/executive_dashboard.html": "<html>executive</html>",
        "results/html/investor_dashboard.html": "<html>investor</html>",
        "results/html/strategy_health.html": "<html>health</html>",
        "logs/dividend_bot.jsonl": '{"event":"cycle_complete"}\n',
        "state/paper_state.json": json.dumps({"paper_trade_mode": True}),
    }
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def test_safety_constants_are_locked():
    assert PAPER_TRADE_MODE is True
    assert LIVE_TRADING_ENABLED is False
    assert BROKER_EXECUTION_ENABLED is False


def test_complete_paper_cycle_is_accepted(tmp_path: Path):
    _populate_required_files(tmp_path)
    report = build_acceptance_report(
        tmp_path,
        email_delivery_status="DRY_RUN_PASSED",
        restart_recovery_status="PASSED",
        generated_at_utc="2026-07-25T20:00:00Z",
    )
    assert report["status"] == "ACCEPTED"
    assert report["summary"]["failed_checks"] == 0
    assert report["paper_trade_mode"] is True


def test_missing_report_rejects_acceptance(tmp_path: Path):
    _populate_required_files(tmp_path)
    (tmp_path / "results/html/index.html").unlink()
    report = build_acceptance_report(
        tmp_path,
        email_delivery_status="DRY_RUN_PASSED",
        restart_recovery_status="PASSED",
    )
    assert report["status"] == "REJECTED"
    assert report["summary"]["failed_checks"] == 1


def test_empty_report_rejects_acceptance(tmp_path: Path):
    _populate_required_files(tmp_path)
    (tmp_path / "results/html/strategy_health.html").write_text("", encoding="utf-8")
    report = build_acceptance_report(
        tmp_path,
        email_delivery_status="DRY_RUN_PASSED",
        restart_recovery_status="PASSED",
    )
    assert report["status"] == "REJECTED"


def test_invalid_json_rejects_acceptance(tmp_path: Path):
    _populate_required_files(tmp_path)
    (tmp_path / "results/enterprise_dividend_dashboard.json").write_text("{", encoding="utf-8")
    report = build_acceptance_report(
        tmp_path,
        email_delivery_status="DRY_RUN_PASSED",
        restart_recovery_status="PASSED",
    )
    assert report["status"] == "REJECTED"
    assert any("Invalid JSON" in item["details"] for item in report["checks"])


def test_email_delivery_is_required(tmp_path: Path):
    _populate_required_files(tmp_path)
    report = build_acceptance_report(
        tmp_path,
        email_delivery_status="NOT_TESTED",
        restart_recovery_status="PASSED",
    )
    assert report["status"] == "REJECTED"
    assert any(item["name"] == "email_delivery" and item["status"] == "FAILED" for item in report["checks"])


def test_restart_recovery_is_required(tmp_path: Path):
    _populate_required_files(tmp_path)
    report = build_acceptance_report(
        tmp_path,
        email_delivery_status="SENT",
        restart_recovery_status="FAILED",
    )
    assert report["status"] == "REJECTED"


def test_governance_never_allows_execution(tmp_path: Path):
    _populate_required_files(tmp_path)
    report = build_acceptance_report(
        tmp_path,
        email_delivery_status="SENT",
        restart_recovery_status="PASSED",
    )
    assert report["governance"] == {
        "order_execution_allowed": False,
        "brokerage_communication_allowed": False,
        "capital_movement_allowed": False,
        "automatic_policy_change_allowed": False,
    }


def test_write_acceptance_report(tmp_path: Path):
    report = {"status": "ACCEPTED", "paper_trade_mode": True}
    destination = tmp_path / "results" / "paper_production_acceptance.json"
    result = write_acceptance_report(report, destination)
    assert result == str(destination)
    assert json.loads(destination.read_text(encoding="utf-8"))["status"] == "ACCEPTED"


def test_identical_inputs_are_deterministic_with_fixed_timestamp(tmp_path: Path):
    _populate_required_files(tmp_path)
    kwargs = {
        "email_delivery_status": "DRY_RUN_PASSED",
        "restart_recovery_status": "PASSED",
        "generated_at_utc": "2026-07-25T20:00:00Z",
    }
    assert build_acceptance_report(tmp_path, **kwargs) == build_acceptance_report(tmp_path, **kwargs)
