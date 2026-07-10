"""Paper-only Decision Review Engine for the Dividend Bot."""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

MODULE_NAME = "decision_review_engine"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

SUPPORTED_DECISION_TYPES = ["BUY", "HOLD", "SELL", "REENTRY", "MISSED_OPPORTUNITY"]
SUPPORTED_GRADES = ["A+", "A", "B+", "B", "C", "D", "F", "PENDING"]
SUPPORTED_STATUSES = ["SUCCESSFUL", "ACCEPTABLE", "REVIEW", "POOR", "PENDING"]

SAFETY_GUARANTEES = [
    "paper_trade_mode is enforced as True",
    "live_trading_enabled is enforced as False",
    "broker_execution_enabled is enforced as False",
    "reporting_only is enforced as True",
    "no brokerage execution is performed",
    "no order placement is performed",
]

REQUIRED_REPORT_FIELDS = [
    "module_name", "module_version", "schema_version", "generated_by", "generated_at_utc",
    "paper_trade_mode", "live_trading_enabled", "broker_execution_enabled", "reporting_only",
    "decision_reviews", "review_count", "average_review_score", "successful_count",
    "review_required_count", "learning_lessons", "warnings", "errors", "safety_guarantees",
]

REVIEW_FIELDS = [
    "decision_id", "symbol", "decision_type", "decision_date", "review_date", "holding_days",
    "decision_price", "review_price", "realized_return_pct", "benchmark_return_pct", "alpha_pct",
    "opportunity_cost_pct", "income_received", "decision_score", "grade", "review_status",
    "confidence_was_accurate", "reasons", "lessons", "strategy_name",
]


@dataclass(frozen=True)
class DecisionRecord:
    decision_id: str
    symbol: str
    decision_type: str
    decision_date: str
    decision_price: float = 0.0
    review_price: float = 0.0
    benchmark_return_pct: float = 0.0
    best_alternative_return_pct: float = 0.0
    income_received: float = 0.0
    confidence: float = 0.0
    expected_direction: str = "UP"
    strategy_name: str = "UNKNOWN"


@dataclass(frozen=True)
class DecisionReview:
    decision_id: str
    symbol: str
    decision_type: str
    decision_date: str
    review_date: str
    holding_days: int
    decision_price: float
    review_price: float
    realized_return_pct: float
    benchmark_return_pct: float
    alpha_pct: float
    opportunity_cost_pct: float
    income_received: float
    decision_score: float
    grade: str
    review_status: str
    confidence_was_accurate: bool
    reasons: List[str] = field(default_factory=list)
    lessons: List[str] = field(default_factory=list)
    strategy_name: str = "UNKNOWN"


@dataclass(frozen=True)
class DecisionReviewReport:
    module_name: str
    module_version: str
    schema_version: str
    generated_by: str
    generated_at_utc: str
    paper_trade_mode: bool
    live_trading_enabled: bool
    broker_execution_enabled: bool
    reporting_only: bool
    decision_reviews: List[Dict[str, Any]]
    review_count: int
    average_review_score: float
    successful_count: int
    review_required_count: int
    learning_lessons: List[str]
    warnings: List[str]
    errors: List[str]
    safety_guarantees: List[str]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value)


def _symbol(value: Any) -> str:
    return value.strip().upper() if isinstance(value, str) and value.strip() else "UNKNOWN"


def calculate_realized_return_pct(decision_price: float, review_price: float) -> float:
    if decision_price <= 0:
        return 0.0
    return round(((review_price - decision_price) / decision_price) * 100.0, 2)


def calculate_decision_score(realized_return_pct: float, benchmark_return_pct: float, opportunity_cost_pct: float) -> float:
    alpha = realized_return_pct - benchmark_return_pct
    score = 50.0 + (alpha * 2.0) - max(0.0, opportunity_cost_pct)
    return round(max(0.0, min(100.0, score)), 2)


