"""Tests for portfolio_decision_engine.py."""

from __future__ import annotations

from pathlib import Path

import pytest

import portfolio_decision_engine as engine


def test_dataclasses_exist():
    assert hasattr(engine, "PortfolioDecisionComponent")
    assert hasattr(engine, "PortfolioDecision")
    assert hasattr(engine, "PortfolioDecisionReport")


def test_public_functions_exist():
    for name in [
        "build_portfolio_decision_report",
        "validate_portfolio_decision_report",
        "calculate_portfolio_decision_score",
        "classify_decision_action",
        "classify_decision_priority",
        "rank_portfolio_decisions",
        "write_portfolio_decision_report_json",
        "read_portfolio_decision_report_json",
        "write_portfolio_decision_report_csv",
        "format_portfolio_decision_report_markdown",
        "write_portfolio_decision_report_markdown",
    ]:
        assert callable(getattr(engine, name))


def test_default_empty_report_is_valid(tmp_path):
    payload = engine.build_portfolio_decision_report(root_path=str(tmp_path))
    assert engine.validate_portfolio_decision_report(payload) is True
    assert payload["portfolio_decisions"] == []
    assert payload["decision_count"] == 0
    assert payload["paper_trade_mode"] is True
    assert payload["reporting_only"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False


def test_weights_total_100():
    assert sum(engine.DEFAULT_DECISION_WEIGHTS.values()) == 100


def test_detects_available_and_missing_inputs(tmp_path):
    (tmp_path / "conviction_report.json").write_text("{}", encoding="utf-8")
    payload = engine.build_portfolio_decision_report(root_path=str(tmp_path))
    assert "conviction_report.json" in payload["available_input_files"]
    assert "entry_score_report.json" in payload["missing_input_files"]


def test_decision_score_calculation():
    candidate = {name: 100 for name in engine.DECISION_COMPONENT_NAMES}
    assert engine.calculate_portfolio_decision_score(candidate, engine.DEFAULT_DECISION_WEIGHTS) == 100.0
    candidate = {name: 0 for name in engine.DECISION_COMPONENT_NAMES}
    assert engine.calculate_portfolio_decision_score(candidate, engine.DEFAULT_DECISION_WEIGHTS) == 0.0
    candidate = {
        "opportunity_score": 100,
        "conviction_score": 80,
        "entry_score": 60,
        "momentum_score": 50,
        "dividend_ranking_score": 70,
        "self_funding_score": 100,
        "risk_adjustment_score": 40,
    }
    assert engine.calculate_portfolio_decision_score(candidate, engine.DEFAULT_DECISION_WEIGHTS) == 78.0


@pytest.mark.parametrize(
    "score,action,priority",
    [
        (85, "INCREASE_ALLOCATION", "HIGH_PRIORITY"),
        (100, "INCREASE_ALLOCATION", "HIGH_PRIORITY"),
        (75, "MAINTAIN_ALLOCATION", "MEDIUM_PRIORITY"),
        (84.99, "MAINTAIN_ALLOCATION", "MEDIUM_PRIORITY"),
        (60, "WAIT_FOR_ENTRY", "LOW_PRIORITY"),
        (74.99, "WAIT_FOR_ENTRY", "LOW_PRIORITY"),
        (45, "REDUCE_ALLOCATION", "MONITOR"),
        (59.99, "REDUCE_ALLOCATION", "MONITOR"),
        (0, "AVOID_ALLOCATION", "AVOID"),
        (44.99, "AVOID_ALLOCATION", "AVOID"),
    ],
)
def test_classification_thresholds(score, action, priority):
    assert engine.classify_decision_action(score) == action
    assert engine.classify_decision_priority(score) == priority


def test_bad_classification_values_unknown():
    for value in [None, "90", True, -1]:
        assert engine.classify_decision_action(value) == "UNKNOWN"
        assert engine.classify_decision_priority(value) == "UNKNOWN"


def test_ranking_sorts_highest_first():
    ranked = engine.rank_portfolio_decisions([
        {"symbol": "BBB", "opportunity_score": 70},
        {"symbol": "AAA", "opportunity_score": 100, "conviction_score": 100, "entry_score": 100, "momentum_score": 100, "dividend_ranking_score": 100, "self_funding_score": 100, "risk_adjustment_score": 100},
    ])
    assert ranked[0]["symbol"] == "AAA"
    assert ranked[0]["decision_score"] == 100.0


def test_build_report_with_candidates_valid():
    payload = engine.build_portfolio_decision_report(decisions=[
        {
            "symbol": "JEPI",
            "opportunity_name": "Income ETF candidate",
            "opportunity_score": 80,
            "conviction_score": 80,
            "entry_score": 80,
            "momentum_score": 80,
            "dividend_ranking_score": 80,
            "self_funding_score": 80,
            "risk_adjustment_score": 80,
            "confidence": 0.7,
            "confidence_level": "HIGH",
            "risk_flags": ["paper review only"],
            "notes": "test candidate",
        }
    ])
    assert payload["decision_count"] == 1
    row = payload["portfolio_decisions"][0]
    assert row["symbol"] == "JEPI"
    assert row["decision_score"] == 80.0
    assert row["decision_action"] == "MAINTAIN_ALLOCATION"
    assert engine.validate_portfolio_decision_report(payload) is True


def test_validate_rejects_malformed_payload():
    for value in [None, [], "bad"]:
        with pytest.raises(ValueError):
            engine.validate_portfolio_decision_report(value)


def test_validate_rejects_missing_required_fields():
    payload = engine.build_portfolio_decision_report()
    for field in engine.REPORT_REQUIRED_FIELDS:
        bad = dict(payload)
        bad.pop(field, None)
        with pytest.raises(ValueError):
            engine.validate_portfolio_decision_report(bad)


def test_validate_rejects_wrong_safety_flags():
    payload = engine.build_portfolio_decision_report()
    for field, value in [
        ("paper_trade_mode", False),
        ("live_trading_enabled", True),
        ("broker_execution_enabled", True),
        ("reporting_only", False),
    ]:
        bad = dict(payload)
        bad[field] = value
        with pytest.raises(ValueError):
            engine.validate_portfolio_decision_report(bad)


def test_validate_rejects_invalid_weights():
    payload = engine.build_portfolio_decision_report()
    bad = dict(payload)
    bad["decision_weights"] = dict(payload["decision_weights"])
    bad["decision_weights"]["risk_adjustment_score"] = 6
    with pytest.raises(ValueError):
        engine.validate_portfolio_decision_report(bad)


def test_validate_rejects_bad_decision_values():
    payload = engine.build_portfolio_decision_report(decisions=[{"symbol": "JEPI", "opportunity_score": 80}])
    for field, value in [
        ("symbol", "jepi"),
        ("decision_score", 101),
        ("confidence", 2),
        ("decision_action", "BAD"),
        ("decision_priority", "BAD"),
        ("confidence_level", "BAD"),
        ("recommended_allocation_change", 2),
        ("risk_flags", "bad"),
    ]:
        bad = dict(payload)
        decisions = [dict(payload["portfolio_decisions"][0])]
        decisions[0][field] = value
        bad["portfolio_decisions"] = decisions
        with pytest.raises(ValueError):
            engine.validate_portfolio_decision_report(bad)


def test_validate_rejects_unsorted_decisions():
    payload = engine.build_portfolio_decision_report(decisions=[
        {"symbol": "AAA", "opportunity_score": 100, "conviction_score": 100, "entry_score": 100, "momentum_score": 100, "dividend_ranking_score": 100, "self_funding_score": 100, "risk_adjustment_score": 100},
        {"symbol": "BBB", "opportunity_score": 50},
    ])
    bad = dict(payload)
    bad["portfolio_decisions"] = list(reversed(payload["portfolio_decisions"]))
    with pytest.raises(ValueError):
        engine.validate_portfolio_decision_report(bad)


def test_json_csv_markdown_outputs(tmp_path):
    json_path = tmp_path / "portfolio_decision_report.json"
    csv_path = tmp_path / "portfolio_decision_report.csv"
    md_path = tmp_path / "portfolio_decision_report.md"
    written = engine.write_portfolio_decision_report_json(path=str(json_path), root_path=str(tmp_path))
    read = engine.read_portfolio_decision_report_json(path=str(json_path))
    assert read == written
    engine.write_portfolio_decision_report_csv(path=str(csv_path), root_path=str(tmp_path))
    engine.write_portfolio_decision_report_markdown(path=str(md_path), root_path=str(tmp_path))
    assert json_path.exists()
    assert csv_path.exists()
    assert md_path.exists()
    markdown = engine.format_portfolio_decision_report_markdown(written)
    assert "# Portfolio Decision Report" in markdown
    assert "## Decision Weights" in markdown
    assert "## Portfolio Decisions" in markdown
    assert "## Safety Guarantees" in markdown


def test_static_safety_no_robinhood_or_order_execution():
    source = Path(engine.__file__).read_text(encoding="utf-8").lower()
    forbidden = [
        "import robinhood",
        "from robinhood",
        "import robin_stocks",
        "from robin_stocks",
        ".place_order(",
        ".submit_order(",
        "place_order(",
        "submit_order(",
        "execute_order(",
        "real_order",
        "live_order",
    ]
    for item in forbidden:
        assert item not in source


def test_static_safety_no_subprocess_os_system_or_internet():
    source = Path(engine.__file__).read_text(encoding="utf-8")
    forbidden = [
        "import subprocess",
        "from subprocess",
        "subprocess.",
        "Popen(",
        "os.system(",
        ".system(",
        "requests.",
        "urllib.request",
        "http.client",
        "socket.",
    ]
    for item in forbidden:
        assert item not in source
