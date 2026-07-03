"""
Read-only Market Regime Engine for Dividend Bot Strategy Intelligence v1.2.

This module provides a safe, deterministic market regime report interface for
downstream strategy engines. The current version defines the public contract and
fallback behavior only; it does not pull live market data and does not modify any
trading, workflow, portfolio, dividend, or asset registry modules.

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


MODULE_NAME = "market_regime_engine"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"

BOT_NAME = "Agentic Robin Dividend Bot"
BOT_TYPE = "paper_dividend_etf_management"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False

STRONG_BULL = "STRONG_BULL"
BULL = "BULL"
NEUTRAL = "NEUTRAL"
BEAR = "BEAR"
STRONG_BEAR = "STRONG_BEAR"
HIGH_VOLATILITY = "HIGH_VOLATILITY"
UNKNOWN = "UNKNOWN"

SUPPORTED_REGIMES = [
    STRONG_BULL,
    BULL,
    NEUTRAL,
    BEAR,
    STRONG_BEAR,
    HIGH_VOLATILITY,
    UNKNOWN,
]

LOW = "LOW"
MEDIUM = "MEDIUM"
HIGH = "HIGH"
SUPPORTED_CONFIDENCE_LEVELS = [LOW, MEDIUM, HIGH]

DEFAULT_REGIME = UNKNOWN
DEFAULT_REGIME_SCORE = 0
DEFAULT_CONFIDENCE = 0.0
DEFAULT_CONFIDENCE_LEVEL = LOW
DEFAULT_PORTFOLIO_POSTURE = "PAPER_ONLY_OBSERVATION"
DEFAULT_RISK_MULTIPLIER = 1.0
DEFAULT_POSITION_SIZING_MULTIPLIER = 1.0
DEFAULT_CASH_RESERVE_TARGET = 0.20

FUTURE_INPUT_SOURCES = [
    "SPY",
    "QQQ",
    "VIX",
    "Treasury yields",
    "Breadth indicators",
    "Volatility indicators",
]

SCORING_MODEL = [
    "Future regime score range is -100 to +100.",
    "75 to 100 maps to STRONG_BULL.",
    "25 to 74 maps to BULL.",
    "-24 to 24 maps to NEUTRAL.",
    "-74 to -25 maps to BEAR.",
    "-100 to -75 maps to STRONG_BEAR.",
    "Volatility override may map to HIGH_VOLATILITY.",
    "Current v1.2 fallback behavior maps to UNKNOWN with score 0.",
]

CONFIDENCE_MODEL = [
    "Confidence range is 0.0 to 1.0.",
    "0.00 to 0.39 maps to LOW.",
    "0.40 to 0.69 maps to MEDIUM.",
    "0.70 to 1.00 maps to HIGH.",
    "Future confidence may use input availability, trend agreement, volatility confirmation, breadth confirmation, yield confirmation, and data freshness.",
    "Current v1.2 fallback behavior uses confidence 0.0 and LOW.",
]

RISK_MULTIPLIER_MODEL = [
    "STRONG_BULL maps to 1.25.",
    "BULL maps to 1.10.",
    "NEUTRAL maps to 1.00.",
    "BEAR maps to 0.70.",
    "STRONG_BEAR maps to 0.40.",
    "HIGH_VOLATILITY maps to 0.50.",
    "UNKNOWN maps to 1.00.",
]

POSITION_SIZING_MULTIPLIER_MODEL = [
    "STRONG_BULL maps to 1.15.",
    "BULL maps to 1.05.",
    "NEUTRAL maps to 1.00.",
    "BEAR maps to 0.75.",
    "STRONG_BEAR maps to 0.50.",
    "HIGH_VOLATILITY maps to 0.50.",
    "UNKNOWN maps to 1.00.",
]

CASH_RESERVE_MODEL = [
    "STRONG_BULL maps to 0.05.",
    "BULL maps to 0.10.",
    "NEUTRAL maps to 0.20.",
    "BEAR maps to 0.35.",
    "STRONG_BEAR maps to 0.50.",
    "HIGH_VOLATILITY maps to 0.45.",
    "UNKNOWN maps to 0.20.",
]

INTEGRATION_TARGETS = [
    "asset_registry.py provides asset classifications for future regime-aware routing.",
    "Future Momentum Engine may consume regime, regime_score, confidence_level, risk_multiplier, and position_sizing_multiplier.",
    "Future Unified Opportunity Engine may consume the regime report as global market context.",
    "Leveraged ETF opportunities may be reduced during BEAR, STRONG_BEAR, or HIGH_VOLATILITY regimes.",
    "UNKNOWN regime should preserve neutral fallback behavior and avoid automatic promotion.",
]

SAFETY_GUARANTEES = [
    "paper_trade_mode is enforced as True",
    "live_trading_enabled is enforced as False",
    "broker_execution_enabled is enforced as False",
    "no Robinhood execution is performed",
    "no broker execution is performed",
    "no real order placement is performed",
    "no trading logic is modified",
    "run_daily_paper_cycle.py is not modified",
    "portfolio_engine.py is not modified",
    "dividend_engine.py is not modified",
    "asset_registry.py is not modified",
    "read-only analysis only",
]

LIMITATIONS = [
    "Current v1.2 version defines safe interfaces and deterministic fallback behavior only.",
    "No live market data is pulled.",
    "No external market-data provider is connected.",
    "Regime defaults to UNKNOWN until future inputs are implemented.",
    "Outputs provide context only and do not authorize trading actions.",
]

REPORT_REQUIRED_FIELDS = [
    "bot_name",
    "bot_type",
    "module_name",
    "module_version",
    "schema_version",
    "generated_by",
    "generated_at_utc",
    "paper_trade_mode",
    "live_trading_enabled",
    "broker_execution_enabled",
    "supported_regimes",
    "future_input_sources",
    "available_inputs",
    "missing_inputs",
    "market_regime",
    "scoring_model",
    "confidence_model",
    "risk_multiplier_model",
    "position_sizing_multiplier_model",
    "cash_reserve_model",
    "integration_targets",
    "warnings",
    "errors",
    "safety_guarantees",
    "limitations",
]

REPORT_LIST_FIELDS = [
    "supported_regimes",
    "future_input_sources",
    "available_inputs",
    "missing_inputs",
    "scoring_model",
    "confidence_model",
    "risk_multiplier_model",
    "position_sizing_multiplier_model",
    "cash_reserve_model",
    "integration_targets",
    "warnings",
    "errors",
    "safety_guarantees",
    "limitations",
]

MARKET_REGIME_REQUIRED_FIELDS = [
    "regime",
    "regime_score",
    "confidence",
    "confidence_level",
    "portfolio_posture",
    "risk_multiplier",
    "position_sizing_multiplier",
    "cash_reserve_target",
    "warnings",
    "recommendations",
]

MARKET_REGIME_LIST_FIELDS = [
    "warnings",
    "recommendations",
]


@dataclass(frozen=True)
class MarketRegime:
    """Active market regime result."""

    regime: str
    regime_score: float
    confidence: float
    confidence_level: str
    portfolio_posture: str
    risk_multiplier: float
    position_sizing_multiplier: float
    cash_reserve_target: float
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class MarketRegimeReport:
    """Full exportable market regime report."""

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
    supported_regimes: List[str]
    future_input_sources: List[str]
    available_inputs: List[str]
    missing_inputs: List[str]
    market_regime: Dict[str, Any]
    scoring_model: List[str]
    confidence_model: List[str]
    risk_multiplier_model: List[str]
    position_sizing_multiplier_model: List[str]
    cash_reserve_model: List[str]
    integration_targets: List[str]
    warnings: List[str]
    errors: List[str]
    safety_guarantees: List[str]
    limitations: List[str]


def _utc_now_iso() -> str:
    """Return a stable UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _build_default_market_regime() -> Dict[str, Any]:
    """Build the deterministic v1.2 fallback regime."""
    regime = MarketRegime(
        regime=DEFAULT_REGIME,
        regime_score=DEFAULT_REGIME_SCORE,
        confidence=DEFAULT_CONFIDENCE,
        confidence_level=DEFAULT_CONFIDENCE_LEVEL,
        portfolio_posture=DEFAULT_PORTFOLIO_POSTURE,
        risk_multiplier=DEFAULT_RISK_MULTIPLIER,
        position_sizing_multiplier=DEFAULT_POSITION_SIZING_MULTIPLIER,
        cash_reserve_target=DEFAULT_CASH_RESERVE_TARGET,
        warnings=["Market regime inputs are not connected in v1.2; using UNKNOWN fallback."],
        recommendations=["Use this report as a paper-only context interface until future inputs are implemented."],
    )
    return asdict(regime)


