"""
Read-only Market Intelligence Engine for Dividend Bot Strategy Intelligence v1.3.

This module provides a deterministic, paper-only market intelligence report
interface for future scoring engines. The current version defines safe interfaces
and fallback behavior only; it does not pull live internet data, scrape websites,
use external APIs, call broker APIs, or modify trading/workflow/strategy modules.

PAPER ONLY:
- paper_trade_mode is always True
- live_trading_enabled is always False
- broker_execution_enabled is always False
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping


MODULE_NAME = "market_intelligence_engine"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"

BOT_NAME = "Agentic Robin Dividend Bot"
BOT_TYPE = "paper_dividend_etf_management"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False

STRONGLY_POSITIVE = "STRONGLY_POSITIVE"
POSITIVE = "POSITIVE"
NEUTRAL = "NEUTRAL"
NEGATIVE = "NEGATIVE"
STRONGLY_NEGATIVE = "STRONGLY_NEGATIVE"
MIXED = "MIXED"
UNKNOWN = "UNKNOWN"

SUPPORTED_INTELLIGENCE_STATUSES = [
    STRONGLY_POSITIVE,
    POSITIVE,
    NEUTRAL,
    NEGATIVE,
    STRONGLY_NEGATIVE,
    MIXED,
    UNKNOWN,
]

LOW = "LOW"
MEDIUM = "MEDIUM"
HIGH = "HIGH"
SUPPORTED_CONFIDENCE_LEVELS = [LOW, MEDIUM, HIGH]

INTELLIGENCE_CATEGORIES = [
    "market_trend",
    "sector_strength",
    "volatility_context",
    "liquidity_context",
    "breadth_context",
    "macro_context",
    "earnings_risk_context",
    "news_risk_context",
    "dividend_income_context",
    "leveraged_etf_risk_context",
]

DEFAULT_OVERALL_INTELLIGENCE_SCORE = 0
DEFAULT_OVERALL_CONFIDENCE = 0.0
DEFAULT_OVERALL_CONFIDENCE_LEVEL = LOW
DEFAULT_OVERALL_INTELLIGENCE_STATUS = UNKNOWN
DEFAULT_SIGNAL_STATUS = UNKNOWN
DEFAULT_SIGNAL_SCORE = 0
DEFAULT_SIGNAL_CONFIDENCE = 0.0
DEFAULT_SIGNAL_CONFIDENCE_LEVEL = LOW
DEFAULT_SIGNAL_SOURCE = "deterministic_fallback"

SCORE_MODEL = [
    "Future intelligence score range is -100 to +100.",
    "75 to 100 maps to STRONGLY_POSITIVE.",
    "25 to 74 maps to POSITIVE.",
    "-24 to 24 maps to NEUTRAL.",
    "-74 to -25 maps to NEGATIVE.",
    "-100 to -75 maps to STRONGLY_NEGATIVE.",
    "Conflicting category signals may map to MIXED.",
    "Missing or unavailable inputs map to UNKNOWN.",
    "Current v1.3 fallback behavior uses score 0 and UNKNOWN.",
]

CONFIDENCE_MODEL = [
    "Confidence range is 0.0 to 1.0.",
    "0.00 to 0.39 maps to LOW.",
    "0.40 to 0.69 maps to MEDIUM.",
    "0.70 to 1.00 maps to HIGH.",
    "Future confidence may use data availability, source reliability, freshness, category agreement, and agreement with Market Regime Engine.",
    "Current v1.3 fallback behavior uses confidence 0.0 and LOW.",
]

RISK_FLAG_MODEL = [
    "Future risk flags are normalized string values.",
    "Examples include HIGH_VOLATILITY_RISK, LOW_LIQUIDITY_RISK, BREADTH_DIVERGENCE_RISK, MACRO_PRESSURE_RISK, EARNINGS_EVENT_RISK, NEWS_EVENT_RISK, DIVIDEND_QUALITY_RISK, LEVERAGED_ETF_DECAY_RISK, and REGIME_CONFLICT_RISK.",
    "Current v1.3 fallback behavior produces no risk flags.",
]

RECOMMENDATION_MODEL = [
    "Recommendations provide readable paper-only strategy context.",
    "Future recommendations may include reduced position sizing, stronger entry confirmation, increased cash reserve, income ETF preference, leveraged ETF caution, or manual review.",
    "Current v1.3 fallback behavior recommends using the report as a paper-only interface until inputs are implemented.",
]

INTEGRATION_TARGETS = [
    "asset_registry.py remains the source of truth for asset classifications and symbol mappings.",
    "market_regime_engine.py may provide regime, regime_score, confidence_level, risk_multiplier, position_sizing_multiplier, and cash reserve context.",
    "Future Momentum Engine may consume overall_intelligence_score, overall_intelligence_status, confidence, risk flags, and category-level signals.",
    "Future Unified Opportunity Engine may consume global and category-level intelligence as opportunity context.",
    "LEVERAGED_ETF classifications may use leveraged_etf_risk_context in future scoring.",
    "INCOME_ETF classifications may use dividend_income_context in future scoring.",
]

SAFETY_GUARANTEES = [
    "paper_trade_mode is enforced as True",
    "live_trading_enabled is enforced as False",
    "broker_execution_enabled is enforced as False",
    "no external brokerage platform APIs are used",
    "no broker APIs are used",
    "no broker execution is performed",
    "no real order placement is performed",
    "no live internet data is pulled",
    "no website scraping is performed",
    "no external APIs are used",
    "no trading logic is modified",
    "run_daily_paper_cycle.py is not modified",
    "portfolio_engine.py is not modified",
    "dividend_engine.py is not modified",
    "asset_registry.py is not modified",
    "market_regime_engine.py is not modified",
    "read-only analysis only",
]

LIMITATIONS = [
    "Current v1.3 version defines safe interfaces and deterministic fallback behavior only.",
    "No live market data is consumed.",
    "No internet data is pulled.",
    "No external APIs are connected.",
    "No broker or brokerage platform APIs are connected.",
    "All intelligence signals default to UNKNOWN until future inputs are implemented.",
    "Outputs provide context only and do not authorize trading actions.",
]

REPORT_REQUIRED_FIELDS = [
    "bot_name", "bot_type", "module_name", "module_version", "schema_version",
    "generated_by", "generated_at_utc", "paper_trade_mode",
    "live_trading_enabled", "broker_execution_enabled",
    "supported_intelligence_statuses", "intelligence_categories",
    "intelligence_signals", "overall_intelligence_score", "overall_confidence",
    "overall_confidence_level", "overall_intelligence_status", "risk_flags",
    "recommendations", "warnings", "errors", "score_model",
    "confidence_model", "risk_flag_model", "recommendation_model",
    "integration_targets", "safety_guarantees", "limitations",
]

REPORT_LIST_FIELDS = [
    "supported_intelligence_statuses", "intelligence_categories",
    "intelligence_signals", "risk_flags", "recommendations", "warnings",
    "errors", "score_model", "confidence_model", "risk_flag_model",
    "recommendation_model", "integration_targets", "safety_guarantees",
    "limitations",
]

SIGNAL_REQUIRED_FIELDS = [
    "category", "status", "score", "confidence", "confidence_level",
    "risk_flags", "recommendations", "warnings", "source", "last_updated_utc",
]

SIGNAL_LIST_FIELDS = ["risk_flags", "recommendations", "warnings"]


@dataclass(frozen=True)
class MarketIntelligenceSignal:
    """One normalized market intelligence signal category."""

    category: str
    status: str
    score: float
    confidence: float
    confidence_level: str
    risk_flags: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    source: str = DEFAULT_SIGNAL_SOURCE
    last_updated_utc: str = ""


@dataclass(frozen=True)
class MarketIntelligenceReport:
    """Full exportable market intelligence report."""

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
    supported_intelligence_statuses: List[str]
    intelligence_categories: List[str]
    intelligence_signals: List[Dict[str, Any]]
    overall_intelligence_score: float
    overall_confidence: float
    overall_confidence_level: str
    overall_intelligence_status: str
    risk_flags: List[str]
    recommendations: List[str]
    warnings: List[str]
    errors: List[str]
    score_model: List[str]
    confidence_model: List[str]
    risk_flag_model: List[str]
    recommendation_model: List[str]
    integration_targets: List[str]
    safety_guarantees: List[str]
    limitations: List[str]


def _utc_now_iso() -> str:
    """Return a stable UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _build_default_signal(category: str, generated_at_utc: str) -> Dict[str, Any]:
    signal = MarketIntelligenceSignal(
        category=category,
        status=DEFAULT_SIGNAL_STATUS,
        score=DEFAULT_SIGNAL_SCORE,
        confidence=DEFAULT_SIGNAL_CONFIDENCE,
        confidence_level=DEFAULT_SIGNAL_CONFIDENCE_LEVEL,
        risk_flags=[],
        recommendations=[
            "Use this signal as a deterministic paper-only placeholder until future inputs are implemented."
        ],
        warnings=[f"No live intelligence input connected for category: {category}."],
        source=DEFAULT_SIGNAL_SOURCE,
        last_updated_utc=generated_at_utc,
    )
    return asdict(signal)


