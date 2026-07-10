"""Tests for portfolio_forecast_engine.py."""
from __future__ import annotations

from pathlib import Path
import pytest
import portfolio_forecast_engine as engine


def test_dataclasses_exist():
    assert hasattr(engine, "ForecastScenario")
    assert hasattr(engine, "PortfolioForecastPoint")
    assert hasattr(engine, "PortfolioForecastReport")


def test_public_functions_exist():
    for name in [
        "project_scenario",
        "calculate_income_milestones",
        "build_portfolio_forecast_report",
        "validate_portfolio_forecast_report",
        "write_portfolio_forecast_report_json",
        "read_portfolio_forecast_report_json",
        "write_portfolio_forecast_report_csv",
        "format_portfolio_forecast_report_markdown",
        "write_portfolio_forecast_report_markdown",
    ]:
        assert callable(getattr(engine, name))


def test_default_report_valid():
    payload = engine.build_portfolio_forecast_report()
    assert engine.validate_portfolio_forecast_report(payload) is True
    assert payload["paper_trade_mode"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False
    assert payload["reporting_only"] is True
    assert payload["starting_portfolio_value"] == 500.0
    assert payload["forecast_years"] == 10


def test_supported_scenarios_and_row_count():
    payload = engine.build_portfolio_forecast_report(forecast_years=5)
    assert payload["supported_scenarios"] == ["CONSERVATIVE", "EXPECTED", "OPTIMISTIC"]
    assert len(payload["forecasts"]) == 15


def test_expected_scenario_grows_portfolio():
    points = engine.project_scenario("EXPECTED", 500, 5, 100, 0, 3)
    assert len(points) == 3
    assert points[0]["projected_portfolio_value"] > 500
    assert points[2]["projected_portfolio_value"] > points[0]["projected_portfolio_value"]


def test_optimistic_outgrows_conservative():
    conservative = engine.project_scenario("CONSERVATIVE", 500, 5, 100, 0, 5)
    optimistic = engine.project_scenario("OPTIMISTIC", 500, 5, 100, 0, 5)
    assert optimistic[-1]["projected_portfolio_value"] > conservative[-1]["projected_portfolio_value"]
    assert optimistic[-1]["projected_monthly_income"] > conservative[-1]["projected_monthly_income"]


def test_annual_contribution_increases_forecast():
    without_contribution = engine.project_scenario("EXPECTED", 500, 5, 100, 0, 3)
    with_contribution = engine.project_scenario("EXPECTED", 500, 5, 100, 500, 3)
    assert with_contribution[-1]["projected_portfolio_value"] > without_contribution[-1]["projected_portfolio_value"]


def test_cash_reserve_grows():
    points = engine.project_scenario("EXPECTED", 500, 5, 100, 0, 3)
    assert points[-1]["projected_cash_reserve"] > 100


def test_income_milestones_detected():
    forecasts = engine.project_scenario("EXPECTED", 500, 95, 100, 0, 5)
    milestones = engine.calculate_income_milestones(forecasts, [100])
    expected = [m for m in milestones if m["scenario"] == "EXPECTED"][0]
    assert expected["reached_within_forecast"] is True
    assert expected["year_reached"] is not None


def test_invalid_scenario_rejected():
    with pytest.raises(ValueError):
        engine.project_scenario("BAD", 500, 0, 100)


def test_invalid_inputs_rejected():
    with pytest.raises(ValueError):
        engine.project_scenario("EXPECTED", 0, 0, 100)
    with pytest.raises(ValueError):
        engine.project_scenario("EXPECTED", 500, -1, 100)
    with pytest.raises(ValueError):
        engine.project_scenario("EXPECTED", 500, 0, 100, forecast_years=0)


def test_validate_rejects_malformed_payload():
    for value in [None, [], "bad"]:
        with pytest.raises(ValueError):
            engine.validate_portfolio_forecast_report(value)


def test_validate_rejects_missing_required_fields():
    payload = engine.build_portfolio_forecast_report()
    for field in engine.REPORT_REQUIRED_FIELDS:
        bad = dict(payload)
        bad.pop(field, None)
        with pytest.raises(ValueError):
            engine.validate_portfolio_forecast_report(bad)


def test_validate_rejects_wrong_safety_flags():
    payload = engine.build_portfolio_forecast_report()
    for field, value in [
        ("paper_trade_mode", False),
        ("live_trading_enabled", True),
        ("broker_execution_enabled", True),
        ("reporting_only", False),
    ]:
        bad = dict(payload)
        bad[field] = value
        with pytest.raises(ValueError):
            engine.validate_portfolio_forecast_report(bad)


def test_json_csv_markdown_outputs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = engine.write_portfolio_forecast_report_json()
    assert engine.read_portfolio_forecast_report_json() == payload
    engine.write_portfolio_forecast_report_csv()
    engine.write_portfolio_forecast_report_markdown()
    assert Path("portfolio_forecast_report.json").exists()
    assert Path("portfolio_forecast_report.csv").exists()
    assert Path("portfolio_forecast_report.md").exists()
    markdown = engine.format_portfolio_forecast_report_markdown(payload)
    assert "# Portfolio Forecast Report" in markdown
    assert "## Forecast Scenarios" in markdown
    assert "## Income Milestones" in markdown
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
