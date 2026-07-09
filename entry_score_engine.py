"""
Entry Score Engine for the Dividend Bot.

This module provides a deterministic, paper-only entry timing interface. It is
reporting-only and does not connect to brokers, pull live data, or place orders.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping


MODULE_NAME = "entry_score_engine"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"

BOT_NAME = "Agentic Robin Dividend Bot"
BOT_TYPE = "paper_dividend_etf_management"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

STRONG_ENTRY = "STRONG_ENTRY"
GOOD_ENTRY = "GOOD_ENTRY"
WAIT = "WAIT"
WATCH = "WATCH"
AVOID = "AVOID"
UNKNOWN = "UNKNOWN"
SUPPORTED_ENTRY_STATUSES = [STRONG_ENTRY, GOOD_ENTRY, WAIT, WATCH, AVOID, UNKNOWN]

PULLBACK_ENTRY = "PULLBACK_ENTRY"
BREAKOUT_ENTRY = "BREAKOUT_ENTRY"
TREND_CONTINUATION = "TREND_CONTINUATION"
REVERSAL_SETUP = "REVERSAL_SETUP"
OVEREXTENDED = "OVEREXTENDED"
RANGE_BOUND = "RANGE_BOUND"
SUPPORTED_TIMING_CONTEXTS = [
    PULLBACK_ENTRY,
    BREAKOUT_ENTRY,
    TREND_CONTINUATION,
    REVERSAL_SETUP,
    OVEREXTENDED,
    RANGE_BOUND,
    UNKNOWN,
]

LOW = "LOW"
MEDIUM = "MEDIUM"
HIGH = "HIGH"
SUPPORTED_CONFIDENCE_LEVELS = [LOW, MEDIUM, HIGH]

ENTRY_SIGNAL_NAMES = [
    "pullback_quality",
    "breakout_quality",
    "trend_confirmation",
    "momentum_confirmation",
    "market_regime_confirmation",
    "market_intelligence_confirmation",
    "volatility_entry_risk",
    "liquidity_entry_quality",
    "overextension_risk",
    "self_funding_confirmation",
]

DEFAULT_ENTRY_SCORE = 0
DEFAULT_ENTRY_STATUS = UNKNOWN
DEFAULT_CONFIDENCE = 0.0
DEFAULT_CONFIDENCE_LEVEL = LOW
DEFAULT_TIMING_CONTEXT = UNKNOWN
DEFAULT_SIGNAL_SOURCE = "deterministic_fallback"

SCORING_MODEL = [
    "Entry score range is 0 to 100.",
    "85 to 100 may map to STRONG_ENTRY.",
    "75 to 84 may map to GOOD_ENTRY.",
    "60 to 74 may map to WATCH.",
    "45 to 59 may map to WAIT.",
    "0 to 44 may map to AVOID when real inputs are available.",
    "Current v1.0 fallback behavior uses score 0 and UNKNOWN.",
]

TIMING_MODEL = [
    "Entry timing is separate from opportunity quality.",
    "Supported contexts include pullback, breakout, continuation, reversal, overextended, range-bound, and unknown.",
    "Current v1.0 fallback behavior uses UNKNOWN.",
]

CONFIRMATION_MODEL = [
    "Future entry confirmation may use momentum, market regime, market intelligence, volatility, liquidity, and self-funding confirmation.",
    "Leveraged ETFs should require stronger confirmation.",
    "Income ETFs may permit lower momentum requirements if income quality and self-funding support are strong.",
]

RISK_FLAG_MODEL = [
    "Future risk flags may include OVEREXTENDED_ENTRY, WEAK_MOMENTUM_CONFIRMATION, HIGH_VOLATILITY_ENTRY_RISK, BEARISH_REGIME_CONFLICT, NEGATIVE_INTELLIGENCE_CONFLICT, LOW_LIQUIDITY_ENTRY_RISK, and UNKNOWN_ASSET_REVIEW_REQUIRED.",
    "Current v1.0 fallback behavior produces no risk flags.",
]

RECOMMENDATION_MODEL = [
    "Recommendations provide paper-only entry timing context.",
    "Current fallback recommends waiting for future entry inputs before treating the score as actionable.",
]

INTEGRATION_TARGETS = [
    "opportunity_pairing_report.json provides ranked income + growth opportunity candidates.",
    "momentum_score_report.json may provide momentum confirmation.",
    "market_regime_report.json may provide regime confirmation.",
    "market_intelligence_report.json may provide broader intelligence confirmation.",
    "asset_registry.json may provide classification and asset-specific entry rules.",
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
    "no live internet data is pulled",
    "no external APIs are used",
    "read-only analysis only",
]

LIMITATIONS = [
    "Current v1.0 version defines safe interfaces and deterministic fallback behavior only.",
    "No live price, broker, or internet data is consumed.",
    "All entry signals default to UNKNOWN until future inputs are implemented.",
]

REPORT_REQUIRED_FIELDS = [
    "bot_name", "bot_type", "module_name", "module_version", "schema_version",
    "generated_by", "generated_at_utc", "paper_trade_mode", "live_trading_enabled",
    "broker_execution_enabled", "reporting_only", "supported_entry_statuses",
    "supported_timing_contexts", "entry_signal_names", "entry_signals", "entry_score",
    "entry_status", "confidence", "confidence_level", "timing_context", "risk_flags",
    "recommendations", "warnings", "errors", "scoring_model", "timing_model",
    "confirmation_model", "risk_flag_model", "recommendation_model", "integration_targets",
    "safety_guarantees", "limitations",
]

REPORT_LIST_FIELDS = [
    "supported_entry_statuses", "supported_timing_contexts", "entry_signal_names",
    "entry_signals", "risk_flags", "recommendations", "warnings", "errors",
    "scoring_model", "timing_model", "confirmation_model", "risk_flag_model",
    "recommendation_model", "integration_targets", "safety_guarantees", "limitations",
]

SIGNAL_REQUIRED_FIELDS = [
    "signal_name", "score", "status", "confidence", "confidence_level", "timing_context",
    "risk_flags", "recommendations", "warnings", "source", "last_updated_utc",
]

SIGNAL_LIST_FIELDS = ["risk_flags", "recommendations", "warnings"]


@dataclass(frozen=True)
class EntrySignal:
    signal_name: str
    score: float = 0.0
    status: str = UNKNOWN
    confidence: float = 0.0
    confidence_level: str = LOW
    timing_context: str = UNKNOWN
    risk_flags: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    source: str = DEFAULT_SIGNAL_SOURCE
    last_updated_utc: str = ""


@dataclass(frozen=True)
class EntryScoreReport:
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
    supported_entry_statuses: List[str]
    supported_timing_contexts: List[str]
    entry_signal_names: List[str]
    entry_signals: List[Dict[str, Any]]
    entry_score: float
    entry_status: str
    confidence: float
    confidence_level: str
    timing_context: str
    risk_flags: List[str]
    recommendations: List[str]
    warnings: List[str]
    errors: List[str]
    scoring_model: List[str]
    timing_model: List[str]
    confirmation_model: List[str]
    risk_flag_model: List[str]
    recommendation_model: List[str]
    integration_targets: List[str]
    safety_guarantees: List[str]
    limitations: List[str]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _build_signal(name: str, now: str) -> Dict[str, Any]:
    return asdict(EntrySignal(
        signal_name=name,
        recommendations=["Use this signal as a deterministic paper-only placeholder until future inputs are implemented."],
        warnings=[f"No live entry input connected for signal: {name}."],
        last_updated_utc=now,
    ))


def build_entry_score_report() -> Dict[str, Any]:
    now = _utc_now_iso()
    payload = asdict(EntryScoreReport(
        bot_name=BOT_NAME,
        bot_type=BOT_TYPE,
        module_name=MODULE_NAME,
        module_version=MODULE_VERSION,
        schema_version=SCHEMA_VERSION,
        generated_by=GENERATED_BY,
        generated_at_utc=now,
        paper_trade_mode=True,
        live_trading_enabled=False,
        broker_execution_enabled=False,
        reporting_only=True,
        supported_entry_statuses=list(SUPPORTED_ENTRY_STATUSES),
        supported_timing_contexts=list(SUPPORTED_TIMING_CONTEXTS),
        entry_signal_names=list(ENTRY_SIGNAL_NAMES),
        entry_signals=[_build_signal(name, now) for name in ENTRY_SIGNAL_NAMES],
        entry_score=DEFAULT_ENTRY_SCORE,
        entry_status=DEFAULT_ENTRY_STATUS,
        confidence=DEFAULT_CONFIDENCE,
        confidence_level=DEFAULT_CONFIDENCE_LEVEL,
        timing_context=DEFAULT_TIMING_CONTEXT,
        risk_flags=[],
        recommendations=["Use this report as a paper-only entry timing interface until future inputs are implemented."],
        warnings=["Entry inputs are not connected in v1.0; using deterministic UNKNOWN fallback."],
        errors=[],
        scoring_model=list(SCORING_MODEL),
        timing_model=list(TIMING_MODEL),
        confirmation_model=list(CONFIRMATION_MODEL),
        risk_flag_model=list(RISK_FLAG_MODEL),
        recommendation_model=list(RECOMMENDATION_MODEL),
        integration_targets=list(INTEGRATION_TARGETS),
        safety_guarantees=list(SAFETY_GUARANTEES),
        limitations=list(LIMITATIONS),
    ))
    validate_entry_score_report(payload)
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


def _validate_signal(signal: Any) -> None:
    signal = _require_mapping(signal, "entry_signal")
    _validate_required(signal, SIGNAL_REQUIRED_FIELDS, "entry_signal")
    if signal["signal_name"] not in ENTRY_SIGNAL_NAMES:
        raise ValueError("signal_name must be supported")
    if signal["status"] not in SUPPORTED_ENTRY_STATUSES:
        raise ValueError("signal status must be supported")
    if signal["timing_context"] not in SUPPORTED_TIMING_CONTEXTS:
        raise ValueError("signal timing_context must be supported")
    if signal["confidence_level"] not in SUPPORTED_CONFIDENCE_LEVELS:
        raise ValueError("signal confidence_level must be LOW, MEDIUM, or HIGH")
    _validate_number(signal["score"], "signal.score", 0, 100)
    _validate_number(signal["confidence"], "signal.confidence", 0.0, 1.0)
    if not isinstance(signal["source"], str) or not signal["source"].strip():
        raise ValueError("signal.source must be a non-empty string")
    if not isinstance(signal["last_updated_utc"], str) or not signal["last_updated_utc"].strip():
        raise ValueError("signal.last_updated_utc must be a non-empty string")
    for field_name in SIGNAL_LIST_FIELDS:
        _validate_string_list(signal[field_name], f"signal.{field_name}", allow_empty=True)


def validate_entry_score_report(payload: Any) -> bool:
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
        if field_name == "entry_signals":
            if not isinstance(payload[field_name], list) or not payload[field_name]:
                raise ValueError("entry_signals must be a non-empty list")
        else:
            _validate_string_list(payload[field_name], field_name, allow_empty=True)

    if payload["supported_entry_statuses"] != SUPPORTED_ENTRY_STATUSES:
        raise ValueError("supported_entry_statuses must match approved list")
    if payload["supported_timing_contexts"] != SUPPORTED_TIMING_CONTEXTS:
        raise ValueError("supported_timing_contexts must match approved list")
    if payload["entry_signal_names"] != ENTRY_SIGNAL_NAMES:
        raise ValueError("entry_signal_names must match approved list")
    if payload["entry_status"] not in SUPPORTED_ENTRY_STATUSES:
        raise ValueError("entry_status must be supported")
    if payload["confidence_level"] not in SUPPORTED_CONFIDENCE_LEVELS:
        raise ValueError("confidence_level must be LOW, MEDIUM, or HIGH")
    if payload["timing_context"] not in SUPPORTED_TIMING_CONTEXTS:
        raise ValueError("timing_context must be supported")
    _validate_number(payload["entry_score"], "entry_score", 0, 100)
    _validate_number(payload["confidence"], "confidence", 0.0, 1.0)

    seen = set()
    for signal in payload["entry_signals"]:
        _validate_signal(signal)
        name = signal["signal_name"]
        if name in seen:
            raise ValueError(f"duplicate entry signal: {name}")
        seen.add(name)
    if set(seen) != set(ENTRY_SIGNAL_NAMES):
        raise ValueError("entry_signals must include exactly the approved signal names")
    return True


def write_entry_score_report_json(path: str = "entry_score_report.json") -> Dict[str, Any]:
    payload = build_entry_score_report()
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_entry_score_report_json(path: str = "entry_score_report.json") -> Dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    validate_entry_score_report(payload)
    return payload


def _format_list(title: str, values: List[str]) -> List[str]:
    lines = [f"## {title}"]
    if values:
        lines.extend(f"- {value}" for value in values)
    else:
        lines.append("- None")
    return lines


def format_entry_score_report_markdown(payload: Mapping[str, Any]) -> str:
    validate_entry_score_report(payload)
    lines = [
        "# Entry Score Report",
        "",
        f"- Module: {payload['module_name']}",
        f"- Generated At UTC: {payload['generated_at_utc']}",
        f"- Paper Trade Mode: {payload['paper_trade_mode']}",
        f"- Reporting Only: {payload['reporting_only']}",
        "",
        "## Entry Summary",
        f"- Entry Score: {payload['entry_score']}",
        f"- Entry Status: {payload['entry_status']}",
        f"- Confidence: {payload['confidence']}",
        f"- Confidence Level: {payload['confidence_level']}",
        f"- Timing Context: {payload['timing_context']}",
        "",
        "## Entry Signals",
        "",
        "| Signal | Status | Score | Confidence | Confidence Level | Timing Context | Source |",
        "|---|---|---:|---:|---|---|---|",
    ]
    for signal in payload["entry_signals"]:
        lines.append(
            f"| {signal['signal_name']} | {signal['status']} | {signal['score']} | {signal['confidence']} | {signal['confidence_level']} | {signal['timing_context']} | {signal['source']} |"
        )
    lines.append("")
    sections = [
        ("Supported Entry Statuses", payload["supported_entry_statuses"]),
        ("Supported Timing Contexts", payload["supported_timing_contexts"]),
        ("Scoring Model", payload["scoring_model"]),
        ("Timing Model", payload["timing_model"]),
        ("Confirmation Model", payload["confirmation_model"]),
        ("Risk Flag Model", payload["risk_flag_model"]),
        ("Recommendation Model", payload["recommendation_model"]),
        ("Integration Targets", payload["integration_targets"]),
        ("Risk Flags", payload["risk_flags"]),
        ("Recommendations", payload["recommendations"]),
        ("Warnings", payload["warnings"]),
        ("Errors", payload["errors"]),
        ("Safety Guarantees", payload["safety_guarantees"]),
        ("Limitations", payload["limitations"]),
    ]
    for title, values in sections:
        lines.extend(_format_list(title, values))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_entry_score_report_markdown(path: str = "entry_score_report.md") -> Dict[str, Any]:
    payload = build_entry_score_report()
    Path(path).write_text(format_entry_score_report_markdown(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    write_entry_score_report_json()
    write_entry_score_report_markdown()
