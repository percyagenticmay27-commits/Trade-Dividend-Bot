"""
Pytest coverage for bot_health_score.py.

These tests verify the read-only health scoring module without modifying runtime
workflow files or production trading logic.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import bot_health_score as health


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _environment_payload(status: str = "OK", warnings=None, errors=None) -> dict:
    return {
        "environment_status": status,
        "warnings": list(warnings or []),
        "errors": list(errors or []),
    }


def _report_integrity_payload(status: str = "OK", warnings=None, errors=None) -> dict:
    return {
        "integrity_status": status,
        "warnings": list(warnings or []),
        "errors": list(errors or []),
    }


def _runtime_metrics_payload(status: str = "OK", warnings=None, errors=None) -> dict:
    return {
        "runtime_status": status,
        "warnings": list(warnings or []),
        "errors": list(errors or []),
    }


def _diagnostics_payload(status: str = "OK", warnings=None, errors=None) -> dict:
    return {
        "overall_diagnostic_status": status,
        "warnings": list(warnings or []),
        "errors": list(errors or []),
    }


def _capabilities_payload(warnings=None, errors=None) -> dict:
    return {
        "warnings": list(warnings or []),
        "errors": list(errors or []),
    }


def _write_all_inputs(
    root: Path,
    environment_status: str = "OK",
    report_integrity_status: str = "OK",
    runtime_metrics_status: str = "OK",
    diagnostics_status: str = "OK",
    warnings=None,
    errors=None,
) -> None:
    _write_json(root / "bot_capabilities.json", _capabilities_payload())
    _write_json(
        root / "bot_environment_check.json",
        _environment_payload(environment_status, warnings=warnings, errors=errors),
    )
    _write_json(
        root / "bot_report_integrity.json",
        _report_integrity_payload(report_integrity_status, warnings=warnings, errors=errors),
    )
    _write_json(
        root / "bot_runtime_metrics.json",
        _runtime_metrics_payload(runtime_metrics_status, warnings=warnings, errors=errors),
    )
    _write_json(
        root / "bot_diagnostics.json",
        _diagnostics_payload(diagnostics_status, warnings=warnings, errors=errors),
    )


def test_module_constants_are_expected():
    assert health.MODULE_NAME == "bot_health_score"
    assert health.MODULE_VERSION == "1.0.0"
    assert health.SCHEMA_VERSION == "1.0"
    assert health.GENERATED_BY == "Agentic-Robin-Dividend.bot"


def test_required_public_functions_exist_and_are_callable():
    assert callable(health.build_bot_health_score)
    assert callable(health.validate_bot_health_score)
    assert callable(health.write_bot_health_score)
    assert callable(health.read_bot_health_score)
    assert callable(health.format_bot_health_score_summary)


def test_build_bot_health_score_returns_valid_payload(tmp_path):
    _write_all_inputs(tmp_path)

    payload = health.build_bot_health_score(root_path=str(tmp_path))

    assert health.validate_bot_health_score(payload) is True
    assert payload["paper_trade_mode"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False
    assert payload["health_score"] == 100
    assert payload["health_grade"] == "A"
    assert payload["health_status"] == "EXCELLENT"


def test_payload_list_fields_are_valid(tmp_path):
    _write_all_inputs(tmp_path)
    payload = health.build_bot_health_score(root_path=str(tmp_path))

    for field in [
        "input_files",
        "available_input_files",
        "missing_input_files",
        "scoring_breakdown",
        "recommendations",
        "warnings",
        "errors",
        "safety_guarantees",
    ]:
        assert isinstance(payload[field], list)
        for item in payload[field]:
            assert isinstance(item, str)
            assert item.strip()


def test_validate_bot_health_score_enforces_paper_only_flags(tmp_path):
    _write_all_inputs(tmp_path)
    payload = health.build_bot_health_score(root_path=str(tmp_path))

    bad_payload = dict(payload)
    bad_payload["paper_trade_mode"] = False
    with pytest.raises(ValueError):
        health.validate_bot_health_score(bad_payload)

    bad_payload = dict(payload)
    bad_payload["live_trading_enabled"] = True
    with pytest.raises(ValueError):
        health.validate_bot_health_score(bad_payload)

    bad_payload = dict(payload)
    bad_payload["broker_execution_enabled"] = True
    with pytest.raises(ValueError):
        health.validate_bot_health_score(bad_payload)


def test_validate_bot_health_score_rejects_missing_required_fields(tmp_path):
    _write_all_inputs(tmp_path)
    payload = health.build_bot_health_score(root_path=str(tmp_path))

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
        "environment_status",
        "report_integrity_status",
        "runtime_metrics_status",
        "diagnostics_status",
        "health_score",
        "health_grade",
        "health_status",
        "scoring_breakdown",
        "recommendations",
        "warnings",
        "errors",
        "safety_guarantees",
    ]

    for field in required_fields:
        bad_payload = dict(payload)
        bad_payload.pop(field, None)
        with pytest.raises(ValueError):
            health.validate_bot_health_score(bad_payload)


def test_validate_bot_health_score_rejects_malformed_payload_values(tmp_path):
    _write_all_inputs(tmp_path)
    payload = health.build_bot_health_score(root_path=str(tmp_path))

    with pytest.raises(ValueError):
        health.validate_bot_health_score(None)

    for field in health.LIST_FIELDS:
        bad_payload = dict(payload)
        bad_payload[field] = "not-a-list"
        with pytest.raises(ValueError):
            health.validate_bot_health_score(bad_payload)

        bad_payload = dict(payload)
        bad_payload[field] = [""]
        with pytest.raises(ValueError):
            health.validate_bot_health_score(bad_payload)

        bad_payload = dict(payload)
        bad_payload[field] = [123]
        with pytest.raises(ValueError):
            health.validate_bot_health_score(bad_payload)


def test_validate_bot_health_score_rejects_bad_component_statuses(tmp_path):
    _write_all_inputs(tmp_path)
    payload = health.build_bot_health_score(root_path=str(tmp_path))

    for field in [
        "environment_status",
        "report_integrity_status",
        "runtime_metrics_status",
        "diagnostics_status",
    ]:
        bad_payload = dict(payload)
        bad_payload[field] = "BAD"
        with pytest.raises(ValueError):
            health.validate_bot_health_score(bad_payload)


def test_validate_bot_health_score_rejects_score_out_of_range_or_non_integer(tmp_path):
    _write_all_inputs(tmp_path)
    payload = health.build_bot_health_score(root_path=str(tmp_path))

    for bad_score in [-1, 101, 1.5, True, "100"]:
        bad_payload = dict(payload)
        bad_payload["health_score"] = bad_score
        with pytest.raises(ValueError):
            health.validate_bot_health_score(bad_payload)


def test_validate_bot_health_score_rejects_incorrect_grade_or_status(tmp_path):
    _write_all_inputs(tmp_path)
    payload = health.build_bot_health_score(root_path=str(tmp_path))

    bad_payload = dict(payload)
    bad_payload["health_grade"] = "F"
    with pytest.raises(ValueError):
        health.validate_bot_health_score(bad_payload)

    bad_payload = dict(payload)
    bad_payload["health_status"] = "CRITICAL"
    with pytest.raises(ValueError):
        health.validate_bot_health_score(bad_payload)


def test_validate_bot_health_score_rejects_incorrect_metadata(tmp_path):
    _write_all_inputs(tmp_path)
    payload = health.build_bot_health_score(root_path=str(tmp_path))

    for field in ["module_name", "module_version", "bot_version", "schema_version", "generated_by"]:
        bad_payload = dict(payload)
        bad_payload[field] = "wrong"
        with pytest.raises(ValueError):
            health.validate_bot_health_score(bad_payload)


def test_score_of_100_produces_grade_a_and_status_excellent(tmp_path):
    _write_all_inputs(tmp_path)

    payload = health.build_bot_health_score(root_path=str(tmp_path))

    assert payload["health_score"] == 100
    assert payload["health_grade"] == "A"
    assert payload["health_status"] == "EXCELLENT"


@pytest.mark.parametrize(
    "score,grade,status",
    [
        (100, "A", "EXCELLENT"),
        (95, "A", "EXCELLENT"),
        (94, "A-", "GOOD"),
        (90, "A-", "GOOD"),
        (89, "B+", "GOOD"),
        (85, "B+", "GOOD"),
        (84, "B", "GOOD"),
        (80, "B", "GOOD"),
        (79, "C+", "FAIR"),
        (75, "C+", "FAIR"),
        (74, "C", "FAIR"),
        (70, "C", "FAIR"),
        (69, "D", "DEGRADED"),
        (60, "D", "DEGRADED"),
        (59, "F", "CRITICAL"),
        (0, "F", "CRITICAL"),
    ],
)
def test_grade_and_health_status_match_score_boundaries(tmp_path, score, grade, status):
    _write_all_inputs(tmp_path)
    payload = health.build_bot_health_score(root_path=str(tmp_path))
    payload["health_score"] = score
    payload["health_grade"] = grade
    payload["health_status"] = status

    assert health.validate_bot_health_score(payload) is True


def test_warning_deductions_produce_correct_reduced_score(tmp_path):
    _write_all_inputs(
        tmp_path,
        environment_status="WARNING",
        report_integrity_status="WARNING",
        runtime_metrics_status="WARNING",
        diagnostics_status="WARNING",
    )

    payload = health.build_bot_health_score(root_path=str(tmp_path))

    assert payload["health_score"] == 60
    assert payload["health_grade"] == "D"
    assert payload["health_status"] == "DEGRADED"
    assert "Environment WARNING: -10" in payload["scoring_breakdown"]
    assert "Report Integrity WARNING: -10" in payload["scoring_breakdown"]
    assert "Runtime Metrics WARNING: -8" in payload["scoring_breakdown"]
    assert "Diagnostics WARNING: -12" in payload["scoring_breakdown"]


def test_error_deductions_produce_correct_reduced_score(tmp_path):
    _write_all_inputs(
        tmp_path,
        environment_status="ERROR",
        report_integrity_status="ERROR",
        runtime_metrics_status="ERROR",
        diagnostics_status="ERROR",
    )

    payload = health.build_bot_health_score(root_path=str(tmp_path))

    assert payload["health_score"] == 0
    assert payload["health_grade"] == "F"
    assert payload["health_status"] == "CRITICAL"
    assert "Environment ERROR: -25" in payload["scoring_breakdown"]
    assert "Report Integrity ERROR: -25" in payload["scoring_breakdown"]
    assert "Runtime Metrics ERROR: -20" in payload["scoring_breakdown"]
    assert "Diagnostics ERROR: -30" in payload["scoring_breakdown"]


def test_missing_input_files_reduce_score_appropriately(tmp_path):
    _write_json(tmp_path / "bot_capabilities.json", _capabilities_payload())

    payload = health.build_bot_health_score(root_path=str(tmp_path))

    assert len(payload["missing_input_files"]) == 4
    assert payload["health_score"] == 92
    assert "Missing input files (4): -8" in payload["scoring_breakdown"]


def test_score_never_drops_below_zero(tmp_path):
    _write_all_inputs(
        tmp_path,
        environment_status="ERROR",
        report_integrity_status="ERROR",
        runtime_metrics_status="ERROR",
        diagnostics_status="ERROR",
        errors=["serious error"],
    )
    (tmp_path / "bot_capabilities.json").unlink()

    payload = health.build_bot_health_score(root_path=str(tmp_path))

    assert payload["health_score"] == 0
    assert payload["health_grade"] == "F"
    assert payload["health_status"] == "CRITICAL"


def test_recommendations_are_generated_when_warnings_or_errors_exist(tmp_path):
    _write_all_inputs(
        tmp_path,
        environment_status="WARNING",
        diagnostics_status="ERROR",
        warnings=["warning"],
        errors=["error"],
    )

    payload = health.build_bot_health_score(root_path=str(tmp_path))

    assert payload["recommendations"]
    assert any("WARNING" in item or "ERROR" in item or "Review" in item for item in payload["recommendations"])


def test_scoring_breakdown_is_populated_and_internally_consistent(tmp_path):
    _write_all_inputs(tmp_path, environment_status="WARNING")

    payload = health.build_bot_health_score(root_path=str(tmp_path))

    assert payload["scoring_breakdown"]
    assert payload["scoring_breakdown"][0] == "Base score: 100"
    assert any("Environment WARNING: -10" == item for item in payload["scoring_breakdown"])
    assert any(item.startswith("Missing input files") for item in payload["scoring_breakdown"])


def test_warning_count_if_present_must_match_warnings(tmp_path):
    _write_all_inputs(tmp_path)
    payload = health.build_bot_health_score(root_path=str(tmp_path))
    payload["warning_count"] = len(payload["warnings"])

    assert health.validate_bot_health_score(payload) is True

    payload["warning_count"] = len(payload["warnings"]) + 1
    with pytest.raises(ValueError):
        health.validate_bot_health_score(payload)


def test_error_count_if_present_must_match_errors(tmp_path):
    _write_all_inputs(tmp_path)
    payload = health.build_bot_health_score(root_path=str(tmp_path))
    payload["error_count"] = len(payload["errors"])

    assert health.validate_bot_health_score(payload) is True

    payload["error_count"] = len(payload["errors"]) + 1
    with pytest.raises(ValueError):
        health.validate_bot_health_score(payload)


def test_write_and_read_bot_health_score_round_trip(tmp_path):
    _write_all_inputs(tmp_path)
    output_path = tmp_path / "bot_health_score.json"

    written_payload = health.write_bot_health_score(path=str(output_path), root_path=str(tmp_path))
    read_payload = health.read_bot_health_score(path=str(output_path))

    assert output_path.exists()
    assert read_payload == written_payload
    assert health.validate_bot_health_score(read_payload) is True


def test_format_bot_health_score_summary_contains_key_sections(tmp_path):
    _write_all_inputs(tmp_path)
    payload = health.build_bot_health_score(root_path=str(tmp_path))

    summary = health.format_bot_health_score_summary(payload)

    assert "# Agentic Robin Dividend Bot Health Score" in summary
    assert "## Health" in summary
    assert "## Component Statuses" in summary
    assert "## Input Files" in summary
    assert "## Available Input Files" in summary
    assert "## Missing Input Files" in summary
    assert "## Scoring Breakdown" in summary
    assert "## Recommendations" in summary
    assert "## Warnings" in summary
    assert "## Errors" in summary
    assert "## Safety Guarantees" in summary
    assert "Health Score" in summary
    assert "Health Grade" in summary
    assert "Health Status" in summary


def test_format_bot_health_score_summary_validates_payload_first(tmp_path):
    _write_all_inputs(tmp_path)
    payload = health.build_bot_health_score(root_path=str(tmp_path))
    payload["paper_trade_mode"] = False

    with pytest.raises(ValueError):
        health.format_bot_health_score_summary(payload)


def test_static_safety_no_broker_or_robinhood_imports():
    source = Path(health.__file__).read_text(encoding="utf-8").lower()

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
    source = Path(health.__file__).read_text(encoding="utf-8").lower()

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
    source = Path(health.__file__).read_text(encoding="utf-8")

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
    source = Path(health.__file__).read_text(encoding="utf-8")

    forbidden_write_targets = [
        "run_daily_paper_cycle.py",
        "send_daily_reports.py",
    ]

    for target in forbidden_write_targets:
        assert f'open("{target}", "w"' not in source
        assert f"open('{target}', 'w'" not in source
        assert f'Path("{target}").write_text' not in source
        assert f"Path('{target}').write_text" not in source
