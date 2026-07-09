"""Tests for entry_score_engine.py."""

from __future__ import annotations

from pathlib import Path

import pytest

import entry_score_engine as engine


def test_dataclasses_exist():
    assert hasattr(engine, "EntrySignal")
    assert hasattr(engine, "EntryScoreReport")


def test_public_functions_exist():
    for name in [
        "build_entry_score_report",
        "validate_entry_score_report",
        "write_entry_score_report_json",
        "read_entry_score_report_json",
        "format_entry_score_report_markdown",
        "write_entry_score_report_markdown",
    ]:
        assert callable(getattr(engine, name))


def test_default_report_is_valid():
    payload = engine.build_entry_score_report()
    assert engine.validate_entry_score_report(payload) is True
    assert payload["paper_trade_mode"] is True
    assert payload["reporting_only"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False


def test_default_fallback_values():
    payload = engine.build_entry_score_report()
    assert payload["entry_score"] == 0
    assert payload["entry_status"] == "UNKNOWN"
    assert payload["confidence"] == 0.0
    assert payload["confidence_level"] == "LOW"
    assert payload["timing_context"] == "UNKNOWN"


def test_all_entry_signals_exist_and_default():
    payload = engine.build_entry_score_report()
    assert payload["entry_signal_names"] == engine.ENTRY_SIGNAL_NAMES
    assert len(payload["entry_signals"]) == len(engine.ENTRY_SIGNAL_NAMES)
    for signal in payload["entry_signals"]:
        assert signal["signal_name"] in engine.ENTRY_SIGNAL_NAMES
        assert signal["score"] == 0.0
        assert signal["status"] == "UNKNOWN"
        assert signal["confidence"] == 0.0
        assert signal["confidence_level"] == "LOW"
        assert signal["timing_context"] == "UNKNOWN"
        assert signal["source"] == "deterministic_fallback"


def test_required_report_fields_exist():
    payload = engine.build_entry_score_report()
    for field in engine.REPORT_REQUIRED_FIELDS:
        assert field in payload


def test_required_signal_fields_exist():
    payload = engine.build_entry_score_report()
    for signal in payload["entry_signals"]:
        for field in engine.SIGNAL_REQUIRED_FIELDS:
            assert field in signal


def test_validate_rejects_malformed_payload():
    for value in [None, [], "bad"]:
        with pytest.raises(ValueError):
            engine.validate_entry_score_report(value)


def test_validate_rejects_missing_required_fields():
    payload = engine.build_entry_score_report()
    for field in engine.REPORT_REQUIRED_FIELDS:
        bad = dict(payload)
        bad.pop(field, None)
        with pytest.raises(ValueError):
            engine.validate_entry_score_report(bad)


def test_validate_rejects_missing_signal_required_fields():
    payload = engine.build_entry_score_report()
    for field in engine.SIGNAL_REQUIRED_FIELDS:
        bad = dict(payload)
        signals = [dict(signal) for signal in payload["entry_signals"]]
        signals[0].pop(field, None)
        bad["entry_signals"] = signals
        with pytest.raises(ValueError):
            engine.validate_entry_score_report(bad)


def test_validate_rejects_wrong_safety_flags():
    payload = engine.build_entry_score_report()
    for field, value in [
        ("paper_trade_mode", False),
        ("live_trading_enabled", True),
        ("broker_execution_enabled", True),
        ("reporting_only", False),
    ]:
        bad = dict(payload)
        bad[field] = value
        with pytest.raises(ValueError):
            engine.validate_entry_score_report(bad)


def test_validate_rejects_invalid_statuses_and_contexts():
    payload = engine.build_entry_score_report()
    bad = dict(payload)
    bad["entry_status"] = "BAD"
    with pytest.raises(ValueError):
        engine.validate_entry_score_report(bad)

    bad = dict(payload)
    bad["timing_context"] = "BAD"
    with pytest.raises(ValueError):
        engine.validate_entry_score_report(bad)

    bad = dict(payload)
    signals = [dict(signal) for signal in payload["entry_signals"]]
    signals[0]["status"] = "BAD"
    bad["entry_signals"] = signals
    with pytest.raises(ValueError):
        engine.validate_entry_score_report(bad)

    bad = dict(payload)
    signals = [dict(signal) for signal in payload["entry_signals"]]
    signals[0]["timing_context"] = "BAD"
    bad["entry_signals"] = signals
    with pytest.raises(ValueError):
        engine.validate_entry_score_report(bad)


@pytest.mark.parametrize("value", [-1, 101, "0", True])
def test_validate_rejects_bad_entry_score(value):
    payload = engine.build_entry_score_report()
    bad = dict(payload)
    bad["entry_score"] = value
    with pytest.raises(ValueError):
        engine.validate_entry_score_report(bad)


@pytest.mark.parametrize("value", [-0.1, 1.1, "0.5", True])
def test_validate_rejects_bad_confidence(value):
    payload = engine.build_entry_score_report()
    bad = dict(payload)
    bad["confidence"] = value
    with pytest.raises(ValueError):
        engine.validate_entry_score_report(bad)


def test_validate_rejects_bad_confidence_level():
    payload = engine.build_entry_score_report()
    bad = dict(payload)
    bad["confidence_level"] = "VERY_HIGH"
    with pytest.raises(ValueError):
        engine.validate_entry_score_report(bad)


def test_validate_rejects_duplicate_or_missing_signals():
    payload = engine.build_entry_score_report()
    bad = dict(payload)
    signals = [dict(signal) for signal in payload["entry_signals"]]
    signals[1]["signal_name"] = signals[0]["signal_name"]
    bad["entry_signals"] = signals
    with pytest.raises(ValueError):
        engine.validate_entry_score_report(bad)

    bad = dict(payload)
    bad["entry_signals"] = payload["entry_signals"][:-1]
    with pytest.raises(ValueError):
        engine.validate_entry_score_report(bad)


def test_json_write_read_round_trip(tmp_path):
    path = tmp_path / "entry_score_report.json"
    written = engine.write_entry_score_report_json(path=str(path))
    read = engine.read_entry_score_report_json(path=str(path))
    assert path.exists()
    assert read == written


def test_markdown_generation(tmp_path):
    payload = engine.build_entry_score_report()
    markdown = engine.format_entry_score_report_markdown(payload)
    assert "# Entry Score Report" in markdown
    assert "## Entry Summary" in markdown
    assert "## Entry Signals" in markdown
    assert "## Scoring Model" in markdown
    assert "## Timing Model" in markdown
    assert "## Confirmation Model" in markdown
    assert "## Integration Targets" in markdown
    assert "## Safety Guarantees" in markdown

    path = tmp_path / "entry_score_report.md"
    engine.write_entry_score_report_markdown(path=str(path))
    assert path.exists()


def test_static_safety_no_broker_robinhood_or_orders():
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
