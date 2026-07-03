"""
Read-only Momentum Score Engine for Dividend Bot Strategy Intelligence v1.4.

This module provides a deterministic, paper-only momentum score report interface
for future scoring engines. The current version defines safe interfaces and
fallback behavior only; it does not pull live internet data, use external APIs,
call broker APIs, or modify trading/workflow/strategy modules.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping


MODULE_NAME = "momentum_score_engine"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"

BOT_NAME = "Agentic Robin Dividend Bot"
BOT_TYPE = "paper_dividend_etf_management"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False

STRONG = "STRONG"
MODERATE = "MODERATE"
WEAK = "WEAK"
NEGATIVE = "NEGATIVE"
MIXED = "MIXED"
UNKNOWN = "UNKNOWN"

SUPPORTED_MOMENTUM_STATUSES = [STRONG, MODERATE, WEAK, NEGATIVE, MIXED, UNKNOWN]

UP = "UP"
DOWN = "DOWN"
SIDEWAYS = "SIDEWAYS"
REVERSAL_UP = "REVERSAL_UP"
REVERSAL_DOWN = "REVERSAL_DOWN"

SUPPORTED_TREND_DIRECTIONS = [UP, DOWN, SIDEWAYS, REVERSAL_UP, REVERSAL_DOWN, UNKNOWN]

LOW = "LOW"
MEDIUM = "MEDIUM"
HIGH = "HIGH"
SUPPORTED_CONFIDENCE_LEVELS = [LOW, MEDIUM, HIGH]

MOMENTUM_SIGNAL_NAMES = [
    "price_trend",
    "relative_strength",
    "moving_average_alignment",
    "volume_confirmation",
    "breakout_confirmation",
    "pullback_quality",
    "trend_consistency",
    "volatility_adjusted_momentum",
    "sector_relative_strength",
    "market_regime_confirmation",
    "market_intelligence_confirmation",
]

DEFAULT_MOMENTUM_SCORE = 0
DEFAULT_MOMENTUM_STATUS = UNKNOWN
DEFAULT_CONFIDENCE = 0.0
DEFAULT_CONFIDENCE_LEVEL = LOW
DEFAULT_TREND_DIRECTION = UNKNOWN
DEFAULT_SIGNAL_SCORE = 0
DEFAULT_SIGNAL_STATUS = UNKNOWN
DEFAULT_SIGNAL_CONFIDENCE = 0.0
DEFAULT_SIGNAL_CONFIDENCE_LEVEL = LOW
DEFAULT_SIGNAL_TREND_DIRECTION = UNKNOWN
DEFAULT_SIGNAL_SOURCE = "deterministic_fallback"

SCORING_MODEL = [
    "Future momentum score range is 0 to 100.",
    "80 to 100 may map to STRONG.",
    "55 to 79 may map to MODERATE.",
    "30 to 54 may map to WEAK.",
    "0 to 29 may map to NEGATIVE when real data is available.",
    "Conflicting momentum signals may map to MIXED.",
    "Missing or unavailable inputs map to UNKNOWN.",
    "Current v1.4 fallback behavior uses score 0 and UNKNOWN.",
]

SIGNAL_WEIGHT_MODEL = [
    "Future signal weighting may emphasize price_trend, relative_strength, moving_average_alignment, and volume_confirmation.",
    "Breakout, pullback, trend consistency, volatility adjustment, sector strength, market regime, and market intelligence may be confirmation factors.",
    "Current v1.4 fallback behavior does not apply active weights.",
]

MOMENTUM_QUALITY_MODEL = [
    "Future momentum quality may consider consistency, confirmation, breakout quality, pullback quality, and volatility-adjusted trend strength.",
    "Overextended or unconfirmed momentum may add risk flags.",
    "Current v1.4 fallback behavior does not compute momentum quality.",
]

CONFIDENCE_MODEL = [
    "Confidence range is 0.0 to 1.0.",
    "0.00 to 0.39 maps to LOW.",
    "0.40 to 0.69 maps to MEDIUM.",
    "0.70 to 1.00 maps to HIGH.",
    "Future confidence may use data availability, data freshness, agreement across momentum signals, volume confirmation, regime confirmation, and market intelligence confirmation.",
    "Current v1.4 fallback behavior uses confidence 0.0 and LOW.",
]

TREND_DIRECTION_MODEL = [
    "UP indicates an upward trend.",
    "DOWN indicates a downward trend.",
    "SIDEWAYS indicates range or consolidation behavior.",
    "REVERSAL_UP indicates possible bullish reversal.",
    "REVERSAL_DOWN indicates possible bearish reversal.",
    "UNKNOWN indicates insufficient data.",
    "Current v1.4 fallback behavior uses UNKNOWN.",
]

RISK_FLAG_MODEL = [
    "Future risk flags are normalized string values.",
    "Examples include WEAK_RELATIVE_STRENGTH, LOW_VOLUME_CONFIRMATION, OVEREXTENDED_BREAKOUT, FAILED_BREAKOUT_RISK, HIGH_VOLATILITY_MOMENTUM, REGIME_CONFLICT_RISK, MARKET_INTELLIGENCE_CONFLICT, LEVERAGED_ETF_DECAY_RISK, PULLBACK_QUALITY_WEAK, and TREND_INCONSISTENCY.",
    "Current v1.4 fallback behavior produces no risk flags.",
]

RECOMMENDATION_MODEL = [
    "Recommendations provide readable paper-only strategy context.",
    "Future recommendations may include requiring stronger entry confirmation, reducing position sizing, waiting for pullback confirmation, preferring non-leveraged fallback, flagging manual review, or confirming momentum support.",
    "Current v1.4 fallback behavior recommends using the report as a paper-only interface until inputs are implemented.",
]

INTEGRATION_TARGETS = [
    "asset_registry.py remains the source of truth for asset classifications and symbol mappings.",
    "market_regime_engine.py may provide regime confirmation and risk context.",
    "market_intelligence_engine.py may provide intelligence confirmation and risk context.",
    "Future Entry Score Engine may consume momentum_score, momentum_status, confidence_level, trend_direction, risk_flags, recommendations, and signal-level details.",
    "Future Conviction Engine may consume momentum_score, momentum_status, confidence, confidence_level, trend_direction, and risk flags.",
    "Future Unified Opportunity Engine may consume Momentum Score as one factor in final opportunity scoring.",
]

SAFETY_GUARANTEES = [
    "paper_trade_mode is enforced as True",
    "live_trading_enabled is enforced as False",
    "broker_execution_enabled is enforced as False",
    "no external brokerage platform APIs are used",
    "no broker APIs are used",
    "no broker execution is performed",
    "no actual order placement is performed",
    "no live internet data is pulled",
    "no external APIs are used",
    "no trading logic is modified",
    "run_daily_paper_cycle.py is not modified",
    "portfolio_engine.py is not modified",
    "dividend_engine.py is not modified",
    "asset_registry.py is not modified",
    "market_regime_engine.py is not modified",
    "market_intelligence_engine.py is not modified",
    "read-only analysis only",
]

LIMITATIONS = [
    "Current v1.4 version defines safe interfaces and deterministic fallback behavior only.",
    "No live market data is consumed.",
    "No internet data is pulled.",
    "No external APIs are connected.",
    "No broker or brokerage platform APIs are connected.",
    "All momentum signals default to UNKNOWN until future inputs are implemented.",
    "Outputs provide context only and do not authorize trading actions.",
]

REPORT_REQUIRED_FIELDS = [
    "bot_name", "bot_type", "module_name", "module_version", "schema_version",
    "generated_by", "generated_at_utc", "paper_trade_mode",
    "live_trading_enabled", "broker_execution_enabled",
    "supported_momentum_statuses", "supported_trend_directions",
    "momentum_signal_names", "momentum_signals", "momentum_score",
    "momentum_status", "confidence", "confidence_level", "trend_direction",
    "risk_flags", "recommendations", "warnings", "errors", "scoring_model",
    "signal_weight_model", "momentum_quality_model", "confidence_model",
    "trend_direction_model", "risk_flag_model", "recommendation_model",
    "integration_targets", "safety_guarantees", "limitations",
]

REPORT_LIST_FIELDS = [
    "supported_momentum_statuses", "supported_trend_directions",
    "momentum_signal_names", "momentum_signals", "risk_flags",
    "recommendations", "warnings", "errors", "scoring_model",
    "signal_weight_model", "momentum_quality_model", "confidence_model",
    "trend_direction_model", "risk_flag_model", "recommendation_model",
    "integration_targets", "safety_guarantees", "limitations",
]

SIGNAL_REQUIRED_FIELDS = [
    "signal_name", "score", "status", "confidence", "confidence_level",
    "trend_direction", "risk_flags", "recommendations", "warnings",
    "source", "last_updated_utc",
]

SIGNAL_LIST_FIELDS = ["risk_flags", "recommendations", "warnings"]


@dataclass(frozen=True)
class MomentumSignal:
    """One normalized momentum signal."""

    signal_name: str
    score: float
    status: str
    confidence: float
    confidence_level: str
    trend_direction: str
    risk_flags: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    source: str = DEFAULT_SIGNAL_SOURCE
    last_updated_utc: str = ""


@dataclass(frozen=True)
class MomentumScoreReport:
    """Full exportable momentum score report."""

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
    supported_momentum_statuses: List[str]
    supported_trend_directions: List[str]
    momentum_signal_names: List[str]
    momentum_signals: List[Dict[str, Any]]
    momentum_score: float
    momentum_status: str
    confidence: float
    confidence_level: str
    trend_direction: str
    risk_flags: List[str]
    recommendations: List[str]
    warnings: List[str]
    errors: List[str]
    scoring_model: List[str]
    signal_weight_model: List[str]
    momentum_quality_model: List[str]
    confidence_model: List[str]
    trend_direction_model: List[str]
    risk_flag_model: List[str]
    recommendation_model: List[str]
    integration_targets: List[str]
    safety_guarantees: List[str]
    limitations: List[str]


def _utc_now_iso() -> str:
    """Return a stable UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _build_default_signal(signal_name: str, generated_at_utc: str) -> Dict[str, Any]:
    signal = MomentumSignal(
        signal_name=signal_name,
        score=DEFAULT_SIGNAL_SCORE,
        status=DEFAULT_SIGNAL_STATUS,
        confidence=DEFAULT_SIGNAL_CONFIDENCE,
        confidence_level=DEFAULT_SIGNAL_CONFIDENCE_LEVEL,
        trend_direction=DEFAULT_SIGNAL_TREND_DIRECTION,
        risk_flags=[],
        recommendations=[
            "Use this signal as a deterministic paper-only placeholder until future inputs are implemented."
        ],
        warnings=[f"No live momentum input connected for signal: {signal_name}."],
        source=DEFAULT_SIGNAL_SOURCE,
        last_updated_utc=generated_at_utc,
    )
    return asdict(signal)


