"""
Daily Portfolio Command Center for the Dividend Bot.

Consolidates existing paper-only engine outputs into one executive daily report.
Missing optional inputs produce warnings rather than failures. No trading,
brokerage, Robinhood, subprocess, network, or order-placement behavior exists.
"""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

MODULE_NAME = "daily_portfolio_command_center"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"
BOT_NAME = "Agentic Robin Dividend Bot"
BOT_TYPE = "paper_dividend_etf_management"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

STATUS_HEALTHY = "HEALTHY"
STATUS_ATTENTION = "ATTENTION"
STATUS_CRITICAL = "CRITICAL"
STATUS_UNKNOWN = "UNKNOWN"
SUPPORTED_PORTFOLIO_STATUSES = [STATUS_HEALTHY, STATUS_ATTENTION, STATUS_CRITICAL, STATUS_UNKNOWN]

ACTION_FIELDS = ["symbol", "action", "priority", "score", "reason"]
INPUT_NAMES = [
    "portfolio_lifecycle",
    "income_reinvestment",
    "portfolio_rebalance",
    "portfolio_construction",
    "capital_allocation",
    "portfolio_decision",
    "conviction",
    "entry_score",
    "opportunity_pairing",
    "dividend_ranking",
]
SAFETY_GUARANTEES = [
    "paper_trade_mode is enforced as True",
    "reporting_only is enforced as True",
    "live_trading_enabled is enforced as False",
    "broker_execution_enabled is enforced as False",
    "no brokerage execution is performed",
    "no Robinhood execution is performed",
    "no live trading is performed",
    "no order placement is performed",
    "read-only aggregation only",
]
REPORT_REQUIRED_FIELDS = [
    "bot_name", "bot_type", "module_name", "module_version", "schema_version",
    "generated_by", "generated_at_utc", "paper_trade_mode", "live_trading_enabled",
    "broker_execution_enabled", "reporting_only", "portfolio_status", "portfolio_health_score",
    "executive_recommendation", "portfolio_value", "cash_balance", "cash_reserve_target_dollars",
    "expected_monthly_income", "expected_annual_income", "market_regime", "top_opportunities",
    "increase_actions", "reduce_actions", "exit_actions", "reentry_actions", "reinvestment_actions",
    "pending_reallocations", "watchlist_promotions", "watchlist_demotions", "risk_flags",
    "available_inputs", "missing_inputs", "warnings", "errors", "safety_guarantees",
]


@dataclass(frozen=True)
class CommandCenterAction:
    symbol: str
    action: str
    priority: int = 0
    score: float = 0.0
    reason: str = ""


