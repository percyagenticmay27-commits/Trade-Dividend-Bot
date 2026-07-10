"""Tests for daily_portfolio_command_center.py."""
from pathlib import Path
import pytest
import daily_portfolio_command_center as engine


def test_dataclasses_exist():
    assert hasattr(engine, "CommandCenterAction")
    assert hasattr(engine, "DailyPortfolioCommandCenterReport")


def test_public_functions_exist():
    for name in [
        "build_daily_portfolio_command_center",
        "validate_daily_portfolio_command_center",
        "write_daily_portfolio_command_center_json",
        "read_daily_portfolio_command_center_json",
        "write_daily_portfolio_command_center_csv",
        "format_daily_portfolio_command_center_markdown",
        "write_daily_portfolio_command_center_markdown",
    ]:
        assert callable(getattr(engine, name))


def test_default_report_valid_with_missing_input_warnings():
    payload = engine.build_daily_portfolio_command_center()
    assert engine.validate_daily_portfolio_command_center(payload) is True
    assert payload["paper_trade_mode"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False
    assert payload["reporting_only"] is True
    assert set(payload["missing_inputs"]) == set(engine.INPUT_NAMES)
    assert payload["warnings"]


def test_lifecycle_values_are_aggregated():
    lifecycle = {
        "portfolio_value": 500,
        "cash_balance": 100,
        "cash_reserve_target_dollars": 100,
        "market_regime": "BULL",
        "income_summary": {"expected_monthly_income": 5, "expected_annual_income": 60},
        "lifecycle_actions": [
            {"symbol": "AAA", "lifecycle_action": "INCREASE", "master_score": 95, "reason": ["Strong rank"]},
            {"symbol": "BBB", "lifecycle_action": "EXIT_TO_SGOV", "master_score": 40, "reason": ["Sale signal"]},
        ],
    }
    payload = engine.build_daily_portfolio_command_center(portfolio_lifecycle=lifecycle)
    assert payload["portfolio_value"] == 500
    assert payload["expected_monthly_income"] == 5
    assert payload["expected_annual_income"] == 60
    assert payload["increase_actions"][0]["symbol"] == "AAA"
    assert payload["exit_actions"][0]["symbol"] == "BBB"
    assert payload["portfolio_status"] in engine.SUPPORTED_PORTFOLIO_STATUSES


def test_rebalance_and_reinvestment_are_aggregated():
    rebalance = {
        "market_regime": "NEUTRAL",
        "rebalance_actions": [
            {"symbol": "AAA", "recommended_action": "REALLOCATE_TO_BETTER_OPPORTUNITY", "master_score": 55, "why": ["Better candidate"]},
            {"symbol": "BBB", "recommended_action": "REENTER_ORIGINAL", "master_score": 70, "why": ["No better candidate"]},
        ],
    }
    reinvestment = {
        "cash_balance": 125,
        "cash_reserve_target_dollars": 100,
        "reinvestment_actions": [{"source_symbol": "JEPI", "action": "SELF_REINVEST", "destination_symbol": "JEPI", "destination_amount": 5}],
    }
    payload = engine.build_daily_portfolio_command_center(
        portfolio_rebalance=rebalance,
        income_reinvestment=reinvestment,
    )
    assert payload["pending_reallocations"][0]["symbol"] == "AAA"
    assert payload["reentry_actions"][0]["symbol"] == "BBB"
    assert len(payload["reinvestment_actions"]) == 1


def test_top_opportunities_sorted():
    pairing = {
        "opportunities": [
            {"opportunity_name": "Pair A", "income_symbol": "AAA", "combined_score": 80, "recommendation": "GOOD"},
            {"opportunity_name": "Pair B", "income_symbol": "BBB", "combined_score": 95, "recommendation": "STRONG"},
        ]
    }
    ranking = {
        "rankings": [
            {"symbol": "CCC", "overall_score": 90, "recommendation": "BUY"}
        ]
    }
    payload = engine.build_daily_portfolio_command_center(
        opportunity_pairing=pairing,
        dividend_ranking=ranking,
    )
    assert [row["symbol"] for row in payload["top_opportunities"]][:3] == ["BBB", "CCC", "AAA"]


def test_risk_flags_lower_health_score():
    clean = engine.build_daily_portfolio_command_center(portfolio_lifecycle={"risk_flags": []})
    risky = engine.build_daily_portfolio_command_center(portfolio_lifecycle={"risk_flags": ["A", "B", "C"]})
    assert risky["portfolio_health_score"] < clean["portfolio_health_score"]


def test_validate_rejects_malformed_payload():
    for value in [None, [], "bad"]:
        with pytest.raises(ValueError):
            engine.validate_daily_portfolio_command_center(value)


def test_validate_rejects_missing_required_fields():
    payload = engine.build_daily_portfolio_command_center()
    for field in engine.REPORT_REQUIRED_FIELDS:
        bad = dict(payload)
        bad.pop(field, None)
        with pytest.raises(ValueError):
            engine.validate_daily_portfolio_command_center(bad)


def test_validate_rejects_wrong_safety_flags():
    payload = engine.build_daily_portfolio_command_center()
    for field, value in [
        ("paper_trade_mode", False),
        ("live_trading_enabled", True),
        ("broker_execution_enabled", True),
        ("reporting_only", False),
    ]:
        bad = dict(payload)
        bad[field] = value
        with pytest.raises(ValueError):
            engine.validate_daily_portfolio_command_center(bad)


def test_json_csv_markdown_outputs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = engine.write_daily_portfolio_command_center_json()
    assert engine.read_daily_portfolio_command_center_json() == payload
    engine.write_daily_portfolio_command_center_csv()
    engine.write_daily_portfolio_command_center_markdown()
    assert Path("daily_portfolio_command_center.json").exists()
    assert Path("daily_portfolio_command_center.csv").exists()
    assert Path("daily_portfolio_command_center.md").exists()
    markdown = engine.format_daily_portfolio_command_center_markdown(payload)
    assert "# Daily Portfolio Command Center" in markdown
    assert "## Executive Recommendation" in markdown
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
