"""Read-only report integrity verification for the deployed Dividend Bot.

This module inspects expected report/output files and emits a platform-facing
integrity payload. It does not import trading engines, does not execute bot
workflows, does not connect to brokers, and does not place orders.
"""

from __future__ import annotations

import json
import platform as platform_module
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

MODULE_NAME = "bot_report_integrity"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"

BOT_NAME = "Agentic Robin Dividend Bot"
BOT_TYPE = "paper_dividend_etf_management_bot"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False

STATUS_OK = "OK"
STATUS_WARNING = "WARNING"
STATUS_ERROR = "ERROR"
VALID_INTEGRITY_STATUSES = {STATUS_OK, STATUS_WARNING, STATUS_ERROR}

REQUIRED_REPORTS = [
    "daily_paper_report.md",
    "daily_change_summary.md",
    "portfolio_snapshot.csv",
    "paper_trade_log.csv",
    "paper_state.json",
]

OPTIONAL_REPORTS = [
    "strategy_health_report.md",
    "live_readiness_report.md",
    "weekly_portfolio_review.md",
    "performance_summary.md",
    "walk_forward_summary.md",
    "performance_report.csv",
    "strategy_health.csv",
    "pair_health.csv",
    "live_readiness.csv",
    "email_delivery_log.csv",
    "snapshot_manifest.json",
    "bot_capabilities.json",
    "bot_environment_check.json",
]

REQUIRED_FIELDS = [
    "module_name",
    "generated_by",
    "bot_name",
    "bot_type",
    "bot_version",
    "schema_version",
    "generated_at_utc",
    "paper_trade_mode",
    "live_trading_enabled",
    "broker_execution_enabled",
    "required_reports",
    "missing_required_reports",
    "unreadable_required_reports",
    "optional_reports",
    "missing_optional_reports",
    "report_file_details",
    "integrity_status",
    "warnings",
    "errors",
    "safety_guarantees",
]

LIST_FIELDS = [
    "required_reports",
    "missing_required_reports",
    "unreadable_required_reports",
    "optional_reports",
    "missing_optional_reports",
    "warnings",
    "errors",
    "safety_guarantees",
]

NON_EMPTY_LIST_FIELDS = [
    "required_reports",
    "optional_reports",
    "safety_guarantees",
]

SAFETY_GUARANTEES = [
    "PAPER ONLY mode is enforced in this platform-facing integrity module.",
    "live_trading_enabled is always False.",
    "broker_execution_enabled is always False.",
    "No broker execution is performed.",
    "No Robinhood execution is performed.",
    "No real order placement is performed.",
    "No trading logic is changed or imported.",
    "No runtime workflow files are modified.",
    "No shell command execution is used.",
]


