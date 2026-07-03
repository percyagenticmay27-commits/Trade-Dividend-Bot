"""
Read-only operational health scoring for the deployed Dividend Bot.

This module combines platform-facing operational JSON outputs into a single
health score from 0 to 100. It does not import or call trading modules, broker
APIs, Robinhood APIs, subprocess APIs, or operating-system command execution.

PAPER ONLY:
- paper_trade_mode is always True
- live_trading_enabled is always False
- broker_execution_enabled is always False
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping


MODULE_NAME = "bot_health_score"
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
VALID_INPUT_STATUSES = {STATUS_OK, STATUS_WARNING, STATUS_ERROR, STATUS_UNKNOWN}

HEALTH_EXCELLENT = "EXCELLENT"
HEALTH_GOOD = "GOOD"
HEALTH_FAIR = "FAIR"
HEALTH_DEGRADED = "DEGRADED"
HEALTH_CRITICAL = "CRITICAL"
VALID_HEALTH_STATUSES = {
    HEALTH_EXCELLENT,
    HEALTH_GOOD,
    HEALTH_FAIR,
    HEALTH_DEGRADED,
    HEALTH_CRITICAL,
}

INPUT_FILES = [
    "bot_capabilities.json",
    "bot_environment_check.json",
    "bot_report_integrity.json",
    "bot_runtime_metrics.json",
    "bot_diagnostics.json",
]

LIST_FIELDS = [
    "input_files",
    "available_input_files",
    "missing_input_files",
    "scoring_breakdown",
    "recommendations",
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
    "only local JSON health inputs are read",
]


def _utc_now_iso() -> str:
    """Return a stable UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json_file(path: Path) -> Any:
    """Read and decode a JSON file."""
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _safe_status(payload: Any, field_name: str) -> str:
    """Extract a known status from a decoded JSON payload."""
    if not isinstance(payload, Mapping):
        return STATUS_UNKNOWN
    value = payload.get(field_name, STATUS_UNKNOWN)
    if isinstance(value, str) and value in VALID_INPUT_STATUSES:
        return value
    return STATUS_UNKNOWN


def _collect_messages(payload: Any, field_name: str) -> List[str]:
    """Collect non-empty strings from a decoded payload list field."""
    if not isinstance(payload, Mapping):
        return []
    values = payload.get(field_name, [])
    if not isinstance(values, list):
        return []
    return [value for value in values if isinstance(value, str) and value.strip()]


def _grade_for_score(score: int) -> str:
    """Return the required letter grade for a score from 0 to 100."""
    if score >= 95:
        return "A"
    if score >= 90:
        return "A-"
    if score >= 85:
        return "B+"
    if score >= 80:
        return "B"
    if score >= 75:
        return "C+"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def _health_status_for_score(score: int) -> str:
    """Return the operational health status for a score from 0 to 100."""
    if score >= 95:
        return HEALTH_EXCELLENT
    if score >= 80:
        return HEALTH_GOOD
    if score >= 70:
        return HEALTH_FAIR
    if score >= 60:
        return HEALTH_DEGRADED
    return HEALTH_CRITICAL


def _penalty_for_status(component: str, status: str) -> int:
    """Return score penalty for a component status."""
    if component == "environment":
        return 25 if status == STATUS_ERROR else 10 if status == STATUS_WARNING else 0
    if component == "report_integrity":
        return 25 if status == STATUS_ERROR else 10 if status == STATUS_WARNING else 0
    if component == "runtime_metrics":
        return 20 if status == STATUS_ERROR else 8 if status == STATUS_WARNING else 0
    if component == "diagnostics":
        return 30 if status == STATUS_ERROR else 12 if status == STATUS_WARNING else 0
    return 0


def _append_status_recommendation(recommendations: List[str], label: str, status: str) -> None:
    """Add a practical recommendation for WARNING or ERROR statuses."""
    if status == STATUS_ERROR:
        recommendations.append(f"Resolve ERROR status reported by {label}.")
    elif status == STATUS_WARNING:
        recommendations.append(f"Review WARNING status reported by {label}.")


