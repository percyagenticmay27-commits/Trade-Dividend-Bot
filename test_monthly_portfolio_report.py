"""Tests for monthly_portfolio_report.py."""
from __future__ import annotations

from pathlib import Path
import pytest
import monthly_portfolio_report as report


def test_dataclasses_exist():
    assert hasattr(report, "MonthlyActualResults")
    assert hasattr(report, "MonthlyPortfolioReport")


def test_public_functions_exist():
    for name in [
        "calculate_blended_benchmark_return",
        "classify_benchmark_status",
        "classify_goal_status",
        "build_monthly_portfolio_report",
        "validate_monthly_portfolio_report",
        "write_monthly_portfolio_report_json",
        "read_monthly_portfolio_report_json",
        "write_monthly_portfolio_report_csv",
        "format_monthly_portfolio_report_markdown",
        "write_monthly_portfolio_report_markdown",
    ]:
        assert callable(getattr(report, name))


def test_default_report_is_valid_and_safe():
    payload = report.build_monthly_portfolio_report()
    assert report.validate_monthly_portfolio_report(payload) is True
    assert payload["paper_trade_mode"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False
    assert payload["reporting_only"] is True
    assert payload["learning_summary"]["approval_required"] is True


def test_blended_benchmark_calculation():
    returns = {"SPY": 0.02, "QQQ": 0.04, "SCHD": 0.01, "SGOV": 0.003}
    expected = round((0.02 * 0.40) + (0.04 * 0.25) + (0.01 * 0.25) + (0.003 * 0.10), 4)
    assert report.calculate_blended_benchmark_return(returns) == expected


def test_benchmark_classification():
    assert report.classify_benchmark_status(0.04, 0.03) == "OUTPERFORMING"
    assert report.classify_benchmark_status(0.02, 0.03) == "UNDERPERFORMING"
    assert report.classify_benchmark_status(0.03, 0.03) == "MATCHING"


def test_goal_classification():
    assert report.classify_goal_status(0.04, 0.04) == "AHEAD_OF_PLAN"
    assert report.classify_goal_status(0.038, 0.04) == "ON_TRACK"
    assert report.classify_goal_status(0.02, 0.04) == "GAP_TO_TARGET"


def test_actual_results_and_prior_month_comparison():
    current = {
        "portfolio_start_value": 500,
        "portfolio_end_value": 525,
        "net_contributions": 0,
        "total_distributions": 5,
        "monthly_income": 5,
        "projected_annual_income": 60,
        "average_opportunity_score": 84,
        "average_conviction_score": 82,
        "average_entry_score": 78,
    }
    previous = {
        "portfolio_end_value": 500,
        "monthly_income": 4,
        "projected_annual_income": 48,
        "average_opportunity_score": 80,
        "average_conviction_score": 79,
        "average_entry_score": 75,
    }
    payload = report.build_monthly_portfolio_report(current, previous, {"SPY": 0.02, "QQQ": 0.02, "SCHD": 0.01, "SGOV": 0.003}, "2026-07")
    assert payload["actual_results"]["total_return_pct"] == 0.06
    assert payload["prior_month_comparison"]["monthly_income_change"] == 1
    assert payload["prior_month_comparison"]["opportunity_score_change"] == 4
    assert payload["benchmark_comparison"]["status"] == "OUTPERFORMING"


def test_actual_and_forward_looking_sections_are_separate():
    current = {
        "leaders": [{"symbol": "PLTR", "score": 90}],
        "emerging_leaders": [{"symbol": "AMD", "score": 88}],
        "fading_opportunities": [{"symbol": "PLTY", "score": 45}],
        "watch_next": ["Watch AMDW + AMDL for leadership confirmation."],
    }
    payload = report.build_monthly_portfolio_report(current=current)
    assert payload["leaders"][0]["symbol"] == "PLTR"
    assert payload["emerging_leaders"][0]["symbol"] == "AMD"
    assert payload["fading_opportunities"][0]["symbol"] == "PLTY"
    assert payload["watch_next"]


def test_semia_adaptive_learning_requires_approval():
    payload = report.build_monthly_portfolio_report(current={"proposed_changes": ["Increase momentum weight by 2 points."]})
    assert payload["learning_summary"]["proposed_changes"]
    assert payload["learning_summary"]["approval_required"] is True


def test_validate_rejects_malformed_payload():
    for value in [None, [], "bad"]:
        with pytest.raises(ValueError):
            report.validate_monthly_portfolio_report(value)


def test_validate_rejects_missing_required_fields():
    payload = report.build_monthly_portfolio_report()
    for field in report.REPORT_REQUIRED_FIELDS:
        bad = dict(payload)
        bad.pop(field, None)
        with pytest.raises(ValueError):
            report.validate_monthly_portfolio_report(bad)


def test_validate_rejects_wrong_safety_flags():
    payload = report.build_monthly_portfolio_report()
    for field, value in [
        ("paper_trade_mode", False),
        ("live_trading_enabled", True),
        ("broker_execution_enabled", True),
        ("reporting_only", False),
    ]:
        bad = dict(payload)
        bad[field] = value
        with pytest.raises(ValueError):
            report.validate_monthly_portfolio_report(bad)


def test_validate_rejects_learning_without_approval():
    payload = report.build_monthly_portfolio_report()
    bad = dict(payload)
    bad["learning_summary"] = dict(payload["learning_summary"])
    bad["learning_summary"]["approval_required"] = False
    with pytest.raises(ValueError):
        report.validate_monthly_portfolio_report(bad)


def test_json_csv_markdown_outputs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = report.write_monthly_portfolio_report_json()
    assert report.read_monthly_portfolio_report_json() == payload
    report.write_monthly_portfolio_report_csv()
    report.write_monthly_portfolio_report_markdown()
    assert Path("monthly_portfolio_report.json").exists()
    assert Path("monthly_portfolio_report.csv").exists()
    assert Path("monthly_portfolio_report.md").exists()
    markdown = report.format_monthly_portfolio_report_markdown(payload)
    assert "# Monthly Portfolio Report" in markdown
    assert "## Goal Progress" in markdown
    assert "## Executive Summary" in markdown
    assert "## Emerging Leaders" in markdown
    assert "## Watch Next" in markdown
    assert "## Safety Guarantees" in markdown


def test_static_safety_no_restricted_execution_terms():
    source = Path(report.__file__).read_text(encoding="utf-8").lower()
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
    source = Path(report.__file__).read_text(encoding="utf-8")
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
