"""
Portfolio Intelligence Engine for the Dividend Bot.

Provides read-only portfolio trend intelligence for downstream dashboards and
reports. It identifies improving and deteriorating holdings, income growth,
concentration risk, allocation priorities, and overall portfolio health.
"""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

MODULE_NAME = "portfolio_intelligence_engine"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"
BOT_NAME = "Agentic Robin Dividend Bot"
BOT_TYPE = "paper_dividend_etf_management"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

IMPROVING = "IMPROVING"
STABLE = "STABLE"
DETERIORATING = "DETERIORATING"
UNKNOWN = "UNKNOWN"
SUPPORTED_TRENDS = [IMPROVING, STABLE, DETERIORATING, UNKNOWN]

EXCELLENT = "EXCELLENT"
GOOD = "GOOD"
FAIR = "FAIR"
WEAK = "WEAK"
SUPPORTED_HEALTH_STATUSES = [EXCELLENT, GOOD, FAIR, WEAK, UNKNOWN]

INCREASE_PRIORITY = "INCREASE_PRIORITY"
MAINTAIN_PRIORITY = "MAINTAIN_PRIORITY"
MONITOR_PRIORITY = "MONITOR_PRIORITY"
REDUCE_PRIORITY = "REDUCE_PRIORITY"
SUPPORTED_CAPITAL_PRIORITIES = [INCREASE_PRIORITY, MAINTAIN_PRIORITY, MONITOR_PRIORITY, REDUCE_PRIORITY, UNKNOWN]

CONCENTRATION_WARNING_PCT = 0.35
IMPROVEMENT_DELTA = 5.0
DETERIORATION_DELTA = -5.0

SAFETY_GUARANTEES = [
    "paper_trade_mode is enforced as True",
    "reporting_only is enforced as True",
    "live_trading_enabled is enforced as False",
    "broker_execution_enabled is enforced as False",
    "no Robinhood execution is performed",
    "no brokerage execution is performed",
    "no order placement is performed",
    "portfolio intelligence is read-only",
]

INTELLIGENCE_RULES = [
    "Every holding competes on its own merit.",
    "Improvement and deterioration are measured from current versus previous scores.",
    "Income growth is evaluated separately from capital growth.",
    "Concentration warnings are generated when a holding exceeds the approved threshold.",
    "Capital-priority signals inform downstream reports but do not cause execution.",
]

HOLDING_REQUIRED_FIELDS = [
    "symbol", "current_score", "previous_score", "score_delta", "trend_status",
    "capital_priority", "allocation_pct", "current_value", "previous_value",
    "capital_growth_pct", "current_monthly_income", "previous_monthly_income",
    "monthly_income_growth_pct", "risk_flags", "why",
]

REPORT_REQUIRED_FIELDS = [
    "bot_name", "bot_type", "module_name", "module_version", "schema_version",
    "generated_by", "generated_at_utc", "paper_trade_mode", "live_trading_enabled",
    "broker_execution_enabled", "reporting_only", "portfolio_health_score",
    "portfolio_health_status", "portfolio_trend", "holdings_analyzed", "improving_count",
    "stable_count", "deteriorating_count", "total_current_value", "total_previous_value",
    "portfolio_capital_growth_pct", "current_monthly_income", "previous_monthly_income",
    "portfolio_income_growth_pct", "concentration_warning_count", "holding_intelligence",
    "top_improvers", "top_deteriorators", "capital_priorities", "risk_flags",
    "recommendations", "warnings", "errors", "intelligence_rules", "safety_guarantees",
]


