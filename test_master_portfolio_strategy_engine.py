"""Tests for master_portfolio_strategy_engine.py."""
from __future__ import annotations

from pathlib import Path
import pytest
import master_portfolio_strategy_engine as engine


def test_dataclasses_exist():
    assert hasattr(engine, "MasterStrategyAction")
    assert hasattr(engine, "MasterPortfolioStrategyReport")


def test_public_functions_exist():
    for name in [
        "calculate_strategy_score",
        "classify_strategy_grade",
        "classify_confidence",
        "resolve_action_conflicts",
        "build_master_portfolio_strategy_report",
        "validate_master_portfolio_strategy_report",
        "write_master_portfolio_strategy_report_json",
        "read_master_portfolio_strategy_report_json",
        "write_master_portfolio_strategy_report_csv",
        "format_master_portfolio_strategy_report_markdown",
        "write_master_portfolio_strategy_report_markdown",
    ]:
        assert callable(getattr(engine, name))


def test_default_report_valid():
    payload = engine.build_master_portfolio_strategy_report()
    assert engine.validate_master_portfolio_strategy_report(payload) is True
    assert payload["paper_trade_mode"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False
    assert payload["reporting_only"] is True
    assert payload["strategy_score"] == 0.0
    assert payload["strategy_grade"] == "F"


def test_strategy_weights_total_100():
    assert sum(engine.STRATEGY_WEIGHTS.values()) == 100


def test_strategy_score_calculation():
    metrics = {key: 100 for key in engine.STRATEGY_WEIGHTS}
    assert engine.calculate_strategy_score(metrics) == 100.0
    assert engine.calculate_strategy_score({}) == 0.0


def test_grade_classification():
    assert engine.classify_strategy_grade(95) == "A"
    assert engine.classify_strategy_grade(85) == "B"
    assert engine.classify_strategy_grade(75) == "C"
    assert engine.classify_strategy_grade(65) == "D"
    assert engine.classify_strategy_grade(55) == "E"
    assert engine.classify_strategy_grade(45) == "F"


def test_confidence_classification():
    assert engine.classify_confidence(0.8) == "HIGH"
    assert engine.classify_confidence(0.5) == "MEDIUM"
    assert engine.classify_confidence(0.1) == "LOW"


def test_conflict_resolution_exit_overrides_hold():
    actions, conflicts = engine.resolve_action_conflicts([
        {"symbol": "AAA", "action": "HOLD", "priority": "LOW", "score": 80, "source_engine": "lifecycle", "reason": ["hold"]},
        {"symbol": "AAA", "action": "EXIT_TO_SGOV", "priority": "CRITICAL", "score": 40, "source_engine": "rebalance", "reason": ["sale signal"]},
    ])
    assert actions[0]["action"] == "EXIT_TO_SGOV"
    assert conflicts


def test_conflict_resolution_reallocate_over_increase():
    actions, _ = engine.resolve_action_conflicts([
        {"symbol": "AAA", "action": "INCREASE", "priority": "HIGH", "score": 90, "source_engine": "allocation", "reason": []},
        {"symbol": "AAA", "action": "REALLOCATE", "priority": "HIGH", "score": 95, "source_engine": "rebalance", "reason": []},
    ])
    assert actions[0]["action"] == "REALLOCATE"


def test_build_report_with_actions():
    payload = engine.build_master_portfolio_strategy_report(
        metrics={
            "portfolio_health_score": 90,
            "portfolio_intelligence_score": 80,
            "portfolio_forecast_score": 70,
            "average_conviction_score": 80,
            "average_opportunity_score": 85,
            "cash_reserve_health_score": 100,
            "confidence": 0.8,
        },
        proposed_actions=[
            {"symbol": "JEPI", "action": "HOLD", "priority": "LOW", "score": 80, "source_engine": "lifecycle", "reason": ["No sale signal"]},
            {"symbol": "AMD", "action": "INCREASE", "priority": "HIGH", "score": 95, "source_engine": "allocation", "reason": ["Top-ranked opportunity"]},
        ],
    )
    assert payload["action_count"] == 2
    assert payload["confidence_level"] == "HIGH"
    assert payload["executive_recommendation"] == "Direct eligible excess cash toward the strongest approved opportunities."


def test_exit_drives_executive_recommendation():
    payload = engine.build_master_portfolio_strategy_report(
        proposed_actions=[{"symbol": "AAA", "action": "EXIT_TO_SGOV", "priority": "CRITICAL", "score": 40, "source_engine": "rebalance", "reason": ["sale signal"]}]
    )
    assert "SGOV" in payload["executive_recommendation"]


def test_input_file_availability(tmp_path):
    (tmp_path / "portfolio_health_report.json").write_text("{}", encoding="utf-8")
    payload = engine.build_master_portfolio_strategy_report(root_path=str(tmp_path))
    assert "portfolio_health_report.json" in payload["available_input_files"]
    assert "portfolio_forecast_report.json" in payload["missing_input_files"]


def test_validate_rejects_malformed_payload():
    for value in [None, [], "bad"]:
        with pytest.raises(ValueError):
            engine.validate_master_portfolio_strategy_report(value)


def test_validate_rejects_missing_required_fields():
    payload = engine.build_master_portfolio_strategy_report()
    for field in engine.REPORT_REQUIRED_FIELDS:
        bad = dict(payload)
        bad.pop(field, None)
        with pytest.raises(ValueError):
            engine.validate_master_portfolio_strategy_report(bad)


def test_validate_rejects_wrong_safety_flags():
    payload = engine.build_master_portfolio_strategy_report()
    for field, value in [
        ("paper_trade_mode", False),
        ("live_trading_enabled", True),
        ("broker_execution_enabled", True),
        ("reporting_only", False),
    ]:
        bad = dict(payload)
        bad[field] = value
        with pytest.raises(ValueError):
            engine.validate_master_portfolio_strategy_report(bad)


def test_json_csv_markdown_outputs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = engine.write_master_portfolio_strategy_report_json()
    assert engine.read_master_portfolio_strategy_report_json() == payload
    engine.write_master_portfolio_strategy_report_csv()
    engine.write_master_portfolio_strategy_report_markdown()
    assert Path("master_portfolio_strategy_report.json").exists()
    assert Path("master_portfolio_strategy_report.csv").exists()
    assert Path("master_portfolio_strategy_report.md").exists()
    markdown = engine.format_master_portfolio_strategy_report_markdown(payload)
    assert "# Master Portfolio Strategy Report" in markdown
    assert "## Final Actions" in markdown
    assert "## Conflicts Resolved" in markdown
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