def _utc_now_iso() -> str:
    """Return current UTC time in stable ISO-8601 format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_root_path(root_path: str | Path) -> Path:
    """Return a resolved root path without requiring it to already exist."""
    return Path(root_path).expanduser().resolve()


def _is_readable_file(path: Path) -> bool:
    """Return True when path is an existing readable regular file."""
    if not path.is_file():
        return False
    try:
        with path.open("rb") as handle:
            handle.read(1)
        return True
    except OSError:
        return False


def _file_detail(root: Path, relative_name: str, required: bool) -> Dict[str, Any]:
    """Build read-only metadata for one report file."""
    path = root / relative_name
    exists = path.is_file()
    readable = _is_readable_file(path) if exists else False
    size_bytes = None
    modified_at_utc = None

    if exists:
        try:
            stat_result = path.stat()
            size_bytes = stat_result.st_size
            modified_at_utc = (
                datetime.fromtimestamp(stat_result.st_mtime, timezone.utc)
                .replace(microsecond=0)
                .isoformat()
                .replace("+00:00", "Z")
            )
        except OSError:
            readable = False

    return {
        "path": relative_name,
        "required": required,
        "exists": exists,
        "readable": readable,
        "size_bytes": size_bytes,
        "modified_at_utc": modified_at_utc,
    }


def build_bot_report_integrity(root_path: str | Path = ".") -> Dict[str, Any]:
    """Build a read-only report integrity payload for the Dividend Bot."""
    root = _as_root_path(root_path)

    required_details = [_file_detail(root, name, True) for name in REQUIRED_REPORTS]
    optional_details = [_file_detail(root, name, False) for name in OPTIONAL_REPORTS]
    all_details = required_details + optional_details

    missing_required_reports = [item["path"] for item in required_details if not item["exists"]]
    unreadable_required_reports = [
        item["path"] for item in required_details if item["exists"] and not item["readable"]
    ]
    missing_optional_reports = [item["path"] for item in optional_details if not item["exists"]]

    warnings: List[str] = []
    errors: List[str] = []

    if missing_optional_reports:
        warnings.append(
            "Missing optional reports detected: " + ", ".join(missing_optional_reports)
        )
    if missing_required_reports:
        errors.append(
            "Missing required reports detected: " + ", ".join(missing_required_reports)
        )
    if unreadable_required_reports:
        errors.append(
            "Unreadable required reports detected: " + ", ".join(unreadable_required_reports)
        )

    if errors:
        integrity_status = STATUS_ERROR
    elif warnings:
        integrity_status = STATUS_WARNING
    else:
        integrity_status = STATUS_OK

    payload: Dict[str, Any] = {
        "module_name": MODULE_NAME,
        "generated_by": GENERATED_BY,
        "bot_name": BOT_NAME,
        "bot_type": BOT_TYPE,
        "bot_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _utc_now_iso(),
        "paper_trade_mode": PAPER_TRADE_MODE,
        "live_trading_enabled": LIVE_TRADING_ENABLED,
        "broker_execution_enabled": BROKER_EXECUTION_ENABLED,
        "python_version": sys.version.split()[0],
        "platform": platform_module.platform(),
        "working_directory": str(root),
        "required_reports": list(REQUIRED_REPORTS),
        "missing_required_reports": missing_required_reports,
        "unreadable_required_reports": unreadable_required_reports,
        "optional_reports": list(OPTIONAL_REPORTS),
        "missing_optional_reports": missing_optional_reports,
        "report_file_details": all_details,
        "integrity_status": integrity_status,
        "warnings": warnings,
        "errors": errors,
        "safety_guarantees": list(SAFETY_GUARANTEES),
    }
    validate_bot_report_integrity(payload)
    return payload


def _validate_required_fields(payload: Mapping[str, Any]) -> None:
    missing = [field for field in REQUIRED_FIELDS if field not in payload]
    if missing:
        raise ValueError("Missing required field(s): " + ", ".join(missing))


def _validate_exact_metadata(payload: Mapping[str, Any]) -> None:
    expected_values = {
        "module_name": MODULE_NAME,
        "generated_by": GENERATED_BY,
        "bot_name": BOT_NAME,
        "bot_type": BOT_TYPE,
        "bot_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
    }
    for key, expected in expected_values.items():
        actual = payload.get(key)
        if actual != expected:
            raise ValueError(f"Invalid {key}: expected {expected!r}, got {actual!r}")


def _validate_string_field(payload: Mapping[str, Any], field_name: str) -> None:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _validate_string_list(payload: Mapping[str, Any], field_name: str, *, allow_empty: bool) -> None:
    value = payload.get(field_name)
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    if not allow_empty and not value:
        raise ValueError(f"{field_name} must not be empty")
    for entry in value:
        if not isinstance(entry, str) or not entry.strip():
            raise ValueError(f"{field_name} entries must be non-empty strings")


def _validate_report_details(details: Any) -> None:
    if not isinstance(details, list):
        raise ValueError("report_file_details must be a list")
    required_detail_fields = {
        "path",
        "required",
        "exists",
        "readable",
        "size_bytes",
        "modified_at_utc",
    }
    for index, item in enumerate(details):
        if not isinstance(item, dict):
            raise ValueError(f"report_file_details[{index}] must be a dictionary")
        missing = required_detail_fields.difference(item)
        if missing:
            raise ValueError(
                f"report_file_details[{index}] missing field(s): " + ", ".join(sorted(missing))
            )
        if not isinstance(item["path"], str) or not item["path"].strip():
            raise ValueError(f"report_file_details[{index}].path must be a non-empty string")
        for boolean_field in ("required", "exists", "readable"):
            if not isinstance(item[boolean_field], bool):
                raise ValueError(
                    f"report_file_details[{index}].{boolean_field} must be a boolean"
                )
        if item["size_bytes"] is not None:
            if not isinstance(item["size_bytes"], int) or item["size_bytes"] < 0:
                raise ValueError(
                    f"report_file_details[{index}].size_bytes must be null or a non-negative integer"
                )
        if item["modified_at_utc"] is not None:
            if not isinstance(item["modified_at_utc"], str) or not item["modified_at_utc"].strip():
                raise ValueError(
                    f"report_file_details[{index}].modified_at_utc must be null or a non-empty string"
                )


def _validate_status_consistency(payload: Mapping[str, Any]) -> None:
    missing_required = payload.get("missing_required_reports")
    unreadable_required = payload.get("unreadable_required_reports")
    missing_optional = payload.get("missing_optional_reports")
    status = payload.get("integrity_status")

    has_required_errors = bool(missing_required) or bool(unreadable_required)
    has_optional_warnings = bool(missing_optional)

    if has_required_errors and status != STATUS_ERROR:
        raise ValueError("integrity_status must be ERROR when required reports are missing or unreadable")
    if not has_required_errors and has_optional_warnings and status != STATUS_WARNING:
        raise ValueError("integrity_status must be WARNING when only optional reports are missing")
    if not has_required_errors and not has_optional_warnings and status != STATUS_OK:
        raise ValueError("integrity_status must be OK when no report issues are present")

    errors = payload.get("errors")
    warnings = payload.get("warnings")
    if has_required_errors and not errors:
        raise ValueError("errors must describe missing or unreadable required reports")
    if has_optional_warnings and not warnings:
        raise ValueError("warnings must describe missing optional reports")


def validate_bot_report_integrity(payload: Mapping[str, Any]) -> bool:
    """Validate a report integrity payload.

    Raises ValueError for malformed or unsafe payloads. Returns True when valid.
    """
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")

    _validate_required_fields(payload)
    _validate_exact_metadata(payload)

    for field_name in (
        "module_name",
        "generated_by",
        "bot_name",
        "bot_type",
        "bot_version",
        "schema_version",
        "generated_at_utc",
    ):
        _validate_string_field(payload, field_name)

    for field_name in LIST_FIELDS:
        _validate_string_list(
            payload,
            field_name,
            allow_empty=field_name not in NON_EMPTY_LIST_FIELDS,
        )

    if payload.get("integrity_status") not in VALID_INTEGRITY_STATUSES:
        raise ValueError("integrity_status must be one of OK, WARNING, or ERROR")

    _validate_report_details(payload.get("report_file_details"))
    _validate_status_consistency(payload)

    return True


def write_bot_report_integrity(
    path: str | Path = "bot_report_integrity.json", root_path: str | Path = "."
) -> Dict[str, Any]:
    """Write the report integrity payload to JSON and return the payload."""
    payload = build_bot_report_integrity(root_path=root_path)
    output_path = Path(path)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_bot_report_integrity(path: str | Path = "bot_report_integrity.json") -> Dict[str, Any]:
    """Read and validate a report integrity JSON file."""
    input_path = Path(path)
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    validate_bot_report_integrity(payload)
    return payload


def _format_list(items: Iterable[str]) -> str:
    values = list(items)
    if not values:
        return "- None"
    return "\n".join(f"- {item}" for item in values)


def _format_report_details(details: List[Mapping[str, Any]]) -> str:
    if not details:
        return "- None"
    rows = []
    for item in details:
        rows.append(
            "- {path} | required={required} | exists={exists} | readable={readable} | size_bytes={size}".format(
                path=item.get("path"),
                required=item.get("required"),
                exists=item.get("exists"),
                readable=item.get("readable"),
                size=item.get("size_bytes"),
            )
        )
    return "\n".join(rows)


def format_bot_report_integrity_summary(payload: Mapping[str, Any]) -> str:
    """Return a Markdown summary for a validated report integrity payload."""
    validate_bot_report_integrity(payload)

    lines = [
        "# Bot Report Integrity Summary",
        "",
        f"Bot Name: {payload['bot_name']}",
        f"Bot Type: {payload['bot_type']}",
        f"Bot Version: {payload['bot_version']}",
        f"Schema Version: {payload['schema_version']}",
        f"Generated At UTC: {payload['generated_at_utc']}",
        f"Integrity Status: {payload['integrity_status']}",
        "",
        "## Safety Flags",
        f"- paper_trade_mode: {payload['paper_trade_mode']}",
        f"- live_trading_enabled: {payload['live_trading_enabled']}",
        f"- broker_execution_enabled: {payload['broker_execution_enabled']}",
        "",
        "## Required Reports",
        _format_list(payload["required_reports"]),
        "",
        "## Missing Required Reports",
        _format_list(payload["missing_required_reports"]),
        "",
        "## Unreadable Required Reports",
        _format_list(payload["unreadable_required_reports"]),
        "",
        "## Optional Reports",
        _format_list(payload["optional_reports"]),
        "",
        "## Missing Optional Reports",
        _format_list(payload["missing_optional_reports"]),
        "",
        "## Report File Details",
        _format_report_details(payload["report_file_details"]),
        "",
        "## Warnings",
        _format_list(payload["warnings"]),
        "",
        "## Errors",
        _format_list(payload["errors"]),
        "",
        "## Safety Guarantees",
        _format_list(payload["safety_guarantees"]),
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(format_bot_report_integrity_summary(write_bot_report_integrity()))