@dataclass(frozen=True)
class HoldingIntelligence:
    symbol: str
    current_score: float = 0.0
    previous_score: float = 0.0
    score_delta: float = 0.0
    trend_status: str = UNKNOWN
    capital_priority: str = UNKNOWN
    allocation_pct: float = 0.0
    current_value: float = 0.0
    previous_value: float = 0.0
    capital_growth_pct: float = 0.0
    current_monthly_income: float = 0.0
    previous_monthly_income: float = 0.0
    monthly_income_growth_pct: float = 0.0
    risk_flags: List[str] = field(default_factory=list)
    why: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class PortfolioIntelligenceReport:
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
    portfolio_health_score: float
    portfolio_health_status: str
    portfolio_trend: str
    holdings_analyzed: int
    improving_count: int
    stable_count: int
    deteriorating_count: int
    total_current_value: float
    total_previous_value: float
    portfolio_capital_growth_pct: float
    current_monthly_income: float
    previous_monthly_income: float
    portfolio_income_growth_pct: float
    concentration_warning_count: int
    holding_intelligence: List[Dict[str, Any]]
    top_improvers: List[str]
    top_deteriorators: List[str]
    capital_priorities: List[Dict[str, str]]
    risk_flags: List[str]
    recommendations: List[str]
    warnings: List[str]
    errors: List[str]
    intelligence_rules: List[str]
    safety_guarantees: List[str]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _clamp(value: Any, low: float, high: float) -> float:
    return max(low, min(high, _number(value, low)))