def build_market_intelligence_report() -> Dict[str, Any]:
    """Build the read-only market intelligence report."""
    generated_at_utc = _utc_now_iso()
    signals = [_build_default_signal(category, generated_at_utc) for category in INTELLIGENCE_CATEGORIES]

    report = MarketIntelligenceReport(
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
        supported_intelligence_statuses=list(SUPPORTED_INTELLIGENCE_STATUSES),
        intelligence_categories=list(INTELLIGENCE_CATEGORIES),
        intelligence_signals=signals,
        overall_intelligence_score=DEFAULT_OVERALL_INTELLIGENCE_SCORE,
        overall_confidence=DEFAULT_OVERALL_CONFIDENCE,
        overall_confidence_level=DEFAULT_OVERALL_CONFIDENCE_LEVEL,
        overall_intelligence_status=DEFAULT_OVERALL_INTELLIGENCE_STATUS,
        risk_flags=[],
        recommendations=[
            "Use this report as a paper-only intelligence interface until future inputs are implemented."
        ],
        warnings=[
            "Market intelligence inputs are not connected in v1.3; using deterministic UNKNOWN fallback."
        ],
        errors=[],
        score_model=list(SCORE_MODEL),
        confidence_model=list(CONFIDENCE_MODEL),
        risk_flag_model=list(RISK_FLAG_MODEL),
        recommendation_model=list(RECOMMENDATION_MODEL),
        integration_targets=list(INTEGRATION_TARGETS),
        safety_guarantees=list(SAFETY_GUARANTEES),
        limitations=list(LIMITATIONS),
    )

    payload = asdict(report)
    validate_market_intelligence_report(payload)
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
    signal = _require_mapping(signal, "intelligence_signal")
    _validate_required_fields(signal, SIGNAL_REQUIRED_FIELDS, "intelligence_signal")

    if signal["category"] not in INTELLIGENCE_CATEGORIES:
        raise ValueError("signal category must be supported")
    if signal["status"] not in SUPPORTED_INTELLIGENCE_STATUSES:
        raise ValueError("signal status must be supported")

    _validate_number_range(signal["score"], "signal.score", -100, 100)
    _validate_number_range(signal["confidence"], "signal.confidence", 0.0, 1.0)
    _validate_confidence_level(signal["confidence_level"], "signal.confidence_level")
    _validate_non_empty_string(signal["source"], "signal.source")
    _validate_non_empty_string(signal["last_updated_utc"], "signal.last_updated_utc")

    for field_name in SIGNAL_LIST_FIELDS:
        _validate_string_list(signal[field_name], f"signal.{field_name}", allow_empty=True)