def build_momentum_score_report() -> Dict[str, Any]:
    """Build the read-only momentum score report."""
    generated_at_utc = _utc_now_iso()
    signals = [_build_default_signal(signal_name, generated_at_utc) for signal_name in MOMENTUM_SIGNAL_NAMES]

    report = MomentumScoreReport(
        bot_name=BOT_NAME,
        bot_type=BOT_TYPE,
        module_name=MODULE_NAME,
        module_version=MODULE_VERSION,
        schema_version=SCHEMA_VERSION,
        generated_by=GENERATED_BY,
        generated_at_utc=generated_at_utc,
        paper_trade_mode=PAPER_TRADE_MODE,
        live_trading_enabled=LIVE_TRADING_ENABLED,
        broker_execution_enabled=BROKER_EXECUTION_ENABLED,
        supported_momentum_statuses=list(SUPPORTED_MOMENTUM_STATUSES),
        supported_trend_directions=list(SUPPORTED_TREND_DIRECTIONS),
        momentum_signal_names=list(MOMENTUM_SIGNAL_NAMES),
        momentum_signals=signals,
        momentum_score=DEFAULT_MOMENTUM_SCORE,
        momentum_status=DEFAULT_MOMENTUM_STATUS,
        confidence=DEFAULT_CONFIDENCE,
        confidence_level=DEFAULT_CONFIDENCE_LEVEL,
        trend_direction=DEFAULT_TREND_DIRECTION,
        risk_flags=[],
        recommendations=[
            "Use this report as a paper-only momentum interface until future inputs are implemented."
        ],
        warnings=[
            "Momentum inputs are not connected in v1.4; using deterministic UNKNOWN fallback."
        ],
        errors=[],
        scoring_model=list(SCORING_MODEL),
        signal_weight_model=list(SIGNAL_WEIGHT_MODEL),
        momentum_quality_model=list(MOMENTUM_QUALITY_MODEL),
        confidence_model=list(CONFIDENCE_MODEL),
        trend_direction_model=list(TREND_DIRECTION_MODEL),
        risk_flag_model=list(RISK_FLAG_MODEL),
        recommendation_model=list(RECOMMENDATION_MODEL),
        integration_targets=list(INTEGRATION_TARGETS),
        safety_guarantees=list(SAFETY_GUARANTEES),
        limitations=list(LIMITATIONS),
    )

    payload = asdict(report)
    validate_momentum_score_report(payload)
    return payload