def build_market_regime_report() -> Dict[str, Any]:
    """Build the read-only market regime report."""
    market_regime = _build_default_market_regime()

    report = MarketRegimeReport(
        bot_name=BOT_NAME,
        bot_type=BOT_TYPE,
        module_name=MODULE_NAME,
        module_version=MODULE_VERSION,
        schema_version=SCHEMA_VERSION,
        generated_by=GENERATED_BY,
        generated_at_utc=_utc_now_iso(),
        paper_trade_mode=PAPER_TRADE_MODE,
        live_trading_enabled=LIVE_TRADING_ENABLED,
        broker_execution_enabled=BROKER_EXECUTION_ENABLED,
        supported_regimes=list(SUPPORTED_REGIMES),
        future_input_sources=list(FUTURE_INPUT_SOURCES),
        available_inputs=[],
        missing_inputs=list(FUTURE_INPUT_SOURCES),
        market_regime=market_regime,
        scoring_model=list(SCORING_MODEL),
        confidence_model=list(CONFIDENCE_MODEL),
        risk_multiplier_model=list(RISK_MULTIPLIER_MODEL),
        position_sizing_multiplier_model=list(POSITION_SIZING_MULTIPLIER_MODEL),
        cash_reserve_model=list(CASH_RESERVE_MODEL),
        integration_targets=list(INTEGRATION_TARGETS),
        warnings=list(market_regime["warnings"]),
        errors=[],
        safety_guarantees=list(SAFETY_GUARANTEES),
        limitations=list(LIMITATIONS),
    )

    payload = asdict(report)
    validate_market_regime_report(payload)
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


