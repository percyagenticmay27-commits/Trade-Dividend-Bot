"""Tests for portfolio_health_engine.py."""
from __future__ import annotations

from pathlib import Path
import pytest
import portfolio_health_engine as engine


def test_dataclasses_exist():
    assert hasattr(engine, "PortfolioHealthComponent")
    assert hasattr(engine, "PortfolioHealthReport")


def test_public_functions_exist():
    for name in [
        "classify_health_grade",
        "classify_health_status",
        "classify_health_trend",
        "calculate_overall_health_score",
        "build_portfolio_health_report",
        "validate_portfolio_health_report",
        "write_portfolio_health_report_json",
        "read_portfolio_health_report_json",
        "format_portfolio_health_report_markdown",
        "write_portfolio_health_report_markdown",
    ]:
        assert callable(getattr(engine, name))


def test_default_report_valid_and_safe():
    payload = engine.build_portfolio_health_report()
    assert engine.validate_portfolio_health_report(payload) is True
    assert payload["paper_trade_mode"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False
    assert payload["reporting_only"] is True
    assert payload["overall_health_score"] == 0.0
    assert payload["health_grade"] == "F"
    assert payload["health_status"] == "CRITICAL"


def test_weights_total_100():
    assert sum(engine.HEALTH_COMPONENT_WEIGHTS.values()) == 100


def test_all_100_scores_produce_excellent_a():
    scores = {name: 100 for name in engine.COMPONENT_NAMES}
    payload = engine.build_portfolio_health_report(scores, previous_health_score=95)
    assert payload["overall_health_score"] == 100.0
    assert payload["health_grade"] == "A"
    assert payload["health_status"] == "EXCELLENT"
    assert payload["health_trend"] == "IMPROVING"


@pytest.mark.parametrize(
    "score,grade,status",
    [
        (90, "A", "EXCELLENT"),
        (80, "B", "GOOD"),
        (70, "C", "FAIR"),
        (60, "D", "WEAK"),
        (59.99, "F", "CRITICAL"),
    ],
)
def test_health_classification_thresholds(score, grade, status):
    assert engine.classify_health_grade(score) == grade
    assert engine.classify_health_status(score) == status


@pytest.mark.parametrize(
    "current,previous,trend",
    [
        (82, 79, "IMPROVING"),
        (80, 79, "STABLE"),
        (75, 78, "DETERIORATING"),
    ],
)
def test_health_trend_classification(current, previous, trend):
    assert engine.classify_health_trend(current, previous) == trend


def test_weighted_score_calculation():
    scores = {name: 50 for name in engine.COMPONENT_NAMES}
    assert engine.calculate_overall_health_score(scores) == 50.0


def test_strengths_concerns_and_risk_flags():
    scores = {name: 80 for name in engine.COMPONENT_NAMES}
    scores["cash_reserve_health_score"] = 40
    scores["concentration_health_score"] = 45
    scores["income_stability_score"] = 50
    scores["momentum_strength_score"] = 40
    payload = engine.build_portfolio_health_report(scores)
    assert payload["top_strengths"]
    assert payload["top_concerns"]
    assert "CASH_RESERVE_BELOW_HEALTH_TARGET" in payload["risk_flags"]
    assert "CONCENTRATION_RISK" in payload["risk_flags"]
    assert "INCOME_STABILITY_RISK" in payload["risk_flags"]
    assert "PORTFOLIO_MOMENTUM_WEAK" in payload["risk_flags"]
    assert payload["recommended_actions"]


def test_all_components_exist_in_approved_order():
    payload = engine.build_portfolio_health_report()
    assert [row["component_name"] for row in payload["health_components"]] == engine.COMPONENT_NAMES


def test_validate_rejects_malformed_payload():
    for value in [None, [], "bad"]:
        with pytest.raises(ValueError):
            engine.validate_portfolio_health_report(value)


def test_validate_rejects_missing_required_fields():
    payload = engine.build_portfolio_health_report()
    for field_name in engine.REPORT_REQUIRED_FIELDS:
        bad = dict(payload)
        bad.pop(field_name, None)
        with pytest.raises(ValueError):
            engine.validate_portfolio_health_report(bad)


def test_validate_rejects_wrong_safety_flags():
    payload = engine.build_portfolio_health_report()
    for field_name, value in [
        ("paper_trade_mode", False),
        ("live_trading_enabled", True),
        ("broker_execution_enabled", True),
        ("reporting_only", False),
    ]:
        bad = dict(payload)
        bad[field_name] = value
        with pytest.raises(ValueError):
            engine.validate_portfolio_health_report(bad)


def test_validate_rejects_bad_weights():
    payload = engine.build_portfolio_health_report()
    bad = dict(payload)
    bad["health_component_weights"] = dict(payload["health_component_weights"])
    bad["health_component_weights"]["portfolio_quality_score"] = 16
    with pytest.raises(ValueError):
        engine.validate_portfolio_health_report(bad)


def test_validate_rejects_bad_health_values():
    payload = engine.build_portfolio_health_report()
    for field_name, value in [
        ("overall_health_score", 101),
        ("health_grade", "Z"),
        ("health_status", "BAD"),
        ("health_trend", "BAD"),
    ]:
        bad = dict(payload)
        bad[field_name] = value
        with pytest.raises(ValueError):
            engine.validate_portfolio_health_report(bad)


def test_json_and_markdown_outputs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = engine.write_portfolio_health_report_json()
    assert engine.read_portfolio_health_report_json() == payload
    engine.write_portfolio_health_report_markdown()
    assert Path("portfolio_health_report.json").exists()
    assert Path("portfolio_health_report.md").exists()
    markdown = engine.format_portfolio_health_report_markdown(payload)
    assert "# Portfolio Health Report" in markdown
    assert "## Health Components" in markdown
    assert "## Top Strengths" in markdown
    assert "## Top Concerns" in markdown
    assert "## Risk Flags" in markdown
    assert "## Recommended Actions" in markdown
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
