"""
Read-only diagnostics profile for the deployed Dividend Bot.

This module combines platform-facing operational JSON outputs into one
diagnostic report. It does not import or call trading modules, broker APIs,
Robinhood APIs, subprocess APIs, or operating-system command execution.

PAPER ONLY:
- paper_trade_mode is always True
- live_trading_enabled is always False
- broker_execution_enabled is always False
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping


MODULE_NAME = "bot_diagnostics"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"

BOT_NAME = "Agentic Robin Dividend Bot"
BOT_TYPE = "paper_dividend_etf_management"
BOT_VERSION = MODULE_VERSION

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False

STATUS_OK = "OK"
STATUS_WARNING = "WARNING"
STATUS_ERROR = "ERROR"
STATUS_UNKNOWN = "UNKNOWN"
VALID_STATUSES = {STATUS_OK, STATUS_WARNING, STATUS_ERROR, STATUS_UNKNOWN}

INPUT_FILES = [
    "bot_capabilities.json",
    "bot_environment_check.json",
    "bot_report_integrity.json",
    "bot_runtime_metrics.json",
]

LIST_FIELDS = [
    "input_files",
    "available_input_files",
    "missing_input_files",
    "diagnostic_findings",
    "warnings",
    "errors",
    "safety_guarantees",
]

COUNT_FIELDS = [
    "warning_count",
    "error_count",
]

REQUIRED_FIELDS = [
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
    "module_name",
    "module_version",
    "generated_by",
]

SAFETY_GUARANTEES = [
    "paper_trade_mode is enforced as True",
    "live_trading_enabled is enforced as False",
    "broker_execution_enabled is enforced as False",
    "no broker execution is performed",
    "no Robinhood execution is performed",
    "no real order placement is performed",
    "no trading logic is changed",
    "runtime workflow files are not modified",
    "only local JSON diagnostic inputs are read",
]


def _utc_now_iso() -> str:
    """Return a stable UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json_file(path: Path) -> Any:
    """Read a JSON file safely and return the decoded payload."""
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _get_status_from_payload(payload: Any, status_key: str) -> str:
    """Extract and normalize a status value from a decoded payload."""
    if not isinstance(payload, Mapping):
        return STATUS_UNKNOWN
    value = payload.get(status_key, STATUS_UNKNOWN)
    if isinstance(value, str) and value in VALID_STATUSES:
        return value
    return STATUS_UNKNOWN