def validate_market_intelligence_report(payload: Any) -> bool:
    """Validate a market intelligence report payload and raise ValueError on failure."""
    payload = _require_mapping(payload)
    _validate_required_fields(payload, REPORT_REQUIRED_FIELDS, "payload")
    _validate_exact_metadata(payload)
    _validate_non_empty_string(payload["generated_at_utc"], "generated_at_utc")

    for field_name in REPORT_LIST_FIELDS:
        if field_name == "intelligence_signals":
            if not isinstance(payload[field_name], list):
                raise ValueError("intelligence_signals must be a list")
            if not payload[field_name]:
                raise ValueError("intelligence_signals must be a non-empty list")
            continue
        _validate_string_list(payload[field_name], field_name, allow_empty=True)

    if payload["supported_intelligence_statuses"] != SUPPORTED_INTELLIGENCE_STATUSES:
        raise ValueError("supported_intelligence_statuses must match the approved status list")
    if payload["intelligence_categories"] != INTELLIGENCE_CATEGORIES:
        raise ValueError("intelligence_categories must match the approved category list")

    if payload["overall_intelligence_status"] not in SUPPORTED_INTELLIGENCE_STATUSES:
        raise ValueError("overall_intelligence_status must be supported")
    _validate_number_range(payload["overall_intelligence_score"], "overall_intelligence_score", -100, 100)
    _validate_number_range(payload["overall_confidence"], "overall_confidence", 0.0, 1.0)
    _validate_confidence_level(payload["overall_confidence_level"], "overall_confidence_level")

    seen_categories = set()
    for signal in payload["intelligence_signals"]:
        _validate_signal(signal)
        category = signal["category"]
        if category in seen_categories:
            raise ValueError(f"duplicate intelligence signal category: {category}")
        seen_categories.add(category)

    if set(seen_categories) != set(INTELLIGENCE_CATEGORIES):
        raise ValueError("intelligence_signals must include exactly the approved categories")

    return True


