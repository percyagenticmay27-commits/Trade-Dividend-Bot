import json
from pathlib import Path

import pytest

from src.dividend_bot import end_to_end_paper_trading_validation as module


def _write_json(root: Path, relative: str, payload: dict) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_jsonl(root: Path, relative: str, payload: dict) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _valid_root(tmp_path: Path) -> Path:
    safety = {"paper_trade_mode": True, "live_trading_enabled": False, "broker_execution_enabled": False}
    _write_json(tmp_path, "results/enterprise_dividend_daily_cycle.json", {**safety, "cycle_status": "COMPLETED"})
    _write_json(tmp_path, "results/paper_production_acceptance.json", {**safety, "status": "ACCEPTED"})
    _write_json(tmp_path, "results/cloud_readiness.json", {**safety, "status": "HEALTHY"})
    for name in (
        "enterprise_dividend_dashboard.json",
        "enterprise_dividend_strategy_health.json",
        "enterprise_dividend_service_registry.json",
    ):
        _write_json(tmp_path, f"results/{name}", safety)
    _write_jsonl(tmp_path, "logs/dividend_bot.jsonl", {"event": "cycle_completed"})
    _write_json(tmp_path, "state/paper_state.json", {"paper_trade_mode": True})
    _write_json(tmp_path, "state/paper_cash_account.json", {"paper_trade_mode": True})
    _write_jsonl(tmp_path, "state/paper_cash_transactions.jsonl", {"transaction_id": "TX-1"})
    _write_jsonl(tmp_path, "state/paper_allocation_requests.jsonl", {"request_id": "REQ-1"})
    return tmp_path


def test_safety_constants_are_locked():
    assert module.PAPER_TRADE_MODE is True
    assert module.LIVE_TRADING_ENABLED is False
    assert module.BROKER_EXECUTION_ENABLED is False
    assert module.CAPITAL_MOVEMENT_ENABLED is False
    assert module.ADVISORY_ONLY is True


def test_valid_operational_evidence_is_validated(tmp_path):
    report = module.build_end_to_end_paper_trading_validation(
        _valid_root(tmp_path),
        scheduler_status="PASSED",
        email_delivery_status="SENT",
        restart_recovery_status="PASSED",
        generated_at_utc="2026-07-30T12:00:00Z",
    )
    assert report["status"] == "VALIDATED"
    assert report["summary"]["failed_checks"] == 0
    assert report["blockers"] == []


def test_dry_run_email_is_accepted(tmp_path):
    report = module.build_end_to_end_paper_trading_validation(
        _valid_root(tmp_path), scheduler_status="PASSED", email_delivery_status="DRY_RUN_PASSED", restart_recovery_status="PASSED"
    )
    assert report["status"] == "VALIDATED"


def test_missing_required_artifact_blocks(tmp_path):
    root = _valid_root(tmp_path)
    (root / "results/enterprise_dividend_dashboard.json").unlink()
    report = module.build_end_to_end_paper_trading_validation(root, scheduler_status="PASSED", email_delivery_status="SENT", restart_recovery_status="PASSED")
    assert report["status"] == "BLOCKED"
    assert "results/enterprise_dividend_dashboard.json" in report["blockers"]


def test_invalid_json_blocks(tmp_path):
    root = _valid_root(tmp_path)
    (root / "results/cloud_readiness.json").write_text("{bad", encoding="utf-8")
    report = module.build_end_to_end_paper_trading_validation(root, scheduler_status="PASSED", email_delivery_status="SENT", restart_recovery_status="PASSED")
    assert report["status"] == "BLOCKED"


def test_incomplete_cycle_blocks(tmp_path):
    root = _valid_root(tmp_path)
    _write_json(root, "results/enterprise_dividend_daily_cycle.json", {"paper_trade_mode": True, "live_trading_enabled": False, "broker_execution_enabled": False, "cycle_status": "PLANNED"})
    report = module.build_end_to_end_paper_trading_validation(root, scheduler_status="PASSED", email_delivery_status="SENT", restart_recovery_status="PASSED")
    assert report["status"] == "BLOCKED"
    assert "daily_cycle_status" in report["blockers"]


