"""Monthly Portfolio Report for the Dividend Bot.

Summarizes verified monthly results, benchmark comparison, income growth,
portfolio quality trends, opportunity rotation, goals, and forward-looking
watch items. Reporting only; no trading or brokerage behavior.
"""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping

MODULE_NAME = "monthly_portfolio_report"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"
BOT_NAME = "Agentic Robin Dividend Bot"
BOT_TYPE = "paper_dividend_etf_management"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

MINIMUM_ANNUAL_GOAL = 0.20
MONTHLY_STRETCH_GOAL = 0.04
BLENDED_BENCHMARK_WEIGHTS = {"SPY": 0.40, "QQQ": 0.25, "SCHD": 0.25, "SGOV": 0.10}
SUPPORTED_BENCHMARK_STATUSES = ["OUTPERFORMING", "MATCHING", "UNDERPERFORMING", "UNKNOWN"]
SUPPORTED_GOAL_STATUSES = ["AHEAD_OF_PLAN", "ON_TRACK", "GAP_TO_TARGET", "UNKNOWN"]
SAFETY_GUARANTEES = [
    "paper_trade_mode is enforced as True",
    "reporting_only is enforced as True",
    "live_trading_enabled is enforced as False",
    "broker_execution_enabled is enforced as False",
    "no Robinhood execution is performed",
    "no brokerage execution is performed",
    "no order placement is performed",
    "actual results and forward-looking watch items are reported separately",
]

REPORT_REQUIRED_FIELDS = [
    "bot_name", "bot_type", "module_name", "module_version", "schema_version",
    "generated_by", "generated_at_utc", "paper_trade_mode", "live_trading_enabled",
    "broker_execution_enabled", "reporting_only", "report_month", "actual_results",
    "prior_month_comparison", "benchmark_comparison", "income_progress",
    "portfolio_quality_trend", "leaders", "emerging_leaders", "fading_opportunities",
    "decision_review", "learning_summary", "goal_progress", "watch_next",
    "executive_summary", "warnings", "errors", "safety_guarantees",
]


@dataclass(frozen=True)
class MonthlyActualResults:
    portfolio_start_value: float = 0.0
    portfolio_end_value: float = 0.0
    net_contributions: float = 0.0
    total_distributions: float = 0.0
    total_return_pct: float = 0.0
    capital_appreciation_pct: float = 0.0
    monthly_income: float = 0.0
    projected_annual_income: float = 0.0
    cash_reserve_pct: float = 0.0
    max_drawdown_pct: float = 0.0


@dataclass(frozen=True)
class MonthlyPortfolioReport:
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
    report_month: str
    actual_results: Dict[str, float]
    prior_month_comparison: Dict[str, float]
    benchmark_comparison: Dict[str, Any]
    income_progress: Dict[str, float]
    portfolio_quality_trend: Dict[str, float]
    leaders: List[Dict[str, Any]]
    emerging_leaders: List[Dict[str, Any]]
    fading_opportunities: List[Dict[str, Any]]
    decision_review: Dict[str, Any]
    learning_summary: Dict[str, Any]
    goal_progress: Dict[str, Any]
    watch_next: List[str]
    executive_summary: List[str]
    warnings: List[str]
    errors: List[str]
    safety_guarantees: List[str]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value)


