"""
Tests for opportunity_pairing_engine.py.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

import opportunity_pairing_engine as engine


def test_dataclasses_exist():
    assert hasattr(engine, "OpportunityComponent")
    assert hasattr(engine, "InvestmentOpportunity")
    assert hasattr(engine, "OpportunityPairingReport")


def test_required_functions_exist():
    for name in [
        "build_opportunity_pairing_report",
        "validate_opportunity_pairing_report",
        "calculate_opportunity_score",
        "classify_opportunity_recommendation",
        "compare_opportunities",
        "rank_opportunities",
        "write_opportunity_pairing_report_json",
        "read_opportunity_pairing_report_json",
        "write_opportunity_pairing_report_csv",
        "format_opportunity_pairing_report_markdown",
        "write_opportunity_pairing_report_markdown",
    ]:
        assert callable(getattr(engine, name))


def test_empty_report_is_valid():
    payload = engine.build_opportunity_pairing_report()
    assert payload["opportunities"] == []
    assert payload["opportunity_count"] == 0
    assert engine.validate_opportunity_pairing_report(payload) is True


def test_required_fields_exist():
    payload = engine.build_opportunity_pairing_report()
    for field in engine.REPORT_REQUIRED_FIELDS:
        assert field in payload
    raw = {
        "opportunity_name": "Sample",
        "opportunity_type": "DIVIDEND_ETF",
    }
    entry = engine.rank_opportunities([raw])[0]
    for field in engine.OPPORTUNITY_FIELDS:
        assert field in entry


def test_paper_trade_mode_always_true():
    payload = engine.build_opportunity_pairing_report()
    assert payload["paper_trade_mode"] is True
    assert payload["reporting_only"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False


def test_default_weights_total_100():
    assert sum(engine.DEFAULT_SCORE_WEIGHTS.values()) == 100


def test_invalid_weights_fail_validation():
    payload = engine.build_opportunity_pairing_report()
    bad = dict(payload)
    bad["score_weights"] = dict(payload["score_weights"])
    bad["score_weights"]["liquidity_score"] = 6
    with pytest.raises(ValueError):
        engine.validate_opportunity_pairing_report(bad)


def test_scoring_favors_income_growth_balance():
    balanced = {
        "opportunity_name": "Balanced",
        "opportunity_type": "ETF_PAIR",
        "income_score": 80,
        "growth_score": 80,
        "total_return_score": 80,
        "sustainability_score": 75,
        "risk_score": 30,
        "liquidity_score": 80,
        "volatility_score": 30,
        "expense_score": 20,
    }
    yield_only = {
        "opportunity_name": "Yield Only",
        "opportunity_type": "COVERED_CALL_ETF",
        "income_score": 95,
        "growth_score": 20,
        "total_return_score": 40,
        "sustainability_score": 50,
        "risk_score": 45,
        "liquidity_score": 70,
        "volatility_score": 35,
        "expense_score": 30,
    }
    assert engine.calculate_opportunity_score(balanced, engine.DEFAULT_SCORE_WEIGHTS) > engine.calculate_opportunity_score(yield_only, engine.DEFAULT_SCORE_WEIGHTS)


def test_etf_pair_can_outrank_standalone_covered_call_etf():
    pair = {
        "opportunity_name": "Income Growth Pair",
        "opportunity_type": "ETF_PAIR",
        "income_symbol": "AMDW",
        "growth_symbol": "AMDL",
        "income_score": 75,
        "growth_score": 90,
        "total_return_score": 85,
        "sustainability_score": 75,
        "risk_score": 35,
        "liquidity_score": 80,
    }
    covered_call = {
        "opportunity_name": "Covered Call ETF",
        "opportunity_type": "COVERED_CALL_ETF",
        "income_symbol": "QQQY",
        "income_score": 90,
        "growth_score": 35,
        "total_return_score": 55,
        "sustainability_score": 60,
        "risk_score": 45,
        "liquidity_score": 80,
    }
    ranked = engine.rank_opportunities([covered_call, pair])
    assert ranked[0]["opportunity_name"] == "Income Growth Pair"


def test_standalone_leveraged_etf_can_outrank_etf_pair():
    pair = {
        "opportunity_name": "TSLW + TSLL",
        "opportunity_type": "ETF_PAIR",
        "income_symbol": "TSLW",
        "growth_symbol": "TSLL",
        "income_score": 70,
        "growth_score": 70,
        "total_return_score": 70,
        "sustainability_score": 60,
        "risk_score": 55,
        "liquidity_score": 75,
    }
    leveraged = {
        "opportunity_name": "SSO",
        "opportunity_type": "LEVERAGED_ETF",
        "growth_symbol": "SSO",
        "income_score": 20,
        "growth_score": 95,
        "total_return_score": 95,
        "sustainability_score": 80,
        "risk_score": 30,
        "liquidity_score": 95,
    }
    ranked = engine.rank_opportunities([pair, leveraged])
    assert ranked[0]["opportunity_name"] == "SSO"


def test_amdw_amdl_example_beats_qqqy():
    amdw_amdl = {
        "opportunity_name": "AMDW + AMDL",
        "opportunity_type": "ETF_PAIR",
        "income_symbol": "AMDW",
        "growth_symbol": "AMDL",
        "income_score": 80,
        "growth_score": 90,
        "total_return_score": 85,
        "sustainability_score": 80,
        "risk_score": 40,
        "liquidity_score": 80,
    }
    qqqy = {
        "opportunity_name": "QQQY",
        "opportunity_type": "COVERED_CALL_ETF",
        "income_symbol": "QQQY",
        "income_score": 95,
        "growth_score": 35,
        "total_return_score": 55,
        "sustainability_score": 60,
        "risk_score": 45,
        "liquidity_score": 85,
    }
    assert engine.rank_opportunities([qqqy, amdw_amdl])[0]["opportunity_name"] == "AMDW + AMDL"


def test_sso_example_beats_tslw_tsll():
    tslw_tsll = {
        "opportunity_name": "TSLW + TSLL",
        "opportunity_type": "ETF_PAIR",
        "income_symbol": "TSLW",
        "growth_symbol": "TSLL",
        "income_score": 80,
        "growth_score": 70,
        "total_return_score": 70,
        "sustainability_score": 60,
        "risk_score": 55,
        "liquidity_score": 80,
    }
    sso = {
        "opportunity_name": "SSO",
        "opportunity_type": "LEVERAGED_ETF",
        "growth_symbol": "SSO",
        "income_score": 25,
        "growth_score": 95,
        "total_return_score": 95,
        "sustainability_score": 80,
        "risk_score": 30,
        "liquidity_score": 95,
    }
    assert engine.rank_opportunities([tslw_tsll, sso])[0]["opportunity_name"] == "SSO"


def test_ranking_sorts_highest_score_first():
    opportunities = [
        {"opportunity_name": "Low", "opportunity_type": "DIVIDEND_ETF", "income_score": 20},
        {"opportunity_name": "High", "opportunity_type": "DIVIDEND_ETF", "income_score": 90, "growth_score": 90, "total_return_score": 90, "sustainability_score": 90, "risk_score": 10, "liquidity_score": 90},
        {"opportunity_name": "Mid", "opportunity_type": "DIVIDEND_ETF", "income_score": 60, "growth_score": 60, "total_return_score": 60, "sustainability_score": 60, "risk_score": 40, "liquidity_score": 60},
    ]
    ranked = engine.rank_opportunities(opportunities)
    assert [item["opportunity_name"] for item in ranked] == ["High", "Mid", "Low"]
    assert [item["allocation_priority"] for item in ranked] == [1, 2, 3]


@pytest.mark.parametrize(
    "score,recommendation",
    [
        (85, "STRONG_OPPORTUNITY"),
        (100, "STRONG_OPPORTUNITY"),
        (75, "GOOD_OPPORTUNITY"),
        (84.99, "GOOD_OPPORTUNITY"),
        (60, "WATCHLIST"),
        (74.99, "WATCHLIST"),
        (45, "HOLD_ONLY"),
        (59.99, "HOLD_ONLY"),
        (44.99, "AVOID"),
        (0, "AVOID"),
    ],
)
def test_recommendation_classification_thresholds(score, recommendation):
    assert engine.classify_opportunity_recommendation(score) == recommendation


def test_compare_opportunities_returns_better():
    a = {"opportunity_name": "A", "opportunity_type": "DIVIDEND_ETF", "combined_score": 80}
    b = {"opportunity_name": "B", "opportunity_type": "DIVIDEND_ETF", "combined_score": 70}
    assert engine.compare_opportunities(a, b) is a


def test_json_write_read(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "opportunity_pairing_report.json"
    written = engine.write_opportunity_pairing_report_json(path=str(output))
    read = engine.read_opportunity_pairing_report_json(path=str(output))
    assert output.exists()
    assert read == written


def test_csv_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "opportunity_pairing_report.csv"
    payload = engine.write_opportunity_pairing_report_csv(path=str(output))
    assert output.exists()
    with output.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows == []
    assert payload["opportunity_count"] == 0


def test_markdown_formatting():
    payload = engine.build_opportunity_pairing_report()
    markdown = engine.format_opportunity_pairing_report_markdown(payload)
    assert "# Opportunity Pairing Report" in markdown
    assert "## Score Weights" in markdown
    assert "## Opportunities" in markdown
    assert "## Safety Guarantees" in markdown


def test_markdown_write(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "opportunity_pairing_report.md"
    engine.write_opportunity_pairing_report_markdown(path=str(output))
    assert output.exists()
    assert "# Opportunity Pairing Report" in output.read_text(encoding="utf-8")


def test_validate_rejects_missing_required_fields():
    payload = engine.build_opportunity_pairing_report()
    for field in engine.REPORT_REQUIRED_FIELDS:
        bad = dict(payload)
        bad.pop(field, None)
        with pytest.raises(ValueError):
            engine.validate_opportunity_pairing_report(bad)


def test_validate_rejects_invalid_opportunity_fields():
    payload = engine.build_opportunity_pairing_report([
        {"opportunity_name": "Bad", "opportunity_type": "DIVIDEND_ETF", "income_score": 50}
    ])
    bad = dict(payload)
    entries = [dict(item) for item in payload["opportunities"]]
    entries[0]["combined_score"] = 101
    bad["opportunities"] = entries
    with pytest.raises(ValueError):
        engine.validate_opportunity_pairing_report(bad)


def test_no_brokerage_execution_fields_functions():
    names = [name.lower() for name in dir(engine)]
    forbidden = [
        "place_order",
        "submit_order",
        "execute_order",
        "execute_trade",
        "live_trade",
        "broker_client",
        "account_id",
        "order_id",
        "quantity",
        "shares_to_buy",
        "shares_to_sell",
    ]
    for item in forbidden:
        assert item not in names


def test_no_robinhood_execution_fields_functions():
    source = Path(engine.__file__).read_text(encoding="utf-8").lower()
    assert "import robinhood" not in source
    assert "from robinhood" not in source
    assert "import robin_stocks" not in source
    assert "from robin_stocks" not in source


def test_no_order_placement_logic():
    source = Path(engine.__file__).read_text(encoding="utf-8").lower()
    forbidden = [
        ".place_order(",
        ".submit_order(",
        ".buy(",
        ".sell(",
        "place_order(",
        "submit_order(",
        "execute_order(",
        "real_order",
        "live_order",
    ]
    for item in forbidden:
        assert item not in source


def test_no_subprocess_or_os_system_usage():
    source = Path(engine.__file__).read_text(encoding="utf-8")
    forbidden = ["import subprocess", "from subprocess", "subprocess.", "Popen(", "os.system(", ".system("]
    for item in forbidden:
        assert item not in source
