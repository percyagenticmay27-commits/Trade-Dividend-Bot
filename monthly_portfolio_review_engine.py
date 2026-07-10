"""Monthly Portfolio Review Engine for the Dividend Bot.

Aggregates monthly paper-only portfolio results, income, strategy analytics,
rebalances, winners, losers, and next-month recommendations. No trading occurs.
"""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

MODULE_NAME = "monthly_portfolio_review_engine"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"
BOT_NAME = "Agentic Robin Dividend Bot"
BOT_TYPE = "paper_dividend_etf_management"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

STATUS_STRONG = "STRONG_MONTH"
STATUS_POSITIVE = "POSITIVE_MONTH"
STATUS_FLAT = "FLAT_MONTH"
STATUS_WEAK = "WEAK_MONTH"
STATUS_UNKNOWN = "UNKNOWN"
SUPPORTED_MONTH_STATUSES = [STATUS_STRONG, STATUS_POSITIVE, STATUS_FLAT, STATUS_WEAK, STATUS_UNKNOWN]
SAFETY_GUARANTEES = [
    "paper_trade_mode is enforced as True",
    "reporting_only is enforced as True",
    "live_trading_enabled is enforced as False",
    "broker_execution_enabled is enforced as False",
    "no brokerage execution is performed",
    "no Robinhood execution is performed",
    "no order placement is performed",
    "read-only monthly aggregation only",
]
SUMMARY_FIELDS = ["symbol", "monthly_return_pct", "income_received", "ending_value", "status"]
REPORT_REQUIRED_FIELDS = [
    "bot_name", "bot_type", "module_name", "module_version", "schema_version", "generated_by",
    "generated_at_utc", "paper_trade_mode", "live_trading_enabled", "broker_execution_enabled",
    "reporting_only", "month_status", "executive_summary", "starting_portfolio_value",
    "ending_portfolio_value", "capital_appreciation", "monthly_return_pct", "dividend_income",
    "monthly_total_return", "expected_monthly_income", "expected_annual_income", "cash_balance",
    "cash_reserve_target_dollars", "market_regime", "best_performers", "worst_performers",
    "strategy_summary", "rebalance_summary", "income_summary", "next_month_actions", "risk_flags",
    "warnings", "errors", "safety_guarantees",
]

@dataclass(frozen=True)
class MonthlyHoldingPerformance:
    symbol: str
    monthly_return_pct: float = 0.0
    income_received: float = 0.0
    ending_value: float = 0.0
    status: str = "FLAT"

@dataclass(frozen=True)
class MonthlyPortfolioReviewReport:
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
    month_status: str
    executive_summary: str
    starting_portfolio_value: float
    ending_portfolio_value: float
    capital_appreciation: float
    monthly_return_pct: float
    dividend_income: float
    monthly_total_return: float
    expected_monthly_income: float
    expected_annual_income: float
    cash_balance: float
    cash_reserve_target_dollars: float
    market_regime: str
    best_performers: List[Dict[str, Any]]
    worst_performers: List[Dict[str, Any]]
    strategy_summary: Dict[str, Any]
    rebalance_summary: Dict[str, Any]
    income_summary: Dict[str, Any]
    next_month_actions: List[str]
    risk_flags: List[str]
    warnings: List[str]
    errors: List[str]
    safety_guarantees: List[str]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _num(value: Any, default: float = 0.0) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else default


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def classify_month_status(monthly_return_pct: float) -> str:
    if monthly_return_pct >= 5:
        return STATUS_STRONG
    if monthly_return_pct > 0:
        return STATUS_POSITIVE
    if monthly_return_pct == 0:
        return STATUS_FLAT
    return STATUS_WEAK