def _validate_market_regime(market_regime: Any) -> None:
    market_regime = _require_mapping(market_regime, "market_regime")
    _validate_required_fields(market_regime, MARKET_REGIME_REQUIRED_FIELDS, "market_regime")

    regime = market_regime["regime"]
    if regime not in SUPPORTED_REGIMES:
        raise ValueError("market_regime.regime must be supported")

    _validate_number_range(market_regime["regime_score"], "market_regime.regime_score", -100, 100)
    _validate_number_range(market_regime["confidence"], "market_regime.confidence", 0.0, 1.0)

    confidence_level = market_regime["confidence_level"]
    if confidence_level not in SUPPORTED_CONFIDENCE_LEVELS:
        raise ValueError("market_regime.confidence_level must be LOW, MEDIUM, or HIGH")

    _validate_non_empty_string(market_regime["portfolio_posture"], "market_regime.portfolio_posture")
    _validate_number_range(market_regime["risk_multiplier"], "market_regime.risk_multiplier", 0.25, 1.50)
    _validate_number_range(
        market_regime["position_sizing_multiplier"],
        "market_regime.position_sizing_multiplier",
        0.25,
        1.25,
    )
    _validate_number_range(market_regime["cash_reserve_target"], "market_regime.cash_reserve_target", 0.0, 1.0)

    for field_name in MARKET_REGIME_LIST_FIELDS:
        _validate_string_list(market_regime[field_name], f"market_regime.{field_name}", allow_empty=True)


