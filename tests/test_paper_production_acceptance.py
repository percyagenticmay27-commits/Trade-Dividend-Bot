from __future__ import annotations

import json
from pathlib import Path

from src.dividend_bot.paper_production_acceptance import (
    BROKER_EXECUTION_ENABLED,
    CAPITAL_MOVEMENT_ENABLED,
    INVESTOR_CONTROLS_LIVE_MODE,
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
        "results/enterprise_dividend_service_registry.json": json.dumps({"strategy_plugins": [{"strategy_id": "dividend", "enabled": True, "paper_trade_mode": True}]}),
        "logs/dividend_bot.jsonl": '{"event":"cycle_complete"}\n',
        "state/paper_state.json": json.dumps({"paper_trade_mode": True}),
        "state/paper_cash_account.json": json.dumps({"investor_id": "investor", "currency": "USD", "starting_cash": 100000, "available_cash": 75000, "reserved_cash": 5000, "allocated_cash": 20000, "paper_trade_mode": True}),
        "state/paper_cash_transactions.jsonl": json.dumps({"transaction_id": "TX-1", "amount": 100000, "balance_after": 100000, "paper_trade_mode": True}) + "\n",
        "state/paper_allocation_requests.jsonl": json.dumps({"request_id": "AR-1", "status": "PENDING_GOVERNANCE_REVIEW", "requested_cash": 20000, "allocations": [{"strategy_id": "dividend", "amount": 20000}], "paper_trade_mode": True}) + "\n",
    }
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _accepted(root: Path, **overrides):
    values = {"email_delivery_status": "DRY_RUN_PASSED", "restart_recovery_status": "PASSED", "allocation_ui_status": "PASSED", "generated_at_utc": "2026-07-26T20:00:00Z"}
    values.update(overrides)
    return build_acceptance_report(root, **values)


def test_safety_constants_are_locked():
    assert PAPER_TRADE_MODE is True
    assert LIVE_TRADING_ENABLED is False
    assert BROKER_EXECUTION_ENABLED is False
    assert CAPITAL_MOVEMENT_ENABLED is False
    assert INVESTOR_CONTROLS_LIVE_MODE is True


def test_complete_paper_cycle_is_accepted(tmp_path: Path):
    _populate_required_files(tmp_path)
    report = _accepted(tmp_path)
    assert report["status"] == "ACCEPTED"
    assert report["summary"]["failed_checks"] == 0
    assert report["investor_controls_live_mode"] is True


def test_missing_report_rejects_acceptance(tmp_path: Path):
    _populate_required_files(tmp_path)
    (tmp_path / "results/html/index.html").unlink()
    assert _accepted(tmp_path)["status"] == "REJECTED"


def test_invalid_dashboard_json_rejects_acceptance(tmp_path: Path):
    _populate_required_files(tmp_path)
    (tmp_path / "results/enterprise_dividend_dashboard.json").write_text("{", encoding="utf-8")
    report = _accepted(tmp_path)
    assert report["status"] == "REJECTED"
    assert any("Invalid JSON" in item["details"] for item in report["checks"])


def test_email_delivery_is_required(tmp_path: Path):
    _populate_required_files(tmp_path)
    assert _accepted(tmp_path, email_delivery_status="NOT_TESTED")["status"] == "REJECTED"


def test_restart_recovery_is_required(tmp_path: Path):
    _populate_required_files(tmp_path)
    assert _accepted(tmp_path, restart_recovery_status="FAILED")["status"] == "REJECTED"


def test_cash_allocation_ui_validation_is_required(tmp_path: Path):
    _populate_required_files(tmp_path)
    report = _accepted(tmp_path, allocation_ui_status="NOT_TESTED")
    assert report["status"] == "REJECTED"
    assert any(item["name"] == "paper_cash_allocation_ui" and item["status"] == "FAILED" for item in report["checks"])


def test_missing_canonical_cash_account_rejects_acceptance(tmp_path: Path):
    _populate_required_files(tmp_path)
    (tmp_path / "state/paper_cash_account.json").unlink()
    assert _accepted(tmp_path)["status"] == "REJECTED"


def test_incomplete_cash_account_rejects_acceptance(tmp_path: Path):
    _populate_required_files(tmp_path)
    (tmp_path / "state/paper_cash_account.json").write_text(json.dumps({"available_cash": 500}), encoding="utf-8")
    report = _accepted(tmp_path)
    assert report["status"] == "REJECTED"
    assert any(item["name"] == "paper_cash_account" and item["status"] == "FAILED" for item in report["checks"])


def test_missing_cash_transaction_log_rejects_acceptance(tmp_path: Path):
    _populate_required_files(tmp_path)
    (tmp_path / "state/paper_cash_transactions.jsonl").unlink()
    assert _accepted(tmp_path)["status"] == "REJECTED"


def test_malformed_allocation_request_rejects_acceptance(tmp_path: Path):
    _populate_required_files(tmp_path)
    (tmp_path / "state/paper_allocation_requests.jsonl").write_text("{", encoding="utf-8")
    assert _accepted(tmp_path)["status"] == "REJECTED"


def test_governance_never_allows_execution(tmp_path: Path):
    _populate_required_files(tmp_path)
    governance = _accepted(tmp_path)["governance"]
    assert governance["order_execution_allowed"] is False
    assert governance["brokerage_communication_allowed"] is False
    assert governance["capital_movement_allowed"] is False
    assert governance["automatic_policy_change_allowed"] is False
    assert governance["live_mode_requires_investor_authorization"] is True


def test_write_acceptance_report(tmp_path: Path):
    destination = tmp_path / "results/paper_production_acceptance.json"
    assert write_acceptance_report({"status": "ACCEPTED"}, destination) == str(destination)
    assert json.loads(destination.read_text(encoding="utf-8"))["status"] == "ACCEPTED"


def test_identical_inputs_are_deterministic_with_fixed_timestamp(tmp_path: Path):
    _populate_required_files(tmp_path)
    assert _accepted(tmp_path) == _accepted(tmp_path)
