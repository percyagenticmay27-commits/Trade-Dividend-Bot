"""
Conviction Engine for the Dividend Bot.

Combines existing strategy-intelligence outputs into a paper-only conviction score.
This module is reporting-only. It does not modify trading logic, portfolio state,
or runtime workflows.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping


MODULE_NAME = "conviction_engine"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"

BOT_NAME = "Agentic Robin Dividend Bot"
BOT_TYPE = "paper_dividend_etf_management"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

VERY_HIGH = "VERY_HIGH"
HIGH = "HIGH"
MEDIUM = "MEDIUM"
LOW = "LOW"
VERY_LOW = "VERY_LOW"
UNKNOWN = "UNKNOWN"
SUPPORTED_CONVICTION_LEVELS = [VERY_HIGH, HIGH, MEDIUM, LOW, VERY_LOW, UNKNOWN]

STRONG_APPROVAL = "STRONG_APPROVAL"
APPROVE = "APPROVE"
WATCH = "WATCH"
WAIT = "WAIT"
REJECT = "REJECT"
SUPPORTED_CONVICTION_ACTIONS = [STRONG_APPROVAL, APPROVE, WATCH, WAIT, REJECT, UNKNOWN]

CONFIDENCE_LEVELS = [LOW, MEDIUM, HIGH]

CONVICTION_COMPONENT_NAMES = [
    "opportunity_quality",
    "entry_score",
    "momentum_confirmation",
    "market_regime_support",
    "market_intelligence_support",
    "dividend_ranking_support",
    "self_funding_support",
    "risk_alignment",
]

DEFAULT_COMPONENT_WEIGHTS = {
    "opportunity_quality": 25,
    "entry_score": 15,
    "momentum_confirmation": 15,
    "market_regime_support": 10,
    "market_intelligence_support": 10,
    "dividend_ranking_support": 10,
    "self_funding_support": 10,
    "risk_alignment": 5,
}

DEFAULT_COMPONENT_SOURCE = "deterministic_fallback"

SAFETY_GUARANTEES = [
    "paper_trade_mode is enforced as True",
    "reporting_only is enforced as True",
    "live_trading_enabled is enforced as False",
    "broker_execution_enabled is enforced as False",
    "no Robinhood execution is performed",
    "no live trading is performed",
    "no order placement is performed",
    "no live internet data is pulled",
    "no external APIs are used",
    "read-only analysis only",
]

INTEGRATION_TARGETS = [
    "opportunity_pairing_report.json",
    "entry_score_report.json",
    "momentum_score_report.json",
    "market_regime_report.json",
    "market_intelligence_report.json",
    "dividend_rankings.json",
    "asset_registry.json",
]

SCORING_MODEL = [
    "Conviction score range is 0 to 100.",
    "Component weights total 100.",
    "Current v1.0 fallback uses score 0 and UNKNOWN until downstream evidence is wired.",
    "Future versions may load existing strategy-intelligence reports and calculate weighted conviction.",
]

RECOMMENDATION_MODEL = [
    "VERY_HIGH conviction may map to STRONG_APPROVAL.",
    "HIGH conviction may map to APPROVE.",
    "MEDIUM conviction may map to WATCH.",
    "LOW conviction may map to WAIT.",
    "VERY_LOW conviction may map to REJECT.",
    "UNKNOWN means deterministic fallback or insufficient evidence.",
]

LIMITATIONS = [
    "Current v1.0 version defines safe interfaces and deterministic fallback behavior only.",
    "No live price, broker, or internet data is consumed.",
    "All conviction components default to UNKNOWN until future inputs are implemented.",
]

REPORT_REQUIRED_FIELDS = [
    "bot_name", "bot_type", "module_name", "module_version", "schema_version",
    "generated_by", "generated_at_utc", "paper_trade_mode", "live_trading_enabled",
    "broker_execution_enabled", "reporting_only", "supported_conviction_levels",
    "supported_conviction_actions", "confidence_levels", "conviction_component_names",
    "component_weights", "conviction_components", "conviction_score", "conviction_level",
    "conviction_action", "confidence", "confidence_level", "risk_flags", "recommendations",
    "warnings", "errors", "scoring_model", "recommendation_model", "integration_targets",
    "safety_guarantees", "limitations",
]

REPORT_LIST_FIELDS = [
    "supported_conviction_levels", "supported_conviction_actions", "confidence_levels",
    "conviction_component_names", "conviction_components", "risk_flags", "recommendations",
    "warnings", "errors", "scoring_model", "recommendation_model", "integration_targets",
    "safety_guarantees", "limitations",
]

COMPONENT_REQUIRED_FIELDS = [
    "component_name", "score", "weight", "weighted_score", "status", "confidence",
    "confidence_level", "source", "warnings", "notes",
]

COMPONENT_LIST_FIELDS = ["warnings"]


@dataclass(frozen=True)
class ConvictionComponent:
    component_name: str
    score: float = 0.0
    weight: float = 0.0
    weighted_score: float = 0.0
    status: str = UNKNOWN
    confidence: float = 0.0
    confidence_level: str = LOW
    source: str = DEFAULT_COMPONENT_SOURCE
    warnings: List[str] = field(default_factory=list)
    notes: str = ""


@dataclass(frozen=True)
class ConvictionReport:
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
    supported_conviction_levels: List[str]
    supported_conviction_actions: List[str]
    confidence_levels: List[str]
    conviction_component_names: List[str]
    component_weights: Dict[str, float]
    conviction_components: List[Dict[str, Any]]
    conviction_score: float
    conviction_level: str
    conviction_action: str
    confidence: float
    confidence_level: str
    risk_flags: List[str]
    recommendations: List[str]
    warnings: List[str]
    errors: List[str]
    scoring_model: List[str]
    recommendation_model: List[str]
    integration_targets: List[str]
    safety_guarantees: List[str]
    limitations: List[str]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def classify_conviction_level(score: Any) -> str:
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        return UNKNOWN
    if score >= 90:
        return VERY_HIGH
    if score >= 80:
        return HIGH
    if score >= 65:
        return MEDIUM
    if score >= 50:
        return LOW
    if score >= 0:
        return VERY_LOW
    return UNKNOWN


def classify_conviction_action(score: Any) -> str:
    level = classify_conviction_level(score)
    if level == VERY_HIGH:
        return STRONG_APPROVAL
    if level == HIGH:
        return APPROVE
    if level == MEDIUM:
        return WATCH
    if level == LOW:
        return WAIT
    if level == VERY_LOW:
        return REJECT
    return UNKNOWN


def calculate_weighted_conviction_score(components: Mapping[str, Any], weights: Mapping[str, Any]) -> float:
    _validate_weights(weights)
    if not isinstance(components, Mapping):
        raise ValueError("components must be a mapping")
    total = 0.0
    for name, weight in weights.items():
        value = components.get(name, 0)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            value = 0
        value = max(0.0, min(100.0, float(value)))
        total += value * (float(weight) / 100.0)
    return round(max(0.0, min(100.0, total)), 2)


def _build_component(name: str) -> Dict[str, Any]:
    weight = DEFAULT_COMPONENT_WEIGHTS[name]
    return asdict(ConvictionComponent(
        component_name=name,
        weight=weight,
        weighted_score=0.0,
        warnings=[f"No live evidence connected for component: {name}."],
        notes="Deterministic fallback component.",
    ))


def build_conviction_report() -> Dict[str, Any]:
    payload = asdict(ConvictionReport(
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
        supported_conviction_levels=list(SUPPORTED_CONVICTION_LEVELS),
        supported_conviction_actions=list(SUPPORTED_CONVICTION_ACTIONS),
        confidence_levels=list(CONFIDENCE_LEVELS),
        conviction_component_names=list(CONVICTION_COMPONENT_NAMES),
        component_weights=dict(DEFAULT_COMPONENT_WEIGHTS),
        conviction_components=[_build_component(name) for name in CONVICTION_COMPONENT_NAMES],
        conviction_score=0.0,
        conviction_level=UNKNOWN,
        conviction_action=UNKNOWN,
        confidence=0.0,
        confidence_level=LOW,
        risk_flags=[],
        recommendations=["Use this report as a paper-only conviction interface until future inputs are implemented."],
        warnings=["Conviction inputs are not connected in v1.0; using deterministic UNKNOWN fallback."],
        errors=[],
        scoring_model=list(SCORING_MODEL),
        recommendation_model=list(RECOMMENDATION_MODEL),
        integration_targets=list(INTEGRATION_TARGETS),
        safety_guarantees=list(SAFETY_GUARANTEES),
        limitations=list(LIMITATIONS),
    ))
    validate_conviction_report(payload)
    return payload


def _require_mapping(payload: Any, label: str = "payload") -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{label} must be a mapping/dictionary")
    return payload


def _validate_required(payload: Mapping[str, Any], fields: List[str], label: str) -> None:
    missing = [field for field in fields if field not in payload]
    if missing:
        raise ValueError(f"{label} missing required field(s): {', '.join(missing)}")


def _validate_string_list(value: Any, field_name: str, allow_empty: bool = True) -> None:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    if not allow_empty and not value:
        raise ValueError(f"{field_name} must not be empty")
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name}[{index}] must be a non-empty string")


def _validate_number(value: Any, field_name: str, minimum: float, maximum: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric")
    if value < minimum or value > maximum:
        raise ValueError(f"{field_name} must be between {minimum} and {maximum}")


def _validate_weights(weights: Mapping[str, Any]) -> None:
    if not isinstance(weights, Mapping):
        raise ValueError("component_weights must be a mapping")
    if set(weights.keys()) != set(DEFAULT_COMPONENT_WEIGHTS.keys()):
        raise ValueError("component_weights keys must match approved component names")
    total = 0.0
    for key, value in weights.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"component weight {key} must be numeric")
        if value < 0:
            raise ValueError(f"component weight {key} must not be negative")
        total += float(value)
    if abs(total - 100.0) > 1e-9:
        raise ValueError("component_weights must total 100")


def _validate_component(component: Any) -> None:
    component = _require_mapping(component, "conviction_component")
    _validate_required(component, COMPONENT_REQUIRED_FIELDS, "conviction_component")
    if component["component_name"] not in CONVICTION_COMPONENT_NAMES:
        raise ValueError("component_name must be supported")
    if component["status"] not in SUPPORTED_CONVICTION_LEVELS:
        raise ValueError("component status must be supported")
    if component["confidence_level"] not in CONFIDENCE_LEVELS:
        raise ValueError("component confidence_level must be LOW, MEDIUM, or HIGH")
    _validate_number(component["score"], "component.score", 0, 100)
    _validate_number(component["weight"], "component.weight", 0, 100)
    _validate_number(component["weighted_score"], "component.weighted_score", 0, 100)
    _validate_number(component["confidence"], "component.confidence", 0.0, 1.0)
    if not isinstance(component["source"], str) or not component["source"].strip():
        raise ValueError("component.source must be a non-empty string")
    if not isinstance(component["notes"], str):
        raise ValueError("component.notes must be a string")
    for field_name in COMPONENT_LIST_FIELDS:
        _validate_string_list(component[field_name], f"component.{field_name}", allow_empty=True)


def validate_conviction_report(payload: Any) -> bool:
    payload = _require_mapping(payload)
    _validate_required(payload, REPORT_REQUIRED_FIELDS, "payload")

    expected = {
        "bot_name": BOT_NAME,
        "bot_type": BOT_TYPE,
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_by": GENERATED_BY,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "reporting_only": True,
    }
    for key, expected_value in expected.items():
        if payload.get(key) != expected_value:
            raise ValueError(f"{key} must be {expected_value!r}")
    if not isinstance(payload["generated_at_utc"], str) or not payload["generated_at_utc"].strip():
        raise ValueError("generated_at_utc must be a non-empty string")

    for field_name in REPORT_LIST_FIELDS:
        if field_name == "conviction_components":
            if not isinstance(payload[field_name], list) or not payload[field_name]:
                raise ValueError("conviction_components must be a non-empty list")
        else:
            _validate_string_list(payload[field_name], field_name, allow_empty=True)

    if payload["supported_conviction_levels"] != SUPPORTED_CONVICTION_LEVELS:
        raise ValueError("supported_conviction_levels must match approved list")
    if payload["supported_conviction_actions"] != SUPPORTED_CONVICTION_ACTIONS:
        raise ValueError("supported_conviction_actions must match approved list")
    if payload["confidence_levels"] != CONFIDENCE_LEVELS:
        raise ValueError("confidence_levels must match approved list")
    if payload["conviction_component_names"] != CONVICTION_COMPONENT_NAMES:
        raise ValueError("conviction_component_names must match approved list")
    _validate_weights(payload["component_weights"])

    if payload["conviction_level"] not in SUPPORTED_CONVICTION_LEVELS:
        raise ValueError("conviction_level must be supported")
    if payload["conviction_action"] not in SUPPORTED_CONVICTION_ACTIONS:
        raise ValueError("conviction_action must be supported")
    if payload["confidence_level"] not in CONFIDENCE_LEVELS:
        raise ValueError("confidence_level must be LOW, MEDIUM, or HIGH")
    _validate_number(payload["conviction_score"], "conviction_score", 0, 100)
    _validate_number(payload["confidence"], "confidence", 0.0, 1.0)

    seen = set()
    for component in payload["conviction_components"]:
        _validate_component(component)
        name = component["component_name"]
        if name in seen:
            raise ValueError(f"duplicate conviction component: {name}")
        seen.add(name)
    if set(seen) != set(CONVICTION_COMPONENT_NAMES):
        raise ValueError("conviction_components must include exactly the approved component names")
    return True


def write_conviction_report_json(path: str = "conviction_report.json") -> Dict[str, Any]:
    payload = build_conviction_report()
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_conviction_report_json(path: str = "conviction_report.json") -> Dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    validate_conviction_report(payload)
    return payload


def _format_list(title: str, values: List[str]) -> List[str]:
    lines = [f"## {title}"]
    if values:
        lines.extend(f"- {value}" for value in values)
    else:
        lines.append("- None")
    return lines


def format_conviction_report_markdown(payload: Mapping[str, Any]) -> str:
    validate_conviction_report(payload)
    lines = [
        "# Conviction Report",
        "",
        f"- Module: {payload['module_name']}",
        f"- Generated At UTC: {payload['generated_at_utc']}",
        f"- Paper Trade Mode: {payload['paper_trade_mode']}",
        f"- Reporting Only: {payload['reporting_only']}",
        "",
        "## Conviction Summary",
        f"- Conviction Score: {payload['conviction_score']}",
        f"- Conviction Level: {payload['conviction_level']}",
        f"- Conviction Action: {payload['conviction_action']}",
        f"- Confidence: {payload['confidence']}",
        f"- Confidence Level: {payload['confidence_level']}",
        "",
        "## Component Weights",
    ]
    for key, value in payload["component_weights"].items():
        lines.append(f"- {key}: {value}")
    lines.extend([
        "",
        "## Conviction Components",
        "",
        "| Component | Status | Score | Weight | Weighted Score | Confidence | Source |",
        "|---|---|---:|---:|---:|---:|---|",
    ])
    for component in payload["conviction_components"]:
        lines.append(
            f"| {component['component_name']} | {component['status']} | {component['score']} | {component['weight']} | {component['weighted_score']} | {component['confidence']} | {component['source']} |"
        )
    lines.append("")
    for title, values in [
        ("Supported Conviction Levels", payload["supported_conviction_levels"]),
        ("Supported Conviction Actions", payload["supported_conviction_actions"]),
        ("Scoring Model", payload["scoring_model"]),
        ("Recommendation Model", payload["recommendation_model"]),
        ("Integration Targets", payload["integration_targets"]),
        ("Risk Flags", payload["risk_flags"]),
        ("Recommendations", payload["recommendations"]),
        ("Warnings", payload["warnings"]),
        ("Errors", payload["errors"]),
        ("Safety Guarantees", payload["safety_guarantees"]),
        ("Limitations", payload["limitations"]),
    ]:
        lines.extend(_format_list(title, values))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_conviction_report_markdown(path: str = "conviction_report.md") -> Dict[str, Any]:
    payload = build_conviction_report()
    Path(path).write_text(format_conviction_report_markdown(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    write_conviction_report_json()
    write_conviction_report_markdown()
