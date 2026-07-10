"""Opportunity Rotation Forecast Engine.

Identifies emerging and fading leadership using score direction, market context,
NAV preservation, wrapper quality, and target-return proximity. Forecasts are
advisory, paper-only, and never place orders or change production weights.
"""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

MODULE_NAME = "opportunity_rotation_forecast_engine"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

MONTHLY_OBJECTIVE_PCT = 4.0
SUPPORTED_STATUSES = ["CURRENT_LEADER", "EMERGING_LEADER", "STABLE", "FADING_LEADER", "DECLINING", "UNKNOWN"]
SUPPORTED_CONFIDENCE_LEVELS = ["LOW", "MEDIUM", "HIGH"]
SUPPORTED_HORIZONS = ["IMMEDIATE", "NEAR_TERM", "INTERMEDIATE", "LONG_TERM", "UNKNOWN"]

FORECAST_WEIGHTS = {
    "opportunity_acceleration": 20,
    "conviction_acceleration": 15,
    "momentum_acceleration": 15,
    "market_intelligence_trend": 10,
    "technical_trend": 10,
    "analyst_revision_trend": 10,
    "sector_leadership": 5,
    "nav_preservation": 10,
    "wrapper_quality": 5,
}

SAFETY_GUARANTEES = [
    "paper_trade_mode is enforced as True",
    "live_trading_enabled is enforced as False",
    "broker_execution_enabled is enforced as False",
    "reporting_only is enforced as True",
    "no brokerage execution",
    "no Robinhood execution",
    "no order placement",
    "no automatic production-weight changes",
]

FORECAST_FIELDS = [
    "symbol", "underlying_symbol", "opportunity_name", "forecast_score", "forecast_status",
    "current_score", "previous_score", "score_change", "current_confidence",
    "future_opportunity_confidence", "confidence_level", "forecast_horizon",
    "projected_monthly_return_pct", "gap_to_monthly_objective_pct", "nav_preservation_score",
    "wrapper_quality_score", "rotation_priority", "opportunity_story", "risk_flags",
]

REPORT_REQUIRED_FIELDS = [
    "module_name", "module_version", "schema_version", "generated_by", "generated_at_utc",
    "paper_trade_mode", "live_trading_enabled", "broker_execution_enabled", "reporting_only",
    "monthly_objective_pct", "forecast_weights", "forecast_entries", "current_leaders",
    "emerging_leaders", "fading_leaders", "warnings", "errors", "safety_guarantees",
]


@dataclass(frozen=True)
class RotationForecastEntry:
    symbol: str
    underlying_symbol: str = ""
    opportunity_name: str = ""
    forecast_score: float = 0.0
    forecast_status: str = "UNKNOWN"
    current_score: float = 0.0
    previous_score: float = 0.0
    score_change: float = 0.0
    current_confidence: float = 0.0
    future_opportunity_confidence: float = 0.0
    confidence_level: str = "LOW"
    forecast_horizon: str = "UNKNOWN"
    projected_monthly_return_pct: float = 0.0
    gap_to_monthly_objective_pct: float = MONTHLY_OBJECTIVE_PCT
    nav_preservation_score: float = 0.0
    wrapper_quality_score: float = 0.0
    rotation_priority: int = 0
    opportunity_story: str = ""
    risk_flags: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class OpportunityRotationForecastReport:
    module_name: str
    module_version: str
    schema_version: str
    generated_by: str
    generated_at_utc: str
    paper_trade_mode: bool
    live_trading_enabled: bool
    broker_execution_enabled: bool
    reporting_only: bool
    monthly_objective_pct: float
    forecast_weights: Dict[str, float]
    forecast_entries: List[Dict[str, Any]]
    current_leaders: List[str]
    emerging_leaders: List[str]
    fading_leaders: List[str]
    warnings: List[str]
    errors: List[str]
    safety_guarantees: List[str]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value)


def _score(value: Any) -> float:
    return max(0.0, min(100.0, _number(value)))


def _symbol(value: Any) -> str:
    return value.strip().upper() if isinstance(value, str) and value.strip() else "UNKNOWN"


def calculate_forecast_score(candidate: Mapping[str, Any]) -> float:
    if not isinstance(candidate, Mapping):
        raise ValueError("candidate must be a mapping")
    weighted = 0.0
    for component, weight in FORECAST_WEIGHTS.items():
        weighted += _score(candidate.get(component, 0.0)) * weight / 100.0
    return round(weighted, 2)


def classify_forecast_status(current_score: float, score_change: float, forecast_score: float) -> str:
    if current_score >= 85 and score_change >= 0:
        return "CURRENT_LEADER"
    if forecast_score >= 75 and score_change >= 5:
        return "EMERGING_LEADER"
    if score_change <= -10:
        return "DECLINING"
    if score_change <= -5:
        return "FADING_LEADER"
    if forecast_score >= 50:
        return "STABLE"
    return "UNKNOWN"


