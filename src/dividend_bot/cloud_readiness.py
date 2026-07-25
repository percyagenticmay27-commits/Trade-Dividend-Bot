"""Cloud readiness utilities for the paper-only Trade Dividend Bot."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

MODULE_NAME = "cloud_readiness"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False

DEFAULT_DIRECTORIES = ("results", "logs", "state", "runtime")
REQUIRED_ENVIRONMENT = ("DIVIDEND_BOT_ENV",)
OPTIONAL_ENVIRONMENT = ("DIVIDEND_BOT_TIMEZONE", "DIVIDEND_BOT_RESULTS_DIR", "DIVIDEND_BOT_LOG_DIR")


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def validate_environment(
    environment: Optional[Mapping[str, str]] = None,
    *,
    required_names: Sequence[str] = REQUIRED_ENVIRONMENT,
) -> dict[str, Any]:
    values = dict(os.environ if environment is None else environment)
    missing = sorted(name for name in required_names if not str(values.get(name, "")).strip())
    configured_optional = sorted(name for name in OPTIONAL_ENVIRONMENT if str(values.get(name, "")).strip())
    return {
        "status": "READY" if not missing else "NOT_READY",
        "missing_required": missing,
        "configured_optional": configured_optional,
        "paper_trade_mode": True,
    }


def ensure_runtime_directories(
    root_dir: str | Path,
    directories: Sequence[str] = DEFAULT_DIRECTORIES,
) -> dict[str, str]:
    root = Path(root_dir)
    created: dict[str, str] = {}
    for name in directories:
        path = root / str(name)
        path.mkdir(parents=True, exist_ok=True)
        created[str(name)] = str(path)
    return created


def write_structured_log(
    log_path: str | Path,
    *,
    level: str,
    event: str,
    message: str,
    timestamp_utc: Optional[str] = None,
    context: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    record = {
        "timestamp_utc": timestamp_utc or _now_utc(),
        "level": str(level).upper(),
        "event": str(event),
        "message": str(message),
        "context": dict(context or {}),
        "paper_trade_mode": True,
    }
    destination = Path(log_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def build_health_check(
    *,
    environment_report: Mapping[str, Any],
    runtime_directories: Mapping[str, str],
    required_files: Optional[Sequence[str | Path]] = None,
    generated_at_utc: Optional[str] = None,
) -> dict[str, Any]:
    missing_files = sorted(str(path) for path in (required_files or []) if not Path(path).exists())
    missing_dirs = sorted(name for name, path in runtime_directories.items() if not Path(path).is_dir())
    ready = environment_report.get("status") == "READY" and not missing_files and not missing_dirs
    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at_utc or _now_utc(),
        "status": "HEALTHY" if ready else "DEGRADED",
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "environment": dict(environment_report),
        "runtime_directories": dict(runtime_directories),
        "missing_required_files": missing_files,
        "missing_runtime_directories": missing_dirs,
        "python": {"version": sys.version.split()[0], "executable": sys.executable},
        "governance": {
            "order_execution_allowed": False,
            "brokerage_communication_allowed": False,
            "capital_movement_allowed": False,
        },
    }


def write_health_check(report: Mapping[str, Any], output_path: str | Path) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def scheduler_command(project_root: str | Path) -> list[str]:
    root = Path(project_root)
    return [sys.executable, str(root / "run_daily_paper_cycle.py")]


def build_cloud_readiness_report(
    root_dir: str | Path,
    *,
    environment: Optional[Mapping[str, str]] = None,
    required_files: Optional[Sequence[str | Path]] = None,
    generated_at_utc: Optional[str] = None,
) -> dict[str, Any]:
    directories = ensure_runtime_directories(root_dir)
    env_report = validate_environment(environment)
    return build_health_check(
        environment_report=env_report,
        runtime_directories=directories,
        required_files=required_files,
        generated_at_utc=generated_at_utc,
    )
