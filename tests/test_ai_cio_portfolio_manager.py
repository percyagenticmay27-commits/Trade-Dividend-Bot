import json
from pathlib import Path

import pytest

from src.dividend_bot import ai_cio_portfolio_manager as manager

FIXED_TIME = "2026-07-30T04:30:00Z"


def dashboard(strategies=None, status="HEALTHY", safe=True):
    return {
        "enterprise_summary": {"enterprise_status": status},
        "strategy_summary": strategies or [],
        "paper_safety": {
            "paper_trade_mode": True,
            "live_trading_enabled": not safe,
            "broker_execution_enabled": False,
        },
    }


def strategy(strategy_id="dividend", health_score=90):
    return {
        "strategy_id": strategy_id,
        "strategy_name": strategy_id.title(),
        "runtime_status": "RUNNING",
        "readiness": "READY",
        "health_score": health_score,
        "health_status": "HEALTHY",
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
    }


def health(strategy_id="dividend", score=90, classification="HEALTHY"):
    return {
        "strategies": [{
            "strategy_id": strategy_id,
            "health_score": score,
            "classification": classification,
        }]
    }


def test_safety_constants_are_locked():
    assert manager.PAPER_TRADE_MODE is True
    assert manager.LIVE_TRADING_ENABLED is False
    assert manager.BROKER_EXECUTION_ENABLED is False
    assert manager.CAPITAL_MOVEMENT_ENABLED is False
    assert manager.AUTOMATIC_ALLOCATION_ENABLED is False


def test_healthy_strategy_receives_advisory_recommendation():
    result = manager.build_portfolio_recommendation(
        dashboard([strategy()]),
        enterprise_health=health(),
        available_paper_cash=1000,
        generated_at_utc=FIXED_TIME,
    )
    assert result["status"] == "ADVISORY_READY"
    assert result["recommendations"][0]["strategy_id"] == "dividend"
    assert result["recommendations"][0]["recommended_paper_amount"] == 500.0
    assert result["summary"]["recommended_cash_reserve_percentage"] == 50.0


def test_multiple_strategies_are_weighted_and_capped():
    result = manager.build_portfolio_recommendation(
        dashboard([strategy("a", 100), strategy("b", 50)]),
        enterprise_health={"strategies": [
            {"strategy_id": "a", "health_score": 100, "classification": "HEALTHY"},
            {"strategy_id": "b", "health_score": 50, "classification": "WARNING"},
        ]},
        investor_policy={"max_strategy_weight": 60, "minimum_cash_reserve": 10},
        available_paper_cash=1000,
    )
    assert result["status"] == "ADVISORY_READY"
    assert round(sum(x["recommended_percentage"] for x in result["recommendations"]), 2) == 90.0
    assert max(x["recommended_percentage"] for x in result["recommendations"]) <= 60.0


def test_critical_strategy_is_excluded():
    result = manager.build_portfolio_recommendation(
        dashboard([strategy()]),
        enterprise_health=health(classification="CRITICAL"),
    )
    assert result["status"] == "NO_ELIGIBLE_STRATEGIES"
    assert result["recommendations"] == []
    assert result["excluded_strategies"][0]["strategy_id"] == "dividend"


def test_inactive_runtime_is_excluded():
    item = strategy()
    item["runtime_status"] = "STOPPED"
    result = manager.build_portfolio_recommendation(dashboard([item]), enterprise_health=health())
    assert result["status"] == "NO_ELIGIBLE_STRATEGIES"
    assert "runtime status STOPPED" in result["excluded_strategies"][0]["exclusion_reasons"][0]


def test_paper_safety_violation_blocks_recommendations():
    result = manager.build_portfolio_recommendation(
        dashboard([strategy()], safe=False),
        enterprise_health=health(),
    )
    assert result["status"] == "BLOCKED"
    assert result["recommendations"] == []
    assert result["blockers"]


def test_unsafe_enterprise_status_blocks_recommendations():
    result = manager.build_portfolio_recommendation(
        dashboard([strategy()], status="UNSAFE"),
        enterprise_health=health(),
    )
    assert result["status"] == "BLOCKED"


def test_performance_score_affects_confidence():
    result = manager.build_portfolio_recommendation(
        dashboard([strategy()]),
        enterprise_health=health(score=80),
        performance_report={"strategies": [{"strategy_id": "dividend", "performance_score": 100}]},
    )
    assert result["recommendations"][0]["advisory_confidence"] == 88.0


def test_governance_is_advisory_only():
    result = manager.build_portfolio_recommendation(dashboard([]))
    governance = result["governance"]
    assert governance["advisory_only"] is True
    assert governance["investor_approval_required"] is True
    assert governance["allocation_request_not_created"] is True
    assert governance["order_execution_allowed"] is False
    assert governance["capital_movement_allowed"] is False


def test_missing_required_dashboard_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        manager.build_ai_cio_portfolio_manager(tmp_path / "missing.json")


def test_invalid_required_dashboard_raises(tmp_path):
    path = tmp_path / "dashboard.json"
    path.write_text("not-json", encoding="utf-8")
    with pytest.raises(ValueError):
        manager.build_ai_cio_portfolio_manager(path)


def test_missing_optional_inputs_create_warnings(tmp_path):
    path = tmp_path / "dashboard.json"
    path.write_text(json.dumps(dashboard([])), encoding="utf-8")
    result = manager.build_ai_cio_portfolio_manager(
        path,
        enterprise_health_path=tmp_path / "missing-health.json",
    )
    assert any("optional input not found" in warning for warning in result["warnings"])


def test_json_and_markdown_outputs(tmp_path):
    report = manager.build_portfolio_recommendation(
        dashboard([strategy()]),
        enterprise_health=health(),
        available_paper_cash=1000,
        generated_at_utc=FIXED_TIME,
    )
    json_path = tmp_path / "report.json"
    md_path = tmp_path / "report.md"
    assert manager.write_ai_cio_portfolio_json(report, json_path) == str(json_path)
    assert manager.write_ai_cio_portfolio_markdown(report, md_path) == str(md_path)
    assert json.loads(json_path.read_text(encoding="utf-8"))["status"] == "ADVISORY_READY"
    assert "AI CIO Portfolio Manager" in md_path.read_text(encoding="utf-8")


def test_standard_output_names(tmp_path):
    dashboard_path = tmp_path / "dashboard.json"
    dashboard_path.write_text(json.dumps(dashboard([])), encoding="utf-8")
    outputs = manager.build_and_write_ai_cio_portfolio_manager(dashboard_path, tmp_path / "results")
    assert Path(outputs["json"]).name == "ai_cio_portfolio_manager.json"
    assert Path(outputs["markdown"]).name == "ai_cio_portfolio_manager.md"


def test_schema_and_metadata_are_present():
    result = manager.build_portfolio_recommendation(dashboard([]), generated_at_utc=FIXED_TIME)
    assert result["module_name"] == manager.MODULE_NAME
    assert result["module_version"] == manager.MODULE_VERSION
    assert result["schema_version"] == manager.SCHEMA_VERSION
    assert result["enterprise_version"] == manager.ENTERPRISE_VERSION
    assert result["generated_at_utc"] == FIXED_TIME
