"""
Portfolio Decision Engine for the Dividend Bot.

Transforms scoring outputs into paper-only portfolio recommendations. This module
is reporting-only and never places orders, connects to brokers, or changes the
existing daily trading workflow.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping


MODULE_NAME = "portfolio_decision_engine"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"

BOT_NAME = "Agentic Robin Dividend Bot"
BOT_TYPE = "paper_dividend_etf_management"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

INCREASE_ALLOCATION = "INCREASE_ALLOCATION"
MAINTAIN_ALLOCATION = "MAINTAIN_ALLOCATION"
REDUCE_ALLOCATION = "REDUCE_ALLOCATION"
ROTATE_OPPORTUNITY = "ROTATE_OPPORTUNITY"
WAIT_FOR_ENTRY = "WAIT_FOR_ENTRY"
AVOID_ALLOCATION = "AVOID_ALLOCATION"
UNKNOWN = "UNKNOWN"
SUPPORTED_DECISION_ACTIONS = [
    INCREASE_ALLOCATION,
    MAINTAIN_ALLOCATION,
    REDUCE_ALLOCATION,
    ROTATE_OPPORTUNITY,
    WAIT_FOR_ENTRY,
    AVOID_ALLOCATION,
    UNKNOWN,
]

HIGH_PRIORITY = "HIGH_PRIORITY"
MEDIUM_PRIORITY = "MEDIUM_PRIORITY"
LOW_PRIORITY = "LOW_PRIORITY"
MONITOR = "MONITOR"
AVOID = "AVOID"
SUPPORTED_DECISION_PRIORITIES = [HIGH_PRIORITY, MEDIUM_PRIORITY, LOW_PRIORITY, MONITOR, AVOID, UNKNOWN]

LOW = "LOW"
MEDIUM = "MEDIUM"
HIGH = "HIGH"
SUPPORTED_CONFIDENCE_LEVELS = [LOW, MEDIUM, HIGH]

DECISION_COMPONENT_NAMES = [
    "opportunity_score",
    "conviction_score",
    "entry_score",
    "momentum_score",
    "dividend_ranking_score",
    "self_funding_score",
    "risk_adjustment_score",
]

DEFAULT_DECISION_WEIGHTS = {
    "opportunity_score": 25,
    "conviction_score": 25,
    "entry_score": 15,
    "momentum_score": 10,
    "dividend_ranking_score": 10,
    "self_funding_score": 10,
    "risk_adjustment_score": 5,
}

SAFETY_GUARANTEES = [
    "paper_trade_mode is enforced as True",
    "reporting_only is enforced as True",
    "live_trading_enabled is enforced as False",
    "broker_execution_enabled is enforced as False",
    "no Robinhood execution is performed",
    "no live trading is performed",
    "no order placement is performed",
    "no portfolio state mutation is performed",
    "read-only recommendations only",
]

INPUT_FILES = [
    "opportunity_pairing_report.json",
    "conviction_report.json",
    "entry_score_report.json",
    "momentum_score_report.json",
    "dividend_rankings.json",
]

SCORING_MODEL = [
    "Portfolio decision score range is 0 to 100.",
    "Component weights total 100.",
    "Higher opportunity, conviction, entry, momentum, dividend ranking, self-funding, and risk-adjustment scores improve the decision score.",
    "Current v1.0 behavior supports explicit candidate input or a valid empty fallback report.",
]

DECISION_MODEL = [
    "85 to 100 maps to INCREASE_ALLOCATION and HIGH_PRIORITY.",
    "75 to 84 maps to MAINTAIN_ALLOCATION and MEDIUM_PRIORITY.",
    "60 to 74 maps to WAIT_FOR_ENTRY and LOW_PRIORITY.",
    "45 to 59 maps to REDUCE_ALLOCATION and MONITOR.",
    "0 to 44 maps to AVOID_ALLOCATION and AVOID.",
    "Missing candidates produce an empty valid report.",
]

LIMITATIONS = [
    "Current v1.0 module does not modify portfolio state.",
    "No live broker, account, position, or order data is consumed.",
    "Recommendations are paper-only decision guidance.",
]

DECISION_FIELDS = [
    "symbol",
    "opportunity_name",
    "decision_score",
    "decision_action",
    "decision_priority",
    "opportunity_score",
    "conviction_score",
    "entry_score",
    "momentum_score",
    "dividend_ranking_score",
    "self_funding_score",
    "risk_adjustment_score",
    "confidence",
    "confidence_level",
    "recommended_allocation_change",
    "risk_flags",
    "notes",
]

REPORT_REQUIRED_FIELDS = [
    "bot_name", "bot_type", "module_name", "module_version", "schema_version",
    "generated_by", "generated_at_utc", "paper_trade_mode", "live_trading_enabled",
    "broker_execution_enabled", "reporting_only", "supported_decision_actions",
    "supported_decision_priorities", "confidence_levels", "decision_component_names",
    "decision_weights", "input_files", "available_input_files", "missing_input_files",
    "portfolio_decisions", "decision_count", "warnings", "errors", "scoring_model",
    "decision_model", "safety_guarantees", "limitations",
]

REPORT_LIST_FIELDS = [
    "supported_decision_actions", "supported_decision_priorities", "confidence_levels",
    "decision_component_names", "input_files", "available_input_files", "missing_input_files",
    "portfolio_decisions", "warnings", "errors", "scoring_model", "decision_model",
    "safety_guarantees", "limitations",
]


@dataclass(frozen=True)
class PortfolioDecisionComponent:
    component_name: str
    score: float = 0.0
    weight: float = 0.0
    weighted_score: float = 0.0


@dataclass(frozen=True)
class PortfolioDecision:
    symbol: str
    opportunity_name: str = ""
    decision_score: float = 0.0
    decision_action: str = UNKNOWN
    decision_priority: str = UNKNOWN
    opportunity_score: float = 0.0
    conviction_score: float = 0.0
    entry_score: float = 0.0
    momentum_score: float = 0.0
    dividend_ranking_score: float = 0.0
    self_funding_score: float = 0.0
    risk_adjustment_score: float = 0.0
    confidence: float = 0.0
    confidence_level: str = LOW
    recommended_allocation_change: float = 0.0
    risk_flags: List[str] = field(default_factory=list)
    notes: str = ""


@dataclass(frozen=True)
class PortfolioDecisionReport:
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
    supported_decision_actions: List[str]
    supported_decision_priorities: List[str]
    confidence_levels: List[str]
    decision_component_names: List[str]
    decision_weights: Dict[str, float]
    input_files: List[str]
    available_input_files: List[str]
    missing_input_files: List[str]
    portfolio_decisions: List[Dict[str, Any]]
    decision_count: int
    warnings: List[str]
    errors: List[str]
    scoring_model: List[str]
    decision_model: List[str]
    safety_guarantees: List[str]
    limitations: List[str]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _clamp_score(value: Any) -> float:
    return max(0.0, min(100.0, _number(value, 0.0)))


def _validate_weights(weights: Mapping[str, Any]) -> None:
    if not isinstance(weights, Mapping):
        raise ValueError("decision_weights must be a mapping")
    if set(weights.keys()) != set(DEFAULT_DECISION_WEIGHTS.keys()):
        raise ValueError("decision_weights keys must match approved component names")
    total = 0.0
    for key, value in weights.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"decision weight {key} must be numeric")
        if value < 0:
            raise ValueError(f"decision weight {key} must not be negative")
        total += float(value)
    if abs(total - 100.0) > 1e-9:
        raise ValueError("decision_weights must total 100")


def calculate_portfolio_decision_score(candidate: Mapping[str, Any], weights: Mapping[str, Any]) -> float:
    _validate_weights(weights)
    if not isinstance(candidate, Mapping):
        raise ValueError("candidate must be a mapping")
    total = 0.0
    for name, weight in weights.items():
        total += _clamp_score(candidate.get(name, 0.0)) * (float(weight) / 100.0)
    return round(max(0.0, min(100.0, total)), 2)


def classify_decision_action(score: Any) -> str:
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        return UNKNOWN
    if score >= 85:
        return INCREASE_ALLOCATION
    if score >= 75:
        return MAINTAIN_ALLOCATION
    if score >= 60:
        return WAIT_FOR_ENTRY
    if score >= 45:
        return REDUCE_ALLOCATION
    if score >= 0:
        return AVOID_ALLOCATION
    return UNKNOWN


def classify_decision_priority(score: Any) -> str:
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        return UNKNOWN
    if score >= 85:
        return HIGH_PRIORITY
    if score >= 75:
        return MEDIUM_PRIORITY
    if score >= 60:
        return LOW_PRIORITY
    if score >= 45:
        return MONITOR
    if score >= 0:
        return AVOID
    return UNKNOWN


def _allocation_change_for_action(action: str) -> float:
    mapping = {
        INCREASE_ALLOCATION: 0.05,
        MAINTAIN_ALLOCATION: 0.0,
        WAIT_FOR_ENTRY: 0.0,
        REDUCE_ALLOCATION: -0.05,
        AVOID_ALLOCATION: -0.10,
        ROTATE_OPPORTUNITY: 0.0,
        UNKNOWN: 0.0,
    }
    return mapping.get(action, 0.0)


def _normalize_candidate(raw: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("candidate must be a mapping")
    symbol = raw.get("symbol", "")
    if not isinstance(symbol, str) or not symbol.strip():
        symbol = "UNKNOWN"
    opportunity_name = raw.get("opportunity_name", "")
    if not isinstance(opportunity_name, str):
        opportunity_name = ""
    risk_flags = raw.get("risk_flags", [])
    if not isinstance(risk_flags, list):
        risk_flags = []
    risk_flags = [str(item) for item in risk_flags if isinstance(item, str) and item.strip()]
    notes = raw.get("notes", "")
    if not isinstance(notes, str):
        notes = ""
    normalized = {
        "symbol": symbol.strip().upper(),
        "opportunity_name": opportunity_name.strip(),
        "opportunity_score": _clamp_score(raw.get("opportunity_score", raw.get("combined_score", 0.0))),
        "conviction_score": _clamp_score(raw.get("conviction_score", 0.0)),
        "entry_score": _clamp_score(raw.get("entry_score", 0.0)),
        "momentum_score": _clamp_score(raw.get("momentum_score", 0.0)),
        "dividend_ranking_score": _clamp_score(raw.get("dividend_ranking_score", raw.get("overall_score", 0.0))),
        "self_funding_score": _clamp_score(raw.get("self_funding_score", 0.0)),
        "risk_adjustment_score": _clamp_score(raw.get("risk_adjustment_score", 0.0)),
        "confidence": max(0.0, min(1.0, _number(raw.get("confidence", 0.0), 0.0))),
        "confidence_level": raw.get("confidence_level", LOW) if raw.get("confidence_level", LOW) in SUPPORTED_CONFIDENCE_LEVELS else LOW,
        "risk_flags": risk_flags,
        "notes": notes,
    }
    score = calculate_portfolio_decision_score(normalized, DEFAULT_DECISION_WEIGHTS)
    action = classify_decision_action(score)
    return asdict(PortfolioDecision(
        symbol=normalized["symbol"],
        opportunity_name=normalized["opportunity_name"],
        decision_score=score,
        decision_action=action,
        decision_priority=classify_decision_priority(score),
        opportunity_score=normalized["opportunity_score"],
        conviction_score=normalized["conviction_score"],
        entry_score=normalized["entry_score"],
        momentum_score=normalized["momentum_score"],
        dividend_ranking_score=normalized["dividend_ranking_score"],
        self_funding_score=normalized["self_funding_score"],
        risk_adjustment_score=normalized["risk_adjustment_score"],
        confidence=normalized["confidence"],
        confidence_level=normalized["confidence_level"],
        recommended_allocation_change=_allocation_change_for_action(action),
        risk_flags=normalized["risk_flags"],
        notes=normalized["notes"],
    ))


def rank_portfolio_decisions(decisions: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    normalized = [_normalize_candidate(item) for item in decisions]
    normalized.sort(key=lambda item: (-item["decision_score"], item["symbol"]))
    return normalized


def _available_inputs(root_path: str) -> tuple[List[str], List[str]]:
    root = Path(root_path)
    available = [name for name in INPUT_FILES if (root / name).exists()]
    missing = [name for name in INPUT_FILES if name not in available]
    return available, missing


def build_portfolio_decision_report(decisions: Iterable[Mapping[str, Any]] | None = None, root_path: str = ".") -> Dict[str, Any]:
    available, missing = _available_inputs(root_path)
    ranked = rank_portfolio_decisions(list(decisions or []))
    warnings = []
    if not ranked:
        warnings.append("No portfolio decision candidates supplied; generated valid empty paper-only report.")
    if missing:
        warnings.append("Optional input files missing; deterministic input-file availability recorded only.")
    payload = asdict(PortfolioDecisionReport(
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
        supported_decision_actions=list(SUPPORTED_DECISION_ACTIONS),
        supported_decision_priorities=list(SUPPORTED_DECISION_PRIORITIES),
        confidence_levels=list(SUPPORTED_CONFIDENCE_LEVELS),
        decision_component_names=list(DECISION_COMPONENT_NAMES),
        decision_weights=dict(DEFAULT_DECISION_WEIGHTS),
        input_files=list(INPUT_FILES),
        available_input_files=available,
        missing_input_files=missing,
        portfolio_decisions=ranked,
        decision_count=len(ranked),
        warnings=warnings,
        errors=[],
        scoring_model=list(SCORING_MODEL),
        decision_model=list(DECISION_MODEL),
        safety_guarantees=list(SAFETY_GUARANTEES),
        limitations=list(LIMITATIONS),
    ))
    validate_portfolio_decision_report(payload)
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


def _validate_decision(decision: Any) -> None:
    decision = _require_mapping(decision, "portfolio_decision")
    _validate_required(decision, DECISION_FIELDS, "portfolio_decision")
    if not isinstance(decision["symbol"], str) or not decision["symbol"].strip() or decision["symbol"] != decision["symbol"].upper():
        raise ValueError("symbol must be a non-empty uppercase string")
    if not isinstance(decision["opportunity_name"], str):
        raise ValueError("opportunity_name must be a string")
    for field_name in [
        "decision_score", "opportunity_score", "conviction_score", "entry_score", "momentum_score",
        "dividend_ranking_score", "self_funding_score", "risk_adjustment_score",
    ]:
        _validate_number(decision[field_name], field_name, 0, 100)
    _validate_number(decision["confidence"], "confidence", 0.0, 1.0)
    _validate_number(decision["recommended_allocation_change"], "recommended_allocation_change", -1.0, 1.0)
    if decision["decision_action"] not in SUPPORTED_DECISION_ACTIONS:
        raise ValueError("decision_action must be supported")
    if decision["decision_priority"] not in SUPPORTED_DECISION_PRIORITIES:
        raise ValueError("decision_priority must be supported")
    if decision["confidence_level"] not in SUPPORTED_CONFIDENCE_LEVELS:
        raise ValueError("confidence_level must be LOW, MEDIUM, or HIGH")
    _validate_string_list(decision["risk_flags"], "risk_flags", allow_empty=True)
    if not isinstance(decision["notes"], str):
        raise ValueError("notes must be a string")


def validate_portfolio_decision_report(payload: Any) -> bool:
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
        if field_name == "portfolio_decisions":
            if not isinstance(payload[field_name], list):
                raise ValueError("portfolio_decisions must be a list")
        else:
            _validate_string_list(payload[field_name], field_name, allow_empty=True)
    if payload["supported_decision_actions"] != SUPPORTED_DECISION_ACTIONS:
        raise ValueError("supported_decision_actions must match approved list")
    if payload["supported_decision_priorities"] != SUPPORTED_DECISION_PRIORITIES:
        raise ValueError("supported_decision_priorities must match approved list")
    if payload["confidence_levels"] != SUPPORTED_CONFIDENCE_LEVELS:
        raise ValueError("confidence_levels must match approved list")
    if payload["decision_component_names"] != DECISION_COMPONENT_NAMES:
        raise ValueError("decision_component_names must match approved list")
    if payload["input_files"] != INPUT_FILES:
        raise ValueError("input_files must match approved list")
    _validate_weights(payload["decision_weights"])
    if not isinstance(payload["decision_count"], int) or isinstance(payload["decision_count"], bool):
        raise ValueError("decision_count must be an integer")
    if payload["decision_count"] != len(payload["portfolio_decisions"]):
        raise ValueError("decision_count must match portfolio_decisions length")
    for decision in payload["portfolio_decisions"]:
        _validate_decision(decision)
    scores = [item["decision_score"] for item in payload["portfolio_decisions"]]
    if scores != sorted(scores, reverse=True):
        raise ValueError("portfolio_decisions must be sorted by decision_score descending")
    return True


def write_portfolio_decision_report_json(path: str = "portfolio_decision_report.json", root_path: str = ".") -> Dict[str, Any]:
    payload = build_portfolio_decision_report(root_path=root_path)
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_portfolio_decision_report_json(path: str = "portfolio_decision_report.json") -> Dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    validate_portfolio_decision_report(payload)
    return payload


def write_portfolio_decision_report_csv(path: str = "portfolio_decision_report.csv", root_path: str = ".") -> Dict[str, Any]:
    payload = build_portfolio_decision_report(root_path=root_path)
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=DECISION_FIELDS)
        writer.writeheader()
        for row in payload["portfolio_decisions"]:
            writer.writerow({field: row.get(field, "") for field in DECISION_FIELDS})
    return payload


def _format_list(title: str, values: List[str]) -> List[str]:
    lines = [f"## {title}"]
    if values:
        lines.extend(f"- {value}" for value in values)
    else:
        lines.append("- None")
    return lines


def format_portfolio_decision_report_markdown(payload: Mapping[str, Any]) -> str:
    validate_portfolio_decision_report(payload)
    lines = [
        "# Portfolio Decision Report",
        "",
        f"- Module: {payload['module_name']}",
        f"- Generated At UTC: {payload['generated_at_utc']}",
        f"- Paper Trade Mode: {payload['paper_trade_mode']}",
        f"- Reporting Only: {payload['reporting_only']}",
        f"- Decision Count: {payload['decision_count']}",
        "",
        "## Decision Weights",
    ]
    for key, value in payload["decision_weights"].items():
        lines.append(f"- {key}: {value}")
    lines.extend([
        "",
        "## Portfolio Decisions",
        "",
        "| Symbol | Opportunity | Score | Action | Priority | Confidence | Allocation Change | Notes |",
        "|---|---|---:|---|---|---:|---:|---|",
    ])
    if payload["portfolio_decisions"]:
        for row in payload["portfolio_decisions"]:
            lines.append(
                f"| {row['symbol']} | {row['opportunity_name']} | {row['decision_score']} | {row['decision_action']} | {row['decision_priority']} | {row['confidence']} | {row['recommended_allocation_change']} | {row['notes']} |"
            )
    else:
        lines.append("| None |  |  |  |  |  |  |  |")
    lines.append("")
    for title, values in [
        ("Supported Decision Actions", payload["supported_decision_actions"]),
        ("Supported Decision Priorities", payload["supported_decision_priorities"]),
        ("Input Files", payload["input_files"]),
        ("Available Input Files", payload["available_input_files"]),
        ("Missing Input Files", payload["missing_input_files"]),
        ("Scoring Model", payload["scoring_model"]),
        ("Decision Model", payload["decision_model"]),
        ("Warnings", payload["warnings"]),
        ("Errors", payload["errors"]),
        ("Safety Guarantees", payload["safety_guarantees"]),
        ("Limitations", payload["limitations"]),
    ]:
        lines.extend(_format_list(title, values))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_portfolio_decision_report_markdown(path: str = "portfolio_decision_report.md", root_path: str = ".") -> Dict[str, Any]:
    payload = build_portfolio_decision_report(root_path=root_path)
    Path(path).write_text(format_portfolio_decision_report_markdown(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    write_portfolio_decision_report_json()
    write_portfolio_decision_report_csv()
    write_portfolio_decision_report_markdown()
