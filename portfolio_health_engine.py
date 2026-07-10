"""
Portfolio Health Engine for the Dividend Bot.

Calculates a paper-only portfolio health score from quality, diversification,
income stability, dividend growth, opportunity strength, conviction, momentum,
cash reserve health, concentration, pair balance, reinvestment efficiency, and
market-regime alignment. No brokerage or order execution is performed.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping

MODULE_NAME = "portfolio_health_engine"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

SUPPORTED_HEALTH_STATUSES = ["EXCELLENT", "GOOD", "FAIR", "WEAK", "CRITICAL", "UNKNOWN"]
SUPPORTED_GRADES = ["A", "B", "C", "D", "F", "UNKNOWN"]
SUPPORTED_TRENDS = ["IMPROVING", "STABLE", "DETERIORATING", "UNKNOWN"]

HEALTH_COMPONENT_WEIGHTS = {
    "portfolio_quality_score": 15,
    "diversification_score": 10,
    "income_stability_score": 10,
    "dividend_growth_score": 10,
    "opportunity_strength_score": 10,
    "conviction_strength_score": 10,
    "momentum_strength_score": 10,
    "cash_reserve_health_score": 10,
    "concentration_health_score": 5,
    "pair_balance_score": 3,
    "reinvestment_efficiency_score": 4,
    "market_regime_alignment_score": 3,
}

COMPONENT_NAMES = list(HEALTH_COMPONENT_WEIGHTS)
SAFETY_GUARANTEES = [
    "paper_trade_mode is enforced as True",
    "reporting_only is enforced as True",
    "live_trading_enabled is enforced as False",
    "broker_execution_enabled is enforced as False",
    "no Robinhood execution is performed",
    "no brokerage execution is performed",
    "no order placement is performed",
    "health output is analytical and read-only",
]

REPORT_REQUIRED_FIELDS = [
    "module_name", "module_version", "schema_version", "generated_by", "generated_at_utc",
    "paper_trade_mode", "live_trading_enabled", "broker_execution_enabled", "reporting_only",
    "health_component_weights", "health_components", "overall_health_score", "health_grade",
    "health_status", "health_trend", "previous_health_score", "score_change", "top_strengths",
    "top_concerns", "risk_flags", "recommended_actions", "warnings", "errors",
    "safety_guarantees",
]


@dataclass(frozen=True)
class PortfolioHealthComponent:
    component_name: str
    score: float = 0.0
    weight: float = 0.0
    weighted_score: float = 0.0
    status: str = "UNKNOWN"
    notes: str = ""


@dataclass(frozen=True)
class PortfolioHealthReport:
    module_name: str
    module_version: str
    schema_version: str
    generated_by: str
    generated_at_utc: str
    paper_trade_mode: bool
    live_trading_enabled: bool
    broker_execution_enabled: bool
    reporting_only: bool
    health_component_weights: Dict[str, float]
    health_components: List[Dict[str, Any]]
    overall_health_score: float
    health_grade: str
    health_status: str
    health_trend: str
    previous_health_score: float
    score_change: float
    top_strengths: List[str]
    top_concerns: List[str]
    risk_flags: List[str]
    recommended_actions: List[str]
    warnings: List[str]
    errors: List[str]
    safety_guarantees: List[str]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _score(value: Any) -> float:
    return round(max(0.0, min(100.0, _number(value, 0.0))), 2)


def classify_health_grade(score: Any) -> str:
    value = _score(score)
    if value >= 90:
        return "A"
    if value >= 80:
        return "B"
    if value >= 70:
        return "C"
    if value >= 60:
        return "D"
    return "F"


def classify_health_status(score: Any) -> str:
    value = _score(score)
    if value >= 90:
        return "EXCELLENT"
    if value >= 80:
        return "GOOD"
    if value >= 70:
        return "FAIR"
    if value >= 60:
        return "WEAK"
    return "CRITICAL"


def classify_health_trend(current_score: Any, previous_score: Any) -> str:
    current = _score(current_score)
    previous = _score(previous_score)
    change = current - previous
    if change >= 2.0:
        return "IMPROVING"
    if change <= -2.0:
        return "DETERIORATING"
    return "STABLE"


def calculate_overall_health_score(components: Mapping[str, Any], weights: Mapping[str, Any] | None = None) -> float:
    if not isinstance(components, Mapping):
        raise ValueError("components must be a mapping")
    active_weights = dict(weights or HEALTH_COMPONENT_WEIGHTS)
    if set(active_weights) != set(HEALTH_COMPONENT_WEIGHTS):
        raise ValueError("weights must match approved component names")
    if abs(sum(float(value) for value in active_weights.values()) - 100.0) > 1e-9:
        raise ValueError("health component weights must total 100")
    total = 0.0
    for name, weight in active_weights.items():
        total += _score(components.get(name, 0.0)) * float(weight) / 100.0
    return round(total, 2)


def _component_status(score: float) -> str:
    if score >= 80:
        return "STRONG"
    if score >= 65:
        return "ACCEPTABLE"
    if score >= 50:
        return "WATCH"
    return "WEAK"


def _build_components(component_scores: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for name in COMPONENT_NAMES:
        score = _score(component_scores.get(name, 0.0))
        weight = float(HEALTH_COMPONENT_WEIGHTS[name])
        rows.append(asdict(PortfolioHealthComponent(
            component_name=name,
            score=score,
            weight=weight,
            weighted_score=round(score * weight / 100.0, 2),
            status=_component_status(score),
            notes="Portfolio-level analytical component.",
        )))
    return rows


def _derive_strengths(component_scores: Mapping[str, Any]) -> List[str]:
    ranked = sorted(((name, _score(component_scores.get(name, 0.0))) for name in COMPONENT_NAMES), key=lambda item: (-item[1], item[0]))
    return [f"{name}: {score:.2f}" for name, score in ranked[:3] if score >= 70]


def _derive_concerns(component_scores: Mapping[str, Any]) -> List[str]:
    ranked = sorted(((name, _score(component_scores.get(name, 0.0))) for name in COMPONENT_NAMES), key=lambda item: (item[1], item[0]))
    return [f"{name}: {score:.2f}" for name, score in ranked[:3] if score < 70]


def _derive_risk_flags(component_scores: Mapping[str, Any]) -> List[str]:
    flags = []
    if _score(component_scores.get("cash_reserve_health_score", 0.0)) < 60:
        flags.append("CASH_RESERVE_BELOW_HEALTH_TARGET")
    if _score(component_scores.get("concentration_health_score", 0.0)) < 60:
        flags.append("CONCENTRATION_RISK")
    if _score(component_scores.get("income_stability_score", 0.0)) < 60:
        flags.append("INCOME_STABILITY_RISK")
    if _score(component_scores.get("momentum_strength_score", 0.0)) < 50:
        flags.append("PORTFOLIO_MOMENTUM_WEAK")
    return flags


def _derive_actions(component_scores: Mapping[str, Any]) -> List[str]:
    actions = []
    for name in COMPONENT_NAMES:
        score = _score(component_scores.get(name, 0.0))
        if score < 60:
            actions.append(f"Review and improve {name}.")
    if not actions:
        actions.append("Maintain current paper-only portfolio controls and continue monitoring.")
    return actions


def build_portfolio_health_report(
    component_scores: Mapping[str, Any] | None = None,
    previous_health_score: float = 0.0,
) -> Dict[str, Any]:
    scores = dict(component_scores or {})
    normalized = {name: _score(scores.get(name, 0.0)) for name in COMPONENT_NAMES}
    overall = calculate_overall_health_score(normalized)
    payload = asdict(PortfolioHealthReport(
        module_name=MODULE_NAME,
        module_version=MODULE_VERSION,
        schema_version=SCHEMA_VERSION,
        generated_by=GENERATED_BY,
        generated_at_utc=_utc_now_iso(),
        paper_trade_mode=True,
        live_trading_enabled=False,
        broker_execution_enabled=False,
        reporting_only=True,
        health_component_weights=dict(HEALTH_COMPONENT_WEIGHTS),
        health_components=_build_components(normalized),
        overall_health_score=overall,
        health_grade=classify_health_grade(overall),
        health_status=classify_health_status(overall),
        health_trend=classify_health_trend(overall, previous_health_score),
        previous_health_score=_score(previous_health_score),
        score_change=round(overall - _score(previous_health_score), 2),
        top_strengths=_derive_strengths(normalized),
        top_concerns=_derive_concerns(normalized),
        risk_flags=_derive_risk_flags(normalized),
        recommended_actions=_derive_actions(normalized),
        warnings=[] if component_scores else ["No component scores supplied; deterministic zero-score fallback used."],
        errors=[],
        safety_guarantees=list(SAFETY_GUARANTEES),
    ))
    validate_portfolio_health_report(payload)
    return payload


def validate_portfolio_health_report(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    for field_name in REPORT_REQUIRED_FIELDS:
        if field_name not in payload:
            raise ValueError(f"missing required field: {field_name}")
    expected = {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_by": GENERATED_BY,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "reporting_only": True,
    }
    for field_name, expected_value in expected.items():
        if payload[field_name] != expected_value:
            raise ValueError(f"{field_name} must be {expected_value!r}")
    if payload["health_component_weights"] != HEALTH_COMPONENT_WEIGHTS:
        raise ValueError("health_component_weights must match approved weights")
    if payload["health_grade"] not in SUPPORTED_GRADES:
        raise ValueError("unsupported health grade")
    if payload["health_status"] not in SUPPORTED_HEALTH_STATUSES:
        raise ValueError("unsupported health status")
    if payload["health_trend"] not in SUPPORTED_TRENDS:
        raise ValueError("unsupported health trend")
    for field_name in ["overall_health_score", "previous_health_score"]:
        value = payload[field_name]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100:
            raise ValueError(f"{field_name} must be between 0 and 100")
    for field_name in ["health_components", "top_strengths", "top_concerns", "risk_flags", "recommended_actions", "warnings", "errors", "safety_guarantees"]:
        if not isinstance(payload[field_name], list):
            raise ValueError(f"{field_name} must be a list")
    if len(payload["health_components"]) != len(COMPONENT_NAMES):
        raise ValueError("health_components must include every approved component")
    names = []
    for component in payload["health_components"]:
        if not isinstance(component, Mapping):
            raise ValueError("health component must be a mapping")
        for field_name in ["component_name", "score", "weight", "weighted_score", "status", "notes"]:
            if field_name not in component:
                raise ValueError(f"health component missing {field_name}")
        names.append(component["component_name"])
        if component["component_name"] not in COMPONENT_NAMES:
            raise ValueError("unsupported health component")
        if not 0 <= component["score"] <= 100:
            raise ValueError("component score must be between 0 and 100")
    if names != COMPONENT_NAMES:
        raise ValueError("health component ordering must match approved component list")
    return True


def write_portfolio_health_report_json(path: str = "portfolio_health_report.json") -> Dict[str, Any]:
    payload = build_portfolio_health_report()
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_portfolio_health_report_json(path: str = "portfolio_health_report.json") -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_portfolio_health_report(payload)
    return payload


def format_portfolio_health_report_markdown(payload: Mapping[str, Any]) -> str:
    validate_portfolio_health_report(payload)
    lines = [
        "# Portfolio Health Report",
        "",
        f"- Overall Health Score: {payload['overall_health_score']}",
        f"- Grade: {payload['health_grade']}",
        f"- Status: {payload['health_status']}",
        f"- Trend: {payload['health_trend']}",
        f"- Score Change: {payload['score_change']}",
        "",
        "## Health Components",
        "",
        "| Component | Score | Weight | Weighted Score | Status |",
        "|---|---:|---:|---:|---|",
    ]
    for row in payload["health_components"]:
        lines.append(f"| {row['component_name']} | {row['score']} | {row['weight']} | {row['weighted_score']} | {row['status']} |")
    for title, values in [
        ("Top Strengths", payload["top_strengths"]),
        ("Top Concerns", payload["top_concerns"]),
        ("Risk Flags", payload["risk_flags"]),
        ("Recommended Actions", payload["recommended_actions"]),
        ("Safety Guarantees", payload["safety_guarantees"]),
    ]:
        lines.extend(["", f"## {title}"])
        lines.extend([f"- {value}" for value in values] or ["- None"])
    return "\n".join(lines) + "\n"


def write_portfolio_health_report_markdown(path: str = "portfolio_health_report.md") -> Dict[str, Any]:
    payload = build_portfolio_health_report()
    Path(path).write_text(format_portfolio_health_report_markdown(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    write_portfolio_health_report_json()
    write_portfolio_health_report_markdown()