def write_market_intelligence_report_json(path: str = "market_intelligence_report.json") -> Dict[str, Any]:
    """Build, validate, and write market_intelligence_report.json."""
    payload = build_market_intelligence_report()
    validate_market_intelligence_report(payload)

    output_path = Path(path)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_market_intelligence_report_json(path: str = "market_intelligence_report.json") -> Dict[str, Any]:
    """Read and validate a market intelligence report JSON file."""
    input_path = Path(path)
    with input_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    validate_market_intelligence_report(payload)
    return payload


def _format_list(title: str, values: List[str]) -> List[str]:
    lines = [f"## {title}"]
    if values:
        lines.extend(f"- {value}" for value in values)
    else:
        lines.append("- None")
    return lines


def format_market_intelligence_report_markdown(payload: Mapping[str, Any]) -> str:
    """Format a validated market intelligence report as Markdown."""
    validate_market_intelligence_report(payload)

    lines = [
        "# Market Intelligence Report",
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
        "## Overall Intelligence",
        f"- Overall Intelligence Score: {payload['overall_intelligence_score']}",
        f"- Overall Confidence: {payload['overall_confidence']}",
        f"- Overall Confidence Level: {payload['overall_confidence_level']}",
        f"- Overall Intelligence Status: {payload['overall_intelligence_status']}",
        "",
        "## Intelligence Signals",
        "",
        "| Category | Status | Score | Confidence | Confidence Level | Source |",
        "|---|---|---|---|---|---|",
    ]

    for signal in payload["intelligence_signals"]:
        lines.append(
            "| {category} | {status} | {score} | {confidence} | {confidence_level} | {source} |".format(
                category=signal["category"],
                status=signal["status"],
                score=signal["score"],
                confidence=signal["confidence"],
                confidence_level=signal["confidence_level"],
                source=signal["source"],
            )
        )

    lines.append("")

    sections = [
        ("Supported Intelligence Statuses", payload["supported_intelligence_statuses"]),
        ("Intelligence Categories", payload["intelligence_categories"]),
        ("Risk Flags", payload["risk_flags"]),
        ("Recommendations", payload["recommendations"]),
        ("Warnings", payload["warnings"]),
        ("Errors", payload["errors"]),
        ("Score Model", payload["score_model"]),
        ("Confidence Model", payload["confidence_model"]),
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


def write_market_intelligence_report_markdown(path: str = "market_intelligence_report.md") -> Dict[str, Any]:
    """Build, validate, and write market_intelligence_report.md."""
    payload = build_market_intelligence_report()
    markdown = format_market_intelligence_report_markdown(payload)

    output_path = Path(path)
    output_path.write_text(markdown, encoding="utf-8")
    return payload


if __name__ == "__main__":
    write_market_intelligence_report_json()
    write_market_intelligence_report_markdown()
