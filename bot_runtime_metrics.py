"""Read-only runtime metrics profile for the deployed Dividend Bot.

This module inspects local runtime/report files and emits a platform-facing
metrics payload. It is intentionally read-only with respect to trading behavior:
it does not import broker libraries, connect to Robinhood, place orders, execute
shell commands, or modify runtime workflow modules.
"""

from __future__ import annotations

import csv
import json
import platform as platform_module
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

MODULE_NAME = "bot_runtime_metrics"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"

BOT_NAME = "Agentic Robin Dividend Bot"
BOT_TYPE = "paper_dividend_etf_management_bot"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False

RUNTIME_STATUS_VALUES = {"OK", "WARNING", "ERROR", "UNKNOWN"}

METRICS_SOURCE_FILES = [
    "email_delivery_log.csv",
    "paper_trade_log.csv",
    "paper_state.json",
    "bot_environment_check.json",
    "bot_report_integrity.json",
    "bot_capabilities.json",
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

LIST_FIELDS = [
    "metrics_source_files",
    "available_source_files",
    "missing_source_files",
    "warnings",
    "errors",
    "safety_guarantees",
]

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

SAFETY_GUARANTEES = [
    "paper_trade_mode is always True",
    "live_trading_enabled is always False",
    "broker_execution_enabled is always False",
    "no broker execution is performed",
    "no Robinhood execution is performed",
    "no real order placement is performed",
    "no trading logic is changed",
    "no runtime workflow files are modified",
    "no command execution is used",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_root(root_path: str | Path) -> Path:
    return Path(root_path).expanduser().resolve()


def _read_json_file(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _read_csv_rows(path: Path) -> List[Dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError:
        return []


def _file_mtime_utc(path: Path) -> Optional[str]:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except OSError:
        return None


def _is_iso_like(value: Any) -> bool:
    if value in (None, ""):
        return False
    return isinstance(value, str)


def _latest_string_datetime(values: Iterable[Any]) -> Optional[str]:
    candidates = [value for value in values if _is_iso_like(value)]
    if not candidates:
        return None
    return sorted(str(value) for value in candidates)[-1]


def _first_present(row: Mapping[str, Any], names: Iterable[str]) -> Optional[str]:
    lowered = {str(key).lower(): value for key, value in row.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value not in (None, ""):
            return str(value)
    return None


def _collect_email_metrics(root: Path) -> Dict[str, Any]:
    path = root / "email_delivery_log.csv"
    rows = _read_csv_rows(path) if path.exists() else []
    timestamps: List[str] = []
    success_count = 0
    failure_count = 0

    for row in rows:
        timestamp = _first_present(row, ["timestamp", "sent_at", "created_at", "date", "datetime"])
        if timestamp:
            timestamps.append(timestamp)
        status = (_first_present(row, ["status", "result", "delivery_status"]) or "").lower()
        if status in {"sent", "success", "successful", "delivered", "ok"}:
            success_count += 1
        elif status in {"failed", "failure", "error", "bounced"}:
            failure_count += 1

    return {
        "email_delivery_count": len(rows),
        "email_success_count": success_count,
        "email_failure_count": failure_count,
        "email_latest_at_utc": _latest_string_datetime(timestamps) or _file_mtime_utc(path),
    }


def _collect_trade_log_metrics(root: Path) -> Dict[str, Any]:
    path = root / "paper_trade_log.csv"
    rows = _read_csv_rows(path) if path.exists() else []
    timestamps: List[str] = []

    for row in rows:
        timestamp = _first_present(row, ["timestamp", "created_at", "date", "datetime", "trade_time"])
        if timestamp:
            timestamps.append(timestamp)

    return {
        "paper_trade_log_rows": len(rows),
        "paper_trade_latest_at_utc": _latest_string_datetime(timestamps) or _file_mtime_utc(path),
    }


def _collect_json_status_metrics(root: Path) -> Dict[str, Any]:
    warning_count = 0
    error_count = 0
    latest_times: List[str] = []
    latest_success_times: List[str] = []
    latest_failure_times: List[str] = []
    statuses: List[str] = []

    for filename in ["bot_environment_check.json", "bot_report_integrity.json", "bot_capabilities.json", "paper_state.json"]:
        path = root / filename
        payload = _read_json_file(path)
        if not payload:
            continue

        generated_at = payload.get("generated_at_utc")
        if _is_iso_like(generated_at):
            latest_times.append(str(generated_at))

        for key in ["environment_status", "integrity_status", "runtime_status", "status"]:
            status = payload.get(key)
            if isinstance(status, str) and status:
                statuses.append(status.upper())

        warnings = payload.get("warnings", [])
        errors = payload.get("errors", [])
        if isinstance(warnings, list):
            warning_count += len(warnings)
        if isinstance(errors, list):
            error_count += len(errors)

    for status in statuses:
        if status == "OK":
            latest_success_times.extend(latest_times)
        elif status == "ERROR":
            latest_failure_times.extend(latest_times)

    return {
        "json_warning_count": warning_count,
        "json_error_count": error_count,
        "json_statuses": statuses,
        "json_latest_at_utc": _latest_string_datetime(latest_times),
        "json_latest_success_at_utc": _latest_string_datetime(latest_success_times),
        "json_latest_failure_at_utc": _latest_string_datetime(latest_failure_times),
    }


def _count_outputs(root: Path) -> Dict[str, int]:
    files = [path for path in root.iterdir() if path.is_file()] if root.exists() else []
    markdown_count = sum(1 for path in files if path.suffix.lower() == ".md")
    csv_count = sum(1 for path in files if path.suffix.lower() == ".csv")
    json_count = sum(1 for path in files if path.suffix.lower() == ".json")
    return {
        "report_file_count": markdown_count + csv_count + json_count,
        "csv_output_count": csv_count,
        "json_output_count": json_count,
        "markdown_output_count": markdown_count,
    }


def _determine_runtime_status(
    available_source_files: List[str],
    missing_source_files: List[str],
    warning_count: int,
    error_count: int,
) -> str:
    if error_count > 0:
        return "ERROR"
    if warning_count > 0 or missing_source_files:
        return "WARNING"
    if available_source_files:
        return "OK"
    return "UNKNOWN"


def build_bot_runtime_metrics(root_path: str | Path = ".") -> Dict[str, Any]:
    """Build a read-only runtime metrics payload from local output files."""
    root = _as_root(root_path)
    available_source_files = [filename for filename in METRICS_SOURCE_FILES if (root / filename).is_file()]
    missing_source_files = [filename for filename in METRICS_SOURCE_FILES if filename not in available_source_files]

    email_metrics = _collect_email_metrics(root)
    trade_metrics = _collect_trade_log_metrics(root)
    json_metrics = _collect_json_status_metrics(root)
    output_counts = _count_outputs(root)

    warnings: List[str] = []
    errors: List[str] = []

    for filename in missing_source_files:
        warnings.append(f"Metrics source file is missing: {filename}")

    warnings.extend([f"Source warning detected in platform status files ({json_metrics['json_warning_count']} total)"] * (1 if json_metrics["json_warning_count"] else 0))
    errors.extend([f"Source error detected in platform status files ({json_metrics['json_error_count']} total)"] * (1 if json_metrics["json_error_count"] else 0))

    warning_count = len(warnings)
    error_count = len(errors)

    run_count = 1 if available_source_files else 0
    failed_run_count = 1 if error_count else 0
    successful_run_count = 1 if run_count and not failed_run_count else 0

    latest_run_at_utc = _latest_string_datetime([
        email_metrics.get("email_latest_at_utc"),
        trade_metrics.get("paper_trade_latest_at_utc"),
        json_metrics.get("json_latest_at_utc"),
    ])
    latest_success_at_utc = json_metrics.get("json_latest_success_at_utc") if successful_run_count else None
    latest_failure_at_utc = json_metrics.get("json_latest_failure_at_utc") if failed_run_count else None

    runtime_status = _determine_runtime_status(
        available_source_files=available_source_files,
        missing_source_files=missing_source_files,
        warning_count=warning_count,
        error_count=error_count,
    )

    payload: Dict[str, Any] = {
        "bot_name": BOT_NAME,
        "bot_type": BOT_TYPE,
        "bot_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _utc_now_iso(),
        "generated_by": GENERATED_BY,
        "module_name": MODULE_NAME,
        "paper_trade_mode": PAPER_TRADE_MODE,
        "live_trading_enabled": LIVE_TRADING_ENABLED,
        "broker_execution_enabled": BROKER_EXECUTION_ENABLED,
        "metrics_source_files": list(METRICS_SOURCE_FILES),
        "available_source_files": available_source_files,
        "missing_source_files": missing_source_files,
        "run_count": run_count,
        "successful_run_count": successful_run_count,
        "failed_run_count": failed_run_count,
        "warning_count": warning_count,
        "error_count": error_count,
        "latest_run_at_utc": latest_run_at_utc,
        "latest_success_at_utc": latest_success_at_utc,
        "latest_failure_at_utc": latest_failure_at_utc,
        "email_delivery_count": int(email_metrics["email_delivery_count"]),
        "report_file_count": output_counts["report_file_count"],
        "csv_output_count": output_counts["csv_output_count"],
        "json_output_count": output_counts["json_output_count"],
        "markdown_output_count": output_counts["markdown_output_count"],
        "runtime_status": runtime_status,
        "warnings": warnings,
        "errors": errors,
        "safety_guarantees": list(SAFETY_GUARANTEES),
    }
    validate_bot_runtime_metrics(payload)
    return payload


def _require_mapping(payload: Any) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("Runtime metrics payload must be a mapping/dictionary.")
    return payload


def _validate_required_fields(payload: Mapping[str, Any]) -> None:
    missing = [field for field in REQUIRED_FIELDS if field not in payload]
    if missing:
        raise ValueError(f"Missing required runtime metrics fields: {', '.join(missing)}")


def _validate_exact_metadata(payload: Mapping[str, Any]) -> None:
    expected = {
        "module_name": MODULE_NAME,
        "bot_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_by": GENERATED_BY,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
    }
    for key, expected_value in expected.items():
        if payload.get(key) != expected_value:
            raise ValueError(f"Invalid {key}: expected {expected_value!r}, got {payload.get(key)!r}")


def _validate_string_field(payload: Mapping[str, Any], field: str) -> None:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string.")


def _validate_optional_datetime_field(payload: Mapping[str, Any], field: str) -> None:
    value = payload.get(field)
    if value is not None and not isinstance(value, str):
        raise ValueError(f"{field} must be a string or None.")


def _validate_list_field(payload: Mapping[str, Any], field: str, allow_empty: bool = True) -> None:
    value = payload.get(field)
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list.")
    if not allow_empty and not value:
        raise ValueError(f"{field} must not be empty.")
    for entry in value:
        if not isinstance(entry, str) or not entry.strip():
            raise ValueError(f"{field} entries must be non-empty strings.")


def _validate_count_field(payload: Mapping[str, Any], field: str) -> None:
    value = payload.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer.")


def _validate_runtime_status_consistency(payload: Mapping[str, Any]) -> None:
    status = payload.get("runtime_status")
    if status not in RUNTIME_STATUS_VALUES:
        raise ValueError(f"runtime_status must be one of: {', '.join(sorted(RUNTIME_STATUS_VALUES))}")

    error_count = payload.get("error_count")
    warning_count = payload.get("warning_count")
    missing_source_files = payload.get("missing_source_files")
    available_source_files = payload.get("available_source_files")

    if error_count and status != "ERROR":
        raise ValueError("runtime_status must be ERROR when error_count is greater than zero.")
    if not error_count and (warning_count or missing_source_files) and status not in {"WARNING", "ERROR"}:
        raise ValueError("runtime_status must be WARNING when warnings or missing source files exist and no errors exist.")
    if not error_count and not warning_count and not missing_source_files and available_source_files and status != "OK":
        raise ValueError("runtime_status must be OK when source files are available and no warnings/errors exist.")
    if not error_count and not warning_count and not missing_source_files and not available_source_files and status != "UNKNOWN":
        raise ValueError("runtime_status must be UNKNOWN when no source files are available and no warnings/errors exist.")


def validate_bot_runtime_metrics(payload: Any) -> bool:
    """Validate a runtime metrics payload and enforce paper-only safety."""
    data = _require_mapping(payload)
    _validate_required_fields(data)
    _validate_exact_metadata(data)

    for field in ["bot_name", "bot_type", "generated_at_utc"]:
        _validate_string_field(data, field)

    for field in ["latest_run_at_utc", "latest_success_at_utc", "latest_failure_at_utc"]:
        _validate_optional_datetime_field(data, field)

    for field in LIST_FIELDS:
        _validate_list_field(data, field, allow_empty=(field != "metrics_source_files" and field != "safety_guarantees"))

    for field in COUNT_FIELDS:
        _validate_count_field(data, field)

    _validate_runtime_status_consistency(data)
    return True


def write_bot_runtime_metrics(
    path: str | Path = "bot_runtime_metrics.json",
    root_path: str | Path = ".",
) -> Dict[str, Any]:
    """Build, validate, and write runtime metrics JSON."""
    payload = build_bot_runtime_metrics(root_path=root_path)
    output_path = Path(path)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_bot_runtime_metrics(path: str | Path = "bot_runtime_metrics.json") -> Dict[str, Any]:
    """Read and validate runtime metrics JSON."""
    input_path = Path(path)
    with input_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    validate_bot_runtime_metrics(payload)
    return payload


def _format_list(items: List[str]) -> str:
    if not items:
        return "- None"
    return "\n".join(f"- {item}" for item in items)


def format_bot_runtime_metrics_summary(payload: Mapping[str, Any]) -> str:
    """Return a Markdown summary for a validated runtime metrics payload."""
    validate_bot_runtime_metrics(payload)
    lines = [
        "# Dividend Bot Runtime Metrics",
        "",
        f"Bot Name: {payload['bot_name']}",
        f"Bot Type: {payload['bot_type']}",
        f"Module Version: {payload['bot_version']}",
        f"Schema Version: {payload['schema_version']}",
        f"Generated At UTC: {payload['generated_at_utc']}",
        f"Runtime Status: {payload['runtime_status']}",
        "",
        "## Paper-Only Safety",
        f"- paper_trade_mode: {payload['paper_trade_mode']}",
        f"- live_trading_enabled: {payload['live_trading_enabled']}",
        f"- broker_execution_enabled: {payload['broker_execution_enabled']}",
        "",
        "## Runtime Counts",
        f"- Run Count: {payload['run_count']}",
        f"- Successful Run Count: {payload['successful_run_count']}",
        f"- Failed Run Count: {payload['failed_run_count']}",
        f"- Warning Count: {payload['warning_count']}",
        f"- Error Count: {payload['error_count']}",
        f"- Email Delivery Count: {payload['email_delivery_count']}",
        "",
        "## Output Counts",
        f"- Report File Count: {payload['report_file_count']}",
        f"- CSV Output Count: {payload['csv_output_count']}",
        f"- JSON Output Count: {payload['json_output_count']}",
        f"- Markdown Output Count: {payload['markdown_output_count']}",
        "",
        "## Latest Runtime Timestamps",
        f"- Latest Run At UTC: {payload['latest_run_at_utc'] or 'None'}",
        f"- Latest Success At UTC: {payload['latest_success_at_utc'] or 'None'}",
        f"- Latest Failure At UTC: {payload['latest_failure_at_utc'] or 'None'}",
        "",
        "## Metrics Source Files",
        _format_list(list(payload["metrics_source_files"])),
        "",
        "## Available Source Files",
        _format_list(list(payload["available_source_files"])),
        "",
        "## Missing Source Files",
        _format_list(list(payload["missing_source_files"])),
        "",
        "## Warnings",
        _format_list(list(payload["warnings"])),
        "",
        "## Errors",
        _format_list(list(payload["errors"])),
        "",
        "## Safety Guarantees",
        _format_list(list(payload["safety_guarantees"])),
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    profile = write_bot_runtime_metrics()
    print(format_bot_runtime_metrics_summary(profile))