def classify_confidence_level(confidence: float) -> str:
    if confidence >= 0.75:
        return "HIGH"
    if confidence >= 0.40:
        return "MEDIUM"
    return "LOW"


def classify_forecast_horizon(score_change: float, forecast_score: float) -> str:
    if score_change >= 10 and forecast_score >= 80:
        return "IMMEDIATE"
    if score_change >= 5 and forecast_score >= 70:
        return "NEAR_TERM"
    if forecast_score >= 55:
        return "INTERMEDIATE"
    return "LONG_TERM"


def _build_story(symbol: str, status: str, change: float, nav: float, wrapper: float, projected: float) -> str:
    direction = "improving" if change > 0 else "weakening" if change < 0 else "stable"
    return (
        f"{symbol} is classified as {status}. Its composite score is {direction} by {change:.2f} points. "
        f"NAV preservation is {nav:.2f}, wrapper quality is {wrapper:.2f}, and projected monthly return "
        f"is {projected:.2f}% versus the {MONTHLY_OBJECTIVE_PCT:.2f}% objective."
    )


def normalize_forecast_candidate(candidate: Mapping[str, Any], priority: int = 0) -> Dict[str, Any]:
    if not isinstance(candidate, Mapping):
        raise ValueError("candidate must be a mapping")
    symbol = _symbol(candidate.get("symbol"))
    current = _score(candidate.get("current_score", candidate.get("opportunity_score", 0.0)))
    previous = _score(candidate.get("previous_score", candidate.get("previous_opportunity_score", current)))
    change = round(current - previous, 2)
    forecast_score = calculate_forecast_score(candidate)
    status = classify_forecast_status(current, change, forecast_score)
    confidence = max(0.0, min(1.0, _number(candidate.get("future_opportunity_confidence", forecast_score / 100.0))))
    projected = max(0.0, _number(candidate.get("projected_monthly_return_pct", 0.0)))
    nav = _score(candidate.get("nav_preservation", candidate.get("nav_preservation_score", 0.0)))
    wrapper = _score(candidate.get("wrapper_quality", candidate.get("wrapper_quality_score", 0.0)))
    flags = candidate.get("risk_flags", [])
    if not isinstance(flags, list):
        flags = []
    flags = [item for item in flags if isinstance(item, str) and item.strip()]
    if nav < 50:
        flags.append("NAV_PRESERVATION_RISK")
    if projected < MONTHLY_OBJECTIVE_PCT:
        flags.append("BELOW_MONTHLY_OBJECTIVE")
    entry = RotationForecastEntry(
        symbol=symbol,
        underlying_symbol=_symbol(candidate.get("underlying_symbol")) if candidate.get("underlying_symbol") else "",
        opportunity_name=str(candidate.get("opportunity_name", "")),
        forecast_score=forecast_score,
        forecast_status=status,
        current_score=current,
        previous_score=previous,
        score_change=change,
        current_confidence=max(0.0, min(1.0, _number(candidate.get("current_confidence", 0.0)))),
        future_opportunity_confidence=round(confidence, 4),
        confidence_level=classify_confidence_level(confidence),
        forecast_horizon=classify_forecast_horizon(change, forecast_score),
        projected_monthly_return_pct=round(projected, 4),
        gap_to_monthly_objective_pct=round(projected - MONTHLY_OBJECTIVE_PCT, 4),
        nav_preservation_score=nav,
        wrapper_quality_score=wrapper,
        rotation_priority=priority,
        opportunity_story=_build_story(symbol, status, change, nav, wrapper, projected),
        risk_flags=flags,
    )
    return asdict(entry)


def build_opportunity_rotation_forecast_report(candidates: Iterable[Mapping[str, Any]] | None = None) -> Dict[str, Any]:
    raw = list(candidates or [])
    ranked = []
    for item in raw:
        normalized = normalize_forecast_candidate(item)
        ranked.append(normalized)
    ranked.sort(key=lambda row: (-row["forecast_score"], -row["score_change"], row["symbol"]))
    for index, row in enumerate(ranked, start=1):
        row["rotation_priority"] = index
    payload = asdict(OpportunityRotationForecastReport(
        module_name=MODULE_NAME,
        module_version=MODULE_VERSION,
        schema_version=SCHEMA_VERSION,
        generated_by=GENERATED_BY,
        generated_at_utc=_utc_now(),
        paper_trade_mode=True,
        live_trading_enabled=False,
        broker_execution_enabled=False,
        reporting_only=True,
        monthly_objective_pct=MONTHLY_OBJECTIVE_PCT,
        forecast_weights=dict(FORECAST_WEIGHTS),
        forecast_entries=ranked,
        current_leaders=[row["symbol"] for row in ranked if row["forecast_status"] == "CURRENT_LEADER"],
        emerging_leaders=[row["symbol"] for row in ranked if row["forecast_status"] == "EMERGING_LEADER"],
        fading_leaders=[row["symbol"] for row in ranked if row["forecast_status"] in ["FADING_LEADER", "DECLINING"]],
        warnings=[] if raw else ["No candidates supplied; generated valid empty forecast report."],
        errors=[],
        safety_guarantees=list(SAFETY_GUARANTEES),
    ))
    validate_opportunity_rotation_forecast_report(payload)
    return payload