def classify_grade(score: float) -> str:
    if score >= 95: return "A+"
    if score >= 90: return "A"
    if score >= 85: return "B+"
    if score >= 75: return "B"
    if score >= 65: return "C"
    if score >= 50: return "D"
    return "F"


def classify_review_status(score: float) -> str:
    if score >= 85: return "SUCCESSFUL"
    if score >= 70: return "ACCEPTABLE"
    if score >= 50: return "REVIEW"
    return "POOR"


def review_decision(record: Mapping[str, Any], review_date: str | None = None) -> Dict[str, Any]:
    if not isinstance(record, Mapping):
        raise ValueError("decision record must be a mapping")
    decision_type = record.get("decision_type", "")
    if decision_type not in SUPPORTED_DECISION_TYPES:
        raise ValueError("unsupported decision_type")
    decision_price = _number(record.get("decision_price", 0.0))
    review_price = _number(record.get("review_price", 0.0))
    realized = calculate_realized_return_pct(decision_price, review_price)
    benchmark = _number(record.get("benchmark_return_pct", 0.0))
    alternative = _number(record.get("best_alternative_return_pct", 0.0))
    opportunity_cost = round(max(0.0, alternative - realized), 2)
    score = calculate_decision_score(realized, benchmark, opportunity_cost)
    grade = classify_grade(score)
    status = classify_review_status(score)
    alpha = round(realized - benchmark, 2)
    confidence = max(0.0, min(1.0, _number(record.get("confidence", 0.0))))
    expected_up = str(record.get("expected_direction", "UP")).upper() != "DOWN"
    confidence_accurate = (realized >= 0 and expected_up) or (realized <= 0 and not expected_up)
    reasons = [f"Realized return was {realized:.2f}%.", f"Alpha versus benchmark was {alpha:.2f}%."]
    lessons: List[str] = []
    if opportunity_cost > 0:
        lessons.append(f"Opportunity cost was {opportunity_cost:.2f}%; review replacement or timing logic.")
    if alpha < 0:
        lessons.append("Decision underperformed the benchmark; review score thresholds and timing evidence.")
    if confidence >= 0.75 and not confidence_accurate:
        lessons.append("High-confidence forecast was inaccurate; review confidence calibration.")
    if not lessons:
        lessons.append("Decision outcome supported the current strategy rules.")
    return asdict(DecisionReview(
        decision_id=str(record.get("decision_id", "UNKNOWN")),
        symbol=_symbol(record.get("symbol", "UNKNOWN")),
        decision_type=decision_type,
        decision_date=str(record.get("decision_date", "")),
        review_date=review_date or _now()[:10],
        holding_days=max(0, int(_number(record.get("holding_days", 0)))),
        decision_price=decision_price,
        review_price=review_price,
        realized_return_pct=realized,
        benchmark_return_pct=benchmark,
        alpha_pct=alpha,
        opportunity_cost_pct=opportunity_cost,
        income_received=max(0.0, _number(record.get("income_received", 0.0))),
        decision_score=score,
        grade=grade,
        review_status=status,
        confidence_was_accurate=confidence_accurate,
        reasons=reasons,
        lessons=lessons,
        strategy_name=str(record.get("strategy_name", "UNKNOWN")),
    ))