def _symbol(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip().upper()
    return "UNKNOWN"


def calculate_growth_pct(current: Any, previous: Any) -> float:
    current_value = _number(current, 0.0)
    previous_value = _number(previous, 0.0)
    if previous_value == 0:
        return 0.0
    return round(((current_value - previous_value) / abs(previous_value)) * 100.0, 2)


def classify_trend(score_delta: Any) -> str:
    delta = _number(score_delta, 0.0)
    if delta >= IMPROVEMENT_DELTA:
        return IMPROVING
    if delta <= DETERIORATION_DELTA:
        return DETERIORATING
    return STABLE


def classify_capital_priority(current_score: Any, trend_status: str) -> str:
    score = _clamp(current_score, 0.0, 100.0)
    if trend_status == DETERIORATING or score < 50:
        return REDUCE_PRIORITY
    if score >= 85 and trend_status == IMPROVING:
        return INCREASE_PRIORITY
    if score >= 70:
        return MAINTAIN_PRIORITY
    return MONITOR_PRIORITY


def classify_health(score: Any) -> str:
    value = _clamp(score, 0.0, 100.0)
    if value >= 85:
        return EXCELLENT
    if value >= 70:
        return GOOD
    if value >= 55:
        return FAIR
    return WEAK


def build_holding_intelligence(holding: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(holding, Mapping):
        raise ValueError("holding must be a mapping")
    symbol = _symbol(holding.get("symbol"))
    current_score = _clamp(holding.get("current_score", holding.get("master_score", 0.0)), 0.0, 100.0)
    previous_score = _clamp(holding.get("previous_score", holding.get("previous_master_score", current_score)), 0.0, 100.0)
    score_delta = round(current_score - previous_score, 2)
    trend_status = classify_trend(score_delta)
    allocation_pct = _clamp(holding.get("allocation_pct", 0.0), 0.0, 1.0)
    current_value = max(0.0, _number(holding.get("current_value", holding.get("allocation_dollars", 0.0)), 0.0))
    previous_value = max(0.0, _number(holding.get("previous_value", current_value), 0.0))
    current_income = max(0.0, _number(holding.get("current_monthly_income", holding.get("expected_monthly_income", 0.0)), 0.0))
    previous_income = max(0.0, _number(holding.get("previous_monthly_income", current_income), 0.0))
    risk_flags: List[str] = []
    why: List[str] = []
    if allocation_pct > CONCENTRATION_WARNING_PCT:
        risk_flags.append("POSITION_CONCENTRATION_WARNING")
        why.append("Allocation exceeds concentration warning threshold.")
    if trend_status == IMPROVING:
        why.append("Current score improved by at least five points.")
    elif trend_status == DETERIORATING:
        why.append("Current score deteriorated by at least five points.")
    else:
        why.append("Current score remains within the stable range.")
    priority = classify_capital_priority(current_score, trend_status)
    return asdict(HoldingIntelligence(
        symbol=symbol,
        current_score=current_score,
        previous_score=previous_score,
        score_delta=score_delta,
        trend_status=trend_status,
        capital_priority=priority,
        allocation_pct=allocation_pct,
        current_value=round(current_value, 2),
        previous_value=round(previous_value, 2),
        capital_growth_pct=calculate_growth_pct(current_value, previous_value),
        current_monthly_income=round(current_income, 2),
        previous_monthly_income=round(previous_income, 2),
        monthly_income_growth_pct=calculate_growth_pct(current_income, previous_income),
        risk_flags=risk_flags,
        why=why,
    ))


def build_portfolio_intelligence_report(holdings: Iterable[Mapping[str, Any]] | None = None) -> Dict[str, Any]:
    rows = [build_holding_intelligence(item) for item in list(holdings or [])]
    rows.sort(key=lambda row: (-row["current_score"], row["symbol"]))
    improving = [row for row in rows if row["trend_status"] == IMPROVING]
    stable = [row for row in rows if row["trend_status"] == STABLE]
    deteriorating = [row for row in rows if row["trend_status"] == DETERIORATING]
    current_value = round(sum(row["current_value"] for row in rows), 2)
    previous_value = round(sum(row["previous_value"] for row in rows), 2)
    current_income = round(sum(row["current_monthly_income"] for row in rows), 2)
    previous_income = round(sum(row["previous_monthly_income"] for row in rows), 2)
    average_score = round(sum(row["current_score"] for row in rows) / len(rows), 2) if rows else 0.0
    portfolio_trend = UNKNOWN
    if rows:
        if len(improving) > len(deteriorating):
            portfolio_trend = IMPROVING
        elif len(deteriorating) > len(improving):
            portfolio_trend = DETERIORATING
        else:
            portfolio_trend = STABLE
    risk_flags = sorted({flag for row in rows for flag in row["risk_flags"]})
    recommendations: List[str] = []
    if improving:
        recommendations.append("Review improving holdings for additional capital priority.")
    if deteriorating:
        recommendations.append("Review deteriorating holdings for risk and sale-signal confirmation.")
    if risk_flags:
        recommendations.append("Review concentration warnings before allocating additional capital.")
    warnings: List[str] = []
    if not rows:
        warnings.append("No holdings supplied; generated valid empty portfolio intelligence report.")
    payload = asdict(PortfolioIntelligenceReport(
        bot_name=BOT_NAME,
        bot_type=BOT_TYPE,
        module_name=MODULE_NAME,
        module_version=MODULE_VERSION,
        schema_version=SCHEMA_VERSION,
        generated_by=GENERATED_BY,
        generated_at_utc=_utc_now_iso(),
        paper_trade_mode=True,
        live_trading_enabled=False,
        broker_execution_enabled=False,
        reporting_only=True,
        portfolio_health_score=average_score,
        portfolio_health_status=classify_health(average_score),
        portfolio_trend=portfolio_trend,
        holdings_analyzed=len(rows),
        improving_count=len(improving),
        stable_count=len(stable),
        deteriorating_count=len(deteriorating),
        total_current_value=current_value,
        total_previous_value=previous_value,
        portfolio_capital_growth_pct=calculate_growth_pct(current_value, previous_value),
        current_monthly_income=current_income,
        previous_monthly_income=previous_income,
        portfolio_income_growth_pct=calculate_growth_pct(current_income, previous_income),
        concentration_warning_count=sum(1 for row in rows if "POSITION_CONCENTRATION_WARNING" in row["risk_flags"]),
        holding_intelligence=rows,
        top_improvers=[row["symbol"] for row in sorted(improving, key=lambda row: (-row["score_delta"], row["symbol"]))[:5]],
        top_deteriorators=[row["symbol"] for row in sorted(deteriorating, key=lambda row: (row["score_delta"], row["symbol"]))[:5]],
        capital_priorities=[{"symbol": row["symbol"], "priority": row["capital_priority"]} for row in rows],
        risk_flags=risk_flags,
        recommendations=recommendations,
        warnings=warnings,
        errors=[],
        intelligence_rules=list(INTELLIGENCE_RULES),
        safety_guarantees=list(SAFETY_GUARANTEES),
    ))
    validate_portfolio_intelligence_report(payload)
    return payload


def validate_portfolio_intelligence_report(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    for field_name in REPORT_REQUIRED_FIELDS:
        if field_name not in payload:
            raise ValueError(f"missing required field: {field_name}")
    expected = {
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "reporting_only": True,
    }
    for field_name, value in expected.items():
        if payload[field_name] is not value:
            raise ValueError(f"{field_name} must be {value}")
    if payload["portfolio_health_status"] not in SUPPORTED_HEALTH_STATUSES:
        raise ValueError("unsupported portfolio health status")
    if payload["portfolio_trend"] not in SUPPORTED_TRENDS:
        raise ValueError("unsupported portfolio trend")
    for list_field in [
        "holding_intelligence", "top_improvers", "top_deteriorators", "capital_priorities",
        "risk_flags", "recommendations", "warnings", "errors", "intelligence_rules", "safety_guarantees",
    ]:
        if not isinstance(payload[list_field], list):
            raise ValueError(f"{list_field} must be a list")
    if payload["holdings_analyzed"] != len(payload["holding_intelligence"]):
        raise ValueError("holdings_analyzed mismatch")
    if payload["improving_count"] + payload["stable_count"] + payload["deteriorating_count"] != payload["holdings_analyzed"]:
        raise ValueError("trend counts must equal holdings analyzed")
    for row in payload["holding_intelligence"]:
        if not isinstance(row, Mapping):
            raise ValueError("holding intelligence rows must be mappings")
        for field_name in HOLDING_REQUIRED_FIELDS:
            if field_name not in row:
                raise ValueError(f"holding intelligence missing field: {field_name}")
        if row["trend_status"] not in SUPPORTED_TRENDS:
            raise ValueError("unsupported holding trend")
        if row["capital_priority"] not in SUPPORTED_CAPITAL_PRIORITIES:
            raise ValueError("unsupported capital priority")
        if row["symbol"] != row["symbol"].upper() or not row["symbol"].strip():
            raise ValueError("symbol must be a non-empty uppercase string")
    return True


def write_portfolio_intelligence_report_json(path: str = "portfolio_intelligence_report.json") -> Dict[str, Any]:
    payload = build_portfolio_intelligence_report()
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_portfolio_intelligence_report_json(path: str = "portfolio_intelligence_report.json") -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_portfolio_intelligence_report(payload)
    return payload


def write_portfolio_intelligence_report_csv(path: str = "portfolio_intelligence_report.csv") -> Dict[str, Any]:
    payload = build_portfolio_intelligence_report()
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HOLDING_REQUIRED_FIELDS)
        writer.writeheader()
        for row in payload["holding_intelligence"]:
            writer.writerow({field_name: row.get(field_name, "") for field_name in HOLDING_REQUIRED_FIELDS})
    return payload


def format_portfolio_intelligence_report_markdown(payload: Mapping[str, Any]) -> str:
    validate_portfolio_intelligence_report(payload)
    lines = [
        "# Portfolio Intelligence Report",
        "",
        f"- Portfolio Health Score: {payload['portfolio_health_score']}",
        f"- Portfolio Health Status: {payload['portfolio_health_status']}",
        f"- Portfolio Trend: {payload['portfolio_trend']}",
        f"- Capital Growth: {payload['portfolio_capital_growth_pct']}%",
        f"- Monthly Income Growth: {payload['portfolio_income_growth_pct']}%",
        "",
        "## Holding Intelligence",
        "",
        "| Symbol | Score | Delta | Trend | Priority | Allocation | Capital Growth | Income Growth |",
        "|---|---:|---:|---|---|---:|---:|---:|",
    ]
    for row in payload["holding_intelligence"]:
        lines.append(
            f"| {row['symbol']} | {row['current_score']} | {row['score_delta']} | {row['trend_status']} | {row['capital_priority']} | {row['allocation_pct']} | {row['capital_growth_pct']}% | {row['monthly_income_growth_pct']}% |"
        )
    lines.extend(["", "## Intelligence Rules"])
    lines.extend(f"- {item}" for item in payload["intelligence_rules"])
    lines.extend(["", "## Safety Guarantees"])
    lines.extend(f"- {item}" for item in payload["safety_guarantees"])
    return "\n".join(lines) + "\n"


def write_portfolio_intelligence_report_markdown(path: str = "portfolio_intelligence_report.md") -> Dict[str, Any]:
    payload = build_portfolio_intelligence_report()
    Path(path).write_text(format_portfolio_intelligence_report_markdown(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    write_portfolio_intelligence_report_json()
    write_portfolio_intelligence_report_csv()
    write_portfolio_intelligence_report_markdown()