@dataclass(frozen=True)
class DailyPortfolioCommandCenterReport:
    bot_name: str
    bot_type: str
    module_name: str
    module_version: str
    schema_version: str
    generated_by: str
    generated_at_utc: str
    paper_trade_mode: bool
    live_trading_enabled: bool
    broker_execution_enabled: bool
    reporting_only: bool
    portfolio_status: str
    portfolio_health_score: float
    executive_recommendation: str
    portfolio_value: float
    cash_balance: float
    cash_reserve_target_dollars: float
    expected_monthly_income: float
    expected_annual_income: float
    market_regime: str
    top_opportunities: List[Dict[str, Any]]
    increase_actions: List[Dict[str, Any]]
    reduce_actions: List[Dict[str, Any]]
    exit_actions: List[Dict[str, Any]]
    reentry_actions: List[Dict[str, Any]]
    reinvestment_actions: List[Dict[str, Any]]
    pending_reallocations: List[Dict[str, Any]]
    watchlist_promotions: List[Dict[str, Any]]
    watchlist_demotions: List[Dict[str, Any]]
    risk_flags: List[str]
    available_inputs: List[str]
    missing_inputs: List[str]
    warnings: List[str]
    errors: List[str]
    safety_guarantees: List[str]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _num(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _action(symbol: Any, action: str, priority: int, score: Any, reason: str) -> Dict[str, Any]:
    clean_symbol = symbol.strip().upper() if isinstance(symbol, str) and symbol.strip() else "UNKNOWN"
    return asdict(CommandCenterAction(clean_symbol, action, priority, _num(score), reason))


def _extract_actions(lifecycle: Mapping[str, Any], rebalance: Mapping[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    groups = {"increase": [], "reduce": [], "exit": [], "reentry": [], "pending": []}
    for row in lifecycle.get("lifecycle_actions", []) if isinstance(lifecycle.get("lifecycle_actions", []), list) else []:
        if not isinstance(row, Mapping):
            continue
        action = row.get("lifecycle_action", "")
        item = _action(row.get("symbol"), action, 1, row.get("master_score", 0), "; ".join(row.get("reason", [])) if isinstance(row.get("reason"), list) else str(row.get("reason", "")))
        if action == "INCREASE":
            groups["increase"].append(item)
        elif action == "REDUCE":
            groups["reduce"].append(item)
        elif action == "EXIT_TO_SGOV":
            groups["exit"].append(item)
        elif action == "REENTER":
            groups["reentry"].append(item)
    for row in rebalance.get("rebalance_actions", []) if isinstance(rebalance.get("rebalance_actions", []), list) else []:
        if not isinstance(row, Mapping):
            continue
        action = row.get("recommended_action", "")
        item = _action(row.get("symbol"), action, 1, row.get("master_score", 0), "; ".join(row.get("why", [])) if isinstance(row.get("why"), list) else str(row.get("why", "")))
        if action in ["REALLOCATE_TO_BETTER_OPPORTUNITY", "REDISTRIBUTE_TO_PORTFOLIO", "MOVE_TO_SGOV"]:
            groups["pending"].append(item)
        if action == "REENTER_ORIGINAL":
            groups["reentry"].append(item)
    for key in groups:
        groups[key].sort(key=lambda x: (-x["score"], x["symbol"]))
    return groups


def _extract_top_opportunities(pairing: Mapping[str, Any], ranking: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for source, key, score_key, name_key in [
        (pairing, "opportunities", "combined_score", "opportunity_name"),
        (ranking, "rankings", "overall_score", "symbol"),
    ]:
        values = source.get(key, [])
        if not isinstance(values, list):
            continue
        for row in values:
            if not isinstance(row, Mapping):
                continue
            symbol = row.get("symbol") or row.get("income_symbol") or row.get(name_key) or "UNKNOWN"
            rows.append(_action(symbol, "TOP_OPPORTUNITY", 1, row.get(score_key, 0), str(row.get("recommendation", ""))))
    rows.sort(key=lambda x: (-x["score"], x["symbol"]))
    return rows[:10]


def _calculate_health(risk_flags: List[str], exit_count: int, missing_count: int) -> float:
    score = 100.0 - (len(risk_flags) * 8.0) - (exit_count * 12.0) - (missing_count * 2.0)
    return round(max(0.0, min(100.0, score)), 2)


def _status_from_health(score: float) -> str:
    if score >= 80:
        return STATUS_HEALTHY
    if score >= 50:
        return STATUS_ATTENTION
    return STATUS_CRITICAL


def build_daily_portfolio_command_center(
    portfolio_lifecycle: Optional[Mapping[str, Any]] = None,
    income_reinvestment: Optional[Mapping[str, Any]] = None,
    portfolio_rebalance: Optional[Mapping[str, Any]] = None,
    portfolio_construction: Optional[Mapping[str, Any]] = None,
    capital_allocation: Optional[Mapping[str, Any]] = None,
    portfolio_decision: Optional[Mapping[str, Any]] = None,
    conviction: Optional[Mapping[str, Any]] = None,
    entry_score: Optional[Mapping[str, Any]] = None,
    opportunity_pairing: Optional[Mapping[str, Any]] = None,
    dividend_ranking: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    inputs = {
        "portfolio_lifecycle": _mapping(portfolio_lifecycle),
        "income_reinvestment": _mapping(income_reinvestment),
        "portfolio_rebalance": _mapping(portfolio_rebalance),
        "portfolio_construction": _mapping(portfolio_construction),
        "capital_allocation": _mapping(capital_allocation),
        "portfolio_decision": _mapping(portfolio_decision),
        "conviction": _mapping(conviction),
        "entry_score": _mapping(entry_score),
        "opportunity_pairing": _mapping(opportunity_pairing),
        "dividend_ranking": _mapping(dividend_ranking),
    }
    available = [name for name, value in inputs.items() if value]
    missing = [name for name in INPUT_NAMES if name not in available]
    lifecycle = inputs["portfolio_lifecycle"]
    reinvestment = inputs["income_reinvestment"]
    rebalance = inputs["portfolio_rebalance"]
    construction = inputs["portfolio_construction"]
    allocation = inputs["capital_allocation"]
    actions = _extract_actions(lifecycle, rebalance)
    reinvestment_actions = reinvestment.get("reinvestment_actions", []) if isinstance(reinvestment.get("reinvestment_actions", []), list) else []
    risk_flags: List[str] = []
    for source in [lifecycle, reinvestment, rebalance, construction, allocation, inputs["portfolio_decision"], inputs["conviction"], inputs["entry_score"]]:
        values = source.get("risk_flags", [])
        if isinstance(values, list):
            risk_flags.extend(str(v) for v in values if isinstance(v, str) and v.strip())
        if source.get("risk_status") in ["WARNING", "ERROR"]:
            risk_flags.append(f"risk_status={source.get('risk_status')}")
    risk_flags = sorted(set(risk_flags))
    portfolio_value = _num(lifecycle.get("portfolio_value", allocation.get("current_portfolio_value", construction.get("portfolio_value", 0))))
    cash_balance = _num(lifecycle.get("cash_balance", reinvestment.get("cash_balance", allocation.get("available_cash", 0))))
    reserve = _num(lifecycle.get("cash_reserve_target_dollars", reinvestment.get("cash_reserve_target_dollars", allocation.get("cash_reserve_target_dollars", 0))))
    monthly = _num(_mapping(lifecycle.get("income_summary")).get("expected_monthly_income", 0))
    annual = _num(_mapping(lifecycle.get("income_summary")).get("expected_annual_income", 0))
    market_regime = str(lifecycle.get("market_regime", rebalance.get("market_regime", "UNKNOWN")))
    health = _calculate_health(risk_flags, len(actions["exit"]), len(missing))
    status = _status_from_health(health)
    if actions["exit"]:
        recommendation = "Review exit signals and stage released capital in SGOV before re-entry or reassignment."
    elif actions["increase"]:
        recommendation = "Maintain current holdings and direct eligible new cash toward the strongest merit-ranked positions."
    else:
        recommendation = "Maintain the paper portfolio and continue monitoring rankings, income, and reserve levels."
    warnings = []
    if missing:
        warnings.append("Optional command-center inputs are missing; available inputs were aggregated without failure.")
    payload = asdict(DailyPortfolioCommandCenterReport(
        BOT_NAME, BOT_TYPE, MODULE_NAME, MODULE_VERSION, SCHEMA_VERSION, GENERATED_BY, _now(),
        True, False, False, True, status, health, recommendation, portfolio_value,
        cash_balance, reserve, monthly, annual, market_regime,
        _extract_top_opportunities(inputs["opportunity_pairing"], inputs["dividend_ranking"]),
        actions["increase"], actions["reduce"], actions["exit"], actions["reentry"],
        [dict(x) for x in reinvestment_actions if isinstance(x, Mapping)], actions["pending"],
        [], [], risk_flags, available, missing, warnings, [], SAFETY_GUARANTEES,
    ))
    validate_daily_portfolio_command_center(payload)
    return payload


def validate_daily_portfolio_command_center(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    for field_name in REPORT_REQUIRED_FIELDS:
        if field_name not in payload:
            raise ValueError(f"missing required field: {field_name}")
    for field_name, expected in {
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "reporting_only": True,
    }.items():
        if payload[field_name] is not expected:
            raise ValueError(f"{field_name} must be {expected}")
    if payload["portfolio_status"] not in SUPPORTED_PORTFOLIO_STATUSES:
        raise ValueError("unsupported portfolio_status")
    for numeric in ["portfolio_health_score", "portfolio_value", "cash_balance", "cash_reserve_target_dollars", "expected_monthly_income", "expected_annual_income"]:
        if isinstance(payload[numeric], bool) or not isinstance(payload[numeric], (int, float)) or payload[numeric] < 0:
            raise ValueError(f"{numeric} must be a non-negative number")
    for list_name in [
        "top_opportunities", "increase_actions", "reduce_actions", "exit_actions", "reentry_actions",
        "reinvestment_actions", "pending_reallocations", "watchlist_promotions", "watchlist_demotions",
        "risk_flags", "available_inputs", "missing_inputs", "warnings", "errors", "safety_guarantees",
    ]:
        if not isinstance(payload[list_name], list):
            raise ValueError(f"{list_name} must be a list")
    return True


def write_daily_portfolio_command_center_json(path: str = "daily_portfolio_command_center.json") -> Dict[str, Any]:
    payload = build_daily_portfolio_command_center()
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_daily_portfolio_command_center_json(path: str = "daily_portfolio_command_center.json") -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_daily_portfolio_command_center(payload)
    return payload


def write_daily_portfolio_command_center_csv(path: str = "daily_portfolio_command_center.csv") -> Dict[str, Any]:
    payload = build_daily_portfolio_command_center()
    rows: List[Dict[str, Any]] = []
    for category in ["increase_actions", "reduce_actions", "exit_actions", "reentry_actions", "pending_reallocations", "top_opportunities"]:
        for row in payload[category]:
            rows.append({"category": category, **{field: row.get(field, "") for field in ACTION_FIELDS}})
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["category"] + ACTION_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return payload


def format_daily_portfolio_command_center_markdown(payload: Mapping[str, Any]) -> str:
    validate_daily_portfolio_command_center(payload)
    lines = [
        "# Daily Portfolio Command Center",
        "",
        f"- Portfolio Status: {payload['portfolio_status']}",
        f"- Portfolio Health Score: {payload['portfolio_health_score']}",
        f"- Portfolio Value: ${payload['portfolio_value']:.2f}",
        f"- Cash Balance: ${payload['cash_balance']:.2f}",
        f"- Cash Reserve Target: ${payload['cash_reserve_target_dollars']:.2f}",
        f"- Expected Monthly Income: ${payload['expected_monthly_income']:.2f}",
        f"- Expected Annual Income: ${payload['expected_annual_income']:.2f}",
        f"- Market Regime: {payload['market_regime']}",
        "",
        "## Executive Recommendation",
        payload["executive_recommendation"],
        "",
    ]
    for title, key in [
        ("Top Opportunities", "top_opportunities"),
        ("Increase Actions", "increase_actions"),
        ("Reduce Actions", "reduce_actions"),
        ("Exit Actions", "exit_actions"),
        ("Re-entry Actions", "reentry_actions"),
        ("Pending Reallocations", "pending_reallocations"),
    ]:
        lines += [f"## {title}", "", "| Symbol | Action | Score | Reason |", "|---|---|---:|---|"]
        rows = payload[key]
        if rows:
            for row in rows:
                lines.append(f"| {row.get('symbol','')} | {row.get('action','')} | {row.get('score',0)} | {row.get('reason','')} |")
        else:
            lines.append("| None |  |  |  |")
        lines.append("")
    lines += ["## Risk Flags"] + ([f"- {x}" for x in payload["risk_flags"]] or ["- None"])
    lines += ["", "## Safety Guarantees"] + [f"- {x}" for x in payload["safety_guarantees"]]
    return "\n".join(lines) + "\n"


def write_daily_portfolio_command_center_markdown(path: str = "daily_portfolio_command_center.md") -> Dict[str, Any]:
    payload = build_daily_portfolio_command_center()
    Path(path).write_text(format_daily_portfolio_command_center_markdown(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    write_daily_portfolio_command_center_json()
    write_daily_portfolio_command_center_csv()
    write_daily_portfolio_command_center_markdown()