def _require_mapping(payload: Any, label: str = "payload") -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{label} must be a mapping/dictionary")
    return payload


def _validate_required_fields(payload: Mapping[str, Any], required_fields: List[str], label: str) -> None:
    missing = [field_name for field_name in required_fields if field_name not in payload]
    if missing:
        raise ValueError(f"{label} missing required field(s): {', '.join(missing)}")


def _validate_exact_metadata(payload: Mapping[str, Any]) -> None:
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
    }
    for field_name, expected_value in expected.items():
        if payload.get(field_name) != expected_value:
            raise ValueError(f"{field_name} must be {expected_value!r}")


def _validate_non_empty_string(value: Any, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _validate_string_list(value: Any, field_name: str, allow_empty: bool = True) -> None:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    if not allow_empty and not value:
        raise ValueError(f"{field_name} must not be empty")
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name}[{index}] must be a non-empty string")


def _validate_number_range(value: Any, field_name: str, minimum: float, maximum: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number")
    if value < minimum or value > maximum:
        raise ValueError(f"{field_name} must be between {minimum} and {maximum}")


def _validate_confidence_level(value: Any, field_name: str) -> None:
    if value not in SUPPORTED_CONFIDENCE_LEVELS:
        raise ValueError(f"{field_name} must be LOW, MEDIUM, or HIGH")


def _validate_signal(signal: Any) -> None:
    signal = _require_mapping(signal, "momentum_signal")
    _validate_required_fields(signal, SIGNAL_REQUIRED_FIELDS, "momentum_signal")

    if signal["signal_name"] not in MOMENTUM_SIGNAL_NAMES:
        raise ValueError("signal_name must be supported")
    if signal["status"] not in SUPPORTED_MOMENTUM_STATUSES:
        raise ValueError("signal status must be supported")
    if signal["trend_direction"] not in SUPPORTED_TREND_DIRECTIONS:
        raise ValueError("signal trend_direction must be supported")

    _validate_number_range(signal["score"], "signal.score", 0, 100)
    _validate_number_range(signal["confidence"], "signal.confidence", 0.0, 1.0)
    _validate_confidence_level(signal["confidence_level"], "signal.confidence_level")
    _validate_non_empty_string(signal["source"], "signal.source")
    _validate_non_empty_string(signal["last_updated_utc"], "signal.last_updated_utc")

    for field_name in SIGNAL_LIST_FIELDS:
        _validate_string_list(signal[field_name], f"signal.{field_name}", allow_empty=True)


def validate_momentum_score_report(payload: Any) -> bool:
    """Validate a momentum score report payload and raise ValueError on failure."""
    payload = _require_mapping(payload)
    _validate_required_fields(payload, REPORT_REQUIRED_FIELDS, "payload")
    _validate_exact_metadata(payload)
    _validate_non_empty_string(payload["generated_at_utc"], "generated_at_utc")

    for field_name in REPORT_LIST_FIELDS:
        if field_name == "momentum_signals":
            if not isinstance(payload[field_name], list):
                raise ValueError("momentum_signals must be a list")
            if not payload[field_name]:
                raise ValueError("momentum_signals must be a non-empty list")
            continue
        _validate_string_list(payload[field_name], field_name, allow_empty=True)

    if payload["supported_momentum_statuses"] != SUPPORTED_MOMENTUM_STATUSES:
        raise ValueError("supported_momentum_statuses must match the approved status list")
    if payload["supported_trend_directions"] != SUPPORTED_TREND_DIRECTIONS:
        raise ValueError("supported_trend_directions must match the approved trend direction list")
    if payload["momentum_signal_names"] != MOMENTUM_SIGNAL_NAMES:
        raise ValueError("momentum_signal_names must match the approved signal list")

    if payload["momentum_status"] not in SUPPORTED_MOMENTUM_STATUSES:
        raise ValueError("momentum_status must be supported")
    if payload["trend_direction"] not in SUPPORTED_TREND_DIRECTIONS:
        raise ValueError("trend_direction must be supported")

    _validate_number_range(payload["momentum_score"], "momentum_score", 0, 100)
    _validate_number_range(payload["confidence"], "confidence", 0.0, 1.0)
    _validate_confidence_level(payload["confidence_level"], "confidence_level")

    seen_signals = set()
    for signal in payload["momentum_signals"]:
        _validate_signal(signal)
        signal_name = signal["signal_name"]
        if signal_name in seen_signals:
            raise ValueError(f"duplicate momentum signal: {signal_name}")
        seen_signals.add(signal_name)

    if set(seen_signals) != set(MOMENTUM_SIGNAL_NAMES):
        raise ValueError("momentum_signals must include exactly the approved signal names")

    return True

def write_momentum_score_report_json(path: str = "momentum_score_report.json") -> Dict[str, Any]:
    """Build, validate, and write momentum_score_report.json."""
    payload = build_momentum_score_report()
    validate_momentum_score_report(payload)

    output_path = Path(path)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_momentum_score_report_json(path: str = "momentum_score_report.json") -> Dict[str, Any]:
    """Read and validate a momentum score report JSON file."""
    input_path = Path(path)
    with input_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    validate_momentum_score_report(payload)
    return payload


def _format_list(title: str, values: List[str]) -> List[str]:
    lines = [f"## {title}"]
    if values:
        lines.extend(f"- {value}" for value in values)
    else:
        lines.append("- None")
    return lines


def format_momentum_score_report_markdown(payload: Mapping[str, Any]) -> str:
    """Format a validated momentum score report as Markdown."""
    validate_momentum_score_report(payload)

    lines = [
        "# Momentum Score Report",
        "",
        f"- Bot Name: {payload['bot_name']}",
        f"- Bot Type: {payload['bot_type']}",
        f"- Module Name: {payload['module_name']}",
        f"- Module Version: {payload['module_version']}",
        f"- Schema Version: {payload['schema_version']}",
        f"- Generated By: {payload['generated_by']}",
        f"- Generated At UTC: {payload['generated_at_utc']}",
        f"- Paper Trade Mode: {payload['paper_trade_mode']}",
        f"- Live Trading Enabled: {payload['live_trading_enabled']}",
        f"- Broker Execution Enabled: {payload['broker_execution_enabled']}",
        "",
        "## Overall Momentum",
        f"- Momentum Score: {payload['momentum_score']}",
        f"- Momentum Status: {payload['momentum_status']}",
        f"- Confidence: {payload['confidence']}",
        f"- Confidence Level: {payload['confidence_level']}",
        f"- Trend Direction: {payload['trend_direction']}",
        "",
        "## Momentum Signals",
        "",
        "| Signal | Status | Score | Confidence | Confidence Level | Trend Direction | Source |",
        "|---|---|---|---|---|---|---|",
    ]

    for signal in payload["momentum_signals"]:
        lines.append(
            "| {signal_name} | {status} | {score} | {confidence} | {confidence_level} | {trend_direction} | {source} |".format(
                signal_name=signal["signal_name"],
                status=signal["status"],
                score=signal["score"],
                confidence=signal["confidence"],
                confidence_level=signal["confidence_level"],
                trend_direction=signal["trend_direction"],
                source=signal["source"],
            )
        )

    lines.append("")

    sections = [
        ("Supported Momentum Statuses", payload["supported_momentum_statuses"]),
        ("Supported Trend Directions", payload["supported_trend_directions"]),
        ("Momentum Signal Names", payload["momentum_signal_names"]),
        ("Risk Flags", payload["risk_flags"]),
        ("Recommendations", payload["recommendations"]),
        ("Warnings", payload["warnings"]),
        ("Errors", payload["errors"]),
        ("Scoring Model", payload["scoring_model"]),
        ("Signal Weight Model", payload["signal_weight_model"]),
        ("Momentum Quality Model", payload["momentum_quality_model"]),
        ("Confidence Model", payload["confidence_model"]),
        ("Trend Direction Model", payload["trend_direction_model"]),
        ("Risk Flag Model", payload["risk_flag_model"]),
        ("Recommendation Model", payload["recommendation_model"]),
        ("Integration Targets", payload["integration_targets"]),
        ("Safety Guarantees", payload["safety_guarantees"]),
        ("Limitations", payload["limitations"]),
    ]

    for title, values in sections:
        lines.extend(_format_list(title, values))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_momentum_score_report_markdown(path: str = "momentum_score_report.md") -> Dict[str, Any]:
    """Build, validate, and write momentum_score_report.md."""
    payload = build_momentum_score_report()
    markdown = format_momentum_score_report_markdown(payload)

    output_path = Path(path)
    output_path.write_text(markdown, encoding="utf-8")
    return payload


if __name__ == "__main__":
    write_momentum_score_report_json()
    write_momentum_score_report_markdown()
