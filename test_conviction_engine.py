"""Tests for conviction_engine.py."""

from __future__ import annotations

from pathlib import Path

import pytest

import conviction_engine as engine


def test_dataclasses_exist():
    assert hasattr(engine, "ConvictionComponent")
    assert hasattr(engine, "ConvictionReport")


def test_public_functions_exist():
    for name in [
        "build_conviction_report",
        "validate_conviction_report",
        "calculate_weighted_conviction_score",
        "classify_conviction_level",
        "classify_conviction_action",
        "write_conviction_report_json",
        "read_conviction_report_json",
        "format_conviction_report_markdown",
        "write_conviction_report_markdown",
    ]:
        assert callable(getattr(engine, name))


def test_default_report_is_valid():
    payload = engine.build_conviction_report()
    assert engine.validate_conviction_report(payload) is True
    assert payload["paper_trade_mode"] is True
    assert payload["reporting_only"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False


def test_default_fallback_values():
    payload = engine.build_conviction_report()
    assert payload["conviction_score"] == 0.0
    assert payload["conviction_level"] == "UNKNOWN"
    assert payload["conviction_action"] == "UNKNOWN"
    assert payload["confidence"] == 0.0
    assert payload["confidence_level"] == "LOW"


def test_default_weights_total_100():
    assert sum(engine.DEFAULT_COMPONENT_WEIGHTS.values()) == 100


def test_all_components_exist_and_default():
    payload = engine.build_conviction_report()
    assert payload["conviction_component_names"] == engine.CONVICTION_COMPONENT_NAMES
    assert len(payload["conviction_components"]) == len(engine.CONVICTION_COMPONENT_NAMES)
    for component in payload["conviction_components"]:
        assert component["component_name"] in engine.CONVICTION_COMPONENT_NAMES
        assert component["score"] == 0.0
        assert component["status"] == "UNKNOWN"
        assert component["confidence"] == 0.0
        assert component["confidence_level"] == "LOW"
        assert component["source"] == "deterministic_fallback"


def test_required_report_fields_exist():
    payload = engine.build_conviction_report()
    for field in engine.REPORT_REQUIRED_FIELDS:
        assert field in payload


def test_required_component_fields_exist():
    payload = engine.build_conviction_report()
    for component in payload["conviction_components"]:
        for field in engine.COMPONENT_REQUIRED_FIELDS:
            assert field in component


def test_weighted_conviction_score_calculation():
    components = {name: 100 for name in engine.CONVICTION_COMPONENT_NAMES}
    assert engine.calculate_weighted_conviction_score(components, engine.DEFAULT_COMPONENT_WEIGHTS) == 100.0
    components = {name: 0 for name in engine.CONVICTION_COMPONENT_NAMES}
    assert engine.calculate_weighted_conviction_score(components, engine.DEFAULT_COMPONENT_WEIGHTS) == 0.0
    components = {
        "opportunity_quality": 100,
        "entry_score": 50,
        "momentum_confirmation": 50,
        "market_regime_support": 0,
        "market_intelligence_support": 0,
        "dividend_ranking_support": 100,
        "self_funding_support": 100,
        "risk_alignment": 100,
    }
    assert engine.calculate_weighted_conviction_score(components, engine.DEFAULT_COMPONENT_WEIGHTS) == 65.0


@pytest.mark.parametrize(
    "score,level,action",
    [
        (90, "VERY_HIGH", "STRONG_APPROVAL"),
        (100, "VERY_HIGH", "STRONG_APPROVAL"),
        (80, "HIGH", "APPROVE"),
        (89.99, "HIGH", "APPROVE"),
        (65, "MEDIUM", "WATCH"),
        (79.99, "MEDIUM", "WATCH"),
        (50, "LOW", "WAIT"),
        (64.99, "LOW", "WAIT"),
        (0, "VERY_LOW", "REJECT"),
        (49.99, "VERY_LOW", "REJECT"),
    ],
)
def test_classification_thresholds(score, level, action):
    assert engine.classify_conviction_level(score) == level
    assert engine.classify_conviction_action(score) == action


def test_classification_rejects_bad_values_as_unknown():
    for value in [None, "90", True, -1]:
        assert engine.classify_conviction_level(value) == "UNKNOWN"
        assert engine.classify_conviction_action(value) == "UNKNOWN"


def test_validate_rejects_malformed_payload():
    for value in [None, [], "bad"]:
        with pytest.raises(ValueError):
            engine.validate_conviction_report(value)


def test_validate_rejects_missing_required_fields():
    payload = engine.build_conviction_report()
    for field in engine.REPORT_REQUIRED_FIELDS:
        bad = dict(payload)
        bad.pop(field, None)
        with pytest.raises(ValueError):
            engine.validate_conviction_report(bad)


def test_validate_rejects_missing_component_fields():
    payload = engine.build_conviction_report()
    for field in engine.COMPONENT_REQUIRED_FIELDS:
        bad = dict(payload)
        components = [dict(component) for component in payload["conviction_components"]]
        components[0].pop(field, None)
        bad["conviction_components"] = components
        with pytest.raises(ValueError):
            engine.validate_conviction_report(bad)


def test_validate_rejects_wrong_safety_flags():
    payload = engine.build_conviction_report()
    for field, value in [
        ("paper_trade_mode", False),
        ("live_trading_enabled", True),
        ("broker_execution_enabled", True),
        ("reporting_only", False),
    ]:
        bad = dict(payload)
        bad[field] = value
        with pytest.raises(ValueError):
            engine.validate_conviction_report(bad)


def test_validate_rejects_invalid_weights():
    payload = engine.build_conviction_report()
    bad = dict(payload)
    bad["component_weights"] = dict(payload["component_weights"])
    bad["component_weights"]["risk_alignment"] = 6
    with pytest.raises(ValueError):
        engine.validate_conviction_report(bad)


def test_validate_rejects_invalid_statuses():
    payload = engine.build_conviction_report()
    bad = dict(payload)
    bad["conviction_level"] = "BAD"
    with pytest.raises(ValueError):
        engine.validate_conviction_report(bad)

    bad = dict(payload)
    bad["conviction_action"] = "BAD"
    with pytest.raises(ValueError):
        engine.validate_conviction_report(bad)

    bad = dict(payload)
    components = [dict(component) for component in payload["conviction_components"]]
    components[0]["status"] = "BAD"
    bad["conviction_components"] = components
    with pytest.raises(ValueError):
        engine.validate_conviction_report(bad)


def test_validate_rejects_bad_confidence_level():
    payload = engine.build_conviction_report()
    bad = dict(payload)
    bad["confidence_level"] = "VERY_HIGH"
    with pytest.raises(ValueError):
        engine.validate_conviction_report(bad)


@pytest.mark.parametrize("value", [-1, 101, "0", True])
def test_validate_rejects_bad_conviction_score(value):
    payload = engine.build_conviction_report()
    bad = dict(payload)
    bad["conviction_score"] = value
    with pytest.raises(ValueError):
        engine.validate_conviction_report(bad)


@pytest.mark.parametrize("value", [-0.1, 1.1, "0.5", True])
def test_validate_rejects_bad_confidence(value):
    payload = engine.build_conviction_report()
    bad = dict(payload)
    bad["confidence"] = value
    with pytest.raises(ValueError):
        engine.validate_conviction_report(bad)


def test_validate_rejects_duplicate_or_missing_components():
    payload = engine.build_conviction_report()
    bad = dict(payload)
    components = [dict(component) for component in payload["conviction_components"]]
    components[1]["component_name"] = components[0]["component_name"]
    bad["conviction_components"] = components
    with pytest.raises(ValueError):
        engine.validate_conviction_report(bad)

    bad = dict(payload)
    bad["conviction_components"] = payload["conviction_components"][:-1]
    with pytest.raises(ValueError):
        engine.validate_conviction_report(bad)


def test_json_write_read_round_trip(tmp_path):
    path = tmp_path / "conviction_report.json"
    written = engine.write_conviction_report_json(path=str(path))
    read = engine.read_conviction_report_json(path=str(path))
    assert path.exists()
    assert read == written


def test_markdown_generation(tmp_path):
    payload = engine.build_conviction_report()
    markdown = engine.format_conviction_report_markdown(payload)
    assert "# Conviction Report" in markdown
    assert "## Conviction Summary" in markdown
    assert "## Component Weights" in markdown
    assert "## Conviction Components" in markdown
    assert "## Scoring Model" in markdown
    assert "## Recommendation Model" in markdown
    assert "## Integration Targets" in markdown
    assert "## Safety Guarantees" in markdown

    path = tmp_path / "conviction_report.md"
    engine.write_conviction_report_markdown(path=str(path))
    assert path.exists()


def test_static_safety_no_robinhood_or_orders():
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