def summarize_holding_performance(holdings: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for raw in holdings:
        if not isinstance(raw, Mapping):
            continue
        symbol = str(raw.get("symbol", "UNKNOWN")).strip().upper() or "UNKNOWN"
        ret = _num(raw.get("monthly_return_pct", raw.get("return_pct", 0)))
        income = max(0.0, _num(raw.get("income_received", 0)))
        ending = max(0.0, _num(raw.get("ending_value", 0)))
        status = "WINNER" if ret > 0 else "LOSER" if ret < 0 else "FLAT"
        rows.append(asdict(MonthlyHoldingPerformance(symbol, ret, income, ending, status)))
    rows.sort(key=lambda row: (-row["monthly_return_pct"], row["symbol"]))
    return rows


def build_monthly_portfolio_review(
    daily_command_center: Optional[Mapping[str, Any]] = None,
    weekly_review: Optional[Mapping[str, Any]] = None,
    strategy_analytics: Optional[Mapping[str, Any]] = None,
    holdings_performance: Optional[Iterable[Mapping[str, Any]]] = None,
    starting_portfolio_value: float = 0.0,
    ending_portfolio_value: float = 0.0,
    dividend_income: float = 0.0,
) -> Dict[str, Any]:
    daily = _mapping(daily_command_center)
    weekly = _mapping(weekly_review)
    strategy = _mapping(strategy_analytics)
    starting = max(0.0, _num(starting_portfolio_value))
    ending = max(0.0, _num(ending_portfolio_value, _num(daily.get("portfolio_value", 0))))
    income = max(0.0, _num(dividend_income))
    appreciation = round(ending - starting, 2)
    monthly_return = round(((ending - starting) / starting) * 100, 2) if starting > 0 else 0.0
    total_return = round(appreciation + income, 2)
    performance = summarize_holding_performance(list(holdings_performance or []))
    best = performance[:5]
    worst = sorted(performance, key=lambda row: (row["monthly_return_pct"], row["symbol"]))[:5]
    status = classify_month_status(monthly_return)
    risk_flags = sorted(set(str(x) for source in [daily, weekly, strategy] for x in source.get("risk_flags", []) if isinstance(x, str) and x.strip()))
    if status == STATUS_WEAK:
        summary = "Monthly performance was negative. Review sale signals, reserve levels, and merit rankings before reallocating capital."
    elif status in [STATUS_STRONG, STATUS_POSITIVE]:
        summary = "Monthly performance was positive. Preserve strong holdings, reinvest income, and allocate new cash by merit rank."
    else:
        summary = "Monthly performance was flat. Maintain discipline and wait for stronger income-plus-growth opportunities."
    actions = []
    if risk_flags:
        actions.append("Review unresolved portfolio risk flags.")
    if income > 0:
        actions.append("Apply self-funding reinvestment rules to monthly distributions.")
    if not actions:
        actions.append("Continue monitoring rankings, income growth, and SGOV reserve targets.")
    payload = asdict(MonthlyPortfolioReviewReport(
        BOT_NAME, BOT_TYPE, MODULE_NAME, MODULE_VERSION, SCHEMA_VERSION, GENERATED_BY, _now(),
        True, False, False, True, status, summary, starting, ending, appreciation, monthly_return,
        income, total_return, _num(daily.get("expected_monthly_income", 0)),
        _num(daily.get("expected_annual_income", 0)), _num(daily.get("cash_balance", 0)),
        _num(daily.get("cash_reserve_target_dollars", 0)), str(daily.get("market_regime", "UNKNOWN")),
        best, worst, dict(strategy), dict(weekly.get("rebalance_summary", {})) if isinstance(weekly.get("rebalance_summary", {}), Mapping) else {},
        {"dividend_income": income, "expected_monthly_income": _num(daily.get("expected_monthly_income", 0)), "expected_annual_income": _num(daily.get("expected_annual_income", 0))},
        actions, risk_flags, [], [], SAFETY_GUARANTEES,
    ))
    validate_monthly_portfolio_review(payload)
    return payload


def validate_monthly_portfolio_review(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    for field_name in REPORT_REQUIRED_FIELDS:
        if field_name not in payload:
            raise ValueError(f"missing required field: {field_name}")
    for field_name, expected in {"paper_trade_mode": True, "live_trading_enabled": False, "broker_execution_enabled": False, "reporting_only": True}.items():
        if payload[field_name] is not expected:
            raise ValueError(f"{field_name} must be {expected}")
    if payload["month_status"] not in SUPPORTED_MONTH_STATUSES:
        raise ValueError("unsupported month_status")
    for numeric in ["starting_portfolio_value", "ending_portfolio_value", "capital_appreciation", "monthly_return_pct", "dividend_income", "monthly_total_return", "expected_monthly_income", "expected_annual_income", "cash_balance", "cash_reserve_target_dollars"]:
        if isinstance(payload[numeric], bool) or not isinstance(payload[numeric], (int, float)):
            raise ValueError(f"{numeric} must be numeric")
    for list_field in ["best_performers", "worst_performers", "next_month_actions", "risk_flags", "warnings", "errors", "safety_guarantees"]:
        if not isinstance(payload[list_field], list):
            raise ValueError(f"{list_field} must be a list")
    for map_field in ["strategy_summary", "rebalance_summary", "income_summary"]:
        if not isinstance(payload[map_field], Mapping):
            raise ValueError(f"{map_field} must be a mapping")
    return True


def write_monthly_portfolio_review_json(path: str = "monthly_portfolio_review.json") -> Dict[str, Any]:
    payload = build_monthly_portfolio_review()
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_monthly_portfolio_review_json(path: str = "monthly_portfolio_review.json") -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_monthly_portfolio_review(payload)
    return payload


def write_monthly_portfolio_review_csv(path: str = "monthly_portfolio_review.csv") -> Dict[str, Any]:
    payload = build_monthly_portfolio_review()
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        for row in payload["best_performers"] + payload["worst_performers"]:
            writer.writerow({field: row.get(field, "") for field in SUMMARY_FIELDS})
    return payload


def format_monthly_portfolio_review_markdown(payload: Mapping[str, Any]) -> str:
    validate_monthly_portfolio_review(payload)
    lines = [
        "# Monthly Portfolio Review", "",
        f"- Month Status: {payload['month_status']}",
        f"- Starting Value: ${payload['starting_portfolio_value']:.2f}",
        f"- Ending Value: ${payload['ending_portfolio_value']:.2f}",
        f"- Monthly Return: {payload['monthly_return_pct']:.2f}%",
        f"- Dividend Income: ${payload['dividend_income']:.2f}",
        f"- Monthly Total Return: ${payload['monthly_total_return']:.2f}",
        "", "## Executive Summary", payload["executive_summary"], "", "## Best Performers",
    ]
    lines.extend(f"- {row['symbol']}: {row['monthly_return_pct']:.2f}%" for row in payload["best_performers"]) or lines.append("- None")
    lines += ["", "## Worst Performers"]
    lines.extend(f"- {row['symbol']}: {row['monthly_return_pct']:.2f}%" for row in payload["worst_performers"]) or lines.append("- None")
    lines += ["", "## Next Month Actions"] + [f"- {x}" for x in payload["next_month_actions"]]
    lines += ["", "## Safety Guarantees"] + [f"- {x}" for x in payload["safety_guarantees"]]
    return "\n".join(lines) + "\n"


def write_monthly_portfolio_review_markdown(path: str = "monthly_portfolio_review.md") -> Dict[str, Any]:
    payload = build_monthly_portfolio_review()
    Path(path).write_text(format_monthly_portfolio_review_markdown(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    write_monthly_portfolio_review_json()
    write_monthly_portfolio_review_csv()
    write_monthly_portfolio_review_markdown()
