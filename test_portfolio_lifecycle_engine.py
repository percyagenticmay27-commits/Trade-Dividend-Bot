"""Tests for portfolio_lifecycle_engine.py."""
from __future__ import annotations

from pathlib import Path
import pytest
import portfolio_lifecycle_engine as engine


def test_dataclasses_exist():
    assert hasattr(engine, "LifecycleHolding")
    assert hasattr(engine, "LifecycleAction")
    assert hasattr(engine, "PortfolioLifecycleReport")


def test_public_functions_exist():
    for name in [
        "determine_cash_reserve_target",
        "calculate_master_score",
        "assign_rank",
        "detect_sale_signal",
        "build_lifecycle_actions",
        "build_portfolio_lifecycle_report",
        "validate_portfolio_lifecycle_report",
        "write_portfolio_lifecycle_report_json",
        "read_portfolio_lifecycle_report_json",
        "write_portfolio_lifecycle_report_csv",
        "format_portfolio_lifecycle_report_markdown",
        "write_portfolio_lifecycle_report_markdown",
    ]:
        assert callable(getattr(engine, name))


def test_default_empty_report_valid():
    payload = engine.build_portfolio_lifecycle_report()
    assert engine.validate_portfolio_lifecycle_report(payload) is True
    assert payload["paper_trade_mode"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False
    assert payload["reporting_only"] is True
    assert payload["action_count"] == 0


def test_cash_reserve_target_by_regime():
    assert engine.determine_cash_reserve_target("BULL") == 0.20
    assert engine.determine_cash_reserve_target("NEUTRAL") == 0.25
    assert engine.determine_cash_reserve_target("BEAR") == 0.30


def test_master_score_weights_total_100():
    assert sum(engine.MASTER_SCORE_WEIGHTS.values()) == 100
    row = {k: 100 for k in engine.MASTER_SCORE_WEIGHTS}
    assert engine.calculate_master_score(row) == 100.0


def test_rank_assignment():
    assert engine.assign_rank(95) == "A"
    assert engine.assign_rank(85) == "B"
    assert engine.assign_rank(75) == "C"
    assert engine.assign_rank(65) == "D"
    assert engine.assign_rank(55) == "E"
    assert engine.assign_rank(40) == "F"


def test_no_sale_signal_holds():
    holdings = [{
        "symbol": "JEPI",
        "allocation_dollars": 100,
        "allocation_pct": 0.2,
        "opportunity_score": 80,
        "conviction_score": 80,
        "previous_conviction_score": 80,
        "momentum_score": 80,
        "entry_score": 80,
        "technical_score": 80,
        "market_regime_support": 80,
    }]
    payload = engine.build_portfolio_lifecycle_report(holdings)
    assert payload["lifecycle_actions"][0]["lifecycle_action"] in ["HOLD", "INCREASE"]


def test_sale_signal_exits_to_sgov():
    holdings = [{
        "symbol": "JEPI",
        "allocation_dollars": 100,
        "opportunity_score": 40,
        "conviction_score": 60,
        "previous_conviction_score": 80,
        "momentum_score": 40,
        "entry_score": 50,
        "technical_score": 50,
        "market_regime_support": 50,
    }]
    payload = engine.build_portfolio_lifecycle_report(holdings)
    assert payload["lifecycle_actions"][0]["lifecycle_action"] == "EXIT_TO_SGOV"


def test_income_summary_rolls_up():
    holdings = [
        {"symbol": "A", "expected_monthly_income": 2, "expected_annual_income": 24, "opportunity_score": 80, "conviction_score": 80, "momentum_score": 80},
        {"symbol": "B", "expected_monthly_income": 3, "expected_annual_income": 36, "opportunity_score": 80, "conviction_score": 80, "momentum_score": 80},
    ]
    payload = engine.build_portfolio_lifecycle_report(holdings)
    assert payload["income_summary"]["expected_monthly_income"] == 5
    assert payload["income_summary"]["expected_annual_income"] == 60


def test_validate_rejects_malformed_payload():
    for value in [None, [], "bad"]:
        with pytest.raises(ValueError):
            engine.validate_portfolio_lifecycle_report(value)


def test_validate_rejects_missing_required_fields():
    payload = engine.build_portfolio_lifecycle_report()
    for field in engine.REPORT_REQUIRED_FIELDS:
        bad = dict(payload)
        bad.pop(field, None)
        with pytest.raises(ValueError):
            engine.validate_portfolio_lifecycle_report(bad)


def test_validate_rejects_wrong_safety_flags():
    payload = engine.build_portfolio_lifecycle_report()
    for field, value in [("paper_trade_mode", False), ("live_trading_enabled", True), ("broker_execution_enabled", True), ("reporting_only", False)]:
        bad = dict(payload)
        bad[field] = value
        with pytest.raises(ValueError):
            engine.validate_portfolio_lifecycle_report(bad)


def test_json_csv_markdown_outputs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = engine.write_portfolio_lifecycle_report_json()
    assert engine.read_portfolio_lifecycle_report_json() == payload
    engine.write_portfolio_lifecycle_report_csv()
    engine.write_portfolio_lifecycle_report_markdown()
    assert Path("portfolio_lifecycle_report.json").exists()
    assert Path("portfolio_lifecycle_report.csv").exists()
    assert Path("portfolio_lifecycle_report.md").exists()
    markdown = engine.format_portfolio_lifecycle_report_markdown(payload)
    assert "# Portfolio Lifecycle Report" in markdown
    assert "## Lifecycle Rules" in markdown
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
