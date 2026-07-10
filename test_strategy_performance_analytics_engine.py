"""Tests for strategy_performance_analytics_engine.py."""
from __future__ import annotations

from pathlib import Path
import pytest
import strategy_performance_analytics_engine as engine


def test_dataclasses_exist():
    assert hasattr(engine, "StrategyTradeRecord")
    assert hasattr(engine, "StrategyMetric")
    assert hasattr(engine, "StrategyPerformanceAnalyticsReport")


def test_public_functions_exist():
    for name in [
        "normalize_trade_record",
        "calculate_strategy_metric",
        "calculate_signal_effectiveness",
        "calculate_opportunity_type_metrics",
        "build_strategy_performance_analytics_report",
        "validate_strategy_performance_analytics_report",
        "write_strategy_performance_analytics_report_json",
        "read_strategy_performance_analytics_report_json",
        "write_strategy_performance_analytics_report_csv",
        "format_strategy_performance_analytics_markdown",
        "write_strategy_performance_analytics_report_markdown",
    ]:
        assert callable(getattr(engine, name))


def test_default_empty_report_valid():
    payload = engine.build_strategy_performance_analytics_report()
    assert engine.validate_strategy_performance_analytics_report(payload) is True
    assert payload["trade_count"] == 0
    assert payload["closed_trade_count"] == 0
    assert payload["open_trade_count"] == 0
    assert payload["analytics_status"] == "INSUFFICIENT_DATA"
    assert payload["best_strategy"] == "UNKNOWN"


def test_normalize_trade_calculates_win_and_return():
    trade = engine.normalize_trade_record({
        "trade_id": "1",
        "symbol": "jepi",
        "strategy": "STRATEGY_A",
        "entry_value": 100,
        "exit_value": 105,
        "income_received": 5,
        "exit_date": "2026-01-10",
    })
    assert trade["symbol"] == "JEPI"
    assert trade["outcome"] == "WIN"
    assert trade["total_return_pct"] == 10.0


def test_open_trade_excluded_from_realized_metrics():
    trades = [
        {"symbol": "AAA", "strategy": "STRATEGY_A", "entry_value": 100, "outcome": "OPEN"},
        {"symbol": "BBB", "strategy": "STRATEGY_A", "entry_value": 100, "exit_value": 110, "exit_date": "2026-01-01"},
    ]
    payload = engine.build_strategy_performance_analytics_report(trades)
    metric = payload["strategy_metrics"][0]
    assert metric["trade_count"] == 2
    assert metric["closed_trade_count"] == 1
    assert metric["win_rate"] == 100.0


def test_strategy_a_can_outperform_strategy_b():
    trades = [
        {"symbol": "AAA", "strategy": "STRATEGY_A", "entry_value": 100, "exit_value": 120, "exit_date": "x"},
        {"symbol": "BBB", "strategy": "STRATEGY_B", "entry_value": 100, "exit_value": 105, "exit_date": "x"},
    ]
    payload = engine.build_strategy_performance_analytics_report(trades)
    assert payload["best_strategy"] == "STRATEGY_A"


def test_strategy_b_can_outperform_strategy_a():
    trades = [
        {"symbol": "AAA", "strategy": "STRATEGY_A", "entry_value": 100, "exit_value": 101, "exit_date": "x"},
        {"symbol": "BBB", "strategy": "STRATEGY_B", "entry_value": 100, "exit_value": 120, "exit_date": "x"},
    ]
    payload = engine.build_strategy_performance_analytics_report(trades)
    assert payload["best_strategy"] == "STRATEGY_B"


def test_signal_effectiveness_groups_score_bands():
    records = [
        engine.normalize_trade_record({"symbol": "AAA", "strategy": "STRATEGY_A", "entry_value": 100, "exit_value": 110, "exit_date": "x", "conviction_score": 95}),
        engine.normalize_trade_record({"symbol": "BBB", "strategy": "STRATEGY_A", "entry_value": 100, "exit_value": 90, "exit_date": "x", "conviction_score": 40}),
    ]
    result = engine.calculate_signal_effectiveness(records)
    assert result["conviction_score"]["90_100"]["average_return_pct"] == 10.0
    assert result["conviction_score"]["0_49"]["average_return_pct"] == -10.0


def test_opportunity_type_metrics_rank_by_return():
    records = [
        engine.normalize_trade_record({"symbol": "AAA", "opportunity_type": "ETF_PAIR", "entry_value": 100, "exit_value": 120, "exit_date": "x"}),
        engine.normalize_trade_record({"symbol": "BBB", "opportunity_type": "DIVIDEND_ETF", "entry_value": 100, "exit_value": 105, "exit_date": "x"}),
    ]
    metrics = engine.calculate_opportunity_type_metrics(records)
    assert metrics[0]["opportunity_type"] == "ETF_PAIR"


def test_strong_status_with_sufficient_good_sample():
    trades = [
        {"symbol": f"A{i}", "strategy": "STRATEGY_A", "entry_value": 100, "exit_value": 110, "exit_date": "x"}
        for i in range(5)
    ]
    payload = engine.build_strategy_performance_analytics_report(trades)
    assert payload["analytics_status"] == "STRONG"


def test_validate_rejects_malformed_payload():
    for value in [None, [], "bad"]:
        with pytest.raises(ValueError):
            engine.validate_strategy_performance_analytics_report(value)


def test_validate_rejects_missing_required_fields():
    payload = engine.build_strategy_performance_analytics_report()
    for field in engine.REPORT_REQUIRED_FIELDS:
        bad = dict(payload)
        bad.pop(field, None)
        with pytest.raises(ValueError):
            engine.validate_strategy_performance_analytics_report(bad)


def test_validate_rejects_wrong_safety_flags():
    payload = engine.build_strategy_performance_analytics_report()
    for field, value in [
        ("paper_trade_mode", False),
        ("live_trading_enabled", True),
        ("broker_execution_enabled", True),
        ("reporting_only", False),
    ]:
        bad = dict(payload)
        bad[field] = value
        with pytest.raises(ValueError):
            engine.validate_strategy_performance_analytics_report(bad)


def test_json_csv_markdown_outputs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = engine.write_strategy_performance_analytics_report_json()
    assert engine.read_strategy_performance_analytics_report_json() == payload
    engine.write_strategy_performance_analytics_report_csv()
    engine.write_strategy_performance_analytics_report_markdown()
    assert Path("strategy_performance_analytics.json").exists()
    assert Path("strategy_performance_analytics.csv").exists()
    assert Path("strategy_performance_analytics.md").exists()
    markdown = engine.format_strategy_performance_analytics_markdown(payload)
    assert "# Strategy Performance Analytics Report" in markdown
    assert "## Strategy Metrics" in markdown
    assert "## Analytics Rules" in markdown
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
