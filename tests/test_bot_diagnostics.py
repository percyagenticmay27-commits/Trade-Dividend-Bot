"""
Pytest coverage for bot_diagnostics.py.

These tests verify the read-only diagnostics module without modifying runtime
workflow files or production trading logic.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import bot_diagnostics as diagnostics


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _base_environment_payload(status: str = "OK", warnings=None, errors=None) -> dict:
    return {
        "environment_status": status,
        "warnings": list(warnings or []),
        "errors": list(errors or []),
    }


def _base_report_integrity_payload(status: str = "OK", warnings=None, errors=None) -> dict:
    return {
        "integrity_status": status,
        "warnings": list(warnings or []),
        "errors": list(errors or []),
    }


def _base_runtime_metrics_payload(status: str = "OK", warnings=None, errors=None) -> dict:
    return {
        "runtime_status": status,
        "warnings": list(warnings or []),
        "errors": list(errors or []),
    }


def _write_all_inputs(root: Path, env_status="OK", report_status="OK", runtime_status="OK", warnings=None, errors=None) -> None:
    _write_json(root / "bot_capabilities.json", {"warnings": [], "errors": []})
    _write_json(root / "bot_environment_check.json", _base_environment_payload(env_status, warnings=warnings, errors=errors))
    _write_json(root / "bot_report_integrity.json", _base_report_integrity_payload(report_status, warnings=warnings, errors=errors))
    _write_json(root / "bot_runtime_metrics.json", _base_runtime_metrics_payload(runtime_status, warnings=warnings, errors=errors))


def test_module_constants_are_expected():
    assert diagnostics.MODULE_NAME == "bot_diagnostics"
    assert diagnostics.MODULE_VERSION == "1.0.0"
    assert diagnostics.SCHEMA_VERSION == "1.0"
    assert diagnostics.GENERATED_BY == "Agentic-Robin-Dividend.bot"


def test_required_public_functions_exist_and_are_callable():
    assert callable(diagnostics.build_bot_diagnostics)
    assert callable(diagnostics.validate_bot_diagnostics)
    assert callable(diagnostics.write_bot_diagnostics)
    assert callable(diagnostics.read_bot_diagnostics)
    assert callable(diagnostics.format_bot_diagnostics_summary)


def test_build_bot_diagnostics_with_all_ok_inputs(tmp_path):
    _write_all_inputs(tmp_path)

    payload = diagnostics.build_bot_diagnostics(root_path=str(tmp_path))

    assert diagnostics.validate_bot_diagnostics(payload) is True
    assert payload["paper_trade_mode"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False
    assert payload["capabilities_status"] == "OK"
    assert payload["environment_status"] == "OK"
    assert payload["report_integrity_status"] == "OK"
    assert payload["runtime_metrics_status"] == "OK"
    assert payload["overall_diagnostic_status"] == "OK"
    assert payload["warning_count"] == 0
    assert payload["error_count"] == 0


def test_diagnostics_payload_list_fields_are_valid(tmp_path):
    _write_all_inputs(tmp_path)
    payload = diagnostics.build_bot_diagnostics(root_path=str(tmp_path))

    for field in [
        "input_files",
        "available_input_files",
        "missing_input_files",
        "diagnostic_findings",
        "warnings",
        "errors",
        "safety_guarantees",
    ]:
        assert isinstance(payload[field], list)
        for item in payload[field]:
            assert isinstance(item, str)
            assert item.strip()


def test_validate_bot_diagnostics_enforces_paper_only_flags(tmp_path):
    _write_all_inputs(tmp_path)
    payload = diagnostics.build_bot_diagnostics(root_path=str(tmp_path))

    bad_payload = dict(payload)
    bad_payload["paper_trade_mode"] = False
    with pytest.raises(ValueError):
        diagnostics.validate_bot_diagnostics(bad_payload)

    bad_payload = dict(payload)
    bad_payload["live_trading_enabled"] = True
    with pytest.raises(ValueError):
        diagnostics.validate_bot_diagnostics(bad_payload)

    bad_payload = dict(payload)
    bad_payload["broker_execution_enabled"] = True
    with pytest.raises(ValueError):
        diagnostics.validate_bot_diagnostics(bad_payload)


def test_validate_bot_diagnostics_rejects_missing_required_fields(tmp_path):
    _write_all_inputs(tmp_path)
    payload = diagnostics.build_bot_diagnostics(root_path=str(tmp_path))

    required_fields = [
        "bot_name",
        "bot_type",
        "bot_version",
        "schema_version",
        "generated_at_utc",
        "paper_trade_mode",
        "live_trading_enabled",
        "broker_execution_enabled",
        "input_files",
        "available_input_files",
        "missing_input_files",
        "capabilities_status",
        "environment_status",
        "report_integrity_status",
        "runtime_metrics_status",
        "overall_diagnostic_status",
        "diagnostic_findings",
        "warning_count",
        "error_count",
        "warnings",
        "errors",
        "safety_guarantees",
    ]

    for field in required_fields:
        bad_payload = dict(payload)
        bad_payload.pop(field, None)
        with pytest.raises(ValueError):
            diagnostics.validate_bot_diagnostics(bad_payload)


def test_validate_bot_diagnostics_rejects_malformed_payload_values(tmp_path):
    _write_all_inputs(tmp_path)
    payload = diagnostics.build_bot_diagnostics(root_path=str(tmp_path))

    with pytest.raises(ValueError):
        diagnostics.validate_bot_diagnostics(None)

    for field in diagnostics.LIST_FIELDS:
        bad_payload = dict(payload)
        bad_payload[field] = "not-a-list"
        with pytest.raises(ValueError):
            diagnostics.validate_bot_diagnostics(bad_payload)

        bad_payload = dict(payload)
        bad_payload[field] = [""]
        with pytest.raises(ValueError):
            diagnostics.validate_bot_diagnostics(bad_payload)

        bad_payload = dict(payload)
        bad_payload[field] = [123]
        with pytest.raises(ValueError):
            diagnostics.validate_bot_diagnostics(bad_payload)


def test_validate_bot_diagnostics_rejects_bad_status_values(tmp_path):
    _write_all_inputs(tmp_path)
    payload = diagnostics.build_bot_diagnostics(root_path=str(tmp_path))

    for field in [
        "capabilities_status",
        "environment_status",
        "report_integrity_status",
        "runtime_metrics_status",
        "overall_diagnostic_status",
    ]:
        bad_payload = dict(payload)
        bad_payload[field] = "BAD"
        with pytest.raises(ValueError):
            diagnostics.validate_bot_diagnostics(bad_payload)


def test_validate_bot_diagnostics_rejects_count_mismatches(tmp_path):
    _write_all_inputs(tmp_path, env_status="WARNING", warnings=["warn"])
    payload = diagnostics.build_bot_diagnostics(root_path=str(tmp_path))

    bad_payload = dict(payload)
    bad_payload["warning_count"] = payload["warning_count"] + 1
    with pytest.raises(ValueError):
        diagnostics.validate_bot_diagnostics(bad_payload)

    error_payload = dict(payload)
    error_payload["errors"] = ["error"]
    error_payload["error_count"] = 0
    error_payload["overall_diagnostic_status"] = "ERROR"
    with pytest.raises(ValueError):
        diagnostics.validate_bot_diagnostics(error_payload)


def test_validate_bot_diagnostics_rejects_negative_or_non_integer_counts(tmp_path):
    _write_all_inputs(tmp_path)
    payload = diagnostics.build_bot_diagnostics(root_path=str(tmp_path))

    for field in ["warning_count", "error_count"]:
        bad_payload = dict(payload)
        bad_payload[field] = -1
        with pytest.raises(ValueError):
            diagnostics.validate_bot_diagnostics(bad_payload)

        bad_payload = dict(payload)
        bad_payload[field] = 1.5
        with pytest.raises(ValueError):
            diagnostics.validate_bot_diagnostics(bad_payload)

        bad_payload = dict(payload)
        bad_payload[field] = True
        with pytest.raises(ValueError):
            diagnostics.validate_bot_diagnostics(bad_payload)


def test_validate_bot_diagnostics_rejects_incorrect_metadata(tmp_path):
    _write_all_inputs(tmp_path)
    payload = diagnostics.build_bot_diagnostics(root_path=str(tmp_path))

    for field in ["module_name", "module_version", "bot_version", "schema_version", "generated_by"]:
        bad_payload = dict(payload)
        bad_payload[field] = "wrong"
        with pytest.raises(ValueError):
            diagnostics.validate_bot_diagnostics(bad_payload)


def test_detects_available_input_files(tmp_path):
    _write_all_inputs(tmp_path)

    payload = diagnostics.build_bot_diagnostics(root_path=str(tmp_path))

    assert sorted(payload["available_input_files"]) == sorted(diagnostics.INPUT_FILES)
    assert payload["missing_input_files"] == []


def test_detects_missing_input_files(tmp_path):
    _write_json(tmp_path / "bot_capabilities.json", {"warnings": [], "errors": []})

    payload = diagnostics.build_bot_diagnostics(root_path=str(tmp_path))

    assert "bot_capabilities.json" in payload["available_input_files"]
    assert "bot_environment_check.json" in payload["missing_input_files"]
    assert "bot_report_integrity.json" in payload["missing_input_files"]
    assert "bot_runtime_metrics.json" in payload["missing_input_files"]
    assert payload["overall_diagnostic_status"] == "WARNING"
    assert payload["warning_count"] == len(payload["warnings"])


def test_handles_malformed_json_input_files_safely(tmp_path):
    _write_json(tmp_path / "bot_capabilities.json", {"warnings": [], "errors": []})
    (tmp_path / "bot_environment_check.json").write_text("{not valid json", encoding="utf-8")
    _write_json(tmp_path / "bot_report_integrity.json", _base_report_integrity_payload("OK"))
    _write_json(tmp_path / "bot_runtime_metrics.json", _base_runtime_metrics_payload("OK"))

    payload = diagnostics.build_bot_diagnostics(root_path=str(tmp_path))

    assert "bot_environment_check.json" in payload["available_input_files"]
    assert payload["overall_diagnostic_status"] == "ERROR"
    assert payload["error_count"] == len(payload["errors"])
    assert any("Unable to read diagnostic input file bot_environment_check.json" in error for error in payload["errors"])


def test_aggregates_ok_statuses_correctly(tmp_path):
    _write_all_inputs(tmp_path)

    payload = diagnostics.build_bot_diagnostics(root_path=str(tmp_path))

    assert payload["overall_diagnostic_status"] == "OK"
    assert payload["errors"] == []
    assert payload["warnings"] == []


def test_aggregates_warning_statuses_correctly(tmp_path):
    _write_all_inputs(tmp_path, env_status="WARNING", warnings=["environment warning"])

    payload = diagnostics.build_bot_diagnostics(root_path=str(tmp_path))

    assert payload["environment_status"] == "WARNING"
    assert payload["overall_diagnostic_status"] == "WARNING"
    assert payload["warning_count"] == len(payload["warnings"])
    assert any("environment warning" in warning for warning in payload["warnings"])


def test_aggregates_error_statuses_correctly(tmp_path):
    _write_all_inputs(tmp_path, report_status="ERROR", errors=["report error"])

    payload = diagnostics.build_bot_diagnostics(root_path=str(tmp_path))

    assert payload["report_integrity_status"] == "ERROR"
    assert payload["overall_diagnostic_status"] == "ERROR"
    assert payload["error_count"] == len(payload["errors"])
    assert any("report error" in error for error in payload["errors"])


def test_produces_diagnostic_findings(tmp_path):
    _write_all_inputs(tmp_path)

    payload = diagnostics.build_bot_diagnostics(root_path=str(tmp_path))

    assert isinstance(payload["diagnostic_findings"], list)
    assert payload["diagnostic_findings"]
    assert all(isinstance(item, str) and item.strip() for item in payload["diagnostic_findings"])


def test_write_and_read_bot_diagnostics_round_trip(tmp_path):
    _write_all_inputs(tmp_path)
    output_path = tmp_path / "bot_diagnostics.json"

    written_payload = diagnostics.write_bot_diagnostics(path=str(output_path), root_path=str(tmp_path))
    read_payload = diagnostics.read_bot_diagnostics(path=str(output_path))

    assert output_path.exists()
    assert read_payload == written_payload
    assert diagnostics.validate_bot_diagnostics(read_payload) is True


def test_format_bot_diagnostics_summary_contains_key_sections(tmp_path):
    _write_all_inputs(tmp_path)
    payload = diagnostics.build_bot_diagnostics(root_path=str(tmp_path))

    summary = diagnostics.format_bot_diagnostics_summary(payload)

    assert "# Agentic Robin Dividend Bot Diagnostics" in summary
    assert "## Status" in summary
    assert "## Input Files" in summary
    assert "## Available Input Files" in summary
    assert "## Missing Input Files" in summary
    assert "## Diagnostic Findings" in summary
    assert "## Warnings" in summary
    assert "## Errors" in summary
    assert "## Safety Guarantees" in summary
    assert "Overall Diagnostic Status" in summary


def test_format_bot_diagnostics_summary_validates_payload_first(tmp_path):
    _write_all_inputs(tmp_path)
    payload = diagnostics.build_bot_diagnostics(root_path=str(tmp_path))
    payload["paper_trade_mode"] = False

    with pytest.raises(ValueError):
        diagnostics.format_bot_diagnostics_summary(payload)


def test_static_safety_no_broker_or_robinhood_imports():
    source = Path(diagnostics.__file__).read_text(encoding="utf-8").lower()

    forbidden_import_patterns = [
        "import robinhood",
        "from robinhood",
        "import robin_stocks",
        "from robin_stocks",
        "import broker",
        "from broker",
        "import alpaca",
        "from alpaca",
        "import ibapi",
        "from ibapi",
    ]

    for pattern in forbidden_import_patterns:
        assert pattern not in source


def test_static_safety_no_real_order_placement_logic():
    source = Path(diagnostics.__file__).read_text(encoding="utf-8").lower()

    forbidden_runtime_patterns = [
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

    for pattern in forbidden_runtime_patterns:
        assert pattern not in source


def test_static_safety_no_subprocess_or_os_system_usage():
    source = Path(diagnostics.__file__).read_text(encoding="utf-8")

    forbidden_runtime_patterns = [
        "import subprocess",
        "from subprocess",
        "subprocess.",
        "Popen(",
        "os.system(",
        ".system(",
    ]

    for pattern in forbidden_runtime_patterns:
        assert pattern not in source

    assert "from subprocess import run" not in source


def test_static_safety_does_not_modify_runtime_workflow_files():
    source = Path(diagnostics.__file__).read_text(encoding="utf-8")

    forbidden_write_targets = [
        "run_daily_paper_cycle.py",
        "send_daily_reports.py",
    ]

    for target in forbidden_write_targets:
        assert f'open("{target}", "w"' not in source
        assert f"open('{target}', 'w'" not in source
        assert f'Path("{target}").write_text' not in source
        assert f"Path('{target}').write_text" not in source