def validate_opportunity_rotation_forecast_report(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    for field_name in REPORT_REQUIRED_FIELDS:
        if field_name not in payload:
            raise ValueError(f"missing required field: {field_name}")
    expected_flags = {
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "reporting_only": True,
    }
    for key, expected in expected_flags.items():
        if payload[key] is not expected:
            raise ValueError(f"{key} must be {expected}")
    if payload["forecast_weights"] != FORECAST_WEIGHTS or sum(payload["forecast_weights"].values()) != 100:
        raise ValueError("forecast_weights must match approved weights and total 100")
    for field_name in ["forecast_entries", "current_leaders", "emerging_leaders", "fading_leaders", "warnings", "errors", "safety_guarantees"]:
        if not isinstance(payload[field_name], list):
            raise ValueError(f"{field_name} must be a list")
    previous_score = float("inf")
    for entry in payload["forecast_entries"]:
        if not isinstance(entry, Mapping):
            raise ValueError("forecast entries must be mappings")
        for field_name in FORECAST_FIELDS:
            if field_name not in entry:
                raise ValueError(f"forecast entry missing field: {field_name}")
        if entry["forecast_status"] not in SUPPORTED_STATUSES:
            raise ValueError("unsupported forecast_status")
        if entry["confidence_level"] not in SUPPORTED_CONFIDENCE_LEVELS:
            raise ValueError("unsupported confidence_level")
        if entry["forecast_horizon"] not in SUPPORTED_HORIZONS:
            raise ValueError("unsupported forecast_horizon")
        if entry["forecast_score"] > previous_score:
            raise ValueError("forecast_entries must be sorted descending")
        previous_score = entry["forecast_score"]
        if not isinstance(entry["risk_flags"], list):
            raise ValueError("risk_flags must be a list")
    return True


def write_opportunity_rotation_forecast_json(path: str = "opportunity_rotation_forecast.json") -> Dict[str, Any]:
    payload = build_opportunity_rotation_forecast_report()
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_opportunity_rotation_forecast_json(path: str = "opportunity_rotation_forecast.json") -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_opportunity_rotation_forecast_report(payload)
    return payload


def write_opportunity_rotation_forecast_csv(path: str = "opportunity_rotation_forecast.csv") -> Dict[str, Any]:
    payload = build_opportunity_rotation_forecast_report()
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FORECAST_FIELDS)
        writer.writeheader()
        for row in payload["forecast_entries"]:
            writer.writerow({field_name: row.get(field_name, "") for field_name in FORECAST_FIELDS})
    return payload


def format_opportunity_rotation_forecast_markdown(payload: Mapping[str, Any]) -> str:
    validate_opportunity_rotation_forecast_report(payload)
    lines = [
        "# Opportunity Rotation Forecast",
        "",
        f"- Monthly Objective: {payload['monthly_objective_pct']:.2f}%",
        f"- Candidates Reviewed: {len(payload['forecast_entries'])}",
        "",
        "## Forecast Rankings",
        "",
        "| Priority | Symbol | Status | Forecast Score | Score Change | Projected Monthly Return | NAV Preservation |",
        "|---:|---|---|---:|---:|---:|---:|",
    ]
    for row in payload["forecast_entries"]:
        lines.append(
            f"| {row['rotation_priority']} | {row['symbol']} | {row['forecast_status']} | "
            f"{row['forecast_score']} | {row['score_change']} | {row['projected_monthly_return_pct']}% | "
            f"{row['nav_preservation_score']} |"
        )
    lines.extend(["", "## Emerging Leaders"])
    lines.extend([f"- {symbol}" for symbol in payload["emerging_leaders"]] or ["- None"])
    lines.extend(["", "## Fading Leaders"])
    lines.extend([f"- {symbol}" for symbol in payload["fading_leaders"]] or ["- None"])
    lines.extend(["", "## Opportunity Stories"])
    lines.extend([f"- **{row['symbol']}**: {row['opportunity_story']}" for row in payload["forecast_entries"]] or ["- None"])
    lines.extend(["", "## Safety Guarantees"])
    lines.extend(f"- {item}" for item in payload["safety_guarantees"])
    return "\n".join(lines) + "\n"


def write_opportunity_rotation_forecast_markdown(path: str = "opportunity_rotation_forecast.md") -> Dict[str, Any]:
    payload = build_opportunity_rotation_forecast_report()
    Path(path).write_text(format_opportunity_rotation_forecast_markdown(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    write_opportunity_rotation_forecast_json()
    write_opportunity_rotation_forecast_csv()
    write_opportunity_rotation_forecast_markdown()
