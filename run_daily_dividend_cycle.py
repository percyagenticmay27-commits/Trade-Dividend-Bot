"""Single-command daily cycle runner for the paper-only Dividend Bot.

This module coordinates the existing Master Portfolio Orchestrator, writes a
consolidated daily-cycle summary, and never invokes brokers, Robinhood, shell
commands, subprocesses, or live order placement.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from master_portfolio_orchestrator import (
    build_master_portfolio_orchestration_report,
    validate_master_portfolio_orchestration_report,
)

MODULE_NAME = "run_daily_dividend_cycle"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

STATUS_COMPLETE = "COMPLETE"
STATUS_PARTIAL = "PARTIAL"
STATUS_ERROR = "ERROR"
SUPPORTED_RUN_STATUSES = [STATUS_COMPLETE, STATUS_PARTIAL, STATUS_ERROR]

DEFAULT_OUTPUT_FILES = {
    "orchestration_json": "master_portfolio_orchestration_report.json",
    "cycle_json": "daily_dividend_cycle_report.json",
    "cycle_markdown": "daily_dividend_cycle_report.md",
}

SAFETY_GUARANTEES = [
    "paper_trade_mode is enforced as True",
    "live_trading_enabled is enforced as False",
    "broker_execution_enabled is enforced as False",
    "reporting_only is enforced as True",
    "no Robinhood execution is performed",
    "no brokerage execution is performed",
    "no order placement is performed",
    "no subprocess or os.system usage",
    "no external network access is performed",
]

REPORT_REQUIRED_FIELDS = [
    "module_name", "module_version", "schema_version", "generated_by",
    "generated_at_utc", "paper_trade_mode", "live_trading_enabled",
    "broker_execution_enabled", "reporting_only", "run_status",
    "orchestration_status", "available_stage_count", "missing_stage_count",
    "invalid_stage_count", "stage_count", "output_files", "warnings",
    "errors", "safety_guarantees",
]


@dataclass(frozen=True)
class DailyDividendCycleReport:
    module_name: str
    module_version: str
    schema_version: str
    generated_by: str
    generated_at_utc: str
    paper_trade_mode: bool
    live_trading_enabled: bool
    broker_execution_enabled: bool
    reporting_only: bool
    run_status: str
    orchestration_status: str
    available_stage_count: int
    missing_stage_count: int
    invalid_stage_count: int
    stage_count: int
    output_files: Dict[str, str]
    warnings: list[str]
    errors: list[str]
    safety_guarantees: list[str]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_daily_dividend_cycle_report(
    stage_payloads: Optional[Mapping[str, Mapping[str, Any]]] = None,
    root_path: str = ".",
    input_files: Optional[Mapping[str, str]] = None,
    output_files: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    files = dict(DEFAULT_OUTPUT_FILES)
    if output_files:
        files.update(output_files)

    orchestration = build_master_portfolio_orchestration_report(
        stage_payloads=stage_payloads,
        root_path=root_path,
        input_files=input_files,
    )
    validate_master_portfolio_orchestration_report(orchestration)

    run_status = orchestration["run_status"]
    payload = asdict(DailyDividendCycleReport(
        module_name=MODULE_NAME,
        module_version=MODULE_VERSION,
        schema_version=SCHEMA_VERSION,
        generated_by=GENERATED_BY,
        generated_at_utc=_now(),
        paper_trade_mode=True,
        live_trading_enabled=False,
        broker_execution_enabled=False,
        reporting_only=True,
        run_status=run_status,
        orchestration_status=orchestration["run_status"],
        available_stage_count=orchestration["available_stage_count"],
        missing_stage_count=orchestration["missing_stage_count"],
        invalid_stage_count=orchestration["invalid_stage_count"],
        stage_count=len(orchestration["stage_results"]),
        output_files=files,
        warnings=list(orchestration["warnings"]),
        errors=list(orchestration["errors"]),
        safety_guarantees=list(SAFETY_GUARANTEES),
    ))
    validate_daily_dividend_cycle_report(payload)
    return payload


def validate_daily_dividend_cycle_report(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    for field in REPORT_REQUIRED_FIELDS:
        if field not in payload:
            raise ValueError(f"missing required field: {field}")
    for field, expected in {
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "reporting_only": True,
    }.items():
        if payload[field] is not expected:
            raise ValueError(f"{field} must be {expected}")
    if payload["run_status"] not in SUPPORTED_RUN_STATUSES:
        raise ValueError("unsupported run_status")
    if payload["orchestration_status"] not in SUPPORTED_RUN_STATUSES:
        raise ValueError("unsupported orchestration_status")
    for field in ["available_stage_count", "missing_stage_count", "invalid_stage_count", "stage_count"]:
        if not isinstance(payload[field], int) or isinstance(payload[field], bool) or payload[field] < 0:
            raise ValueError(f"{field} must be a non-negative integer")
    if payload["available_stage_count"] + payload["missing_stage_count"] + payload["invalid_stage_count"] != payload["stage_count"]:
        raise ValueError("stage counts must total stage_count")
    if not isinstance(payload["output_files"], Mapping):
        raise ValueError("output_files must be a mapping")
    for key, value in payload["output_files"].items():
        if not isinstance(key, str) or not key.strip() or not isinstance(value, str) or not value.strip():
            raise ValueError("output_files entries must be non-empty strings")
    for field in ["warnings", "errors", "safety_guarantees"]:
        if not isinstance(payload[field], list):
            raise ValueError(f"{field} must be a list")
        for item in payload[field]:
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"{field} entries must be non-empty strings")
    return True


def format_daily_dividend_cycle_markdown(payload: Mapping[str, Any]) -> str:
    validate_daily_dividend_cycle_report(payload)
    lines = [
        "# Daily Dividend Cycle Report",
        "",
        f"- Run Status: {payload['run_status']}",
        f"- Available Stages: {payload['available_stage_count']}",
        f"- Missing Stages: {payload['missing_stage_count']}",
        f"- Invalid Stages: {payload['invalid_stage_count']}",
        f"- Total Stages: {payload['stage_count']}",
        "",
        "## Output Files",
    ]
    lines.extend(f"- {key}: {value}" for key, value in payload["output_files"].items())
    lines += ["", "## Warnings"]
    lines.extend(f"- {item}" for item in payload["warnings"]) or lines.append("- None")
    lines += ["", "## Errors"]
    lines.extend(f"- {item}" for item in payload["errors"]) or lines.append("- None")
    lines += ["", "## Safety Guarantees"]
    lines.extend(f"- {item}" for item in payload["safety_guarantees"])
    return "\n".join(lines) + "\n"


def run_daily_dividend_cycle(
    root_path: str = ".",
    stage_payloads: Optional[Mapping[str, Mapping[str, Any]]] = None,
    input_files: Optional[Mapping[str, str]] = None,
    output_files: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    files = dict(DEFAULT_OUTPUT_FILES)
    if output_files:
        files.update(output_files)

    root = Path(root_path)
    root.mkdir(parents=True, exist_ok=True)

    orchestration = build_master_portfolio_orchestration_report(
        stage_payloads=stage_payloads,
        root_path=str(root),
        input_files=input_files,
    )
    Path(root / files["orchestration_json"]).write_text(
        json.dumps(orchestration, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    payload = build_daily_dividend_cycle_report(
        stage_payloads=stage_payloads,
        root_path=str(root),
        input_files=input_files,
        output_files=files,
    )
    Path(root / files["cycle_json"]).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    Path(root / files["cycle_markdown"]).write_text(
        format_daily_dividend_cycle_markdown(payload),
        encoding="utf-8",
    )
    return payload


if __name__ == "__main__":
    report = run_daily_dividend_cycle()
    print(f"Daily Dividend Cycle: {report['run_status']}")