def build_bot_health_score(root_path: str = ".") -> Dict[str, Any]:
    """Build a read-only operational health score payload."""
    root = Path(root_path)
    available_input_files: List[str] = []
    missing_input_files: List[str] = []
    warnings: List[str] = []
    errors: List[str] = []
    recommendations: List[str] = []
    decoded_inputs: Dict[str, Any] = {}

    for filename in INPUT_FILES:
        file_path = root / filename
        if not file_path.exists():
            missing_input_files.append(filename)
            warnings.append(f"Missing health score input file: {filename}")
            continue

        available_input_files.append(filename)
        try:
            decoded_inputs[filename] = _read_json_file(file_path)
        except (OSError, json.JSONDecodeError) as exc:
            decoded_inputs[filename] = None
            errors.append(f"Unable to read health score input file {filename}: {exc}")

    environment_status = _safe_status(decoded_inputs.get("bot_environment_check.json"), "environment_status")
    report_integrity_status = _safe_status(decoded_inputs.get("bot_report_integrity.json"), "integrity_status")
    runtime_metrics_status = _safe_status(decoded_inputs.get("bot_runtime_metrics.json"), "runtime_status")
    diagnostics_status = _safe_status(decoded_inputs.get("bot_diagnostics.json"), "overall_diagnostic_status")

    for filename, payload in decoded_inputs.items():
        if payload is None:
            continue
        warnings.extend(f"{filename}: {message}" for message in _collect_messages(payload, "warnings"))
        errors.extend(f"{filename}: {message}" for message in _collect_messages(payload, "errors"))

    score = 100
    scoring_breakdown: List[str] = ["Base score: 100"]

    component_statuses = [
        ("environment", "Environment", environment_status),
        ("report_integrity", "Report Integrity", report_integrity_status),
        ("runtime_metrics", "Runtime Metrics", runtime_metrics_status),
        ("diagnostics", "Diagnostics", diagnostics_status),
    ]

    for component_key, component_label, status in component_statuses:
        penalty = _penalty_for_status(component_key, status)
        if penalty:
            score -= penalty
            scoring_breakdown.append(f"{component_label} {status}: -{penalty}")
        else:
            scoring_breakdown.append(f"{component_label} {status}: -0")
        _append_status_recommendation(recommendations, component_label, status)

    missing_penalty = len(missing_input_files) * 2
    if missing_penalty:
        score -= missing_penalty
        scoring_breakdown.append(f"Missing input files ({len(missing_input_files)}): -{missing_penalty}")
        recommendations.append("Generate missing platform JSON outputs before relying on the health score.")
    else:
        scoring_breakdown.append("Missing input files (0): -0")

    score = max(0, min(100, int(score)))

    if errors:
        recommendations.append("Review and resolve health score input errors.")
    if warnings:
        recommendations.append("Review health score warnings and confirm platform outputs are current.")
    if not recommendations:
        recommendations.append("No immediate action required. Continue normal paper-only monitoring.")

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
        "environment_status": environment_status,
        "report_integrity_status": report_integrity_status,
        "runtime_metrics_status": runtime_metrics_status,
        "diagnostics_status": diagnostics_status,
        "health_score": score,
        "health_grade": _grade_for_score(score),
        "health_status": _health_status_for_score(score),
        "scoring_breakdown": scoring_breakdown,
        "recommendations": recommendations,
        "warnings": warnings,
        "errors": errors,
        "safety_guarantees": list(SAFETY_GUARANTEES),
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "generated_by": GENERATED_BY,
    }

    validate_bot_health_score(payload)
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


def _validate_status(payload: Mapping[str, Any], field_name: str) -> None:
    value = payload.get(field_name)
    if value not in VALID_INPUT_STATUSES:
        raise ValueError(f"{field_name} must be one of: {', '.join(sorted(VALID_INPUT_STATUSES))}")


def validate_bot_health_score(payload: Any) -> bool:
    """Validate a health score payload and raise ValueError on failure."""
    payload = _require_mapping(payload)
    _validate_required_fields(payload)
    _validate_exact_metadata(payload)
    _validate_non_empty_string(payload.get("generated_at_utc"), "generated_at_utc")

    for field_name in LIST_FIELDS:
        _validate_list_field(payload, field_name)

    for field_name in [
        "environment_status",
        "report_integrity_status",
        "runtime_metrics_status",
        "diagnostics_status",
    ]:
        _validate_status(payload, field_name)

    score = payload.get("health_score")
    if not isinstance(score, int) or isinstance(score, bool) or score < 0 or score > 100:
        raise ValueError("health_score must be an integer between 0 and 100")

    expected_grade = _grade_for_score(score)
    if payload.get("health_grade") != expected_grade:
        raise ValueError(f"health_grade must match health_score: {expected_grade}")

    expected_status = _health_status_for_score(score)
    if payload.get("health_status") != expected_status:
        raise ValueError(f"health_status must match health_score: {expected_status}")

    return True


def write_bot_health_score(path: str = "bot_health_score.json", root_path: str = ".") -> Dict[str, Any]:
    """Build, validate, and write the health score payload to JSON."""
    payload = build_bot_health_score(root_path=root_path)
    validate_bot_health_score(payload)

    output_path = Path(path)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_bot_health_score(path: str = "bot_health_score.json") -> Dict[str, Any]:
    """Read and validate a health score JSON file."""
    input_path = Path(path)
    with input_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    validate_bot_health_score(payload)
    return payload


def _format_list(title: str, values: List[str]) -> List[str]:
    lines = [f"## {title}"]
    if values:
        lines.extend(f"- {value}" for value in values)
    else:
        lines.append("- None")
    return lines


def format_bot_health_score_summary(payload: Mapping[str, Any]) -> str:
    """Format a validated health score payload as a Markdown summary."""
    validate_bot_health_score(payload)

    lines = [
        f"# {payload['bot_name']} Health Score",
        "",
        f"- Bot Type: {payload['bot_type']}",
        f"- Bot Version: {payload['bot_version']}",
        f"- Schema Version: {payload['schema_version']}",
        f"- Generated At UTC: {payload['generated_at_utc']}",
        f"- Paper Trade Mode: {payload['paper_trade_mode']}",
        f"- Live Trading Enabled: {payload['live_trading_enabled']}",
        f"- Broker Execution Enabled: {payload['broker_execution_enabled']}",
        "",
        "## Health",
        f"- Health Score: {payload['health_score']}",
        f"- Health Grade: {payload['health_grade']}",
        f"- Health Status: {payload['health_status']}",
        "",
        "## Component Statuses",
        f"- Environment Status: {payload['environment_status']}",
        f"- Report Integrity Status: {payload['report_integrity_status']}",
        f"- Runtime Metrics Status: {payload['runtime_metrics_status']}",
        f"- Diagnostics Status: {payload['diagnostics_status']}",
        "",
    ]

    sections = [
        ("Input Files", payload["input_files"]),
        ("Available Input Files", payload["available_input_files"]),
        ("Missing Input Files", payload["missing_input_files"]),
        ("Scoring Breakdown", payload["scoring_breakdown"]),
        ("Recommendations", payload["recommendations"]),
        ("Warnings", payload["warnings"]),
        ("Errors", payload["errors"]),
        ("Safety Guarantees", payload["safety_guarantees"]),
    ]

    for title, values in sections:
        lines.extend(_format_list(title, values))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


if __name__ == "__main__":
    write_bot_health_score()
