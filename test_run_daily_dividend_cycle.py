"""Tests for run_daily_dividend_cycle.py."""
from __future__ import annotations

from pathlib import Path
import json
import pytest

import run_daily_dividend_cycle as runner
from master_portfolio_orchestrator import STAGE_ORDER


def test_dataclass_exists():
    assert hasattr(runner, "DailyDividendCycleReport")


def test_public_functions_exist():
    for name in [
        "build_daily_dividend_cycle_report",
        "validate_daily_dividend_cycle_report",
        "format_daily_dividend_cycle_markdown",
        "run_daily_dividend_cycle",
    ]:
        assert callable(getattr(runner, name))


def test_default_report_is_partial_and_valid(tmp_path):
    payload = runner.build_daily_dividend_cycle_report(root_path=str(tmp_path))
    assert runner.validate_daily_dividend_cycle_report(payload) is True
    assert payload["run_status"] == "PARTIAL"
    assert payload["available_stage_count"] == 0
    assert payload["missing_stage_count"] == len(STAGE_ORDER)
    assert payload["invalid_stage_count"] == 0
    assert payload["stage_count"] == len(STAGE_ORDER)


def test_complete_when_all_stage_payloads_supplied():
    supplied = {stage: {"module_name": stage, "module_version": "1.0.0"} for stage in STAGE_ORDER}
    payload = runner.build_daily_dividend_cycle_report(stage_payloads=supplied)
    assert payload["run_status"] == "COMPLETE"
    assert payload["available_stage_count"] == len(STAGE_ORDER)
    assert payload["missing_stage_count"] == 0
    assert payload["invalid_stage_count"] == 0


def test_invalid_stage_makes_error_status():
    supplied = {stage: {"module_name": stage} for stage in STAGE_ORDER}
    supplied[STAGE_ORDER[0]] = []
    payload = runner.build_daily_dividend_cycle_report(stage_payloads=supplied)
    assert payload["run_status"] == "ERROR"
    assert payload["invalid_stage_count"] == 1
    assert payload["errors"]


def test_safety_flags_are_enforced():
    payload = runner.build_daily_dividend_cycle_report()
    assert payload["paper_trade_mode"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False
    assert payload["reporting_only"] is True


def test_validate_rejects_malformed_payload():
    for value in [None, [], "bad"]:
        with pytest.raises(ValueError):
            runner.validate_daily_dividend_cycle_report(value)


def test_validate_rejects_missing_required_fields():
    payload = runner.build_daily_dividend_cycle_report()
    for field in runner.REPORT_REQUIRED_FIELDS:
        bad = dict(payload)
        bad.pop(field, None)
        with pytest.raises(ValueError):
            runner.validate_daily_dividend_cycle_report(bad)


def test_validate_rejects_wrong_safety_flags():
    payload = runner.build_daily_dividend_cycle_report()
    for field, value in [
        ("paper_trade_mode", False),
        ("live_trading_enabled", True),
        ("broker_execution_enabled", True),
        ("reporting_only", False),
    ]:
        bad = dict(payload)
        bad[field] = value
        with pytest.raises(ValueError):
            runner.validate_daily_dividend_cycle_report(bad)


def test_validate_rejects_count_mismatch():
    payload = runner.build_daily_dividend_cycle_report()
    bad = dict(payload)
    bad["stage_count"] += 1
    with pytest.raises(ValueError):
        runner.validate_daily_dividend_cycle_report(bad)


def test_run_writes_all_outputs(tmp_path):
    payload = runner.run_daily_dividend_cycle(root_path=str(tmp_path))
    assert payload["run_status"] == "PARTIAL"
    for filename in runner.DEFAULT_OUTPUT_FILES.values():
        assert (tmp_path / filename).exists()
    cycle_json = json.loads((tmp_path / runner.DEFAULT_OUTPUT_FILES["cycle_json"]).read_text(encoding="utf-8"))
    assert cycle_json == payload
    markdown = (tmp_path / runner.DEFAULT_OUTPUT_FILES["cycle_markdown"]).read_text(encoding="utf-8")
    assert "# Daily Dividend Cycle Report" in markdown
    assert "## Safety Guarantees" in markdown


def test_custom_output_paths(tmp_path):
    outputs = {
        "orchestration_json": "reports/orchestration.json",
        "cycle_json": "reports/cycle.json",
        "cycle_markdown": "reports/cycle.md",
    }
    (tmp_path / "reports").mkdir()
    runner.run_daily_dividend_cycle(root_path=str(tmp_path), output_files=outputs)
    for filename in outputs.values():
        assert (tmp_path / filename).exists()


def test_static_safety_no_restricted_execution_terms():
    source = Path(runner.__file__).read_text(encoding="utf-8").lower()
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
    source = Path(runner.__file__).read_text(encoding="utf-8")
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
