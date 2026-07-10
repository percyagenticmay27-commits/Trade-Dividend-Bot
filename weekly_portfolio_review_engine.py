"""
Weekly Portfolio Review Engine for the Dividend Bot.

Aggregates daily command-center reports into one paper-only weekly review.
Missing daily reports are warnings, not failures. No brokerage, order placement,
network access, or runtime workflow mutation is performed.
"""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

MODULE_NAME = "weekly_portfolio_review_engine"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"
BOT_NAME = "Agentic Robin Dividend Bot"
BOT_TYPE = "paper_dividend_etf_management"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

STATUS_IMPROVING = "IMPROVING"
STATUS_STABLE = "STABLE"
STATUS_WEAKENING = "WEAKENING"
STATUS_CRITICAL = "CRITICAL"
STATUS_UNKNOWN = "UNKNOWN"
SUPPORTED_WEEKLY_STATUSES = [STATUS_IMPROVING, STATUS_STABLE, STATUS_WEAKENING, STATUS_CRITICAL, STATUS_UNKNOWN]

ACTION_FIELDS = ["symbol", "action", "score", "occurrences", "reason"]
SAFETY_GUARANTEES = [
    "paper_trade_mode is enforced as True",
    "reporting_only is enforced as True",
    "live_trading_enabled is enforced as False",
    "broker_execution_enabled is enforced as False",
    "no brokerage execution is performed",
    "no Robinhood execution is performed",
    "no live trading is performed",
    "no order placement is performed",
    "read-only weekly aggregation only",
]

REPORT_REQUIRED_FIELDS = [
    "bot_name", "bot_type", "module_name", "module_version", "schema_version",
    "generated_by", "generated_at_utc", "paper_trade_mode", "live_trading_enabled",
    "broker_execution_enabled", "reporting_only", "weekly_status", "weekly_health_score",
    "executive_summary", "days_reviewed", "missing_days", "starting_portfolio_value",
    "ending_portfolio_value", "portfolio_value_change", "portfolio_value_change_pct",
    "starting_monthly_income", "ending_monthly_income", "monthly_income_change",
    "starting_annual_income", "ending_annual_income", "annual_income_change",
    "average_cash_balance", "average_cash_reserve_target", "market_regime_summary",
    "top_opportunities", "increase_actions", "reduce_actions", "exit_actions",
    "reentry_actions", "reinvestment_actions", "pending_reallocations",
    "watchlist_promotions", "watchlist_demotions", "risk_flags", "action_items",
    "warnings", "errors", "safety_guarantees",
]


@dataclass(frozen=True)
class WeeklyReviewAction:
    symbol: str
    action: str
    score: float = 0.0
    occurrences: int = 1
    reason: str = ""


@dataclass(frozen=True)
class WeeklyPortfolioReviewReport:
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
    weekly_status: str
    weekly_health_score: float
    executive_summary: str
    days_reviewed: int
    missing_days: int
    starting_portfolio_value: float
    ending_portfolio_value: float
    portfolio_value_change: float
    portfolio_value_change_pct: float
    starting_monthly_income: float
    ending_monthly_income: float
    monthly_income_change: float
    starting_annual_income: float
    ending_annual_income: float
    annual_income_change: float
    average_cash_balance: float
    average_cash_reserve_target: float
    market_regime_summary: Dict[str, int]
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
    action_items: List[str]
    warnings: List[str]
    errors: List[str]
    safety_guarantees: List[str]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _num(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value)


def _normalize_reports(reports: Iterable[Mapping[str, Any]] | None) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in list(reports or []):
        if isinstance(item, Mapping):
            rows.append(dict(item))
    return rows


def _aggregate_actions(reports: List[Mapping[str, Any]], field_name: str) -> List[Dict[str, Any]]:
    grouped: Dict[tuple[str, str], Dict[str, Any]] = {}
    for report in reports:
        values = report.get(field_name, [])
        if not isinstance(values, list):
            continue
        for row in values:
            if not isinstance(row, Mapping):
                continue
            symbol = str(row.get("symbol", "UNKNOWN")).strip().upper() or "UNKNOWN"
            action = str(row.get("action", row.get("lifecycle_action", field_name))).strip() or field_name
            key = (symbol, action)
            score = _num(row.get("score", row.get("master_score", 0)))
            reason = str(row.get("reason", row.get("why", "")))
            if isinstance(row.get("reason"), list):
                reason = "; ".join(str(x) for x in row["reason"])
            current = grouped.get(key)
            if current is None:
                grouped[key] = asdict(WeeklyReviewAction(symbol, action, score, 1, reason))
            else:
                current["occurrences"] += 1
                current["score"] = max(current["score"], score)
                if reason and reason not in current["reason"]:
                    current["reason"] = (current["reason"] + "; " + reason).strip("; ")
    result = list(grouped.values())
    result.sort(key=lambda x: (-x["score"], -x["occurrences"], x["symbol"]))
    return result


def _aggregate_regimes(reports: List[Mapping[str, Any]]) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for report in reports:
        regime = str(report.get("market_regime", "UNKNOWN"))
        result[regime] = result.get(regime, 0) + 1
    return dict(sorted(result.items()))


