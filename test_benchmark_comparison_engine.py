"""Tests for benchmark_comparison_engine.py."""
from __future__ import annotations

from pathlib import Path
import pytest
import benchmark_comparison_engine as engine


def test_dataclasses_exist():
    assert hasattr(engine, "BenchmarkPeriodResult")
    assert hasattr(engine, "BenchmarkComparisonReport")


def test_public_functions_exist():
    for name in [
        "validate_benchmark_weights",
        "calculate_blended_return",
        "classify_performance",
        "calculate_max_drawdown",
        "calculate_sharpe_like",
        "annualize_monthly_return",
        "build_benchmark_comparison_report",
        "validate_benchmark_comparison_report",
        "write_benchmark_comparison_report_json",
        "read_benchmark_comparison_report_json",
        "write_benchmark_comparison_report_csv",
        "format_benchmark_comparison_report_markdown",
        "write_benchmark_comparison_report_markdown",
    ]:
        assert callable(getattr(engine, name))


def test_default_report_valid_and_empty():
    payload = engine.build_benchmark_comparison_report()
    assert engine.validate_benchmark_comparison_report(payload) is True
    assert payload["monthly_status"] == "INSUFFICIENT_DATA"
    assert payload["paper_trade_mode"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False
    assert payload["reporting_only"] is True


def test_approved_benchmark_weights():
    assert engine.BENCHMARK_WEIGHTS == {"SPY": 0.40, "QQQ": 0.25, "SCHD": 0.25, "SGOV": 0.10}
    assert sum(engine.BENCHMARK_WEIGHTS.values()) == 1.0
    assert engine.validate_benchmark_weights(engine.BENCHMARK_WEIGHTS) is True


def test_invalid_weights_rejected():
    with pytest.raises(ValueError):
        engine.validate_benchmark_weights({"SPY": 1.0})


def test_blended_return_calculation():
    result = engine.calculate_blended_return({"SPY": 0.10, "QQQ": 0.20, "SCHD": 0.05, "SGOV": 0.01})
    assert result == pytest.approx(0.1035)


def test_performance_classification():
    assert engine.classify_performance(0.01) == "OUTPERFORMING"
    assert engine.classify_performance(-0.01) == "UNDERPERFORMING"
    assert engine.classify_performance(0.0005) == "MATCHING"


def test_annualize_monthly_return():
    assert engine.annualize_monthly_return(0.04) == pytest.approx((1.04 ** 12) - 1.0)


def test_max_drawdown_calculation():
    result = engine.calculate_max_drawdown([0.10, -0.20, 0.05])
    assert result < 0


def test_sharpe_like_requires_variation():
    assert engine.calculate_sharpe_like([0.01]) == 0.0
    assert engine.calculate_sharpe_like([0.01, 0.01]) == 0.0
    assert engine.calculate_sharpe_like([0.01, 0.03, -0.01]) != 0.0


def test_report_calculates_alpha_and_goals():
    portfolio = [0.03, 0.05, 0.04]
    components = [
        {"SPY": 0.02, "QQQ": 0.03, "SCHD": 0.01, "SGOV": 0.003},
        {"SPY": 0.03, "QQQ": 0.04, "SCHD": 0.02, "SGOV": 0.003},
        {"SPY": 0.02, "QQQ": 0.025, "SCHD": 0.015, "SGOV": 0.003},
    ]
    payload = engine.build_benchmark_comparison_report(portfolio, components)
    assert payload["monthly_portfolio_return"] == 0.04
    assert payload["monthly_alpha"] > 0
    assert payload["monthly_status"] == "OUTPERFORMING"
    assert payload["monthly_stretch_goal"] == 0.04
    assert payload["annual_goal"] == 0.20
    assert payload["rolling_results"][0]["status"] != "INSUFFICIENT_DATA"


def test_rolling_periods_insufficient_when_history_short():
    payload = engine.build_benchmark_comparison_report([0.02], [{"SPY": 0.01, "QQQ": 0.01, "SCHD": 0.01, "SGOV": 0.001}])
    statuses = {row["period"]: row["status"] for row in payload["rolling_results"]}
    assert statuses["3_MONTH"] == "INSUFFICIENT_DATA"
    assert statuses["6_MONTH"] == "INSUFFICIENT_DATA"
    assert statuses["12_MONTH"] == "INSUFFICIENT_DATA"


def test_validate_rejects_malformed_payload():
    for value in [None, [], "bad"]:
        with pytest.raises(ValueError):
            engine.validate_benchmark_comparison_report(value)


def test_validate_rejects_missing_fields():
    payload = engine.build_benchmark_comparison_report()
    for field in engine.BenchmarkComparisonReport.__dataclass_fields__:
        bad = dict(payload)
        bad.pop(field, None)
        with pytest.raises(ValueError):
            engine.validate_benchmark_comparison_report(bad)


def test_validate_rejects_wrong_safety_flags():
    payload = engine.build_benchmark_comparison_report()
    for field, value in [
        ("paper_trade_mode", False),
        ("live_trading_enabled", True),
        ("broker_execution_enabled", True),
        ("reporting_only", False),
    ]:
        bad = dict(payload)
        bad[field] = value
        with pytest.raises(ValueError):
            engine.validate_benchmark_comparison_report(bad)


def test_json_csv_markdown_outputs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = engine.write_benchmark_comparison_report_json()
    assert engine.read_benchmark_comparison_report_json() == payload
    engine.write_benchmark_comparison_report_csv()
    engine.write_benchmark_comparison_report_markdown()
    assert Path("benchmark_comparison_report.json").exists()
    assert Path("benchmark_comparison_report.csv").exists()
    assert Path("benchmark_comparison_report.md").exists()
    markdown = engine.format_benchmark_comparison_report_markdown(payload)
    assert "# Benchmark Comparison Report" in markdown
    assert "## Approved Blended Benchmark" in markdown
    assert "## Rolling Performance" in markdown
    assert "## Safety" in markdown


def test_standard_library_only_and_safety_flags():
    source = Path(engine.__file__).read_text(encoding="utf-8")
    assert "PAPER_TRADE_MODE = True" in source
    assert "LIVE_TRADING_ENABLED = False" in source
    assert "BROKER_EXECUTION_ENABLED = False" in source
    assert "REPORTING_ONLY = True" in source
