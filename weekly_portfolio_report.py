"""Weekly Portfolio Report for the paper-only Dividend Bot."""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping

MODULE_NAME = "weekly_portfolio_report"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

INPUT_FILES = [
    "daily_portfolio_command_center.json",
    "portfolio_lifecycle_report.json",
    "income_reinvestment_report.json",
    "portfolio_rebalance_report.json",
    "capital_allocation_report.json",
]

SAFETY_GUARANTEES = [
    "paper_trade_mode is enforced as True",
    "reporting_only is enforced as True",
    "live_trading_enabled is enforced as False",
    "broker_execution_enabled is enforced as False",
    "no Robinhood execution is performed",
    "no brokerage execution is performed",
    "no order placement is performed",
    "report generation is read-only",
]

SUMMARY_FIELDS = [
    "portfolio_value",
    "cash_balance",
    "cash_reserve_target",
    "expected_monthly_income",
    "expected_annual_income",
    "holdings_count",
    "increase_count",
    "hold_count",
    "exit_count",
    "reinvestment_action_count",
    "rebalance_action_count",
]

REPORT_REQUIRED_FIELDS = [
    "module_name", "module_version", "schema_version", "generated_by", "generated_at_utc",
    "paper_trade_mode", "live_trading_enabled", "broker_execution_enabled", "reporting_only",
    "week_ending", "input_files", "available_input_files", "missing_input_files",
    "weekly_summary", "top_actions", "risk_flags", "warnings", "errors", "safety_guarantees",
]


@dataclass(frozen=True)
class WeeklyPortfolioSummary:
    portfolio_value: float = 0.0
    cash_balance: float = 0.0
    cash_reserve_target: float = 0.0
    expected_monthly_income: float = 0.0
    expected_annual_income: float = 0.0
    holdings_count: int = 0
    increase_count: int = 0
    hold_count: int = 0
    exit_count: int = 0
    reinvestment_action_count: int = 0
    rebalance_action_count: int = 0


@dataclass(frozen=True)
class WeeklyPortfolioReport:
    module_name: str
    module_version: str
    schema_version: str
    generated_by: str
    generated_at_utc: str
    paper_trade_mode: bool
    live_trading_enabled: bool
    broker_execution_enabled: bool
    reporting_only: bool
    week_ending: str
    input_files: List[str]
    available_input_files: List[str]
    missing_input_files: List[str]
    weekly_summary: Dict[str, Any]
    top_actions: List[Dict[str, Any]]
    risk_flags: List[str]
    warnings: List[str]
    errors: List[str]
    safety_guarantees: List[str]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read valid JSON from {path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"JSON root in {path} must be an object")
    return data