def build_decision_review_report(records: Iterable[Mapping[str, Any]] | None = None) -> Dict[str, Any]:
    reviews = [review_decision(record) for record in list(records or [])]
    average = round(sum(item["decision_score"] for item in reviews) / len(reviews), 2) if reviews else 0.0
    lessons: List[str] = []
    for item in reviews:
        for lesson in item["lessons"]:
            if lesson not in lessons:
                lessons.append(lesson)
    warnings = [] if reviews else ["No decisions supplied; generated a valid empty review report."]
    payload = asdict(DecisionReviewReport(
        module_name=MODULE_NAME,
        module_version=MODULE_VERSION,
        schema_version=SCHEMA_VERSION,
        generated_by=GENERATED_BY,
        generated_at_utc=_now(),
        paper_trade_mode=True,
        live_trading_enabled=False,
        broker_execution_enabled=False,
        reporting_only=True,
        decision_reviews=reviews,
        review_count=len(reviews),
        average_review_score=average,
        successful_count=sum(1 for item in reviews if item["review_status"] == "SUCCESSFUL"),
        review_required_count=sum(1 for item in reviews if item["review_status"] in ["REVIEW", "POOR"]),
        learning_lessons=lessons,
        warnings=warnings,
        errors=[],
        safety_guarantees=list(SAFETY_GUARANTEES),
    ))
    validate_decision_review_report(payload)
    return payload


def validate_decision_review_report(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    for field_name in REQUIRED_REPORT_FIELDS:
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
    for field_name in ["decision_reviews", "learning_lessons", "warnings", "errors", "safety_guarantees"]:
        if not isinstance(payload[field_name], list):
            raise ValueError(f"{field_name} must be a list")
    if payload["review_count"] != len(payload["decision_reviews"]):
        raise ValueError("review_count mismatch")
    for review in payload["decision_reviews"]:
        if not isinstance(review, Mapping):
            raise ValueError("review entries must be mappings")
        for field_name in REVIEW_FIELDS:
            if field_name not in review:
                raise ValueError(f"review missing field: {field_name}")
        if review["decision_type"] not in SUPPORTED_DECISION_TYPES:
            raise ValueError("unsupported decision_type")
        if review["grade"] not in SUPPORTED_GRADES:
            raise ValueError("unsupported grade")
        if review["review_status"] not in SUPPORTED_STATUSES:
            raise ValueError("unsupported review_status")
        if not isinstance(review["reasons"], list) or not isinstance(review["lessons"], list):
            raise ValueError("reasons and lessons must be lists")
    return True


def write_decision_review_report_json(path: str = "decision_review_report.json") -> Dict[str, Any]:
    payload = build_decision_review_report()
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_decision_review_report_json(path: str = "decision_review_report.json") -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_decision_review_report(payload)
    return payload


def write_decision_review_report_csv(path: str = "decision_review_report.csv") -> Dict[str, Any]:
    payload = build_decision_review_report()
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        for row in payload["decision_reviews"]:
            writer.writerow({field_name: row.get(field_name, "") for field_name in REVIEW_FIELDS})
    return payload


def format_decision_review_report_markdown(payload: Mapping[str, Any]) -> str:
    validate_decision_review_report(payload)
    lines = [
        "# Decision Review Report", "",
        f"- Reviews: {payload['review_count']}",
        f"- Average Review Score: {payload['average_review_score']}",
        f"- Successful Decisions: {payload['successful_count']}",
        f"- Review Required: {payload['review_required_count']}", "",
        "## Decision Grades", "",
        "| Symbol | Type | Return | Alpha | Opportunity Cost | Score | Grade | Status |",
        "|---|---|---:|---:|---:|---:|---|---|",
    ]
    for row in payload["decision_reviews"]:
        lines.append(f"| {row['symbol']} | {row['decision_type']} | {row['realized_return_pct']} | {row['alpha_pct']} | {row['opportunity_cost_pct']} | {row['decision_score']} | {row['grade']} | {row['review_status']} |")
    lines.extend(["", "## Learning Lessons"] + [f"- {item}" for item in payload["learning_lessons"]])
    lines.extend(["", "## Safety Guarantees"] + [f"- {item}" for item in payload["safety_guarantees"]])
    return "\n".join(lines) + "\n"


def write_decision_review_report_markdown(path: str = "decision_review_report.md") -> Dict[str, Any]:
    payload = build_decision_review_report()
    Path(path).write_text(format_decision_review_report_markdown(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    write_decision_review_report_json()
    write_decision_review_report_csv()
    write_decision_review_report_markdown()