def validate_market_regime_report(payload: Any) -> bool:
    """Validate a market regime report payload and raise ValueError on failure."""
    payload = _require_mapping(payload)
    _validate_required_fields(payload, REPORT_REQUIRED_FIELDS, "payload")
    _validate_exact_metadata(payload)
    _validate_non_empty_string(payload["generated_at_utc"], "generated_at_utc")

    for field_name in REPORT_LIST_FIELDS:
        _validate_string_list(payload[field_name], field_name, allow_empty=True)

    if payload["supported_regimes"] != SUPPORTED_REGIMES:
        raise ValueError("supported_regimes must match the approved regime list")

    _validate_market_regime(payload["market_regime"])
    return True


def write_market_regime_report_json(path: str = "market_regime_report.json") -> Dict[str, Any]:
    """Build, validate, and write market_regime_report.json."""
    payload = build_market_regime_report()
    validate_market_regime_report(payload)

    output_path = Path(path)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_market_regime_report_json(path: str = "market_regime_report.json") -> Dict[str, Any]:
    """Read and validate a market regime report JSON file."""
    input_path = Path(path)
    with input_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    validate_market_regime_report(payload)
    return payload


def _format_list(title: str, values: List[str]) -> List[str]:
    lines = [f"## {title}"]
    if values:
        lines.extend(f"- {value}" for value in values)
    else:
        lines.append("- None")
    return lines


def format_market_regime_report_markdown(payload: Mapping[str, Any]) -> str:
    """Format a validated market regime report as Markdown."""
    validate_market_regime_report(payload)
    regime = payload["market_regime"]

    lines = [
        "# Market Regime Report",
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
        "## Current Regime",
        f"- Regime: {regime['regime']}",
        f"- Regime Score: {regime['regime_score']}",
        f"- Confidence: {regime['confidence']}",
        f"- Confidence Level: {regime['confidence_level']}",
        f"- Portfolio Posture: {regime['portfolio_posture']}",
        f"- Risk Multiplier: {regime['risk_multiplier']}",
        f"- Position Sizing Multiplier: {regime['position_sizing_multiplier']}",
        f"- Cash Reserve Target: {regime['cash_reserve_target']}",
        "",
    ]

    sections = [
        ("Supported Regimes", payload["supported_regimes"]),
        ("Future Input Sources", payload["future_input_sources"]),
        ("Available Inputs", payload["available_inputs"]),
        ("Missing Inputs", payload["missing_inputs"]),
        ("Scoring Model", payload["scoring_model"]),
        ("Confidence Model", payload["confidence_model"]),
        ("Risk Multiplier Model", payload["risk_multiplier_model"]),
        ("Position Sizing Multiplier Model", payload["position_sizing_multiplier_model"]),
        ("Cash Reserve Model", payload["cash_reserve_model"]),
        ("Integration Targets", payload["integration_targets"]),
        ("Regime Warnings", regime["warnings"]),
        ("Regime Recommendations", regime["recommendations"]),
        ("Warnings", payload["warnings"]),
        ("Errors", payload["errors"]),
        ("Safety Guarantees", payload["safety_guarantees"]),
        ("Limitations", payload["limitations"]),
    ]

    for title, values in sections:
        lines.extend(_format_list(title, values))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_market_regime_report_markdown(path: str = "market_regime_report.md") -> Dict[str, Any]:
    """Build, validate, and write market_regime_report.md."""
    payload = build_market_regime_report()
    markdown = format_market_regime_report_markdown(payload)

    output_path = Path(path)
    output_path.write_text(markdown, encoding="utf-8")
    return payload


if __name__ == "__main__":
    write_market_regime_report_json()
    write_market_regime_report_markdown()
