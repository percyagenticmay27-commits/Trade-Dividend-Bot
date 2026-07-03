"""
Tests for dividend_ranking_engine.py.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

import dividend_ranking_engine as engine


def _write_json(path: Path, payload):
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_dataclasses_exist():
    assert hasattr(engine, "DividendRankingComponent")
    assert hasattr(engine, "DividendRankingEntry")
    assert hasattr(engine, "DividendRankingReport")


def test_required_functions_exist():
    for name in [
        "build_dividend_ranking_report",
        "validate_dividend_ranking_report",
        "calculate_weighted_score",
        "classify_overall_rating",
        "write_dividend_ranking_report_json",
        "read_dividend_ranking_report_json",
        "write_dividend_ranking_report_csv",
        "format_dividend_ranking_report_markdown",
        "write_dividend_ranking_report_markdown",
    ]:
        assert callable(getattr(engine, name))


def test_default_report_is_valid_and_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = engine.build_dividend_ranking_report()
    assert engine.validate_dividend_ranking_report(payload) is True
    assert payload["rankings"] == []
    assert payload["ranking_count"] == 0


def test_required_report_fields_exist(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = engine.build_dividend_ranking_report()
    for field in engine.REPORT_REQUIRED_FIELDS:
        assert field in payload


def test_paper_trade_mode_always_true(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = engine.build_dividend_ranking_report()
    assert payload["paper_trade_mode"] is True
    assert payload["reporting_only"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False


def test_default_weights_total_100():
    assert sum(engine.DEFAULT_COMPONENT_WEIGHTS.values()) == 100


def test_invalid_weights_fail_validation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = engine.build_dividend_ranking_report()
    bad = dict(payload)
    bad["component_weights"] = dict(payload["component_weights"])
    bad["component_weights"]["valuation"] = 11
    with pytest.raises(ValueError):
        engine.validate_dividend_ranking_report(bad)


def test_weighted_score_calculation():
    components = {
        "dividend_quality": 100,
        "momentum": 50,
        "dividend_growth": 50,
        "dividend_safety": 100,
        "valuation": 0,
    }
    assert engine.calculate_weighted_score(components, engine.DEFAULT_COMPONENT_WEIGHTS) == 70.0


@pytest.mark.parametrize(
    "score,rating",
    [
        (90, "STRONG_BUY"),
        (100, "STRONG_BUY"),
        (80, "BUY"),
        (89.99, "BUY"),
        (65, "HOLD"),
        (79.99, "HOLD"),
        (50, "WATCHLIST"),
        (64.99, "WATCHLIST"),
        (49.99, "AVOID"),
        (0, "AVOID"),
    ],
)
def test_rating_classification_thresholds(score, rating):
    assert engine.classify_overall_rating(score) == rating


def test_missing_component_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_json(tmp_path / "dividend_quality_report.json", {"entries": [{"symbol": "AAPL", "quality_score": 100}]})

    payload = engine.build_dividend_ranking_report()
    entry = payload["rankings"][0]

    assert entry["symbol"] == "AAPL"
    assert entry["quality_score"] == 100
    assert entry["momentum_score"] == 0
    assert entry["growth_score"] == 0
    assert entry["safety_score"] == 0
    assert entry["valuation_score"] == 0
    assert entry["confidence"] == 0.0
    assert entry["confidence_level"] == "LOW"
    assert entry["trend_direction"] == "UNKNOWN"
    assert entry["recommendation"] == "HOLD"
    assert entry["notes"] == ""


def test_merge_by_symbol(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_json(tmp_path / "dividend_quality_report.json", {"entries": [{"symbol": "aapl", "quality_score": 80}]})
    _write_json(tmp_path / "momentum_score_report.json", {"entries": [{"symbol": "AAPL", "momentum_score": 70, "confidence": 0.5, "confidence_level": "MEDIUM", "trend_direction": "UP"}]})
    _write_json(tmp_path / "dividend_growth_report.json", {"entries": [{"symbol": "AAPL", "growth_score": 60}]})
    _write_json(tmp_path / "dividend_safety_report.json", {"entries": [{"symbol": "AAPL", "safety_score": 90}]})
    _write_json(tmp_path / "valuation_report.json", {"entries": [{"symbol": "AAPL", "valuation_score": 50}]})

    payload = engine.build_dividend_ranking_report()
    assert payload["ranking_count"] == 1
    entry = payload["rankings"][0]
    assert entry["symbol"] == "AAPL"
    assert entry["quality_score"] == 80
    assert entry["momentum_score"] == 70
    assert entry["growth_score"] == 60
    assert entry["safety_score"] == 90
    assert entry["valuation_score"] == 50
    assert entry["confidence"] == 0.5
    assert entry["confidence_level"] == "MEDIUM"
    assert entry["trend_direction"] == "UP"


def test_json_write_read(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_json(tmp_path / "dividend_quality_report.json", {"entries": [{"symbol": "AAPL", "quality_score": 90}]})
    out = tmp_path / "dividend_rankings.json"

    written = engine.write_dividend_ranking_report_json(path=str(out))
    read = engine.read_dividend_ranking_report_json(path=str(out))

    assert out.exists()
    assert read == written


def test_csv_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_json(tmp_path / "dividend_quality_report.json", {"entries": [{"symbol": "AAPL", "quality_score": 90}]})
    out = tmp_path / "dividend_rankings.csv"

    payload = engine.write_dividend_ranking_report_csv(path=str(out))

    assert out.exists()
    with out.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert rows[0]["symbol"] == "AAPL"
    assert payload["ranking_count"] == 1


def test_markdown_formatting(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = engine.build_dividend_ranking_report()
    markdown = engine.format_dividend_ranking_report_markdown(payload)

    assert "# Dividend Ranking Report" in markdown
    assert "## Component Weights" in markdown
    assert "## Rankings" in markdown
    assert "## Safety Guarantees" in markdown


def test_markdown_write(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "dividend_rankings.md"
    engine.write_dividend_ranking_report_markdown(path=str(out))
    assert out.exists()
    assert "# Dividend Ranking Report" in out.read_text(encoding="utf-8")


def test_validate_rejects_missing_required_fields(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = engine.build_dividend_ranking_report()
    for field in engine.REPORT_REQUIRED_FIELDS:
        bad = dict(payload)
        bad.pop(field, None)
        with pytest.raises(ValueError):
            engine.validate_dividend_ranking_report(bad)


def test_validate_rejects_invalid_entry_fields(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_json(tmp_path / "dividend_quality_report.json", {"entries": [{"symbol": "AAPL", "quality_score": 90}]})
    payload = engine.build_dividend_ranking_report()
    bad = dict(payload)
    rankings = [dict(item) for item in payload["rankings"]]
    rankings[0]["overall_score"] = 101
    bad["rankings"] = rankings
    with pytest.raises(ValueError):
        engine.validate_dividend_ranking_report(bad)


def test_no_brokerage_execution_fields_or_functions_exist():
    names = dir(engine)
    forbidden = [
        "place_order",
        "submit_order",
        "execute_order",
        "buy",
        "sell",
        "robinhood",
        "brokerage_execute",
    ]
    lowered = [name.lower() for name in names]
    for item in forbidden:
        assert item not in lowered


def test_no_robinhood_execution_fields_or_functions_exist():
    source = Path(engine.__file__).read_text(encoding="utf-8").lower()
    assert "import robinhood" not in source
    assert "from robinhood" not in source
    assert "import robin_stocks" not in source
    assert "from robin_stocks" not in source


def test_no_order_placement_logic_exists():
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