def _number(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def build_weekly_portfolio_report(root_path: str = ".", week_ending: str = "") -> Dict[str, Any]:
    root = Path(root_path)
    available = [name for name in INPUT_FILES if (root / name).exists()]
    missing = [name for name in INPUT_FILES if name not in available]
    payloads = {name: _read_json(root / name) for name in available}

    command = payloads.get("daily_portfolio_command_center.json", {})
    lifecycle = payloads.get("portfolio_lifecycle_report.json", {})
    reinvestment = payloads.get("income_reinvestment_report.json", {})
    rebalance = payloads.get("portfolio_rebalance_report.json", {})

    lifecycle_actions = lifecycle.get("lifecycle_actions", []) if isinstance(lifecycle.get("lifecycle_actions", []), list) else []
    top_actions = []
    for action in lifecycle_actions:
        if isinstance(action, dict):
            top_actions.append({
                "symbol": action.get("symbol", "UNKNOWN"),
                "rank": action.get("current_rank", "F"),
                "score": _number(action.get("master_score", 0)),
                "action": action.get("lifecycle_action", "NO_ACTION"),
                "reason": action.get("reason", []),
            })
    top_actions.sort(key=lambda row: (-row["score"], row["symbol"]))

    summary = asdict(WeeklyPortfolioSummary(
        portfolio_value=_number(lifecycle.get("portfolio_value", command.get("portfolio_value", 0))),
        cash_balance=_number(lifecycle.get("cash_balance", command.get("cash_balance", 0))),
        cash_reserve_target=_number(lifecycle.get("cash_reserve_target_dollars", command.get("cash_reserve_target_dollars", 0))),
        expected_monthly_income=_number(lifecycle.get("income_summary", {}).get("expected_monthly_income", 0)) if isinstance(lifecycle.get("income_summary", {}), dict) else 0.0,
        expected_annual_income=_number(lifecycle.get("income_summary", {}).get("expected_annual_income", 0)) if isinstance(lifecycle.get("income_summary", {}), dict) else 0.0,
        holdings_count=int(_number(lifecycle.get("holdings_reviewed", 0))),
        increase_count=sum(1 for item in lifecycle_actions if isinstance(item, dict) and item.get("lifecycle_action") == "INCREASE"),
        hold_count=sum(1 for item in lifecycle_actions if isinstance(item, dict) and item.get("lifecycle_action") == "HOLD"),
        exit_count=sum(1 for item in lifecycle_actions if isinstance(item, dict) and item.get("lifecycle_action") == "EXIT_TO_SGOV"),
        reinvestment_action_count=int(_number(reinvestment.get("action_count", 0))),
        rebalance_action_count=int(_number(rebalance.get("action_count", 0))),
    ))

    risk_flags: List[str] = []
    if summary["exit_count"] > 0:
        risk_flags.append("One or more holdings have exit-to-SGOV recommendations.")
    if summary["cash_balance"] < summary["cash_reserve_target"]:
        risk_flags.append("Cash balance is below the current reserve target.")

    warnings = []
    if missing:
        warnings.append("One or more optional weekly input files are missing.")
    if not available:
        warnings.append("No weekly inputs were available; generated a valid empty report.")

    report = asdict(WeeklyPortfolioReport(
        module_name=MODULE_NAME,
        module_version=MODULE_VERSION,
        schema_version=SCHEMA_VERSION,
        generated_by=GENERATED_BY,
        generated_at_utc=_now(),
        paper_trade_mode=True,
        live_trading_enabled=False,
        broker_execution_enabled=False,
        reporting_only=True,
        week_ending=week_ending or datetime.now(timezone.utc).date().isoformat(),
        input_files=list(INPUT_FILES),
        available_input_files=available,
        missing_input_files=missing,
        weekly_summary=summary,
        top_actions=top_actions,
        risk_flags=risk_flags,
        warnings=warnings,
        errors=[],
        safety_guarantees=list(SAFETY_GUARANTEES),
    ))
    validate_weekly_portfolio_report(report)
    return report


def validate_weekly_portfolio_report(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    for field_name in REPORT_REQUIRED_FIELDS:
        if field_name not in payload:
            raise ValueError(f"missing required field: {field_name}")
    for key, expected in {
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "reporting_only": True,
    }.items():
        if payload[key] is not expected:
            raise ValueError(f"{key} must be {expected}")
    if payload["input_files"] != INPUT_FILES:
        raise ValueError("input_files must match approved list")
    if not isinstance(payload["weekly_summary"], Mapping):
        raise ValueError("weekly_summary must be a mapping")
    for field_name in SUMMARY_FIELDS:
        if field_name not in payload["weekly_summary"]:
            raise ValueError(f"weekly_summary missing field: {field_name}")
    for list_name in ["available_input_files", "missing_input_files", "top_actions", "risk_flags", "warnings", "errors", "safety_guarantees"]:
        if not isinstance(payload[list_name], list):
            raise ValueError(f"{list_name} must be a list")
    return True


def write_weekly_portfolio_report_json(path: str = "weekly_portfolio_report.json", root_path: str = ".") -> Dict[str, Any]:
    payload = build_weekly_portfolio_report(root_path=root_path)
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_weekly_portfolio_report_json(path: str = "weekly_portfolio_report.json") -> Dict[str, Any]:
    payload = _read_json(Path(path))
    validate_weekly_portfolio_report(payload)
    return payload


def write_weekly_portfolio_report_csv(path: str = "weekly_portfolio_report.csv", root_path: str = ".") -> Dict[str, Any]:
    payload = build_weekly_portfolio_report(root_path=root_path)
    fields = ["symbol", "rank", "score", "action", "reason"]
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in payload["top_actions"]:
            writer.writerow({name: row.get(name, "") for name in fields})
    return payload


def format_weekly_portfolio_report_markdown(payload: Mapping[str, Any]) -> str:
    validate_weekly_portfolio_report(payload)
    summary = payload["weekly_summary"]
    lines = [
        "# Weekly Portfolio Report",
        "",
        f"- Week Ending: {payload['week_ending']}",
        f"- Portfolio Value: ${summary['portfolio_value']:.2f}",
        f"- Cash Balance: ${summary['cash_balance']:.2f}",
        f"- Cash Reserve Target: ${summary['cash_reserve_target']:.2f}",
        f"- Expected Monthly Income: ${summary['expected_monthly_income']:.2f}",
        f"- Expected Annual Income: ${summary['expected_annual_income']:.2f}",
        "",
        "## Weekly Actions",
        "",
        "| Symbol | Rank | Score | Action |",
        "|---|---|---:|---|",
    ]
    if payload["top_actions"]:
        for row in payload["top_actions"]:
            lines.append(f"| {row['symbol']} | {row['rank']} | {row['score']} | {row['action']} |")
    else:
        lines.append("| None |  |  |  |")
    lines.extend(["", "## Risk Flags"])
    lines.extend([f"- {item}" for item in payload["risk_flags"]] or ["- None"])
    lines.extend(["", "## Safety Guarantees"])
    lines.extend(f"- {item}" for item in payload["safety_guarantees"])
    return "\n".join(lines) + "\n"


def write_weekly_portfolio_report_markdown(path: str = "weekly_portfolio_report.md", root_path: str = ".") -> Dict[str, Any]:
    payload = build_weekly_portfolio_report(root_path=root_path)
    Path(path).write_text(format_weekly_portfolio_report_markdown(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    write_weekly_portfolio_report_json()
    write_weekly_portfolio_report_csv()
    write_weekly_portfolio_report_markdown()