def _collect_messages(payload: Any, key: str) -> List[str]:
    """Collect non-empty string messages from a payload list field."""
    if not isinstance(payload, Mapping):
        return []
    value = payload.get(key, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _overall_status(statuses: Iterable[str], missing_inputs: List[str], errors: List[str], warnings: List[str]) -> str:
    """Calculate the overall diagnostic status from component statuses and findings."""
    normalized = list(statuses)
    if errors or STATUS_ERROR in normalized:
        return STATUS_ERROR
    if warnings or missing_inputs or STATUS_WARNING in normalized:
        return STATUS_WARNING
    if not normalized or STATUS_UNKNOWN in normalized:
        return STATUS_UNKNOWN
    return STATUS_OK


def build_bot_diagnostics(root_path: str = ".") -> Dict[str, Any]:
    """Build a read-only diagnostics report from available platform JSON outputs."""
    root = Path(root_path)
    available_input_files: List[str] = []
    missing_input_files: List[str] = []
    warnings: List[str] = []
    errors: List[str] = []
    diagnostic_findings: List[str] = []

    decoded_inputs: Dict[str, Any] = {}

    for filename in INPUT_FILES:
        file_path = root / filename
        if not file_path.exists():
            missing_input_files.append(filename)
            warnings.append(f"Missing diagnostic input file: {filename}")
            continue

        available_input_files.append(filename)
        try:
            decoded_inputs[filename] = _read_json_file(file_path)
            diagnostic_findings.append(f"Loaded diagnostic input file: {filename}")
        except (OSError, json.JSONDecodeError) as exc:
            decoded_inputs[filename] = None
            errors.append(f"Unable to read diagnostic input file {filename}: {exc}")

    capabilities_status = STATUS_OK if "bot_capabilities.json" in available_input_files and decoded_inputs.get("bot_capabilities.json") is not None else STATUS_UNKNOWN
    environment_status = _get_status_from_payload(decoded_inputs.get("bot_environment_check.json"), "environment_status")
    report_integrity_status = _get_status_from_payload(decoded_inputs.get("bot_report_integrity.json"), "integrity_status")
    runtime_metrics_status = _get_status_from_payload(decoded_inputs.get("bot_runtime_metrics.json"), "runtime_status")

    for filename, payload in decoded_inputs.items():
        if payload is None:
            continue
        warnings.extend(f"{filename}: {message}" for message in _collect_messages(payload, "warnings"))
        errors.extend(f"{filename}: {message}" for message in _collect_messages(payload, "errors"))

    component_statuses = [
        capabilities_status,
        environment_status,
        report_integrity_status,
        runtime_metrics_status,
    ]
    overall_diagnostic_status = _overall_status(component_statuses, missing_input_files, errors, warnings)

    if not diagnostic_findings:
        diagnostic_findings.append("No diagnostic input files were loaded.")
    if missing_input_files:
        diagnostic_findings.append("One or more diagnostic input files are missing.")
    if errors:
        diagnostic_findings.append("One or more diagnostic errors were detected.")
    elif warnings:
        diagnostic_findings.append("One or more diagnostic warnings were detected.")
    elif overall_diagnostic_status == STATUS_OK:
        diagnostic_findings.append("All available diagnostic inputs report OK status.")

    payload: Dict[str, Any] = {
        "bot_name": BOT_NAME,
        "bot_type": BOT_TYPE,
        "bot_version": BOT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _utc_now_iso(),
        "paper_trade_mode": PAPER_TRADE_MODE,
        "live_trading_enabled": LIVE_TRADING_ENABLED,
        "broker_execution_enabled": BROKER_EXECUTION_ENABLED,
        "input_files": list(INPUT_FILES),
        "available_input_files": available_input_files,
        "missing_input_files": missing_input_files,
        "capabilities_status": capabilities_status,
        "environment_status": environment_status,
        "report_integrity_status": report_integrity_status,
        "runtime_metrics_status": runtime_metrics_status,
        "overall_diagnostic_status": overall_diagnostic_status,
        "diagnostic_findings": diagnostic_findings,
        "warning_count": len(warnings),
        "error_count": len(errors),
        "warnings": warnings,
        "errors": errors,
        "safety_guarantees": list(SAFETY_GUARANTEES),
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "generated_by": GENERATED_BY,
    }

    validate_bot_diagnostics(payload)
    return payload


def _require_mapping(payload: Any) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping/dictionary")
    return payload


def _validate_required_fields(payload: Mapping[str, Any]) -> None:
    missing = [field for field in REQUIRED_FIELDS if field not in payload]
    if missing:
        raise ValueError(f"missing required field(s): {', '.join(missing)}")


def _validate_exact_metadata(payload: Mapping[str, Any]) -> None:
    expected = {
        "bot_name": BOT_NAME,
        "bot_type": BOT_TYPE,
        "bot_version": BOT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "generated_by": GENERATED_BY,
    }
    for key, expected_value in expected.items():
        if payload.get(key) != expected_value:
            raise ValueError(f"{key} must be {expected_value!r}")


def _validate_non_empty_string(value: Any, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _validate_list_field(payload: Mapping[str, Any], field_name: str) -> None:
    value = payload.get(field_name)
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name}[{index}] must be a non-empty string")


def _validate_counts(payload: Mapping[str, Any]) -> None:
    for field_name in COUNT_FIELDS:
        value = payload.get(field_name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"{field_name} must be a non-negative integer")
    if payload.get("warning_count") != len(payload.get("warnings", [])):
        raise ValueError("warning_count must match warnings length")
    if payload.get("error_count") != len(payload.get("errors", [])):
        raise ValueError("error_count must match errors length")


def _validate_status(payload: Mapping[str, Any], field_name: str) -> None:
    value = payload.get(field_name)
    if value not in VALID_STATUSES:
        raise ValueError(f"{field_name} must be one of: {', '.join(sorted(VALID_STATUSES))}")


def validate_bot_diagnostics(payload: Any) -> bool:
    """Validate a diagnostics payload and raise ValueError on failure."""
    payload = _require_mapping(payload)
    _validate_required_fields(payload)
    _validate_exact_metadata(payload)
    _validate_non_empty_string(payload.get("generated_at_utc"), "generated_at_utc")

    for field_name in LIST_FIELDS:
        _validate_list_field(payload, field_name)

    for field_name in [
        "capabilities_status",
        "environment_status",
        "report_integrity_status",
        "runtime_metrics_status",
        "overall_diagnostic_status",
    ]:
        _validate_status(payload, field_name)

    _validate_counts(payload)

    if payload["overall_diagnostic_status"] == STATUS_OK and (payload["warnings"] or payload["errors"]):
        raise ValueError("overall_diagnostic_status cannot be OK when warnings or errors exist")
    if payload["errors"] and payload["overall_diagnostic_status"] != STATUS_ERROR:
        raise ValueError("overall_diagnostic_status must be ERROR when errors exist")
    if payload["warnings"] and not payload["errors"] and payload["overall_diagnostic_status"] not in {STATUS_WARNING, STATUS_ERROR}:
        raise ValueError("overall_diagnostic_status must reflect warnings")

    return True


def write_bot_diagnostics(path: str = "bot_diagnostics.json", root_path: str = ".") -> Dict[str, Any]:
    """Build, validate, and write the diagnostics payload to JSON."""
    payload = build_bot_diagnostics(root_path=root_path)
    validate_bot_diagnostics(payload)

    output_path = Path(path)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_bot_diagnostics(path: str = "bot_diagnostics.json") -> Dict[str, Any]:
    """Read and validate a diagnostics JSON file."""
    input_path = Path(path)
    with input_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    validate_bot_diagnostics(payload)
    return payload


def _format_list(title: str, values: List[str]) -> List[str]:
    lines = [f"## {title}"]
    if values:
        lines.extend(f"- {value}" for value in values)
    else:
        lines.append("- None")
    return lines


def format_bot_diagnostics_summary(payload: Mapping[str, Any]) -> str:
    """Format a validated diagnostics payload as a Markdown summary."""
    validate_bot_diagnostics(payload)

    lines = [
        f"# {payload['bot_name']} Diagnostics",
        "",
        f"- Bot Type: {payload['bot_type']}",
        f"- Bot Version: {payload['bot_version']}",
        f"- Schema Version: {payload['schema_version']}",
        f"- Generated At UTC: {payload['generated_at_utc']}",
        f"- Paper Trade Mode: {payload['paper_trade_mode']}",
        f"- Live Trading Enabled: {payload['live_trading_enabled']}",
        f"- Broker Execution Enabled: {payload['broker_execution_enabled']}",
        "",
        "## Status",
        f"- Capabilities Status: {payload['capabilities_status']}",
        f"- Environment Status: {payload['environment_status']}",
        f"- Report Integrity Status: {payload['report_integrity_status']}",
        f"- Runtime Metrics Status: {payload['runtime_metrics_status']}",
        f"- Overall Diagnostic Status: {payload['overall_diagnostic_status']}",
        f"- Warning Count: {payload['warning_count']}",
        f"- Error Count: {payload['error_count']}",
        "",
    ]

    sections = [
        ("Input Files", payload["input_files"]),
        ("Available Input Files", payload["available_input_files"]),
        ("Missing Input Files", payload["missing_input_files"]),
        ("Diagnostic Findings", payload["diagnostic_findings"]),
        ("Warnings", payload["warnings"]),
        ("Errors", payload["errors"]),
        ("Safety Guarantees", payload["safety_guarantees"]),
    ]

    for title, values in sections:
        lines.extend(_format_list(title, values))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


if __name__ == "__main__":
    write_bot_diagnostics()
