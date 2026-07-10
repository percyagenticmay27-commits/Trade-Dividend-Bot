"""Tests for weekly_portfolio_review_engine.py."""
from __future__ import annotations

from pathlib import Path
import pytest
import weekly_portfolio_review_engine as engine


def _daily(value, monthly, annual, health=90, regime="BULL", **extra):
    payload = {
        "portfolio_value": value,
        "expected_monthly_income": monthly,
        "expected_annual_income": annual,
        "portfolio_health_score": health,
        "cash_balance": 100,
        "cash_reserve_target_dollars": 100,
        "market_regime": regime,
        "top_opportunities": [],
        "increase_actions": [],
        "reduce_actions": [],
        "exit_actions": [],
        "reentry_actions": [],
        "reinvestment_actions": [],
        "pending_reallocations": [],
        "watchlist_promotions": [],
        "watchlist_demotions": [],
        "risk_flags": [],
    }
    payload.update(extra)
    return payload


def test_dataclasses_exist():
    assert hasattr(engine, "WeeklyReviewAction")
    assert hasattr(engine, "WeeklyPortfolioReviewReport")


def test_public_functions_exist():
    for name in [
        "build_weekly_portfolio_review",
        "validate_weekly_portfolio_review",
        "write_weekly_portfolio_review_json",
        "read_weekly_portfolio_review_json",
        "write_weekly_portfolio_review_csv",
        "format_weekly_portfolio_review_markdown",
        "write_weekly_portfolio_review_markdown",
    ]:
        assert callable(getattr(engine, name))


def test_default_empty_report_valid():
    payload = engine.build_weekly_portfolio_review()
    assert engine.validate_weekly_portfolio_review(payload) is True
    assert payload["weekly_status"] == "UNKNOWN"
    assert payload["days_reviewed"] == 0
    assert payload["missing_days"] == 5
    assert payload["paper_trade_mode"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False
    assert payload["reporting_only"] is True


def test_improving_week_status():
    payload = engine.build_weekly_portfolio_review([
        _daily(500, 5, 60),
        _daily(525, 6, 72),
    ], expected_days=2)
    assert payload["weekly_status"] == "IMPROVING"
    assert payload["portfolio_value_change"] == 25
    assert payload["monthly_income_change"] == 1
    assert payload["annual_income_change"] == 12


def test_weakening_week_status():
    payload = engine.build_weekly_portfolio_review([
        _daily(500, 5, 60),
        _daily(475, 4, 48),
    ], expected_days=2)
    assert payload["weekly_status"] == "WEAKENING"


def test_critical_week_from_multiple_exits():
    exit_row = {"symbol": "AAA", "action": "EXIT", "score": 40, "reason": "sale signal"}
    payload = engine.build_weekly_portfolio_review([
        _daily(500, 5, 60, exit_actions=[exit_row]),
        _daily(500, 5, 60, exit_actions=[
            {"symbol": "BBB", "action": "EXIT", "score": 35, "reason": "sale signal"},
            {"symbol": "CCC", "action": "EXIT", "score": 30, "reason": "sale signal"},
        ]),
    ], expected_days=2)
    assert payload["weekly_status"] == "CRITICAL"


def test_action_aggregation_counts_occurrences():
    action = {"symbol": "AMD", "action": "INCREASE", "score": 95, "reason": "strong rank"}
    payload = engine.build_weekly_portfolio_review([
        _daily(500, 5, 60, increase_actions=[action]),
        _daily(510, 5, 60, increase_actions=[action]),
    ], expected_days=2)
    assert payload["increase_actions"][0]["occurrences"] == 2
    assert payload["increase_actions"][0]["symbol"] == "AMD"


def test_market_regime_summary():
    payload = engine.build_weekly_portfolio_review([
        _daily(500, 5, 60, regime="BULL"),
        _daily(505, 5, 60, regime="NEUTRAL"),
        _daily(510, 5, 60, regime="BULL"),
    ], expected_days=3)
    assert payload["market_regime_summary"] == {"BULL": 2, "NEUTRAL": 1}


def test_missing_days_warning():
    payload = engine.build_weekly_portfolio_review([_daily(500, 5, 60)], expected_days=5)
    assert payload["missing_days"] == 4
    assert payload["warnings"]


def test_validate_rejects_invalid_expected_days():
    with pytest.raises(ValueError):
        engine.build_weekly_portfolio_review([], expected_days=0)


def test_validate_rejects_malformed_payload():
    for value in [None, [], "bad"]:
        with pytest.raises(ValueError):
            engine.validate_weekly_portfolio_review(value)


def test_validate_rejects_missing_required_fields():
    payload = engine.build_weekly_portfolio_review()
    for field in engine.REPORT_REQUIRED_FIELDS:
        bad = dict(payload)
        bad.pop(field, None)
        with pytest.raises(ValueError):
            engine.validate_weekly_portfolio_review(bad)


def test_validate_rejects_wrong_safety_flags():
    payload = engine.build_weekly_portfolio_review()
    for field, value in [
        ("paper_trade_mode", False),
        ("live_trading_enabled", True),
        ("broker_execution_enabled", True),
        ("reporting_only", False),
    ]:
        bad = dict(payload)
        bad[field] = value
        with pytest.raises(ValueError):
            engine.validate_weekly_portfolio_review(bad)


def test_json_csv_markdown_outputs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = engine.write_weekly_portfolio_review_json()
    assert engine.read_weekly_portfolio_review_json() == payload
    engine.write_weekly_portfolio_review_csv()
    engine.write_weekly_portfolio_review_markdown()
    assert Path("weekly_portfolio_review.json").exists()
    assert Path("weekly_portfolio_review.csv").exists()
    assert Path("weekly_portfolio_review.md").exists()
    markdown = engine.format_weekly_portfolio_review_markdown(payload)
    assert "# Weekly Portfolio Review" in markdown
    assert "## Executive Summary" in markdown
    assert "## Action Items" in markdown
    assert "## Safety Guarantees" in markdown


def test_static_safety_no_restricted_execution_terms():
    source = Path(engine.__file__).read_text(encoding="utf-8").lower()
    restricted = [
        "import " + "robinhood",
        "from " + "robinhood",
        "import robin" + "_stocks",
        "from robin" + "_stocks",
        "place" + "_order(",
        "submit" + "_order(",
        "execute" + "_order(",
        "real" + "_order",
        "live" + "_order",
    ]
    for item in restricted:
        assert item not in source


def test_static_safety_no_process_or_network_terms():
    source = Path(engine.__file__).read_text(encoding="utf-8")
    restricted = [
        "import sub" + "process",
        "from sub" + "process",
        "sub" + "process.",
        "P" + "open(",
        "os." + "system(",
        "." + "system(",
        "requests.",
        "urllib." + "request",
        "http." + "client",
        "socket.",
    ]
    for item in restricted:
        assert item not in source
