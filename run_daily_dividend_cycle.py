"""Single-command daily execution cycle for the paper-only Dividend Bot.

The runner refreshes one shared read-only market snapshot, executes each approved
engine in order, adapts upstream reports into accepted downstream arguments, writes
all stage artifacts, and produces consolidated cycle reports.
"""
from __future__ import annotations

import importlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from market_data_integration_engine import write_market_data_snapshot
from master_portfolio_orchestrator import (
    DEFAULT_INPUT_FILES,
    STAGE_ORDER,
    build_master_portfolio_orchestration_report,
    validate_master_portfolio_orchestration_report,
)
from stage_input_adapters import prepare_stage_kwargs

MODULE_NAME = "run_daily_dividend_cycle"
MODULE_VERSION = "1.4.0"
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

STAGE_EXECUTION_PLAN = {
    "market_regime": ("market_regime_engine", "build_market_regime_report"),
    "market_intelligence": ("market_intelligence_engine", "build_market_intelligence_report"),
    "momentum_score": ("momentum_score_engine", "build_momentum_score_report"),
    "entry_score": ("entry_score_engine", "build_entry_score_report"),
    "conviction": ("conviction_engine", "build_conviction_report"),
    "dividend_quality": ("src.dividend_bot.dividend_quality_engine", "build_dividend_quality_report"),
    "dividend_ranking": ("dividend_ranking_engine", "build_dividend_ranking_report"),
    "opportunity_pairing": ("opportunity_pairing_engine", "build_opportunity_pairing_report"),
    "portfolio_decision": ("portfolio_decision_engine", "build_portfolio_decision_report"),
    "capital_allocation": ("capital_allocation_engine", "build_capital_allocation_report"),
    "portfolio_construction": ("portfolio_construction_engine", "build_portfolio_construction_report"),
    "portfolio_rebalance": ("portfolio_rebalance_engine", "build_portfolio_rebalance_report"),
    "income_reinvestment": ("income_reinvestment_engine", "build_income_reinvestment_report"),
    "portfolio_lifecycle": ("portfolio_lifecycle_engine", "build_portfolio_lifecycle_report"),
    "daily_command_center": ("daily_portfolio_command_center", "build_daily_portfolio_command_center"),
    "weekly_portfolio_review": ("weekly_portfolio_review_engine", "build_weekly_portfolio_review"),
    "strategy_performance_analytics": ("strategy_performance_analytics_engine", "build_strategy_performance_analytics_report"),
    "monthly_portfolio_review": ("monthly_portfolio_review_engine", "build_monthly_portfolio_review"),
}

