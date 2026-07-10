"""Tests for monthly_portfolio_review_engine.py."""
from __future__ import annotations

from pathlib import Path
import pytest
import monthly_portfolio_review_engine as engine


def test_dataclasses_exist():
    assert hasattr(engine, "MonthlyHoldingPerformance")
    assert hasattr(engine, "MonthlyPortfolioReviewReport")


def test_public_functions_exist():
    for name in [
        "classify_month_status",
        "summarize_holding_performance",
        "build_monthly_portfolio_review",
        "validate_monthly_portfolio_review",
        "write_monthly_portfolio_review_json",
        "read_monthly_portfolio_review_json",
        "write_monthly_portfolio_review_csv",
        "format_monthly_portfolio_review_markdown",
        "write_monthly_portfolio_review_markdown",
    ]:
        assert callable(getattr(engine, name))


def test_default_report_valid():
    payload = engine.build_monthly_portfolio_review()
    assert engine.validate_monthly_portfolio_review(payload) is True
    assert payload["paper_trade_mode"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False
    assert payload["reporting_only"] is True
    assert payload["month_status"] == "FLAT_MONTH"


def test_month_status_thresholds():
    assert engine.classify_month_status(5) == "STRONG_MONTH"
    assert engine.classify_month_status(1) == "POSITIVE_MONTH"
    assert engine.classify_month_status(0) == "FLAT_MONTH"
    assert engine.classify_month_status(-1) == "WEAK_MONTH"


def test_monthly_return_and_total_return_calculation():
    payload = engine.build_monthly_portfolio_review(
        starting_portfolio_value=500,
        ending_portfolio_value=550,
        dividend_income=10,
    )
    assert payload["capital_appreciation"] == 50
    assert payload["monthly_return_pct"] == 10
    assert payload["monthly_total_return"] == 60
    assert payload["month_status"] == "STRONG_MONTH"


def test_holding_performance_sorts_best_first():
    rows = engine.summarize_holding_performance([
        {"symbol": "BBB", "monthly_return_pct": -2},
        {"symbol": "AAA", "monthly_return_pct": 8},
        {"symbol": "CCC", "monthly_return_pct": 3},
    ])
    assert [row["symbol"] for row in rows] == ["AAA", "CCC", "BBB"]
    assert rows[0]["status"] == "WINNER"
    assert rows[-1]["status"] == "LOSER"


def test_daily_values_are_aggregated():
    payload = engine.build_monthly_portfolio_review(
        daily_command_center={
            "portfolio_value": 600,
            "expected_monthly_income": 12,
            "expected_annual_income": 144,
            "cash_balance": 120,
            "cash_reserve_target_dollars": 100,
            "market_regime": "BULL",
        },
        starting_portfolio_value=500,
    )
    assert payload["ending_portfolio_value"] == 600
    assert payload["expected_monthly_income"] == 12
    assert payload["expected_annual_income"] == 144
    assert payload["cash_balance"] == 120
    assert payload["market_regime"] == "BULL"


def test_risk_flags_are_deduplicated():
    payload = engine.build_monthly_portfolio_review(
        daily_command_center={"risk_flags": ["A", "B"]},
        weekly_review={"risk_flags": ["A"]},
        strategy_analytics={"risk_flags": ["C"]},
    )
    assert payload["risk_flags"] == ["A", "B", "C"]


def test_income_action_is_added():
    payload = engine.build_monthly_portfolio_review(dividend_income=5)
    assert any("self-funding" in action.lower() for action in payload["next_month_actions"])


def test_validate_rejects_malformed_payload():
    for value in [None, [], "bad"]:
        with pytest.raises(ValueError):
            engine.validate_monthly_portfolio_review(value)


def test_validate_rejects_missing_required_fields():
    payload = engine.build_monthly_portfolio_review()
    for field in engine.REPORT_REQUIRED_FIELDS:
        bad = dict(payload)
        bad.pop(field, None)
        with pytest.raises(ValueError):
            engine.validate_monthly_portfolio_review(bad)


def test_validate_rejects_wrong_safety_flags():
    payload = engine.build_monthly_portfolio_review()
    for field, value in [
        ("paper_trade_mode", False),
        ("live_trading_enabled", True),
        ("broker_execution_enabled", True),
        ("reporting_only", False),
    ]:
        bad = dict(payload)
        bad[field] = value
        with pytest.raises(ValueError):
            engine.validate_monthly_portfolio_review(bad)


def test_json_csv_markdown_outputs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = engine.write_monthly_portfolio_review_json()
    assert engine.read_monthly_portfolio_review_json() == payload
    engine.write_monthly_portfolio_review_csv()
    engine.write_monthly_portfolio_review_markdown()
    assert Path("monthly_portfolio_review.json").exists()
    assert Path("monthly_portfolio_review.csv").exists()
    assert Path("monthly_portfolio_review.md").exists()
    markdown = engine.format_monthly_portfolio_review_markdown(payload)
    assert "# Monthly Portfolio Review" in markdown
    assert "## Executive Summary" in markdown
    assert "## Next Month Actions" in markdown
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