def _weekly_status(start_value: float, end_value: float, start_income: float, end_income: float, risk_count: int, exit_count: int) -> str:
    if risk_count >= 5 or exit_count >= 3:
        return STATUS_CRITICAL
    value_delta = end_value - start_value
    income_delta = end_income - start_income
    if value_delta > 0 and income_delta >= 0:
        return STATUS_IMPROVING
    if value_delta < 0 or income_delta < 0:
        return STATUS_WEAKENING
    return STATUS_STABLE


def _health_score(reports: List[Mapping[str, Any]], risk_count: int, exit_count: int, missing_days: int) -> float:
    if not reports:
        return 0.0
    daily_scores = [_num(r.get("portfolio_health_score", 0)) for r in reports]
    base = sum(daily_scores) / len(daily_scores)
    score = base - risk_count * 2.0 - exit_count * 4.0 - missing_days * 2.0
    return round(max(0.0, min(100.0, score)), 2)


def build_weekly_portfolio_review(
    daily_reports: Iterable[Mapping[str, Any]] | None = None,
    expected_days: int = 5,
) -> Dict[str, Any]:
    if expected_days <= 0:
        raise ValueError("expected_days must be positive")
    reports = _normalize_reports(daily_reports)
    missing_days = max(0, expected_days - len(reports))

    first = reports[0] if reports else {}
    last = reports[-1] if reports else {}
    start_value = _num(first.get("portfolio_value", 0))
    end_value = _num(last.get("portfolio_value", 0))
    value_change = round(end_value - start_value, 2)
    value_change_pct = round(value_change / start_value, 4) if start_value > 0 else 0.0
    start_monthly = _num(first.get("expected_monthly_income", 0))
    end_monthly = _num(last.get("expected_monthly_income", 0))
    start_annual = _num(first.get("expected_annual_income", 0))
    end_annual = _num(last.get("expected_annual_income", 0))

    cash_values = [_num(r.get("cash_balance", 0)) for r in reports]
    reserve_values = [_num(r.get("cash_reserve_target_dollars", 0)) for r in reports]
    avg_cash = round(sum(cash_values) / len(cash_values), 2) if cash_values else 0.0
    avg_reserve = round(sum(reserve_values) / len(reserve_values), 2) if reserve_values else 0.0

    increase = _aggregate_actions(reports, "increase_actions")
    reduce = _aggregate_actions(reports, "reduce_actions")
    exits = _aggregate_actions(reports, "exit_actions")
    reentry = _aggregate_actions(reports, "reentry_actions")
    reinvestment = _aggregate_actions(reports, "reinvestment_actions")
    pending = _aggregate_actions(reports, "pending_reallocations")
    promotions = _aggregate_actions(reports, "watchlist_promotions")
    demotions = _aggregate_actions(reports, "watchlist_demotions")
    top = _aggregate_actions(reports, "top_opportunities")[:10]

    risk_flags = sorted({str(flag) for report in reports for flag in report.get("risk_flags", []) if isinstance(flag, str) and flag.strip()})
    status = _weekly_status(start_value, end_value, start_monthly, end_monthly, len(risk_flags), len(exits)) if reports else STATUS_UNKNOWN
    health = _health_score(reports, len(risk_flags), len(exits), missing_days)

    action_items: List[str] = []
    if exits:
        action_items.append("Review exit signals and confirm SGOV staging before reassignment.")
    if pending:
        action_items.append("Review pending reallocations and enforce the minimum improvement threshold.")
    if increase:
        action_items.append("Direct eligible new cash toward the strongest merit-ranked holdings.")
    if reinvestment:
        action_items.append("Confirm weekly distributions followed self-funding reinvestment rules.")
    if not action_items:
        action_items.append("Maintain current allocations and continue monitoring scores, income, and reserve levels.")

    if status == STATUS_IMPROVING:
        summary = "Portfolio value and income trend improved or remained supportive during the review period."
    elif status == STATUS_WEAKENING:
        summary = "Portfolio value or income trend weakened; review risk flags and sale-signal conditions."
    elif status == STATUS_CRITICAL:
        summary = "Multiple risk or exit conditions require immediate paper-only portfolio review."
    elif status == STATUS_STABLE:
        summary = "Portfolio remained stable during the review period."
    else:
        summary = "Insufficient daily reports were available to establish a weekly trend."

    warnings: List[str] = []
    if missing_days:
        warnings.append("One or more expected daily command-center reports are missing.")
    if not reports:
        warnings.append("No daily reports supplied; generated valid empty weekly review.")

    payload = asdict(WeeklyPortfolioReviewReport(
        BOT_NAME, BOT_TYPE, MODULE_NAME, MODULE_VERSION, SCHEMA_VERSION, GENERATED_BY, _now(),
        True, False, False, True, status, health, summary, len(reports), missing_days,
        start_value, end_value, value_change, value_change_pct,
        start_monthly, end_monthly, round(end_monthly - start_monthly, 2),
        start_annual, end_annual, round(end_annual - start_annual, 2),
        avg_cash, avg_reserve, _aggregate_regimes(reports), top, increase, reduce, exits,
        reentry, reinvestment, pending, promotions, demotions, risk_flags, action_items,
        warnings, [], SAFETY_GUARANTEES,
    ))
    validate_weekly_portfolio_review(payload)
    return payload


