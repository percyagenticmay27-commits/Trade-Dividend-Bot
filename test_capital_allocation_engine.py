"""Tests for capital_allocation_engine.py."""

from __future__ import annotations

from pathlib import Path

import pytest

import capital_allocation_engine as engine


def test_dataclasses_exist():
    assert hasattr(engine, "CapitalAllocationInput")
    assert hasattr(engine, "CapitalAllocation")
    assert hasattr(engine, "CapitalAllocationReport")


def test_public_functions_exist():
    for name in [
        "determine_portfolio_tier",
        "calculate_allocation_score",
        "build_allocations",
        "build_capital_allocation_report",
        "validate_capital_allocation_report",
        "write_capital_allocation_report_json",
        "read_capital_allocation_report_json",
        "write_capital_allocation_report_csv",
        "format_capital_allocation_report_markdown",
        "write_capital_allocation_report_markdown",
    ]:
        assert callable(getattr(engine, name))


def test_default_500_account_report_is_valid():
    payload = engine.build_capital_allocation_report()
    assert engine.validate_capital_allocation_report(payload) is True
    assert payload["starting_capital"] == 500.0
    assert payload["current_portfolio_value"] == 500.0
    assert payload["portfolio_tier"] == "TIER_1_FOUNDATION"
    assert payload["target_holding_count"] == 2
    assert payload["cash_reserve_target_pct"] == 0.20
    assert payload["cash_reserve_target_dollars"] == 100.0
    assert payload["investable_cash"] == 400.0


@pytest.mark.parametrize(
    "value,tier",
    [
        (500, "TIER_1_FOUNDATION"),
        (999.99, "TIER_1_FOUNDATION"),
        (1000, "TIER_2_DIVERSIFICATION"),
        (4999.99, "TIER_2_DIVERSIFICATION"),
        (5000, "TIER_3_GROWTH_AND_INCOME"),
        (24999.99, "TIER_3_GROWTH_AND_INCOME"),
        (25000, "TIER_4_OPTIMIZATION"),
        (99999.99, "TIER_4_OPTIMIZATION"),
        (100000, "TIER_5_ADVANCED_OPTIMIZATION"),
    ],
)
def test_portfolio_tiers(value, tier):
    assert engine.determine_portfolio_tier(value) == tier


def test_allocation_score_calculation():
    candidate = {
        "decision_score": 100,
        "conviction_score": 100,
        "opportunity_score": 100,
        "entry_score": 100,
        "self_funding_score": 100,
        "confidence": 1.0,
    }
    assert engine.calculate_allocation_score(candidate) == 100.0
    assert engine.calculate_allocation_score({}) == 0.0


def test_500_account_selects_two_best_candidates():
    candidates = [
        {"symbol": "AAA", "decision_score": 100, "conviction_score": 100, "opportunity_score": 100, "entry_score": 100, "self_funding_score": 100, "confidence": 1.0},
        {"symbol": "BBB", "decision_score": 90, "conviction_score": 90, "opportunity_score": 90, "entry_score": 90, "self_funding_score": 90, "confidence": 0.9},
        {"symbol": "CCC", "decision_score": 80, "conviction_score": 80, "opportunity_score": 80, "entry_score": 80, "self_funding_score": 80, "confidence": 0.8},
    ]
    payload = engine.build_capital_allocation_report(candidates=candidates, current_portfolio_value=500, available_cash=500)
    assert payload["allocation_count"] == 2
    assert [row["symbol"] for row in payload["allocations"]] == ["AAA", "BBB"]
    assert all(row["allocation_action"] == "ALLOCATE" for row in payload["allocations"])


def test_minimum_position_size_skips_small_allocations():
    candidates = [{"symbol": "AAA", "decision_score": 100}, {"symbol": "BBB", "decision_score": 100}]
    payload = engine.build_capital_allocation_report(candidates=candidates, current_portfolio_value=500, available_cash=100)
    assert all(row["allocation_action"] == "SKIP_SMALL_POSITION" for row in payload["allocations"])


def test_max_position_cap_is_enforced():
    candidates = [{"symbol": "AAA", "decision_score": 100, "conviction_score": 100, "opportunity_score": 100, "entry_score": 100, "self_funding_score": 100, "confidence": 1.0}]
    payload = engine.build_capital_allocation_report(candidates=candidates, current_portfolio_value=500, available_cash=500)
    assert payload["allocations"][0]["target_allocation_dollars"] <= 200.0


def test_larger_account_targets_more_holdings():
    candidates = [{"symbol": f"AAA{i}", "decision_score": 90, "conviction_score": 90, "opportunity_score": 90, "entry_score": 90, "self_funding_score": 90, "confidence": 0.9} for i in range(20)]
    payload = engine.build_capital_allocation_report(candidates=candidates, current_portfolio_value=10000, available_cash=10000)
    assert payload["portfolio_tier"] == "TIER_3_GROWTH_AND_INCOME"
    assert payload["target_holding_count"] == 10
    assert payload["allocation_count"] == 10


def test_validate_rejects_malformed_payload():
    for value in [None, [], "bad"]:
        with pytest.raises(ValueError):
            engine.validate_capital_allocation_report(value)


def test_validate_rejects_missing_required_fields():
    payload = engine.build_capital_allocation_report()
    for field in engine.REPORT_REQUIRED_FIELDS:
        bad = dict(payload)
        bad.pop(field, None)
        with pytest.raises(ValueError):
            engine.validate_capital_allocation_report(bad)


def test_validate_rejects_wrong_safety_flags():
    payload = engine.build_capital_allocation_report()
    for field, value in [("paper_trade_mode", False), ("live_trading_enabled", True), ("broker_execution_enabled", True), ("reporting_only", False)]:
        bad = dict(payload)
        bad[field] = value
        with pytest.raises(ValueError):
            engine.validate_capital_allocation_report(bad)


def test_json_csv_markdown_outputs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = engine.write_capital_allocation_report_json()
    assert engine.read_capital_allocation_report_json() == payload
    engine.write_capital_allocation_report_csv()
    engine.write_capital_allocation_report_markdown()
    assert Path("capital_allocation_report.json").exists()
    assert Path("capital_allocations.csv").exists()
    assert Path("capital_allocation_report.md").exists()
    markdown = engine.format_capital_allocation_report_markdown(payload)
    assert "# Capital Allocation Report" in markdown
    assert "## Allocations" in markdown
    assert "## Scoring Model" in markdown
    assert "## Safety Guarantees" in markdown


def test_static_safety_no_robinhood_or_order_execution():
    source = Path(engine.__file__).read_text(encoding="utf-8").lower()
    forbidden = ["import robinhood", "from robinhood", "import robin_stocks", "from robin_stocks", "place_order(", "submit_order(", "execute_order(", "real_order", "live_order"]
    for item in forbidden:
        assert item not in source


def test_static_safety_no_subprocess_os_system_or_internet():
    source = Path(engine.__file__).read_text(encoding="utf-8")
    forbidden = ["import subprocess", "from subprocess", "subprocess.", "Popen(", "os.system(", ".system(", "requests.", "urllib.request", "http.client", "socket."]
    for item in forbidden:
        assert item not in source