def test_cycle_warning_is_disclosed(tmp_path):
    root = _valid_root(tmp_path)
    _write_json(root, "results/enterprise_dividend_daily_cycle.json", {"paper_trade_mode": True, "live_trading_enabled": False, "broker_execution_enabled": False, "cycle_status": "COMPLETED_WITH_WARNINGS"})
    report = module.build_end_to_end_paper_trading_validation(root, scheduler_status="PASSED", email_delivery_status="SENT", restart_recovery_status="PASSED")
    assert report["status"] == "VALIDATED"
    assert report["warnings"]


def test_rejected_acceptance_blocks(tmp_path):
    root = _valid_root(tmp_path)
    _write_json(root, "results/paper_production_acceptance.json", {"paper_trade_mode": True, "live_trading_enabled": False, "broker_execution_enabled": False, "status": "REJECTED"})
    report = module.build_end_to_end_paper_trading_validation(root, scheduler_status="PASSED", email_delivery_status="SENT", restart_recovery_status="PASSED")
    assert "paper_production_acceptance" in report["blockers"]


def test_degraded_cloud_readiness_blocks(tmp_path):
    root = _valid_root(tmp_path)
    _write_json(root, "results/cloud_readiness.json", {"paper_trade_mode": True, "live_trading_enabled": False, "broker_execution_enabled": False, "status": "DEGRADED"})
    report = module.build_end_to_end_paper_trading_validation(root, scheduler_status="PASSED", email_delivery_status="SENT", restart_recovery_status="PASSED")
    assert "cloud_readiness_status" in report["blockers"]


@pytest.mark.parametrize("field", ["scheduler", "email_delivery", "restart_recovery"])
def test_untested_operational_gate_blocks(tmp_path, field):
    values = {"scheduler_status": "PASSED", "email_delivery_status": "SENT", "restart_recovery_status": "PASSED"}
    values[f"{field}_status"] = "NOT_TESTED"
    report = module.build_end_to_end_paper_trading_validation(_valid_root(tmp_path), **values)
    assert report["status"] == "BLOCKED"
    assert field in report["blockers"]


def test_unsafe_payload_blocks(tmp_path):
    root = _valid_root(tmp_path)
    _write_json(root, "results/cloud_readiness.json", {"paper_trade_mode": False, "live_trading_enabled": True, "broker_execution_enabled": True, "status": "HEALTHY"})
    report = module.build_end_to_end_paper_trading_validation(root, scheduler_status="PASSED", email_delivery_status="SENT", restart_recovery_status="PASSED")
    assert "cloud_readiness_paper_safety" in report["blockers"]


def test_standard_json_and_markdown_outputs(tmp_path):
    root = _valid_root(tmp_path / "root")
    report = module.build_end_to_end_paper_trading_validation(root, scheduler_status="PASSED", email_delivery_status="SENT", restart_recovery_status="PASSED")
    outputs = module.write_end_to_end_paper_trading_validation(report, tmp_path / "out")
    assert Path(outputs["json"]).name == "end_to_end_paper_trading_validation.json"
    assert Path(outputs["markdown"]).name == "end_to_end_paper_trading_validation.md"
    assert "# End-to-End Paper Trading Validation" in Path(outputs["markdown"]).read_text(encoding="utf-8")


def test_schema_and_governance_are_present(tmp_path):
    report = module.build_end_to_end_paper_trading_validation(_valid_root(tmp_path), scheduler_status="PASSED", email_delivery_status="SENT", restart_recovery_status="PASSED")
    assert report["module_name"] == module.MODULE_NAME
    assert report["schema_version"] == module.SCHEMA_VERSION
    assert report["governance"]["order_execution_allowed"] is False
    assert report["governance"]["brokerage_communication_allowed"] is False