def validate_weekly_portfolio_review(payload: Any) -> bool:
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
    if payload["weekly_status"] not in SUPPORTED_WEEKLY_STATUSES:
        raise ValueError("unsupported weekly_status")
    numeric_fields = [
        "weekly_health_score", "starting_portfolio_value", "ending_portfolio_value",
        "starting_monthly_income", "ending_monthly_income", "starting_annual_income",
        "ending_annual_income", "average_cash_balance", "average_cash_reserve_target",
    ]
    for field_name in numeric_fields:
        value = payload[field_name]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise ValueError(f"{field_name} must be a non-negative number")
    for field_name in ["days_reviewed", "missing_days"]:
        if isinstance(payload[field_name], bool) or not isinstance(payload[field_name], int) or payload[field_name] < 0:
            raise ValueError(f"{field_name} must be a non-negative integer")
    if not isinstance(payload["market_regime_summary"], Mapping):
        raise ValueError("market_regime_summary must be a mapping")
    list_fields = [
        "top_opportunities", "increase_actions", "reduce_actions", "exit_actions",
        "reentry_actions", "reinvestment_actions", "pending_reallocations",
        "watchlist_promotions", "watchlist_demotions", "risk_flags", "action_items",
        "warnings", "errors", "safety_guarantees",
    ]
    for field_name in list_fields:
        if not isinstance(payload[field_name], list):
            raise ValueError(f"{field_name} must be a list")
    for field_name in [
        "top_opportunities", "increase_actions", "reduce_actions", "exit_actions",
        "reentry_actions", "reinvestment_actions", "pending_reallocations",
        "watchlist_promotions", "watchlist_demotions",
    ]:
        for row in payload[field_name]:
            if not isinstance(row, Mapping):
                raise ValueError(f"{field_name} entries must be mappings")
            for required in ACTION_FIELDS:
                if required not in row:
                    raise ValueError(f"{field_name} entry missing {required}")
    return True


def write_weekly_portfolio_review_json(path: str = "weekly_portfolio_review.json") -> Dict[str, Any]:
    payload = build_weekly_portfolio_review()
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_weekly_portfolio_review_json(path: str = "weekly_portfolio_review.json") -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_weekly_portfolio_review(payload)
    return payload


def write_weekly_portfolio_review_csv(path: str = "weekly_portfolio_review.csv") -> Dict[str, Any]:
    payload = build_weekly_portfolio_review()
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["category"] + ACTION_FIELDS)
        writer.writeheader()
        for category in [
            "top_opportunities", "increase_actions", "reduce_actions", "exit_actions",
            "reentry_actions", "reinvestment_actions", "pending_reallocations",
            "watchlist_promotions", "watchlist_demotions",
        ]:
            for row in payload[category]:
                writer.writerow({"category": category, **{field: row.get(field, "") for field in ACTION_FIELDS}})
    return payload


def format_weekly_portfolio_review_markdown(payload: Mapping[str, Any]) -> str:
    validate_weekly_portfolio_review(payload)
    lines = [
        "# Weekly Portfolio Review",
        "",
        f"- Weekly Status: {payload['weekly_status']}",
        f"- Weekly Health Score: {payload['weekly_health_score']}",
        f"- Days Reviewed: {payload['days_reviewed']}",
        f"- Portfolio Value Change: ${payload['portfolio_value_change']:.2f}",
        f"- Monthly Income Change: ${payload['monthly_income_change']:.2f}",
        f"- Annual Income Change: ${payload['annual_income_change']:.2f}",
        "",
        "## Executive Summary",
        payload["executive_summary"],
        "",
        "## Action Items",
    ]
    lines.extend(f"- {item}" for item in payload["action_items"])
    lines.extend(["", "## Weekly Actions", "", "| Category | Symbol | Action | Score | Occurrences |", "|---|---|---|---:|---:|"])
    for category in ["increase_actions", "reduce_actions", "exit_actions", "reentry_actions", "pending_reallocations"]:
        for row in payload[category]:
            lines.append(f"| {category} | {row['symbol']} | {row['action']} | {row['score']} | {row['occurrences']} |")
    lines.extend(["", "## Risk Flags"])
    lines.extend([f"- {item}" for item in payload["risk_flags"]] or ["- None"])
    lines.extend(["", "## Safety Guarantees"])
    lines.extend(f"- {item}" for item in payload["safety_guarantees"])
    return "\n".join(lines) + "\n"


def write_weekly_portfolio_review_markdown(path: str = "weekly_portfolio_review.md") -> Dict[str, Any]:
    payload = build_weekly_portfolio_review()
    Path(path).write_text(format_weekly_portfolio_review_markdown(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    write_weekly_portfolio_review_json()
    write_weekly_portfolio_review_csv()
    write_weekly_portfolio_review_markdown()
