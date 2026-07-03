"""
bot_environment_check.py

Read-only environment verification for the deployed Dividend Bot.

This module inspects expected project files and directories only. It does not
modify trading logic, does not connect to any broker, does not use subprocesses,
does not call os.system, and does not place orders. It is permanently
constrained to PAPER ONLY metadata reporting.
"""

from __future__ import annotations

import json
import platform as platform_module
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


MODULE_NAME = "bot_environment_check"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"


_REQUIRED_FILES = [
    "run_daily_paper_cycle.py",
    "send_daily_reports.py",
    "paper_trading_engine.py",
    "portfolio_engine.py",
    "dividend_engine.py",
    "daily_paper_report.md",
    "portfolio_snapshot.csv",
    "paper_trade_log.csv",
    "bot_capabilities.py",
    "bot_capabilities.json",
]

_OPTIONAL_FILES = [
    "run_dividend_bot.sh",
    "health_check_dividend_bot.sh",
    "backup_dividend_bot.sh",
    "rotate_dividend_logs.sh",
    "strategy_health_report.md",
    "live_readiness_report.md",
    "weekly_portfolio_review.md",
]

_REQUIRED_DIRECTORIES = [
    ".",
]

_REQUIRED_KEYS = {
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
    "python_version",
    "platform",
    "working_directory",
    "required_files",
    "missing_required_files",
    "optional_files",
    "missing_optional_files",
    "required_directories",
    "missing_required_directories",
    "environment_status",
    "warnings",
    "errors",
    "safety_guarantees",
}

_LIST_FIELDS = (
    "required_files",
    "missing_required_files",
    "optional_files",
    "missing_optional_files",
    "required_directories",
    "missing_required_directories",
    "warnings",
    "errors",
    "safety_guarantees",
)

_NON_EMPTY_LIST_FIELDS = (
    "required_files",
    "optional_files",
    "required_directories",
    "safety_guarantees",
)

_VALID_ENVIRONMENT_STATUSES = {"OK", "WARNING", "ERROR"}

_SAFETY_GUARANTEES = [
    "paper_trade_mode is always True",
    "live_trading_enabled is always False",
    "broker_execution_enabled is always False",
    "no broker execution is performed",
    "no Robinhood execution is performed",
    "no real order placement is performed",
    "module is read-only except for writing bot_environment_check.json",
    "module uses Python standard library only",
    "module does not use subprocess",
    "module does not use os.system",
]

_REQUIRED_SAFETY_PHRASES = (
    "paper_trade_mode is always true",
    "live_trading_enabled is always false",
    "broker_execution_enabled is always false",
    "no broker execution",
    "no robinhood execution",
    "no real order placement",
)


def _utc_now_iso() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalize_root(root_path: str) -> Path:
    root = Path(root_path).expanduser()
    return root.resolve()


def _missing_files(root: Path, filenames: List[str]) -> List[str]:
    return [name for name in filenames if not (root / name).is_file()]


def _missing_directories(root: Path, directories: List[str]) -> List[str]:
    return [name for name in directories if not (root / name).is_dir()]


def _build_warnings(missing_optional_files: List[str]) -> List[str]:
    if not missing_optional_files:
        return []
    return [f"optional file missing: {name}" for name in missing_optional_files]


def _build_errors(missing_required_files: List[str], missing_required_directories: List[str]) -> List[str]:
    errors: List[str] = []
    errors.extend(f"required file missing: {name}" for name in missing_required_files)
    errors.extend(f"required directory missing: {name}" for name in missing_required_directories)
    return errors


def _environment_status(errors: List[str], warnings: List[str]) -> str:
    if errors:
        return "ERROR"
    if warnings:
        return "WARNING"
    return "OK"


def build_bot_environment_check(root_path: str = ".") -> Dict[str, Any]:
    """
    Build a read-only Dividend Bot environment verification payload.

    Args:
        root_path: Project root to inspect. Defaults to current directory.

    Returns:
        A JSON-serializable dictionary describing environment status, required
        files, optional files, missing files, warnings, errors, and safety flags.
    """
    root = _normalize_root(root_path)
    missing_required_files = _missing_files(root, _REQUIRED_FILES)
    missing_optional_files = _missing_files(root, _OPTIONAL_FILES)
    missing_required_directories = _missing_directories(root, _REQUIRED_DIRECTORIES)
    warnings = _build_warnings(missing_optional_files)
    errors = _build_errors(missing_required_files, missing_required_directories)

    payload: Dict[str, Any] = {
        "bot_name": "Agentic Robin Dividend Bot",
        "bot_type": "paper_only_dividend_etf_management_bot",
        "bot_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _utc_now_iso(),
        "generated_by": GENERATED_BY,
        "module_name": MODULE_NAME,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "python_version": sys.version.split()[0],
        "platform": platform_module.platform(),
        "working_directory": str(root),
        "required_files": list(_REQUIRED_FILES),
        "missing_required_files": missing_required_files,
        "optional_files": list(_OPTIONAL_FILES),
        "missing_optional_files": missing_optional_files,
        "required_directories": list(_REQUIRED_DIRECTORIES),
        "missing_required_directories": missing_required_directories,
        "environment_status": _environment_status(errors, warnings),
        "warnings": warnings,
        "errors": errors,
        "safety_guarantees": list(_SAFETY_GUARANTEES),
    }
    validate_bot_environment_check(payload)
    return payload


def _validate_string_field(payload: Dict[str, Any], field_name: str) -> None:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _validate_list_field(payload: Dict[str, Any], field_name: str, *, require_non_empty: bool = False) -> None:
    value = payload.get(field_name)
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    if require_non_empty and not value:
        raise ValueError(f"{field_name} must not be empty")
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name}[{index}] must be a non-empty string")