def _pct_change(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0
    return round((current - previous) / abs(previous), 4)


def calculate_blended_benchmark_return(benchmark_returns: Mapping[str, Any]) -> float:
    if not isinstance(benchmark_returns, Mapping):
        raise ValueError("benchmark_returns must be a mapping")
    return round(sum(_number(benchmark_returns.get(symbol, 0.0)) * weight for symbol, weight in BLENDED_BENCHMARK_WEIGHTS.items()), 4)


def classify_benchmark_status(portfolio_return: float, benchmark_return: float) -> str:
    gap = round(portfolio_return - benchmark_return, 4)
    if gap > 0.001:
        return "OUTPERFORMING"
    if gap < -0.001:
        return "UNDERPERFORMING"
    return "MATCHING"


def classify_goal_status(actual: float, target: float) -> str:
    if target <= 0:
        return "UNKNOWN"
    ratio = actual / target
    if ratio >= 1.0:
        return "AHEAD_OF_PLAN"
    if ratio >= 0.90:
        return "ON_TRACK"
    return "GAP_TO_TARGET"


def build_monthly_portfolio_report(
    current: Mapping[str, Any] | None = None,
    previous: Mapping[str, Any] | None = None,
    benchmark_returns: Mapping[str, Any] | None = None,
    report_month: str | None = None,
) -> Dict[str, Any]:
    current = dict(current or {})
    previous = dict(previous or {})
    report_month = report_month or datetime.now(timezone.utc).strftime("%Y-%m")

    start_value = _number(current.get("portfolio_start_value", 0.0))
    end_value = _number(current.get("portfolio_end_value", 0.0))
    contributions = _number(current.get("net_contributions", 0.0))
    distributions = _number(current.get("total_distributions", 0.0))
    denominator = start_value if start_value > 0 else 0.0
    total_return = round((end_value - start_value - contributions + distributions) / denominator, 4) if denominator else 0.0
    capital_appreciation = round((end_value - start_value - contributions) / denominator, 4) if denominator else 0.0

    monthly_income = _number(current.get("monthly_income", distributions))
    projected_annual_income = _number(current.get("projected_annual_income", monthly_income * 12))
    cash_reserve_pct = _number(current.get("cash_reserve_pct", 0.0))
    max_drawdown_pct = _number(current.get("max_drawdown_pct", 0.0))

    actual = asdict(MonthlyActualResults(
        portfolio_start_value=start_value,
        portfolio_end_value=end_value,
        net_contributions=contributions,
        total_distributions=distributions,
        total_return_pct=total_return,
        capital_appreciation_pct=capital_appreciation,
        monthly_income=monthly_income,
        projected_annual_income=projected_annual_income,
        cash_reserve_pct=cash_reserve_pct,
        max_drawdown_pct=max_drawdown_pct,
    ))

    prior_income = _number(previous.get("monthly_income", 0.0))
    prior_annual_income = _number(previous.get("projected_annual_income", 0.0))
    prior_end_value = _number(previous.get("portfolio_end_value", 0.0))
    prior_quality = _number(previous.get("average_opportunity_score", 0.0))
    current_quality = _number(current.get("average_opportunity_score", 0.0))
    prior_conviction = _number(previous.get("average_conviction_score", 0.0))
    current_conviction = _number(current.get("average_conviction_score", 0.0))
    prior_entry = _number(previous.get("average_entry_score", 0.0))
    current_entry = _number(current.get("average_entry_score", 0.0))

    prior_comparison = {
        "portfolio_value_change": round(end_value - prior_end_value, 2),
        "monthly_income_change": round(monthly_income - prior_income, 2),
        "monthly_income_growth_pct": _pct_change(monthly_income, prior_income),
        "projected_annual_income_change": round(projected_annual_income - prior_annual_income, 2),
        "opportunity_score_change": round(current_quality - prior_quality, 2),
        "conviction_score_change": round(current_conviction - prior_conviction, 2),
        "entry_score_change": round(current_entry - prior_entry, 2),
    }

    benchmark_return = calculate_blended_benchmark_return(benchmark_returns or {})
    benchmark = {
        "weights": dict(BLENDED_BENCHMARK_WEIGHTS),
        "benchmark_return_pct": benchmark_return,
        "portfolio_return_pct": total_return,
        "alpha_pct": round(total_return - benchmark_return, 4),
        "status": classify_benchmark_status(total_return, benchmark_return),
    }

    income_progress = {
        "monthly_income": monthly_income,
        "prior_month_income": prior_income,
        "income_growth_pct": _pct_change(monthly_income, prior_income),
        "projected_annual_income": projected_annual_income,
    }

    quality_trend = {
        "average_opportunity_score": current_quality,
        "average_conviction_score": current_conviction,
        "average_entry_score": current_entry,
        "opportunity_score_change": round(current_quality - prior_quality, 2),
        "conviction_score_change": round(current_conviction - prior_conviction, 2),
        "entry_score_change": round(current_entry - prior_entry, 2),
    }

    leaders = list(current.get("leaders", [])) if isinstance(current.get("leaders", []), list) else []
    emerging = list(current.get("emerging_leaders", [])) if isinstance(current.get("emerging_leaders", []), list) else []
    fading = list(current.get("fading_opportunities", [])) if isinstance(current.get("fading_opportunities", []), list) else []

    decision_review = {
        "buys": int(_number(current.get("buy_count", 0))),
        "holds": int(_number(current.get("hold_count", 0))),
        "exits": int(_number(current.get("exit_count", 0))),
        "reentries": int(_number(current.get("reentry_count", 0))),
        "successful_decisions": int(_number(current.get("successful_decisions", 0))),
        "decisions_reviewed": int(_number(current.get("decisions_reviewed", 0))),
    }

    learning_summary = {
        "best_strategy": str(current.get("best_strategy", "UNKNOWN")),
        "weakest_strategy": str(current.get("weakest_strategy", "UNKNOWN")),
        "largest_improvement": str(current.get("largest_improvement", "UNKNOWN")),
        "largest_risk": str(current.get("largest_risk", "UNKNOWN")),
        "proposed_changes": list(current.get("proposed_changes", [])) if isinstance(current.get("proposed_changes", []), list) else [],
        "approval_required": True,
    }

    annualized_run_rate = round(total_return * 12, 4)
    goals = {
        "minimum_annual_goal": MINIMUM_ANNUAL_GOAL,
        "monthly_stretch_goal": MONTHLY_STRETCH_GOAL,
        "actual_monthly_return": total_return,
        "annualized_run_rate": annualized_run_rate,
        "monthly_goal_status": classify_goal_status(total_return, MONTHLY_STRETCH_GOAL),
        "annual_goal_status": classify_goal_status(annualized_run_rate, MINIMUM_ANNUAL_GOAL),
        "monthly_gap_to_target": round(MONTHLY_STRETCH_GOAL - total_return, 4),
        "annual_gap_to_target": round(MINIMUM_ANNUAL_GOAL - annualized_run_rate, 4),
    }

    watch_next = list(current.get("watch_next", [])) if isinstance(current.get("watch_next", []), list) else []
    summary = [
        f"Portfolio monthly return was {total_return:.2%} versus the blended benchmark at {benchmark_return:.2%}.",
        f"Benchmark status: {benchmark['status']} with alpha of {benchmark['alpha_pct']:.2%}.",
        f"Monthly income was ${monthly_income:.2f}, a change of {income_progress['income_growth_pct']:.2%} from the prior month.",
        f"Monthly stretch-goal status: {goals['monthly_goal_status']} with a gap of {goals['monthly_gap_to_target']:.2%}.",
    ]

    warnings: List[str] = []
    if not current:
        warnings.append("No current monthly data supplied; generated deterministic zero-value report.")
    if not previous:
        warnings.append("No prior-month data supplied; comparison values default to zero.")
    if not benchmark_returns:
        warnings.append("No benchmark returns supplied; blended benchmark defaults to zero.")

    payload = asdict(MonthlyPortfolioReport(
        bot_name=BOT_NAME,
        bot_type=BOT_TYPE,
        module_name=MODULE_NAME,
        module_version=MODULE_VERSION,
        schema_version=SCHEMA_VERSION,
        generated_by=GENERATED_BY,
        generated_at_utc=_now(),
        paper_trade_mode=True,
        live_trading_enabled=False,
        broker_execution_enabled=False,
        reporting_only=True,
        report_month=report_month,
        actual_results=actual,
        prior_month_comparison=prior_comparison,
        benchmark_comparison=benchmark,
        income_progress=income_progress,
        portfolio_quality_trend=quality_trend,
        leaders=leaders,
        emerging_leaders=emerging,
        fading_opportunities=fading,
        decision_review=decision_review,
        learning_summary=learning_summary,
        goal_progress=goals,
        watch_next=watch_next,
        executive_summary=summary,
        warnings=warnings,
        errors=[],
        safety_guarantees=list(SAFETY_GUARANTEES),
    ))
    validate_monthly_portfolio_report(payload)
    return payload


def validate_monthly_portfolio_report(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    for field in REPORT_REQUIRED_FIELDS:
        if field not in payload:
            raise ValueError(f"missing required field: {field}")
    for key, expected in {
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "reporting_only": True,
    }.items():
        if payload[key] is not expected:
            raise ValueError(f"{key} must be {expected}")
    if not isinstance(payload["report_month"], str) or not payload["report_month"].strip():
        raise ValueError("report_month must be a non-empty string")
    for field in ["actual_results", "prior_month_comparison", "benchmark_comparison", "income_progress", "portfolio_quality_trend", "decision_review", "learning_summary", "goal_progress"]:
        if not isinstance(payload[field], Mapping):
            raise ValueError(f"{field} must be a mapping")
    for field in ["leaders", "emerging_leaders", "fading_opportunities", "watch_next", "executive_summary", "warnings", "errors", "safety_guarantees"]:
        if not isinstance(payload[field], list):
            raise ValueError(f"{field} must be a list")
    if payload["benchmark_comparison"].get("status") not in SUPPORTED_BENCHMARK_STATUSES:
        raise ValueError("unsupported benchmark status")
    if payload["goal_progress"].get("monthly_goal_status") not in SUPPORTED_GOAL_STATUSES:
        raise ValueError("unsupported monthly goal status")
    if payload["goal_progress"].get("annual_goal_status") not in SUPPORTED_GOAL_STATUSES:
        raise ValueError("unsupported annual goal status")
    if payload["learning_summary"].get("approval_required") is not True:
        raise ValueError("semi-adaptive learning proposals must require approval")
    return True


def write_monthly_portfolio_report_json(path: str = "monthly_portfolio_report.json") -> Dict[str, Any]:
    payload = build_monthly_portfolio_report()
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_monthly_portfolio_report_json(path: str = "monthly_portfolio_report.json") -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_monthly_portfolio_report(payload)
    return payload


def write_monthly_portfolio_report_csv(path: str = "monthly_portfolio_report.csv") -> Dict[str, Any]:
    payload = build_monthly_portfolio_report()
    row = {
        "report_month": payload["report_month"],
        "portfolio_return_pct": payload["actual_results"]["total_return_pct"],
        "benchmark_return_pct": payload["benchmark_comparison"]["benchmark_return_pct"],
        "alpha_pct": payload["benchmark_comparison"]["alpha_pct"],
        "monthly_income": payload["actual_results"]["monthly_income"],
        "projected_annual_income": payload["actual_results"]["projected_annual_income"],
        "monthly_goal_status": payload["goal_progress"]["monthly_goal_status"],
        "annual_goal_status": payload["goal_progress"]["annual_goal_status"],
    }
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)
    return payload


def format_monthly_portfolio_report_markdown(payload: Mapping[str, Any]) -> str:
    validate_monthly_portfolio_report(payload)
    a = payload["actual_results"]
    b = payload["benchmark_comparison"]
    g = payload["goal_progress"]
    lines = [
        "# Monthly Portfolio Report",
        "",
        f"- Report Month: {payload['report_month']}",
        f"- Portfolio Return: {a['total_return_pct']:.2%}",
        f"- Benchmark Return: {b['benchmark_return_pct']:.2%}",
        f"- Alpha: {b['alpha_pct']:.2%}",
        f"- Benchmark Status: {b['status']}",
        f"- Monthly Income: ${a['monthly_income']:.2f}",
        f"- Projected Annual Income: ${a['projected_annual_income']:.2f}",
        "",
        "## Goal Progress",
        f"- Monthly Stretch Goal: {g['monthly_stretch_goal']:.2%}",
        f"- Monthly Status: {g['monthly_goal_status']}",
        f"- Gap to Monthly Target: {g['monthly_gap_to_target']:.2%}",
        f"- Minimum Annual Goal: {g['minimum_annual_goal']:.2%}",
        f"- Annual Status: {g['annual_goal_status']}",
        "",
        "## Executive Summary",
    ]
    lines.extend(f"- {item}" for item in payload["executive_summary"])
    lines.extend(["", "## Emerging Leaders"])
    if payload["emerging_leaders"]:
        for item in payload["emerging_leaders"]:
            lines.append(f"- {item}")
    else:
        lines.append("- None")
    lines.extend(["", "## Watch Next"])
    lines.extend(f"- {item}" for item in payload["watch_next"] or ["None"])
    lines.extend(["", "## Safety Guarantees"])
    lines.extend(f"- {item}" for item in payload["safety_guarantees"])
    return "\n".join(lines) + "\n"


def write_monthly_portfolio_report_markdown(path: str = "monthly_portfolio_report.md") -> Dict[str, Any]:
    payload = build_monthly_portfolio_report()
    Path(path).write_text(format_monthly_portfolio_report_markdown(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    write_monthly_portfolio_report_json()
    write_monthly_portfolio_report_csv()
    write_monthly_portfolio_report_markdown()
