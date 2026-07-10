"""Paper-only Benchmark Comparison Engine for the Dividend Bot."""
from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Dict, Iterable, List, Mapping

MODULE_NAME = "benchmark_comparison_engine"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

BENCHMARK_WEIGHTS = {"SPY": 0.40, "QQQ": 0.25, "SCHD": 0.25, "SGOV": 0.10}
ANNUAL_GOAL = 0.20
MONTHLY_STRETCH_GOAL = 0.04
SUPPORTED_STATUSES = ["OUTPERFORMING", "MATCHING", "UNDERPERFORMING", "INSUFFICIENT_DATA"]


@dataclass(frozen=True)
class BenchmarkPeriodResult:
    period: str
    portfolio_return: float
    benchmark_return: float
    alpha: float
    status: str


@dataclass(frozen=True)
class BenchmarkComparisonReport:
    paper_trade_mode: bool
    live_trading_enabled: bool
    broker_execution_enabled: bool
    reporting_only: bool
    benchmark_weights: Dict[str, float]
    monthly_portfolio_return: float
    monthly_benchmark_return: float
    monthly_alpha: float
    monthly_status: str
    annualized_portfolio_return: float
    annualized_benchmark_return: float
    annualized_alpha: float
    annual_goal: float
    monthly_stretch_goal: float
    annual_goal_gap: float
    monthly_goal_gap: float
    portfolio_max_drawdown: float
    benchmark_max_drawdown: float
    portfolio_sharpe_like: float
    benchmark_sharpe_like: float
    rolling_results: List[Dict[str, Any]] = field(default_factory=list)
    explanations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _num(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return default


def validate_benchmark_weights(weights: Mapping[str, Any]) -> bool:
    if dict(weights) != BENCHMARK_WEIGHTS:
        raise ValueError("benchmark_weights must match the approved blended benchmark")
    if abs(sum(weights.values()) - 1.0) > 1e-9:
        raise ValueError("benchmark weights must total 1.0")
    return True


def calculate_blended_return(component_returns: Mapping[str, Any], weights: Mapping[str, float] = BENCHMARK_WEIGHTS) -> float:
    validate_benchmark_weights(weights)
    return round(sum(_num(component_returns.get(symbol, 0.0)) * weight for symbol, weight in weights.items()), 8)


def classify_performance(alpha: float, tolerance: float = 0.001) -> str:
    value = _num(alpha)
    if value > tolerance:
        return "OUTPERFORMING"
    if value < -tolerance:
        return "UNDERPERFORMING"
    return "MATCHING"


def calculate_max_drawdown(returns: Iterable[Any]) -> float:
    wealth = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for item in returns:
        wealth *= 1.0 + _num(item)
        peak = max(peak, wealth)
        if peak > 0:
            max_drawdown = min(max_drawdown, wealth / peak - 1.0)
    return round(max_drawdown, 8)


def calculate_sharpe_like(returns: Iterable[Any]) -> float:
    values = [_num(item) for item in returns]
    if len(values) < 2:
        return 0.0
    volatility = pstdev(values)
    if volatility == 0:
        return 0.0
    return round(mean(values) / volatility * math.sqrt(12), 8)


def annualize_monthly_return(monthly_return: float) -> float:
    value = _num(monthly_return)
    if value <= -1.0:
        return -1.0
    return round((1.0 + value) ** 12 - 1.0, 8)


def _rolling_result(period: str, portfolio_returns: List[float], benchmark_returns: List[float], months: int) -> Dict[str, Any]:
    if len(portfolio_returns) < months or len(benchmark_returns) < months:
        return asdict(BenchmarkPeriodResult(period, 0.0, 0.0, 0.0, "INSUFFICIENT_DATA"))
    p = math.prod(1.0 + value for value in portfolio_returns[-months:]) - 1.0
    b = math.prod(1.0 + value for value in benchmark_returns[-months:]) - 1.0
    alpha = p - b
    return asdict(BenchmarkPeriodResult(period, round(p, 8), round(b, 8), round(alpha, 8), classify_performance(alpha)))


def build_benchmark_comparison_report(
    portfolio_monthly_returns: Iterable[Any] | None = None,
    benchmark_component_monthly_returns: Iterable[Mapping[str, Any]] | None = None,
) -> Dict[str, Any]:
    portfolio_returns = [_num(value) for value in (portfolio_monthly_returns or [])]
    component_rows = list(benchmark_component_monthly_returns or [])
    benchmark_returns = [calculate_blended_return(row) for row in component_rows]
    matched = min(len(portfolio_returns), len(benchmark_returns))
    if matched:
        portfolio_returns = portfolio_returns[-matched:]
        benchmark_returns = benchmark_returns[-matched:]
        monthly_portfolio = portfolio_returns[-1]
        monthly_benchmark = benchmark_returns[-1]
        monthly_alpha = monthly_portfolio - monthly_benchmark
        monthly_status = classify_performance(monthly_alpha)
    else:
        monthly_portfolio = monthly_benchmark = monthly_alpha = 0.0
        monthly_status = "INSUFFICIENT_DATA"
    annual_portfolio = annualize_monthly_return(monthly_portfolio)
    annual_benchmark = annualize_monthly_return(monthly_benchmark)
    explanations = []
    if monthly_status == "OUTPERFORMING":
        explanations.append("The portfolio outperformed the approved blended benchmark for the latest month.")
    elif monthly_status == "UNDERPERFORMING":
        explanations.append("The portfolio underperformed the approved blended benchmark for the latest month and requires review.")
    elif monthly_status == "MATCHING":
        explanations.append("The portfolio approximately matched the approved blended benchmark for the latest month.")
    else:
        explanations.append("There is not enough matched history to classify benchmark performance.")
    payload = asdict(BenchmarkComparisonReport(
        paper_trade_mode=True,
        live_trading_enabled=False,
        broker_execution_enabled=False,
        reporting_only=True,
        benchmark_weights=dict(BENCHMARK_WEIGHTS),
        monthly_portfolio_return=round(monthly_portfolio, 8),
        monthly_benchmark_return=round(monthly_benchmark, 8),
        monthly_alpha=round(monthly_alpha, 8),
        monthly_status=monthly_status,
        annualized_portfolio_return=annual_portfolio,
        annualized_benchmark_return=annual_benchmark,
        annualized_alpha=round(annual_portfolio - annual_benchmark, 8),
        annual_goal=ANNUAL_GOAL,
        monthly_stretch_goal=MONTHLY_STRETCH_GOAL,
        annual_goal_gap=round(annual_portfolio - ANNUAL_GOAL, 8),
        monthly_goal_gap=round(monthly_portfolio - MONTHLY_STRETCH_GOAL, 8),
        portfolio_max_drawdown=calculate_max_drawdown(portfolio_returns),
        benchmark_max_drawdown=calculate_max_drawdown(benchmark_returns),
        portfolio_sharpe_like=calculate_sharpe_like(portfolio_returns),
        benchmark_sharpe_like=calculate_sharpe_like(benchmark_returns),
        rolling_results=[
            _rolling_result("3_MONTH", portfolio_returns, benchmark_returns, 3),
            _rolling_result("6_MONTH", portfolio_returns, benchmark_returns, 6),
            _rolling_result("12_MONTH", portfolio_returns, benchmark_returns, 12),
        ],
        explanations=explanations,
        warnings=[] if matched else ["No matched portfolio and benchmark history was supplied."],
    ))
    validate_benchmark_comparison_report(payload)
    return payload


def validate_benchmark_comparison_report(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    required = set(BenchmarkComparisonReport.__dataclass_fields__)
    missing = required - set(payload)
    if missing:
        raise ValueError(f"missing required fields: {sorted(missing)}")
    for key, expected in {
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "reporting_only": True,
    }.items():
        if payload[key] is not expected:
            raise ValueError(f"{key} must be {expected}")
    validate_benchmark_weights(payload["benchmark_weights"])
    if payload["monthly_status"] not in SUPPORTED_STATUSES:
        raise ValueError("unsupported monthly_status")
    for field_name in ["rolling_results", "explanations", "warnings"]:
        if not isinstance(payload[field_name], list):
            raise ValueError(f"{field_name} must be a list")
    for row in payload["rolling_results"]:
        if row.get("status") not in SUPPORTED_STATUSES:
            raise ValueError("unsupported rolling status")
    return True


def write_benchmark_comparison_report_json(path: str = "benchmark_comparison_report.json") -> Dict[str, Any]:
    payload = build_benchmark_comparison_report()
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_benchmark_comparison_report_json(path: str = "benchmark_comparison_report.json") -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_benchmark_comparison_report(payload)
    return payload


def write_benchmark_comparison_report_csv(path: str = "benchmark_comparison_report.csv") -> Dict[str, Any]:
    payload = build_benchmark_comparison_report()
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["period", "portfolio_return", "benchmark_return", "alpha", "status"])
        writer.writeheader()
        writer.writerow({"period": "LATEST_MONTH", "portfolio_return": payload["monthly_portfolio_return"], "benchmark_return": payload["monthly_benchmark_return"], "alpha": payload["monthly_alpha"], "status": payload["monthly_status"]})
        writer.writerows(payload["rolling_results"])
    return payload


def format_benchmark_comparison_report_markdown(payload: Mapping[str, Any]) -> str:
    validate_benchmark_comparison_report(payload)
    lines = [
        "# Benchmark Comparison Report",
        "",
        "## Approved Blended Benchmark",
        "",
        "- SPY: 40%",
        "- QQQ: 25%",
        "- SCHD: 25%",
        "- SGOV: 10%",
        "",
        "## Latest Month",
        "",
        f"- Portfolio return: {payload['monthly_portfolio_return']:.2%}",
        f"- Benchmark return: {payload['monthly_benchmark_return']:.2%}",
        f"- Alpha: {payload['monthly_alpha']:.2%}",
        f"- Status: {payload['monthly_status']}",
        "",
        "## Goals",
        "",
        f"- Annual objective: {payload['annual_goal']:.2%}",
        f"- Monthly stretch objective: {payload['monthly_stretch_goal']:.2%}",
        f"- Annual goal gap: {payload['annual_goal_gap']:.2%}",
        f"- Monthly goal gap: {payload['monthly_goal_gap']:.2%}",
        "",
        "## Rolling Performance",
        "",
        "| Period | Portfolio | Benchmark | Alpha | Status |",
        "|---|---:|---:|---:|---|",
    ]
    for row in payload["rolling_results"]:
        lines.append(f"| {row['period']} | {row['portfolio_return']:.2%} | {row['benchmark_return']:.2%} | {row['alpha']:.2%} | {row['status']} |")
    lines.extend(["", "## Explanation"] + [f"- {item}" for item in payload["explanations"]] + ["", "## Safety", "- Paper-only reporting.", "- No brokerage execution.", "- No order placement."])
    return "\n".join(lines) + "\n"


def write_benchmark_comparison_report_markdown(path: str = "benchmark_comparison_report.md") -> Dict[str, Any]:
    payload = build_benchmark_comparison_report()
    Path(path).write_text(format_benchmark_comparison_report_markdown(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    write_benchmark_comparison_report_json()
    write_benchmark_comparison_report_csv()
    write_benchmark_comparison_report_markdown()
