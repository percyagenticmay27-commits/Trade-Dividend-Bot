"""Tests for opportunity_rotation_forecast_engine.py."""
from __future__ import annotations

from pathlib import Path

import pytest

import opportunity_rotation_forecast_engine as engine


def test_dataclasses_exist():
    assert hasattr(engine, "RotationForecastEntry")
    assert hasattr(engine, "OpportunityRotationForecastReport")


def test_public_functions_exist():
    for name in [
        "calculate_forecast_score",
        "classify_forecast_status",
        "classify_confidence_level",
        "classify_forecast_horizon",
        "normalize_forecast_candidate",
        "build_opportunity_rotation_forecast_report",
        "validate_opportunity_rotation_forecast_report",
        "write_opportunity_rotation_forecast_json",
        "read_opportunity_rotation_forecast_json",
        "write_opportunity_rotation_forecast_csv",
        "format_opportunity_rotation_forecast_markdown",
        "write_opportunity_rotation_forecast_markdown",
    ]:
        assert callable(getattr(engine, name))


def test_default_report_is_valid_and_empty():
    payload = engine.build_opportunity_rotation_forecast_report()
    assert engine.validate_opportunity_rotation_forecast_report(payload) is True
    assert payload["forecast_entries"] == []
    assert payload["paper_trade_mode"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False
    assert payload["reporting_only"] is True


def test_forecast_weights_total_100():
    assert sum(engine.FORECAST_WEIGHTS.values()) == 100
    candidate = {name: 100 for name in engine.FORECAST_WEIGHTS}
    assert engine.calculate_forecast_score(candidate) == 100.0


def test_emerging_leader_classification():
    assert engine.classify_forecast_status(80, 8, 85) == "EMERGING_LEADER"


def test_current_leader_classification():
    assert engine.classify_forecast_status(90, 2, 85) == "CURRENT_LEADER"


def test_fading_and_declining_classifications():
    assert engine.classify_forecast_status(80, -6, 70) == "FADING_LEADER"
    assert engine.classify_forecast_status(80, -12, 70) == "DECLINING"


def test_confidence_and_horizon_models():
    assert engine.classify_confidence_level(0.80) == "HIGH"
    assert engine.classify_confidence_level(0.50) == "MEDIUM"
    assert engine.classify_confidence_level(0.10) == "LOW"
    assert engine.classify_forecast_horizon(12, 90) == "IMMEDIATE"
    assert engine.classify_forecast_horizon(7, 75) == "NEAR_TERM"


def test_nav_erosion_creates_risk_flag():
    row = engine.normalize_forecast_candidate({
        "symbol": "PLTY",
        "current_score": 70,
        "previous_score": 75,
        "nav_preservation": 30,
        "wrapper_quality": 45,
    })
    assert "NAV_PRESERVATION_RISK" in row["risk_flags"]


def test_four_percent_objective_gap():
    row = engine.normalize_forecast_candidate({
        "symbol": "AMDW_AMDL",
        "projected_monthly_return_pct": 4.5,
    })
    assert row["gap_to_monthly_objective_pct"] == 0.5


def test_amd_can_emerge_while_pltr_fades():
    candidates = [
        {
            "symbol": "AMD",
            "current_score": 84,
            "previous_score": 76,
            "opportunity_acceleration": 90,
            "conviction_acceleration": 85,
            "momentum_acceleration": 88,
            "market_intelligence_trend": 90,
            "technical_trend": 80,
            "analyst_revision_trend": 95,
            "sector_leadership": 90,
            "nav_preservation": 90,
            "wrapper_quality": 90,
            "projected_monthly_return_pct": 4.2,
        },
        {
            "symbol": "PLTR",
            "current_score": 82,
            "previous_score": 90,
            "opportunity_acceleration": 55,
            "conviction_acceleration": 50,
            "momentum_acceleration": 45,
            "market_intelligence_trend": 50,
            "technical_trend": 45,
            "analyst_revision_trend": 50,
            "sector_leadership": 55,
            "nav_preservation": 80,
            "wrapper_quality": 80,
        },
    ]
    payload = engine.build_opportunity_rotation_forecast_report(candidates)
    assert "AMD" in payload["emerging_leaders"]
    assert "PLTR" in payload["fading_leaders"]
    assert payload["forecast_entries"][0]["symbol"] == "AMD"


def test_validate_rejects_malformed_payload():
    for value in [None, [], "bad"]:
        with pytest.raises(ValueError):
            engine.validate_opportunity_rotation_forecast_report(value)


def test_validate_rejects_missing_required_fields():
    payload = engine.build_opportunity_rotation_forecast_report()
    for field_name in engine.REPORT_REQUIRED_FIELDS:
        bad = dict(payload)
        bad.pop(field_name, None)
        with pytest.raises(ValueError):
            engine.validate_opportunity_rotation_forecast_report(bad)


def test_validate_rejects_wrong_safety_flags():
    payload = engine.build_opportunity_rotation_forecast_report()
    for field_name, value in [
        ("paper_trade_mode", False),
        ("live_trading_enabled", True),
        ("broker_execution_enabled", True),
        ("reporting_only", False),
    ]:
        bad = dict(payload)
        bad[field_name] = value
        with pytest.raises(ValueError):
            engine.validate_opportunity_rotation_forecast_report(bad)


def test_json_csv_markdown_outputs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = engine.write_opportunity_rotation_forecast_json()
    assert engine.read_opportunity_rotation_forecast_json() == payload
    engine.write_opportunity_rotation_forecast_csv()
    engine.write_opportunity_rotation_forecast_markdown()
    assert Path("opportunity_rotation_forecast.json").exists()
    assert Path("opportunity_rotation_forecast.csv").exists()
    assert Path("opportunity_rotation_forecast.md").exists()
    markdown = engine.format_opportunity_rotation_forecast_markdown(payload)
    assert "# Opportunity Rotation Forecast" in markdown
    assert "## Emerging Leaders" in markdown
    assert "## Fading Leaders" in markdown
    assert "## Opportunity Stories" in markdown
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