SAFETY_GUARANTEES = [
    "paper_trade_mode is enforced as True",
    "live_trading_enabled is enforced as False",
    "broker_execution_enabled is enforced as False",
    "reporting_only is enforced as True",
    "read-only market information may be refreshed through the approved provider layer",
    "no brokerage execution is performed",
    "no order placement is performed",
    "no operating-system process launch is performed",
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


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def execute_stage(
    stage_name: str,
    root_path: str = ".",
    input_files: Optional[Mapping[str, str]] = None,
    stage_payloads: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    if stage_name not in STAGE_EXECUTION_PLAN:
        raise ValueError(f"unsupported stage: {stage_name}")
    module_name, builder_name = STAGE_EXECUTION_PLAN[stage_name]
    module = importlib.import_module(module_name)
    builder = getattr(module, builder_name, None)
    if not callable(builder):
        raise AttributeError(f"{module_name}.{builder_name} is not callable")
    kwargs = prepare_stage_kwargs(stage_name, stage_payloads or {}, builder, root_path)
    payload = builder(**kwargs)
    if not isinstance(payload, Mapping):
        raise ValueError(f"{stage_name} builder must return a mapping")
    files = dict(DEFAULT_INPUT_FILES)
    if input_files:
        files.update(input_files)
    _write_json(Path(root_path) / files[stage_name], payload)
    return dict(payload)


def execute_all_stages(
    root_path: str = ".",
    input_files: Optional[Mapping[str, str]] = None,
    refresh_market_data: bool = False,
    market_symbols: Optional[Iterable[str]] = None,
    market_data_service: Any = None,
    force_market_refresh: bool = False,
) -> tuple[Dict[str, Dict[str, Any]], list[str], list[str]]:
    """Execute all stages in order, optionally beginning with one shared snapshot."""
    payloads: Dict[str, Dict[str, Any]] = {}
    warnings: list[str] = []
    errors: list[str] = []

    if refresh_market_data:
        try:
            market_payload = write_market_data_snapshot(
                root_path=root_path,
                symbols=market_symbols,
                service=market_data_service,
                force_refresh=force_market_refresh,
            )
            payloads["market_data"] = market_payload
            warnings.extend(str(item) for item in market_payload.get("warnings", []))
            if market_payload.get("status") == "ERROR":
                warnings.append("The shared market snapshot could not refresh; downstream fallback behavior remains active.")
        except (ImportError, OSError, RuntimeError, TypeError, ValueError) as exc:
            warnings.append(f"Market data refresh was unavailable: {exc}")

    for stage_name in STAGE_ORDER:
        try:
            payloads[stage_name] = execute_stage(
                stage_name,
                root_path=root_path,
                input_files=input_files,
                stage_payloads=payloads,
            )
        except (ImportError, AttributeError, OSError, TypeError, ValueError) as exc:
            errors.append(f"Stage {stage_name} failed: {exc}")
    if errors:
        warnings.append("One or more stages failed; successful stages were preserved for review.")
    return payloads, warnings, errors


def build_daily_dividend_cycle_report(
    stage_payloads: Optional[Mapping[str, Mapping[str, Any]]] = None,
    root_path: str = ".",
    input_files: Optional[Mapping[str, str]] = None,
    output_files: Optional[Mapping[str, str]] = None,
    execution_warnings: Optional[list[str]] = None,
    execution_errors: Optional[list[str]] = None,
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
    errors = list(execution_errors or []) + list(orchestration["errors"])
    warnings = list(execution_warnings or []) + list(orchestration["warnings"])
    run_status = STATUS_ERROR if errors else orchestration["run_status"]
    payload = asdict(DailyDividendCycleReport(
        MODULE_NAME, MODULE_VERSION, SCHEMA_VERSION, GENERATED_BY, _now(),
        True, False, False, True, run_status, orchestration["run_status"],
        orchestration["available_stage_count"], orchestration["missing_stage_count"],
        orchestration["invalid_stage_count"], len(orchestration["stage_results"]),
        files, warnings, errors, list(SAFETY_GUARANTEES),
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
    if payload["run_status"] not in SUPPORTED_RUN_STATUSES or payload["orchestration_status"] not in SUPPORTED_RUN_STATUSES:
        raise ValueError("unsupported run status")
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
        if any(not isinstance(item, str) or not item.strip() for item in payload[field]):
            raise ValueError(f"{field} entries must be non-empty strings")
    return True


def format_daily_dividend_cycle_markdown(payload: Mapping[str, Any]) -> str:
    validate_daily_dividend_cycle_report(payload)
    lines = [
        "# Daily Dividend Cycle Report", "",
        f"- Run Status: {payload['run_status']}",
        f"- Available Stages: {payload['available_stage_count']}",
        f"- Missing Stages: {payload['missing_stage_count']}",
        f"- Invalid Stages: {payload['invalid_stage_count']}",
        f"- Total Stages: {payload['stage_count']}", "", "## Output Files",
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
    execute_stages: bool = True,
    refresh_market_data: bool = True,
    market_symbols: Optional[Iterable[str]] = None,
    market_data_service: Any = None,
    force_market_refresh: bool = False,
) -> Dict[str, Any]:
    files = dict(DEFAULT_OUTPUT_FILES)
    if output_files:
        files.update(output_files)
    root = Path(root_path)
    root.mkdir(parents=True, exist_ok=True)
    execution_warnings: list[str] = []
    execution_errors: list[str] = []
    supplied = dict(stage_payloads or {})
    if execute_stages:
        generated, execution_warnings, execution_errors = execute_all_stages(
            str(root),
            input_files,
            refresh_market_data=refresh_market_data,
            market_symbols=market_symbols,
            market_data_service=market_data_service,
            force_market_refresh=force_market_refresh,
        )
        generated.update(supplied)
        supplied = generated

    orchestration = build_master_portfolio_orchestration_report(
        stage_payloads=supplied or None,
        root_path=str(root),
        input_files=input_files,
    )
    _write_json(root / files["orchestration_json"], orchestration)
    payload = build_daily_dividend_cycle_report(
        stage_payloads=supplied or None,
        root_path=str(root),
        input_files=input_files,
        output_files=files,
        execution_warnings=execution_warnings,
        execution_errors=execution_errors,
    )
    _write_json(root / files["cycle_json"], payload)
    markdown_path = root / files["cycle_markdown"]
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(format_daily_dividend_cycle_markdown(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    report = run_daily_dividend_cycle()
    print(f"Daily Dividend Cycle: {report['run_status']}")
