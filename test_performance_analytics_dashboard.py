"""Tests for performance_analytics_dashboard.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import performance_analytics_dashboard as dashboard


def test_public_functions_exist():
    for name in [
        "build_performance_analytics_dashboard",
        "validate_performance_analytics_dashboard",
        "format_performance_analytics_dashboard_markdown",
        "format_performance_analytics_dashboard_html",
        "write_performance_analytics_dashboard",
    ]:
        assert callable(getattr(dashboard, name))


def test_build_aggregates_metrics():
    payload = dashboard.build_performance_analytics_dashboard(
        daily_command_center={
            "portfolio_value": 600,
            "expected_monthly_income": 12,
            "expected_annual_income": 144,
            "cash_balance": 100,
            "cash_reserve_target_dollars": 125,
            "portfolio_health_score": 92,
            "market_regime": "BULL",
            "top_opportunities": [{"symbol": "AAA"}],
            "increase_actions": [{"symbol": "AAA"}],
            "reduce_actions": [],
            "exit_actions": [],
        },
        monthly_review={"starting_portfolio_value": 500},
        weekly_review={"status": "OK"},
        strategy_analytics={"status": "OK"},
        portfolio_lifecycle={"portfolio_value": 600},
    )
    assert payload["dashboard_status"] == "COMPLETE"
    assert payload["capital_appreciation"] == 100
    assert payload["capital_appreciation_pct"] == 20
    assert payload["yield_on_cost_pct"] == 28.8
    assert payload["reserve_coverage_pct"] == 80
    assert payload["portfolio_health_score"] == 92
    assert payload["top_opportunity_count"] == 1


def test_missing_inputs_produce_partial_valid_report():
    payload = dashboard.build_performance_analytics_dashboard(
        daily_command_center={"portfolio_value": 500}
    )
    assert payload["dashboard_status"] == "PARTIAL"
    assert payload["warnings"]
    assert dashboard.validate_performance_analytics_dashboard(payload)


def test_invalid_safety_flags_rejected():
    payload = dashboard.build_performance_analytics_dashboard(
        daily_command_center={"portfolio_value": 500}
    )
    for field, value in [
        ("paper_trade_mode", False),
        ("live_trading_enabled", True),
        ("broker_execution_enabled", True),
        ("reporting_only", False),
    ]:
        bad = dict(payload)
        bad[field] = value
        with pytest.raises(ValueError):
            dashboard.validate_performance_analytics_dashboard(bad)


def test_json_markdown_html_outputs(tmp_path: Path):
    inputs = {
        "daily_portfolio_command_center.json": {
            "portfolio_value": 500,
            "expected_monthly_income": 10,
            "expected_annual_income": 120,
            "cash_balance": 100,
            "cash_reserve_target_dollars": 100,
            "portfolio_health_score": 90,
            "market_regime": "BULL",
        },
        "weekly_portfolio_review.json": {},
        "monthly_portfolio_review.json": {"starting_portfolio_value": 500},
        "strategy_performance_analytics.json": {},
        "portfolio_lifecycle_report.json": {},
    }
    for name, payload in inputs.items():
        (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")
    result = dashboard.write_performance_analytics_dashboard(str(tmp_path))
    assert result["dashboard_status"] in {"COMPLETE", "PARTIAL"}
    assert (tmp_path / "performance_analytics_dashboard.json").exists()
    assert (tmp_path / "performance_analytics_dashboard.md").exists()
    assert (tmp_path / "performance_analytics_dashboard.html").exists()
    assert "Dividend Bot Performance Analytics Dashboard" in (tmp_path / "performance_analytics_dashboard.html").read_text(encoding="utf-8")


def test_no_execution_or_broker_terms():
    source = Path(dashboard.__file__).read_text(encoding="utf-8")
    forbidden = ["subprocess", "os.system", "requests", "robin_stocks", "place_order(", "execute_trade("]
    for token in forbidden:
        assert token not in source
