"""Master Portfolio Orchestrator for the Dividend Bot.

Coordinates the paper-only portfolio workflow in a deterministic order. The
orchestrator reads or accepts existing engine outputs, records stage status,
and produces one consolidated run manifest. It never places orders or invokes
external processes.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

MODULE_NAME = "master_portfolio_orchestrator"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

STAGE_ORDER = [
    "market_regime",
    "market_intelligence",
    "momentum_score",
    "entry_score",
    "conviction",
    "dividend_ranking",
    "opportunity_pairing",
    "portfolio_decision",
    "capital_allocation",
    "portfolio_construction",
    "portfolio_rebalance",
    "income_reinvestment",
    "portfolio_lifecycle",
    "daily_command_center",
    "weekly_portfolio_review",
    "strategy_performance_analytics",
    "monthly_portfolio_review",
]

DEFAULT_INPUT_FILES = {
    "market_regime": "market_regime_report.json",
    "market_intelligence": "market_intelligence_report.json",
    "momentum_score": "momentum_score_report.json",
    "entry_score": "entry_score_report.json",
    "conviction": "conviction_report.json",
    "dividend_ranking": "dividend_rankings.json",
    "opportunity_pairing": "opportunity_pairing_report.json",
    "portfolio_decision": "portfolio_decision_report.json",
    "capital_allocation": "capital_allocation_report.json",
    "portfolio_construction": "portfolio_construction_report.json",
    "portfolio_rebalance": "portfolio_rebalance_report.json",
    "income_reinvestment": "income_reinvestment_report.json",
    "portfolio_lifecycle": "portfolio_lifecycle_report.json",
    "daily_command_center": "daily_portfolio_command_center.json",
    "weekly_portfolio_review": "weekly_portfolio_review.json",
    "strategy_performance_analytics": "strategy_performance_analytics.json",
    "monthly_portfolio_review": "monthly_portfolio_review.json",
}

STATUS_AVAILABLE = "AVAILABLE"
STATUS_MISSING = "MISSING"
STATUS_INVALID = "INVALID"
SUPPORTED_STAGE_STATUSES = [STATUS_AVAILABLE, STATUS_MISSING, STATUS_INVALID]

SAFETY_GUARANTEES = [
    "paper_trade_mode is enforced as True",
    "live_trading_enabled is enforced as False",
    "broker_execution_enabled is enforced as False",
    "reporting_only is enforced as True",
    "no brokerage execution is performed",
    "no Robinhood execution is performed",
    "no order placement is performed",
    "no subprocess or os.system usage",
    "read-only orchestration and reporting only",
]

REPORT_REQUIRED_FIELDS = [
    "module_name", "module_version", "schema_version", "generated_by",
    "generated_at_utc", "paper_trade_mode", "live_trading_enabled",
    "broker_execution_enabled", "reporting_only", "run_status",
    "stage_order", "stage_results", "available_stage_count",
    "missing_stage_count", "invalid_stage_count", "warnings", "errors",
    "safety_guarantees",
]


@dataclass(frozen=True)
class OrchestrationStageResult:
    stage_name: str
    status: str
    source_path: str
    module_name: str = ""
    module_version: str = ""
    warning: str = ""
    error: str = ""


@dataclass(frozen=True)
class MasterPortfolioOrchestrationReport:
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
    stage_order: list[str]
    stage_results: list[Dict[str, Any]]
    available_stage_count: int
    missing_stage_count: int
    invalid_stage_count: int
    warnings: list[str]
    errors: list[str]
    safety_guarantees: list[str]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> tuple[str, Dict[str, Any], str]:
    if not path.exists():
        return STATUS_MISSING, {}, f"Missing optional stage input: {path.name}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return STATUS_INVALID, {}, f"Unable to read valid JSON from {path.name}: {exc}"
    if not isinstance(payload, dict):
        return STATUS_INVALID, {}, f"Stage input {path.name} must contain a JSON object"
    return STATUS_AVAILABLE, payload, ""


def build_master_portfolio_orchestration_report(
    stage_payloads: Optional[Mapping[str, Mapping[str, Any]]] = None,
    root_path: str = ".",
    input_files: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    supplied = dict(stage_payloads or {})
    files = dict(DEFAULT_INPUT_FILES)
    if input_files:
        files.update(input_files)
    root = Path(root_path)
    results = []
    warnings = []
    errors = []

    for stage in STAGE_ORDER:
        source_path = files[stage]
        if stage in supplied:
            raw = supplied[stage]
            if isinstance(raw, Mapping):
                status, payload, message = STATUS_AVAILABLE, dict(raw), ""
            else:
                status, payload, message = STATUS_INVALID, {}, f"Supplied stage {stage} must be a mapping"
        else:
            status, payload, message = _load_json(root / source_path)

        warning = message if status == STATUS_MISSING else ""
        error = message if status == STATUS_INVALID else ""
        if warning:
            warnings.append(warning)
        if error:
            errors.append(error)
        results.append(asdict(OrchestrationStageResult(
            stage_name=stage,
            status=status,
            source_path=source_path,
            module_name=str(payload.get("module_name", "")),
            module_version=str(payload.get("module_version", "")),
            warning=warning,
            error=error,
        )))

    available = sum(1 for row in results if row["status"] == STATUS_AVAILABLE)
    missing = sum(1 for row in results if row["status"] == STATUS_MISSING)
    invalid = sum(1 for row in results if row["status"] == STATUS_INVALID)
    run_status = "ERROR" if invalid else "COMPLETE" if missing == 0 else "PARTIAL"

    payload = asdict(MasterPortfolioOrchestrationReport(
        MODULE_NAME, MODULE_VERSION, SCHEMA_VERSION, GENERATED_BY, _now(),
        True, False, False, True, run_status, list(STAGE_ORDER), results,
        available, missing, invalid, warnings, errors, list(SAFETY_GUARANTEES),
    ))
    validate_master_portfolio_orchestration_report(payload)
    return payload


def validate_master_portfolio_orchestration_report(payload: Any) -> bool:
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
    if payload["run_status"] not in ["COMPLETE", "PARTIAL", "ERROR"]:
        raise ValueError("unsupported run_status")
    if payload["stage_order"] != STAGE_ORDER:
        raise ValueError("stage_order must match approved workflow")
    if not isinstance(payload["stage_results"], list):
        raise ValueError("stage_results must be a list")
    if len(payload["stage_results"]) != len(STAGE_ORDER):
        raise ValueError("stage_results length must match stage_order")
    for row in payload["stage_results"]:
        if not isinstance(row, Mapping):
            raise ValueError("stage result must be a mapping")
        if row.get("stage_name") not in STAGE_ORDER:
            raise ValueError("unsupported stage_name")
        if row.get("status") not in SUPPORTED_STAGE_STATUSES:
            raise ValueError("unsupported stage status")
    counts = {
        STATUS_AVAILABLE: payload["available_stage_count"],
        STATUS_MISSING: payload["missing_stage_count"],
        STATUS_INVALID: payload["invalid_stage_count"],
    }
    for status, expected in counts.items():
        if expected != sum(1 for row in payload["stage_results"] if row["status"] == status):
            raise ValueError(f"{status.lower()} stage count mismatch")
    for field in ["warnings", "errors", "safety_guarantees"]:
        if not isinstance(payload[field], list):
            raise ValueError(f"{field} must be a list")
    return True


def write_master_portfolio_orchestration_report_json(
    path: str = "master_portfolio_orchestration_report.json",
    root_path: str = ".",
) -> Dict[str, Any]:
    payload = build_master_portfolio_orchestration_report(root_path=root_path)
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_master_portfolio_orchestration_report_json(
    path: str = "master_portfolio_orchestration_report.json",
) -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_master_portfolio_orchestration_report(payload)
    return payload


def format_master_portfolio_orchestration_report_markdown(payload: Mapping[str, Any]) -> str:
    validate_master_portfolio_orchestration_report(payload)
    lines = [
        "# Master Portfolio Orchestration Report", "",
        f"- Run Status: {payload['run_status']}",
        f"- Available Stages: {payload['available_stage_count']}",
        f"- Missing Stages: {payload['missing_stage_count']}",
        f"- Invalid Stages: {payload['invalid_stage_count']}",
        "", "## Stage Results", "",
        "| Stage | Status | Source | Module Version |",
        "|---|---|---|---|",
    ]
    for row in payload["stage_results"]:
        lines.append(f"| {row['stage_name']} | {row['status']} | {row['source_path']} | {row['module_version']} |")
    lines += ["", "## Safety Guarantees"] + [f"- {item}" for item in payload["safety_guarantees"]]
    return "\n".join(lines) + "\n"


def write_master_portfolio_orchestration_report_markdown(
    path: str = "master_portfolio_orchestration_report.md",
    root_path: str = ".",
) -> Dict[str, Any]:
    payload = build_master_portfolio_orchestration_report(root_path=root_path)
    Path(path).write_text(format_master_portfolio_orchestration_report_markdown(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    write_master_portfolio_orchestration_report_json()
    write_master_portfolio_orchestration_report_markdown()
