"""Tests for bot_runtime_metrics.py."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

import bot_runtime_metrics as metrics


REQUIRED_FIELDS = [
    "bot_name",
    "bot_type",
    "bot_version",
    "schema_version",
    "generated_at_utc",
    "generated_by",
    "module_name",
    "paper_trade_mode",
    "live_trading_enabled",
    "broker_execution_enabled",
    "metrics_source_files",
    "available_source_files",
    "missing_source_files",
    "run_count",
    "successful_run_count",
    "failed_run_count",
    "warning_count",
    "error_count",
    "latest_run_at_utc",
    "latest_success_at_utc",
    "latest_failure_at_utc",
    "email_delivery_count",
    "report_file_count",
    "csv_output_count",
    "json_output_count",
    "markdown_output_count",
    "runtime_status",
    "warnings",
    "errors",
    "safety_guarantees",
]

LIST_FIELDS = [
    "metrics_source_files",
    "available_source_files",
    "missing_source_files",
    "warnings",
    "errors",
    "safety_guarantees",
]

COUNT_FIELDS = [
    "run_count",
    "successful_run_count",
    "failed_run_count",
    "warning_count",
    "error_count",
    "email_delivery_count",
    "report_file_count",
    "csv_output_count",
    "json_output_count",
    "markdown_output_count",
]


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = sorted({key for row in rows for key in row}) or ["timestamp", "status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _create_all_source_files(root: Path) -> None:
    _write_csv(
        root / "email_delivery_log.csv",
        [
            {"sent_at": "2026-06-28T10:00:00Z", "delivery_status": "SENT"},
            {"sent_at": "2026-06-28T11:00:00Z", "delivery_status": "DELIVERED"},
        ],
    )
    _write_csv(root / "paper_trade_log.csv", [{"trade_time": "2026-06-28T09:00:00Z", "status": "OK"}])
    _write_json(root / "paper_state.json", {"updated_at": "2026-06-28T12:00:00Z", "status": "OK"})
    _write_json(root / "bot_environment_check.json", {"generated_at_utc": "2026-06-28T12:01:00Z", "environment_status": "OK", "warnings": [], "errors": []})
    _write_json(root / "bot_report_integrity.json", {"generated_at_utc": "2026-06-28T12:02:00Z", "integrity_status": "OK", "warnings": [], "errors": []})
    _write_json(root / "bot_capabilities.json", {"generated_at_utc": "2026-06-28T12:03:00Z", "warnings": [], "errors": []})


def test_module_constants_are_expected() -> None:
    assert metrics.MODULE_NAME == "bot_runtime_metrics"
    assert metrics.MODULE_VERSION == "1.0.0"
    assert metrics.SCHEMA_VERSION == "1.0"
    assert metrics.GENERATED_BY == "Agentic-Robin-Dividend.bot"


def test_required_public_functions_exist_and_are_callable() -> None:
    for function_name in [
        "build_bot_runtime_metrics",
        "validate_bot_runtime_metrics",
        "write_bot_runtime_metrics",
        "read_bot_runtime_metrics",
        "format_bot_runtime_metrics_summary",
    ]:
        assert callable(getattr(metrics, function_name))


def test_build_bot_runtime_metrics_returns_valid_payload(tmp_path: Path) -> None:
    _create_all_source_files(tmp_path)
    payload = metrics.build_bot_runtime_metrics(root_path=tmp_path)

    assert metrics.validate_bot_runtime_metrics(payload) is True
    assert payload["paper_trade_mode"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False
    assert payload["runtime_status"] in {"OK", "WARNING", "ERROR", "UNKNOWN"}
    assert payload["runtime_status"] == "OK"


def test_required_fields_exist(tmp_path: Path) -> None:
    _create_all_source_files(tmp_path)
    payload = metrics.build_bot_runtime_metrics(root_path=tmp_path)

    for field in REQUIRED_FIELDS:
        assert field in payload


def test_list_fields_are_lists_with_non_empty_string_entries(tmp_path: Path) -> None:
    _create_all_source_files(tmp_path)
    payload = metrics.build_bot_runtime_metrics(root_path=tmp_path)

    for field in LIST_FIELDS:
        assert isinstance(payload[field], list)
        for entry in payload[field]:
            assert isinstance(entry, str)
            assert entry.strip()


def test_count_fields_are_non_negative_integers(tmp_path: Path) -> None:
    _create_all_source_files(tmp_path)
    payload = metrics.build_bot_runtime_metrics(root_path=tmp_path)

    for field in COUNT_FIELDS:
        assert isinstance(payload[field], int)
        assert not isinstance(payload[field], bool)
        assert payload[field] >= 0


def test_detects_available_and_missing_source_files(tmp_path: Path) -> None:
    _write_json(tmp_path / "paper_state.json", {"updated_at": "2026-06-28T12:00:00Z", "status": "OK"})

    payload = metrics.build_bot_runtime_metrics(root_path=tmp_path)

    assert "paper_state.json" in payload["available_source_files"]
    assert "email_delivery_log.csv" in payload["missing_source_files"]
    assert payload["runtime_status"] == "WARNING"
    assert payload["warnings"]


def test_counts_email_deliveries_from_email_delivery_log(tmp_path: Path) -> None:
    _write_csv(
        tmp_path / "email_delivery_log.csv",
        [
            {"sent_at": "2026-06-28T10:00:00Z", "delivery_status": "SENT"},
            {"sent_at": "2026-06-28T11:00:00Z", "delivery_status": "DELIVERED"},
            {"sent_at": "2026-06-28T12:00:00Z", "delivery_status": "SENT"},
        ],
    )

    payload = metrics.build_bot_runtime_metrics(root_path=tmp_path)

    assert payload["email_delivery_count"] == 3
    assert payload["latest_success_at_utc"] is not None


def test_counts_csv_json_and_markdown_outputs(tmp_path: Path) -> None:
    (tmp_path / "daily_paper_report.md").write_text("# report\n", encoding="utf-8")
    (tmp_path / "weekly_portfolio_review.md").write_text("# weekly\n", encoding="utf-8")
    (tmp_path / "portfolio_snapshot.csv").write_text("symbol,value\nSCHD,1\n", encoding="utf-8")
    _write_json(tmp_path / "paper_state.json", {"updated_at": "2026-06-28T12:00:00Z", "status": "OK"})

    payload = metrics.build_bot_runtime_metrics(root_path=tmp_path)

    assert payload["markdown_output_count"] == 2
    assert payload["csv_output_count"] == 1
    assert payload["json_output_count"] == 1
    assert payload["report_file_count"] == 4


def test_handles_missing_source_files_safely(tmp_path: Path) -> None:
    payload = metrics.build_bot_runtime_metrics(root_path=tmp_path)

    assert payload["available_source_files"] == []
    assert sorted(payload["missing_source_files"]) == sorted(metrics.METRICS_SOURCE_FILES)
    assert payload["runtime_status"] == "WARNING"
    assert payload["error_count"] == 0


def test_handles_malformed_source_files_safely(tmp_path: Path) -> None:
    (tmp_path / "paper_state.json").write_text("{not valid json", encoding="utf-8")
    (tmp_path / "email_delivery_log.csv").write_text("not,a,normal\ncsv", encoding="utf-8")

    payload = metrics.build_bot_runtime_metrics(root_path=tmp_path)

    assert metrics.validate_bot_runtime_metrics(payload) is True
    assert "paper_state.json" in payload["available_source_files"]
    assert payload["runtime_status"] in {"WARNING", "ERROR", "UNKNOWN", "OK"}


def test_validate_bot_runtime_metrics_enforces_paper_only_flags(tmp_path: Path) -> None:
    _create_all_source_files(tmp_path)
    payload = metrics.build_bot_runtime_metrics(root_path=tmp_path)

    for field, value in [
        ("paper_trade_mode", False),
        ("live_trading_enabled", True),
        ("broker_execution_enabled", True),
    ]:
        malformed = dict(payload)
        malformed[field] = value
        with pytest.raises(ValueError):
            metrics.validate_bot_runtime_metrics(malformed)


def test_validate_bot_runtime_metrics_rejects_missing_required_fields(tmp_path: Path) -> None:
    _create_all_source_files(tmp_path)
    payload = metrics.build_bot_runtime_metrics(root_path=tmp_path)

    for field in REQUIRED_FIELDS:
        malformed = dict(payload)
        malformed.pop(field)
        with pytest.raises(ValueError):
            metrics.validate_bot_runtime_metrics(malformed)


def test_validate_bot_runtime_metrics_rejects_malformed_payload_values(tmp_path: Path) -> None:
    _create_all_source_files(tmp_path)
    payload = metrics.build_bot_runtime_metrics(root_path=tmp_path)

    malformed = dict(payload)
    malformed["metrics_source_files"] = "email_delivery_log.csv"
    with pytest.raises(ValueError):
        metrics.validate_bot_runtime_metrics(malformed)

    malformed = dict(payload)
    malformed["warnings"] = [""]
    with pytest.raises(ValueError):
        metrics.validate_bot_runtime_metrics(malformed)

    malformed = dict(payload)
    malformed["runtime_status"] = "BAD"
    with pytest.raises(ValueError):
        metrics.validate_bot_runtime_metrics(malformed)

    malformed = dict(payload)
    malformed["run_count"] = -1
    with pytest.raises(ValueError):
        metrics.validate_bot_runtime_metrics(malformed)

    malformed = dict(payload)
    malformed["email_delivery_count"] = True
    with pytest.raises(ValueError):
        metrics.validate_bot_runtime_metrics(malformed)


def test_validate_bot_runtime_metrics_rejects_incorrect_metadata(tmp_path: Path) -> None:
    _create_all_source_files(tmp_path)
    payload = metrics.build_bot_runtime_metrics(root_path=tmp_path)

    for field in ["module_name", "bot_version", "schema_version", "generated_by"]:
        malformed = dict(payload)
        malformed[field] = "wrong"
        with pytest.raises(ValueError):
            metrics.validate_bot_runtime_metrics(malformed)


def test_runtime_status_consistency_is_enforced(tmp_path: Path) -> None:
    _create_all_source_files(tmp_path)
    payload = metrics.build_bot_runtime_metrics(root_path=tmp_path)

    malformed = dict(payload)
    malformed["error_count"] = 1
    malformed["errors"] = ["error"]
    malformed["runtime_status"] = "WARNING"
    with pytest.raises(ValueError):
        metrics.validate_bot_runtime_metrics(malformed)

    malformed = dict(payload)
    malformed["warning_count"] = 1
    malformed["warnings"] = ["warning"]
    malformed["runtime_status"] = "OK"
    with pytest.raises(ValueError):
        metrics.validate_bot_runtime_metrics(malformed)


def test_write_and_read_bot_runtime_metrics_round_trip(tmp_path: Path) -> None:
    _create_all_source_files(tmp_path)
    output_path = tmp_path / "bot_runtime_metrics.json"

    written = metrics.write_bot_runtime_metrics(path=output_path, root_path=tmp_path)
    read_back = metrics.read_bot_runtime_metrics(path=output_path)

    assert read_back == written
    assert output_path.is_file()


def test_format_bot_runtime_metrics_summary_contains_key_sections(tmp_path: Path) -> None:
    _create_all_source_files(tmp_path)
    payload = metrics.build_bot_runtime_metrics(root_path=tmp_path)

    summary = metrics.format_bot_runtime_metrics_summary(payload)

    assert "# Dividend Bot Runtime Metrics" in summary
    assert "## Paper-Only Safety" in summary
    assert "## Runtime Counts" in summary
    assert "## Output Counts" in summary
    assert "## Latest Runtime Timestamps" in summary
    assert "## Metrics Source Files" in summary
    assert "## Available Source Files" in summary
    assert "## Missing Source Files" in summary
    assert "## Safety Guarantees" in summary


def test_format_bot_runtime_metrics_summary_validates_payload_first(tmp_path: Path) -> None:
    _create_all_source_files(tmp_path)
    payload = metrics.build_bot_runtime_metrics(root_path=tmp_path)
    payload["runtime_status"] = "BAD"

    with pytest.raises(ValueError):
        metrics.format_bot_runtime_metrics_summary(payload)


def test_static_safety_no_broker_or_robinhood_imports() -> None:
    source = Path(metrics.__file__).read_text(encoding="utf-8").lower()

    assert "import robinhood" not in source
    assert "from robinhood" not in source
    assert "robin_stocks" not in source
    assert "import broker" not in source
    assert "from broker" not in source


def test_static_safety_no_real_order_placement_logic() -> None:
    source = Path(metrics.__file__).read_text(encoding="utf-8").lower()

    forbidden_patterns = [
        "place_order(",
        "submit_order(",
        "buy_order(",
        "sell_order(",
        "order_buy",
        "order_sell",
        "execute_trade(",
        "real_order",
    ]
    for pattern in forbidden_patterns:
        assert pattern not in source


def test_static_safety_no_subprocess_or_os_system_usage() -> None:
    source = Path(metrics.__file__).read_text(encoding="utf-8")

    forbidden_patterns = [
        "import subprocess",
        "from subprocess",
        "subprocess.",
        "Popen(",
        "os.system(",
        ".system(",
    ]
    for pattern in forbidden_patterns:
        assert pattern not in source


def test_static_safety_does_not_modify_runtime_workflow_files() -> None:
    source = Path(metrics.__file__).read_text(encoding="utf-8")

    assert "run_daily_paper_cycle.py" not in source
    assert "send_daily_reports.py" not in source
