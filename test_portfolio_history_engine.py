"""Tests for portfolio_history_engine.py."""
from __future__ import annotations

from datetime import date
from pathlib import Path
import pytest
import portfolio_history_engine as engine


def test_dataclasses_exist():
    assert hasattr(engine, "PortfolioHistorySnapshot")
    assert hasattr(engine, "PortfolioHistoryReport")


def test_public_functions_exist():
    for name in [
        "build_history_snapshot",
        "validate_history_snapshot",
        "find_archive_candidates",
        "build_portfolio_history_report",
        "validate_portfolio_history_report",
        "history_directory_for_snapshot",
        "write_history_snapshot",
        "write_portfolio_history_json",
        "read_portfolio_history_json",
        "write_portfolio_history_csv",
        "format_portfolio_history_markdown",
        "write_portfolio_history_markdown",
    ]:
        assert callable(getattr(engine, name))


def test_default_empty_report_valid():
    payload = engine.build_portfolio_history_report()
    assert engine.validate_portfolio_history_report(payload) is True
    assert payload["snapshot_count"] == 0
    assert payload["paper_trade_mode"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False
    assert payload["reporting_only"] is True


def test_actual_and_forecast_remain_separate():
    actual = engine.build_history_snapshot({"portfolio_value": 550, "total_return_pct": 10}, record_type="ACTUAL_RESULT")
    forecast = engine.build_history_snapshot({"portfolio_value": 600, "total_return_pct": 20}, record_type="FORECAST")
    payload = engine.build_portfolio_history_report([actual, forecast])
    assert payload["actual_result_count"] == 1
    assert payload["forecast_count"] == 1


def test_benchmark_gap_calculated():
    snapshot = engine.build_history_snapshot({"total_return_pct": 25, "benchmark_return_pct": 20})
    assert snapshot["benchmark_gap_pct"] == 5


def test_default_goals_present():
    snapshot = engine.build_history_snapshot()
    assert snapshot["objective_monthly_return_pct"] == 4.0
    assert snapshot["minimum_annual_return_pct"] == 20.0


def test_history_path_uses_year_month_and_period(tmp_path):
    snapshot = engine.build_history_snapshot({"recorded_at_utc": "2026-07-10T12:00:00Z"}, period="MONTHLY")
    directory = engine.history_directory_for_snapshot(snapshot, str(tmp_path))
    assert directory == tmp_path / "2026-07" / "monthly"


def test_write_history_snapshot_is_append_only(tmp_path):
    snapshot = engine.build_history_snapshot({"recorded_at_utc": "2026-07-10T12:00:00Z"})
    path = engine.write_history_snapshot(snapshot, str(tmp_path))
    assert path.exists()
    with pytest.raises(FileExistsError):
        engine.write_history_snapshot(snapshot, str(tmp_path))


def test_archive_candidates_older_than_five_years():
    old_snapshot = engine.build_history_snapshot({"recorded_at_utc": "2019-01-01T00:00:00Z"})
    recent_snapshot = engine.build_history_snapshot({"recorded_at_utc": "2025-01-01T00:00:00Z"})
    candidates = engine.find_archive_candidates([old_snapshot, recent_snapshot], as_of_date=date(2026, 7, 10))
    assert len(candidates) == 1
    assert candidates[0]["archive_name"] == "portfolio_history_2019.zip"


def test_validation_rejects_bad_period_and_type():
    with pytest.raises(ValueError):
        engine.build_history_snapshot(period="YEARLY")
    with pytest.raises(ValueError):
        engine.build_history_snapshot(record_type="UNKNOWN_TYPE")


def test_validation_rejects_malformed_payloads():
    for value in [None, [], "bad"]:
        with pytest.raises(ValueError):
            engine.validate_portfolio_history_report(value)


def test_validation_rejects_missing_report_fields():
    payload = engine.build_portfolio_history_report()
    for field in engine.REPORT_REQUIRED_FIELDS:
        bad = dict(payload)
        bad.pop(field, None)
        with pytest.raises(ValueError):
            engine.validate_portfolio_history_report(bad)


def test_validation_rejects_wrong_safety_flags():
    payload = engine.build_portfolio_history_report()
    for field, value in [
        ("paper_trade_mode", False),
        ("live_trading_enabled", True),
        ("broker_execution_enabled", True),
        ("reporting_only", False),
    ]:
        bad = dict(payload)
        bad[field] = value
        with pytest.raises(ValueError):
            engine.validate_portfolio_history_report(bad)


def test_json_csv_markdown_outputs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    snapshot = engine.build_history_snapshot({"portfolio_value": 500})
    written = engine.write_portfolio_history_json(snapshots=[snapshot])
    assert engine.read_portfolio_history_json() == written
    engine.write_portfolio_history_csv(snapshots=[snapshot])
    engine.write_portfolio_history_markdown(snapshots=[snapshot])
    assert Path("portfolio_history.json").exists()
    assert Path("portfolio_history.csv").exists()
    assert Path("portfolio_history.md").exists()
    markdown = engine.format_portfolio_history_markdown(written)
    assert "# Portfolio History Report" in markdown
    assert "## Retention Policy" in markdown
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
