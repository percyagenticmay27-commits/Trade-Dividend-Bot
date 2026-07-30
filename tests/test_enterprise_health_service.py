from datetime import datetime, timezone

import pytest

from src.dividend_bot import enterprise_health_service as health

NOW = datetime(2026, 7, 30, 3, 0, tzinfo=timezone.utc)


def make_strategy(**overrides):
    row = {
        "strategy_id": "STRATEGY-DIVIDEND-001",
        "strategy_name": "Dividend Strategy",
        "runtime_status": "RUNNING",
        "health_status": "OK",
        "readiness": "READY",
        "last_heartbeat": "2026-07-30T02:50:00Z",
        "contract_complete": True,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "required_enterprise_services": ["Enterprise Runtime", "Market Data"],
        "warnings": [],
        "errors": [],
    }
    row.update(overrides)
    return row


def test_safety_constants_are_locked():
    assert health.PAPER_TRADE_MODE is True
    assert health.LIVE_TRADING_ENABLED is False
    assert health.BROKER_EXECUTION_ENABLED is False


def test_healthy_strategy_scores_100():
    result = health.assess_strategy_health(make_strategy(), now_utc=NOW)
    assert result.health_score == 100
    assert result.effective_health_status == "HEALTHY"
    assert result.heartbeat_status == "CURRENT"
    assert result.paper_safe is True


def test_stale_heartbeat_degrades_score():
    result = health.assess_strategy_health(
        make_strategy(last_heartbeat="2026-07-30T01:00:00Z"),
        now_utc=NOW,
        stale_after_minutes=30,
    )
    assert result.heartbeat_status == "STALE"
    assert result.health_score == 80
    assert result.effective_health_status == "WARNING"


def test_missing_contracts_are_critical():
    result = health.assess_strategy_health(make_strategy(contract_complete=False), now_utc=NOW)
    assert result.health_score == 70
    assert result.effective_health_status == "CRITICAL"
    assert "required strategy contracts are incomplete" in result.errors


def test_runtime_offline_is_critical():
    result = health.assess_strategy_health(make_strategy(runtime_status="OFFLINE"), now_utc=NOW)
    assert result.effective_health_status == "CRITICAL"
    assert result.health_score == 60


def test_paper_safety_failure_forces_zero():
    result = health.assess_strategy_health(make_strategy(live_trading_enabled=True), now_utc=NOW)
    assert result.health_score == 0
    assert result.effective_health_status == "CRITICAL"
    assert result.paper_safe is False


def test_dependency_failure_degrades_strategy():
    result = health.assess_strategy_health(
        make_strategy(),
        now_utc=NOW,
        dependency_health={"Enterprise Runtime": "HEALTHY", "Market Data": "ERROR"},
    )
    assert result.dependency_status == "DEGRADED"
    assert result.health_score == 90
    assert result.effective_health_status == "WARNING"


def test_build_report_sorts_strategies_and_aggregates_summary():
    report = health.build_enterprise_health_report(
        {"strategies": [make_strategy(strategy_id="STRATEGY-Z"), make_strategy(strategy_id="STRATEGY-A")]},
        now_utc=NOW,
    )
    assert [item.strategy_id for item in report.strategies] == ["STRATEGY-A", "STRATEGY-Z"]
    assert report.enterprise_status == "HEALTHY"
    assert report.to_dict()["summary"]["registered_strategies"] == 2


def test_empty_inventory_returns_unknown_with_warning():
    report = health.build_enterprise_health_report({"strategies": []}, now_utc=NOW)
    assert report.enterprise_status == "UNKNOWN"
    assert report.warnings


def test_invalid_stale_threshold_rejected():
    with pytest.raises(ValueError):
        health.build_enterprise_health_report({"strategies": []}, stale_after_minutes=0)


def test_load_invalid_inventory_rejected(tmp_path):
    path = tmp_path / "strategy_inventory.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError):
        health.load_strategy_inventory(path)


def test_json_and_markdown_outputs(tmp_path):
    report = health.build_enterprise_health_report(
        {"strategies": [make_strategy()]},
        now_utc=NOW,
        generated_at_utc="2026-07-30T03:00:00Z",
    )
    json_path = health.write_enterprise_health_json(report, tmp_path / "results/enterprise_health.json")
    md_path = health.write_enterprise_health_markdown(report, tmp_path / "results/enterprise_health.md")
    assert "enterprise_health.json" in json_path
    assert "Enterprise Status" in (tmp_path / "results/enterprise_health.md").read_text(encoding="utf-8")
    assert md_path.endswith("enterprise_health.md")
