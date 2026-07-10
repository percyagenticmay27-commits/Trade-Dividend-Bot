"""Tests for weekly_portfolio_report.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import weekly_portfolio_report as report


def test_dataclasses_exist():
    assert hasattr(report, "WeeklyPortfolioSummary")
    assert hasattr(report, "WeeklyPortfolioReport")


def test_public_functions_exist():
    for name in [
        "build_weekly_portfolio_report",
        "validate_weekly_portfolio_report",
        "write_weekly_portfolio_report_json",
        "read_weekly_portfolio_report_json",
        "write_weekly_portfolio_report_csv",
        "format_weekly_portfolio_report_markdown",
        "write_weekly_portfolio_report_markdown",
    ]:
        assert callable(getattr(report, name))


def test_empty_report_is_valid(tmp_path):
    payload = report.build_weekly_portfolio_report(root_path=str(tmp_path), week_ending="2026-07-10")
    assert report.validate_weekly_portfolio_report(payload) is True
    assert payload["paper_trade_mode"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False
    assert payload["reporting_only"] is True
    assert payload["week_ending"] == "2026-07-10"
    assert payload["weekly_summary"]["holdings_count"] == 0


def test_builds_summary_from_lifecycle_and_other_inputs(tmp_path):
    lifecycle = {
        "portfolio_value": 650,
        "cash_balance": 150,
        "cash_reserve_target_dollars": 130,
        "holdings_reviewed": 3,
        "income_summary": {"expected_monthly_income": 12, "expected_annual_income": 144},
        "lifecycle_actions": [
            {"symbol": "AAA", "current_rank": "A", "master_score": 95, "lifecycle_action": "INCREASE", "reason": ["strong"]},
            {"symbol": "BBB", "current_rank": "B", "master_score": 85, "lifecycle_action": "HOLD", "reason": ["stable"]},
            {"symbol": "CCC", "current_rank": "F", "master_score": 40, "lifecycle_action": "EXIT_TO_SGOV", "reason": ["sale signal"]},
        ],
    }
    reinvest = {"action_count": 2}
    rebalance = {"action_count": 1}
    (tmp_path / "portfolio_lifecycle_report.json").write_text(json.dumps(lifecycle), encoding="utf-8")
    (tmp_path / "income_reinvestment_report.json").write_text(json.dumps(reinvest), encoding="utf-8")
    (tmp_path / "portfolio_rebalance_report.json").write_text(json.dumps(rebalance), encoding="utf-8")

    payload = report.build_weekly_portfolio_report(root_path=str(tmp_path))
    summary = payload["weekly_summary"]
    assert summary["portfolio_value"] == 650
    assert summary["cash_balance"] == 150
    assert summary["cash_reserve_target"] == 130
    assert summary["expected_monthly_income"] == 12
    assert summary["expected_annual_income"] == 144
    assert summary["holdings_count"] == 3
    assert summary["increase_count"] == 1
    assert summary["hold_count"] == 1
    assert summary["exit_count"] == 1
    assert summary["reinvestment_action_count"] == 2
    assert summary["rebalance_action_count"] == 1
    assert payload["top_actions"][0]["symbol"] == "AAA"
    assert payload["risk_flags"]


def test_cash_below_reserve_creates_risk_flag(tmp_path):
    lifecycle = {
        "portfolio_value": 500,
        "cash_balance": 50,
        "cash_reserve_target_dollars": 100,
        "holdings_reviewed": 0,
        "income_summary": {},
        "lifecycle_actions": [],
    }
    (tmp_path / "portfolio_lifecycle_report.json").write_text(json.dumps(lifecycle), encoding="utf-8")
    payload = report.build_weekly_portfolio_report(root_path=str(tmp_path))
    assert any("below" in item.lower() for item in payload["risk_flags"])


def test_invalid_json_raises_value_error(tmp_path):
    (tmp_path / "portfolio_lifecycle_report.json").write_text("{bad", encoding="utf-8")
    with pytest.raises(ValueError):
        report.build_weekly_portfolio_report(root_path=str(tmp_path))


def test_validate_rejects_malformed_payload():
    for value in [None, [], "bad"]:
        with pytest.raises(ValueError):
            report.validate_weekly_portfolio_report(value)


def test_validate_rejects_missing_required_fields(tmp_path):
    payload = report.build_weekly_portfolio_report(root_path=str(tmp_path))
    for field in report.REPORT_REQUIRED_FIELDS:
        bad = dict(payload)
        bad.pop(field, None)
        with pytest.raises(ValueError):
            report.validate_weekly_portfolio_report(bad)


def test_validate_rejects_wrong_safety_flags(tmp_path):
    payload = report.build_weekly_portfolio_report(root_path=str(tmp_path))
    for field, value in [
        ("paper_trade_mode", False),
        ("live_trading_enabled", True),
        ("broker_execution_enabled", True),
        ("reporting_only", False),
    ]:
        bad = dict(payload)
        bad[field] = value
        with pytest.raises(ValueError):
            report.validate_weekly_portfolio_report(bad)


def test_json_csv_markdown_outputs(tmp_path):
    json_path = tmp_path / "weekly_portfolio_report.json"
    csv_path = tmp_path / "weekly_portfolio_report.csv"
    md_path = tmp_path / "weekly_portfolio_report.md"

    written = report.write_weekly_portfolio_report_json(path=str(json_path), root_path=str(tmp_path))
    read_back = report.read_weekly_portfolio_report_json(path=str(json_path))
    assert read_back == written
    report.write_weekly_portfolio_report_csv(path=str(csv_path), root_path=str(tmp_path))
    report.write_weekly_portfolio_report_markdown(path=str(md_path), root_path=str(tmp_path))

    assert json_path.exists()
    assert csv_path.exists()
    assert md_path.exists()
    markdown = report.format_weekly_portfolio_report_markdown(written)
    assert "# Weekly Portfolio Report" in markdown
    assert "## Weekly Actions" in markdown
    assert "## Risk Flags" in markdown
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
