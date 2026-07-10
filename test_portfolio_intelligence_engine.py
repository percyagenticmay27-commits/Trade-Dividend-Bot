"""Tests for portfolio_intelligence_engine.py."""
from __future__ import annotations

from pathlib import Path
import pytest
import portfolio_intelligence_engine as engine


def test_dataclasses_exist():
    assert hasattr(engine, "HoldingIntelligence")
    assert hasattr(engine, "PortfolioIntelligenceReport")


def test_public_functions_exist():
    for name in [
        "calculate_growth_pct",
        "classify_trend",
        "classify_capital_priority",
        "classify_health",
        "build_holding_intelligence",
        "build_portfolio_intelligence_report",
        "validate_portfolio_intelligence_report",
        "write_portfolio_intelligence_report_json",
        "read_portfolio_intelligence_report_json",
        "write_portfolio_intelligence_report_csv",
        "format_portfolio_intelligence_report_markdown",
        "write_portfolio_intelligence_report_markdown",
    ]:
        assert callable(getattr(engine, name))


def test_default_empty_report_valid():
    payload = engine.build_portfolio_intelligence_report()
    assert engine.validate_portfolio_intelligence_report(payload) is True
    assert payload["paper_trade_mode"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False
    assert payload["reporting_only"] is True
    assert payload["holdings_analyzed"] == 0
    assert payload["portfolio_trend"] == "UNKNOWN"


def test_growth_calculation():
    assert engine.calculate_growth_pct(110, 100) == 10.0
    assert engine.calculate_growth_pct(90, 100) == -10.0
    assert engine.calculate_growth_pct(10, 0) == 0.0


def test_trend_classification():
    assert engine.classify_trend(5) == "IMPROVING"
    assert engine.classify_trend(-5) == "DETERIORATING"
    assert engine.classify_trend(2) == "STABLE"


def test_capital_priority_classification():
    assert engine.classify_capital_priority(90, "IMPROVING") == "INCREASE_PRIORITY"
    assert engine.classify_capital_priority(80, "STABLE") == "MAINTAIN_PRIORITY"
    assert engine.classify_capital_priority(60, "STABLE") == "MONITOR_PRIORITY"
    assert engine.classify_capital_priority(90, "DETERIORATING") == "REDUCE_PRIORITY"


def test_health_classification():
    assert engine.classify_health(90) == "EXCELLENT"
    assert engine.classify_health(75) == "GOOD"
    assert engine.classify_health(60) == "FAIR"
    assert engine.classify_health(40) == "WEAK"


def test_holding_intelligence_improving():
    row = engine.build_holding_intelligence({
        "symbol": "amd",
        "current_score": 90,
        "previous_score": 80,
        "allocation_pct": 0.20,
        "current_value": 110,
        "previous_value": 100,
        "current_monthly_income": 5,
        "previous_monthly_income": 4,
    })
    assert row["symbol"] == "AMD"
    assert row["trend_status"] == "IMPROVING"
    assert row["capital_priority"] == "INCREASE_PRIORITY"
    assert row["capital_growth_pct"] == 10.0
    assert row["monthly_income_growth_pct"] == 25.0


def test_concentration_warning():
    row = engine.build_holding_intelligence({
        "symbol": "JEPI",
        "current_score": 80,
        "previous_score": 80,
        "allocation_pct": 0.50,
    })
    assert "POSITION_CONCENTRATION_WARNING" in row["risk_flags"]


def test_portfolio_report_rolls_up_trends_and_income():
    holdings = [
        {"symbol": "AAA", "current_score": 90, "previous_score": 80, "current_value": 110, "previous_value": 100, "current_monthly_income": 5, "previous_monthly_income": 4},
        {"symbol": "BBB", "current_score": 60, "previous_score": 70, "current_value": 90, "previous_value": 100, "current_monthly_income": 3, "previous_monthly_income": 4},
    ]
    payload = engine.build_portfolio_intelligence_report(holdings)
    assert payload["holdings_analyzed"] == 2
    assert payload["improving_count"] == 1
    assert payload["deteriorating_count"] == 1
    assert payload["total_current_value"] == 200
    assert payload["total_previous_value"] == 200
    assert payload["current_monthly_income"] == 8
    assert payload["previous_monthly_income"] == 8
    assert payload["top_improvers"] == ["AAA"]
    assert payload["top_deteriorators"] == ["BBB"]


def test_validate_rejects_malformed_payload():
    for value in [None, [], "bad"]:
        with pytest.raises(ValueError):
            engine.validate_portfolio_intelligence_report(value)


def test_validate_rejects_missing_required_fields():
    payload = engine.build_portfolio_intelligence_report()
    for field in engine.REPORT_REQUIRED_FIELDS:
        bad = dict(payload)
        bad.pop(field, None)
        with pytest.raises(ValueError):
            engine.validate_portfolio_intelligence_report(bad)


def test_validate_rejects_wrong_safety_flags():
    payload = engine.build_portfolio_intelligence_report()
    for field, value in [
        ("paper_trade_mode", False),
        ("live_trading_enabled", True),
        ("broker_execution_enabled", True),
        ("reporting_only", False),
    ]:
        bad = dict(payload)
        bad[field] = value
        with pytest.raises(ValueError):
            engine.validate_portfolio_intelligence_report(bad)


def test_json_csv_markdown_outputs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = engine.write_portfolio_intelligence_report_json()
    assert engine.read_portfolio_intelligence_report_json() == payload
    engine.write_portfolio_intelligence_report_csv()
    engine.write_portfolio_intelligence_report_markdown()
    assert Path("portfolio_intelligence_report.json").exists()
    assert Path("portfolio_intelligence_report.csv").exists()
    assert Path("portfolio_intelligence_report.md").exists()
    markdown = engine.format_portfolio_intelligence_report_markdown(payload)
    assert "# Portfolio Intelligence Report" in markdown
    assert "## Holding Intelligence" in markdown
    assert "## Intelligence Rules" in markdown
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