def validate_bot_environment_check(payload: Dict[str, Any]) -> bool:
    """
    Validate a Dividend Bot environment verification payload.

    Args:
        payload: Environment check dictionary to validate.

    Returns:
        True when the payload is valid.

    Raises:
        TypeError: If payload is not a dictionary.
        ValueError: If required fields are missing or safety rules are violated.
    """
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dictionary")

    missing_keys = sorted(_REQUIRED_KEYS.difference(payload.keys()))
    if missing_keys:
        raise ValueError(f"missing required environment check keys: {missing_keys}")

    for field_name in (
        "bot_name",
        "bot_type",
        "bot_version",
        "schema_version",
        "generated_at_utc",
        "generated_by",
        "module_name",
        "python_version",
        "platform",
        "working_directory",
        "environment_status",
    ):
        _validate_string_field(payload, field_name)

    if payload.get("module_name") != MODULE_NAME:
        raise ValueError(f"module_name must be {MODULE_NAME!r}")
    if payload.get("bot_version") != MODULE_VERSION:
        raise ValueError(f"bot_version must be {MODULE_VERSION!r}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")
    if payload.get("generated_by") != GENERATED_BY:
        raise ValueError(f"generated_by must be {GENERATED_BY!r}")

    if payload.get("paper_trade_mode") is not True:
        raise ValueError("paper_trade_mode must be True")
    if payload.get("live_trading_enabled") is not False:
        raise ValueError("live_trading_enabled must be False")
    if payload.get("broker_execution_enabled") is not False:
        raise ValueError("broker_execution_enabled must be False")

    for field_name in _LIST_FIELDS:
        _validate_list_field(
            payload,
            field_name,
            require_non_empty=field_name in _NON_EMPTY_LIST_FIELDS,
        )

    if payload["environment_status"] not in _VALID_ENVIRONMENT_STATUSES:
        raise ValueError("environment_status must be one of OK, WARNING, ERROR")

    if payload["missing_required_files"] or payload["missing_required_directories"]:
        if payload["environment_status"] != "ERROR":
            raise ValueError("missing required files or directories must produce ERROR")
        if not payload["errors"]:
            raise ValueError("missing required files or directories must produce errors")
    elif payload["missing_optional_files"]:
        if payload["environment_status"] != "WARNING":
            raise ValueError("missing optional files must produce WARNING when no errors exist")
        if not payload["warnings"]:
            raise ValueError("missing optional files must produce warnings")
    else:
        if payload["environment_status"] != "OK":
            raise ValueError("environment_status must be OK when no warnings or errors exist")

    safety_text = " ".join(item.lower() for item in payload["safety_guarantees"])
    for phrase in _REQUIRED_SAFETY_PHRASES:
        if phrase not in safety_text:
            raise ValueError(f"missing safety guarantee: {phrase}")

    return True


def write_bot_environment_check(
    path: str = "bot_environment_check.json",
    root_path: str = ".",
) -> Dict[str, Any]:
    """
    Write the environment check payload to JSON.

    This is the module's only file-writing operation. It writes platform-facing
    environment metadata only and does not alter trading state, reports,
    workflows, broker settings, or order logic.
    """
    payload = build_bot_environment_check(root_path=root_path)
    output_path = Path(path)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_bot_environment_check(path: str = "bot_environment_check.json") -> Dict[str, Any]:
    """Read and validate a Dividend Bot environment check JSON file."""
    input_path = Path(path)
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    validate_bot_environment_check(payload)
    return payload


def format_bot_environment_check_summary(payload: Dict[str, Any]) -> str:
    """Format a Markdown-compatible environment check summary."""
    validate_bot_environment_check(payload)

    lines: List[str] = [
        f"# {payload['bot_name']} Environment Check",
        "",
        f"- Bot type: {payload['bot_type']}",
        f"- Bot version: {payload['bot_version']}",
        f"- Schema version: {payload['schema_version']}",
        f"- Generated at UTC: {payload['generated_at_utc']}",
        f"- Python version: {payload['python_version']}",
        f"- Platform: {payload['platform']}",
        f"- Working directory: {payload['working_directory']}",
        f"- Environment status: {payload['environment_status']}",
        f"- Paper trade mode: {payload['paper_trade_mode']}",
        f"- Live trading enabled: {payload['live_trading_enabled']}",
        f"- Broker execution enabled: {payload['broker_execution_enabled']}",
        "",
        "## Required Files",
    ]
    lines.extend(f"- {item}" for item in payload["required_files"])
    lines.extend(["", "## Missing Required Files"])
    lines.extend(f"- {item}" for item in payload["missing_required_files"] or ["None"])
    lines.extend(["", "## Optional Files"])
    lines.extend(f"- {item}" for item in payload["optional_files"])
    lines.extend(["", "## Missing Optional Files"])
    lines.extend(f"- {item}" for item in payload["missing_optional_files"] or ["None"])
    lines.extend(["", "## Required Directories"])
    lines.extend(f"- {item}" for item in payload["required_directories"])
    lines.extend(["", "## Missing Required Directories"])
    lines.extend(f"- {item}" for item in payload["missing_required_directories"] or ["None"])
    lines.extend(["", "## Warnings"])
    lines.extend(f"- {item}" for item in payload["warnings"] or ["None"])
    lines.extend(["", "## Errors"])
    lines.extend(f"- {item}" for item in payload["errors"] or ["None"])
    lines.extend(["", "## Safety Guarantees"])
    lines.extend(f"- {item}" for item in payload["safety_guarantees"])

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    write_bot_environment_check()
