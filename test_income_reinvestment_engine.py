"""Tests for income_reinvestment_engine.py."""
from __future__ import annotations

from pathlib import Path
import pytest
import income_reinvestment_engine as engine


def test_dataclasses_exist():
    assert hasattr(engine, "DistributionEvent")
    assert hasattr(engine, "ReinvestmentAction")
    assert hasattr(engine, "IncomeReinvestmentReport")


def test_public_functions_exist():
    for name in [
        "determine_cash_reserve_target",
        "normalize_distribution",
        "build_reinvestment_actions",
        "build_reinvestment_ledger",
        "build_income_reinvestment_report",
        "validate_income_reinvestment_report",
        "write_income_reinvestment_report_json",
        "read_income_reinvestment_report_json",
        "write_income_reinvestment_report_csv",
        "format_income_reinvestment_report_markdown",
        "write_income_reinvestment_report_markdown",
    ]:
        assert callable(getattr(engine, name))


def test_default_empty_report_valid():
    payload = engine.build_income_reinvestment_report()
    assert engine.validate_income_reinvestment_report(payload) is True
    assert payload["paper_trade_mode"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False
    assert payload["reporting_only"] is True
    assert payload["total_distributions_received"] == 0


def test_cash_reserve_target_by_regime():
    assert engine.determine_cash_reserve_target("BULL") == 0.20
    assert engine.determine_cash_reserve_target("NEUTRAL") == 0.25
    assert engine.determine_cash_reserve_target("BEAR") == 0.30


def test_single_holding_reinvests_into_itself_when_reserve_protected():
    payload = engine.build_income_reinvestment_report(
        [{"source_symbol": "JEPI", "distribution_amount": 10, "holding_type": "SINGLE"}],
        portfolio_value=500,
        cash_balance=200,
        market_regime="BULL",
    )
    action = payload["reinvestment_actions"][0]
    assert action["action"] == "SELF_REINVEST"
    assert action["destination_symbol"] == "JEPI"
    assert action["destination_amount"] == 10


def test_etf_pair_splits_distribution_50_50():
    payload = engine.build_income_reinvestment_report(
        [{"source_symbol": "AMDW_AMDL", "distribution_amount": 11, "holding_type": "ETF_PAIR", "income_symbol": "AMDW", "growth_symbol": "AMDL"}],
        portfolio_value=500,
        cash_balance=200,
        market_regime="BULL",
    )
    assert len(payload["reinvestment_actions"]) == 2
    assert payload["reinvestment_actions"][0]["destination_symbol"] == "AMDW"
    assert payload["reinvestment_actions"][0]["destination_amount"] == 5.5
    assert payload["reinvestment_actions"][1]["destination_symbol"] == "AMDL"
    assert payload["reinvestment_actions"][1]["destination_amount"] == 5.5


def test_reserve_below_target_protects_sgov_first():
    payload = engine.build_income_reinvestment_report(
        [{"source_symbol": "JEPI", "distribution_amount": 10, "holding_type": "SINGLE"}],
        portfolio_value=500,
        cash_balance=50,
        market_regime="BULL",
    )
    action = payload["reinvestment_actions"][0]
    assert action["action"] == "PROTECT_CASH_RESERVE"
    assert action["destination_symbol"] == "SGOV"


def test_exceptional_opportunity_deploys_ten_percent_excess_cash():
    payload = engine.build_income_reinvestment_report(
        [],
        portfolio_value=500,
        cash_balance=200,
        market_regime="BULL",
        opportunities=[{"symbol": "AMD", "allocation_score": 95}],
    )
    deploy = [a for a in payload["reinvestment_actions"] if a["action"] == "DEPLOY_EXCESS_CASH"]
    assert deploy
    assert deploy[0]["destination_symbol"] == "AMD"
    assert deploy[0]["destination_amount"] == 10.0


def test_cash_shield_distribution_holds_cash():
    payload = engine.build_income_reinvestment_report(
        [{"source_symbol": "SGOV", "distribution_amount": 3, "holding_type": "CASH_SHIELD"}],
        portfolio_value=500,
        cash_balance=200,
        market_regime="BULL",
    )
    assert payload["reinvestment_actions"][0]["action"] == "HOLD_CASH"


def test_validate_rejects_malformed_payload():
    for value in [None, [], "bad"]:
        with pytest.raises(ValueError):
            engine.validate_income_reinvestment_report(value)


def test_validate_rejects_missing_required_fields():
    payload = engine.build_income_reinvestment_report()
    for field in engine.REPORT_REQUIRED_FIELDS:
        bad = dict(payload)
        bad.pop(field, None)
        with pytest.raises(ValueError):
            engine.validate_income_reinvestment_report(bad)


def test_validate_rejects_wrong_safety_flags():
    payload = engine.build_income_reinvestment_report()
    for field, value in [("paper_trade_mode", False), ("live_trading_enabled", True), ("broker_execution_enabled", True), ("reporting_only", False)]:
        bad = dict(payload)
        bad[field] = value
        with pytest.raises(ValueError):
            engine.validate_income_reinvestment_report(bad)


def test_json_csv_markdown_outputs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = engine.write_income_reinvestment_report_json()
    assert engine.read_income_reinvestment_report_json() == payload
    engine.write_income_reinvestment_report_csv()
    engine.write_income_reinvestment_report_markdown()
    assert Path("income_reinvestment_report.json").exists()
    assert Path("income_reinvestment_report.csv").exists()
    assert Path("income_reinvestment_report.md").exists()
    markdown = engine.format_income_reinvestment_report_markdown(payload)
    assert "# Income Reinvestment Report" in markdown
    assert "## Reinvestment Rules" in markdown
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
