"""
Opportunity Pairing Engine.

Finds and ranks total-market income + growth opportunities.

Primary objective:
Rank opportunities by combined income + growth potential, not dividend yield alone.

Safety:
- paper_trade_mode is always True
- reporting only
- no brokerage execution
- no Robinhood execution
- no live trading
- no order placement
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping


MODULE_NAME = "opportunity_pairing_engine"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

ETF_PAIR = "ETF_PAIR"
COVERED_CALL_ETF = "COVERED_CALL_ETF"
DIVIDEND_ETF = "DIVIDEND_ETF"
DIVIDEND_STOCK = "DIVIDEND_STOCK"
LEVERAGED_ETF = "LEVERAGED_ETF"
CASH_SHIELD = "CASH_SHIELD"

OPPORTUNITY_TYPES = [
    ETF_PAIR,
    COVERED_CALL_ETF,
    DIVIDEND_ETF,
    DIVIDEND_STOCK,
    LEVERAGED_ETF,
    CASH_SHIELD,
]

STRONG_OPPORTUNITY = "STRONG_OPPORTUNITY"
GOOD_OPPORTUNITY = "GOOD_OPPORTUNITY"
WATCHLIST = "WATCHLIST"
HOLD_ONLY = "HOLD_ONLY"
AVOID = "AVOID"

RECOMMENDATIONS = [
    STRONG_OPPORTUNITY,
    GOOD_OPPORTUNITY,
    WATCHLIST,
    HOLD_ONLY,
    AVOID,
]

DEFAULT_SCORE_WEIGHTS = {
    "income_score": 20,
    "growth_score": 25,
    "total_return_score": 25,
    "sustainability_score": 15,
    "risk_score": 10,
    "liquidity_score": 5,
}

OPPORTUNITY_FIELDS = [
    "opportunity_name",
    "opportunity_type",
    "income_symbol",
    "growth_symbol",
    "combined_score",
    "income_score",
    "growth_score",
    "total_return_score",
    "risk_score",
    "sustainability_score",
    "volatility_score",
    "liquidity_score",
    "expense_score",
    "allocation_priority",
    "recommendation",
    "notes",
]

REPORT_REQUIRED_FIELDS = [
    "module_name",
    "module_version",
    "schema_version",
    "generated_by",
    "generated_at_utc",
    "paper_trade_mode",
    "live_trading_enabled",
    "broker_execution_enabled",
    "reporting_only",
    "score_weights",
    "opportunity_types",
    "recommendation_thresholds",
    "opportunities",
    "opportunity_count",
    "warnings",
    "errors",
    "safety_guarantees",
]

LIST_FIELDS = [
    "opportunity_types",
    "opportunities",
    "warnings",
    "errors",
    "safety_guarantees",
]

RECOMMENDATION_THRESHOLDS = {
    STRONG_OPPORTUNITY: 85,
    GOOD_OPPORTUNITY: 75,
    WATCHLIST: 60,
    HOLD_ONLY: 45,
    AVOID: 0,
}

SAFETY_GUARANTEES = [
    "paper_trade_mode is enforced as True",
    "reporting_only is enforced as True",
    "live_trading_enabled is enforced as False",
    "broker_execution_enabled is enforced as False",
    "no brokerage execution is performed",
    "no Robinhood execution is performed",
    "no live trading is performed",
    "no order placement is performed",
]


@dataclass(frozen=True)
class OpportunityComponent:
    """One score component for an investment opportunity."""

    name: str
    score: float = 0.0
    weight: float = 0.0


@dataclass(frozen=True)
class InvestmentOpportunity:
    """One ranked income + growth opportunity."""

    opportunity_name: str
    opportunity_type: str
    income_symbol: str = ""
    growth_symbol: str = ""
    combined_score: float = 0.0
    income_score: float = 0.0
    growth_score: float = 0.0
    total_return_score: float = 0.0
    risk_score: float = 0.0
    sustainability_score: float = 0.0
    volatility_score: float = 0.0
    liquidity_score: float = 0.0
    expense_score: float = 0.0
    allocation_priority: int = 0
    recommendation: str = WATCHLIST
    notes: str = ""


@dataclass(frozen=True)
class OpportunityPairingReport:
    """Full Opportunity Pairing report."""

    module_name: str
    module_version: str
    schema_version: str
    generated_by: str
    generated_at_utc: str
    paper_trade_mode: bool
    live_trading_enabled: bool
    broker_execution_enabled: bool
    reporting_only: bool
    score_weights: Dict[str, float]
    opportunity_types: List[str]
    recommendation_thresholds: Dict[str, float]
    opportunities: List[Dict[str, Any]]
    opportunity_count: int
    warnings: List[str]
    errors: List[str]
    safety_guarantees: List[str]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _clamp_score(value: Any) -> float:
    score = _as_number(value, 0.0)
    if score < 0:
        return 0.0
    if score > 100:
        return 100.0
    return score


def _validate_weights(weights: Mapping[str, Any]) -> None:
    if not isinstance(weights, Mapping):
        raise ValueError("score_weights must be a mapping")
    if set(weights.keys()) != set(DEFAULT_SCORE_WEIGHTS.keys()):
        raise ValueError("score_weights keys must match approved score weight keys")
    total = 0.0
    for key, value in weights.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"weight {key} must be numeric")
        if value < 0:
            raise ValueError(f"weight {key} must not be negative")
        total += float(value)
    if abs(total - 100.0) > 1e-9:
        raise ValueError("score_weights must total 100")


def _normalize_opportunity(raw: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("opportunity must be a mapping")

    name = raw.get("opportunity_name", "")
    if not isinstance(name, str) or not name.strip():
        name = "UNNAMED_OPPORTUNITY"

    opportunity_type = raw.get("opportunity_type", WATCHLIST)
    if opportunity_type not in OPPORTUNITY_TYPES:
        opportunity_type = DIVIDEND_ETF

    income_symbol = raw.get("income_symbol", "")
    growth_symbol = raw.get("growth_symbol", "")
    recommendation = raw.get("recommendation", WATCHLIST)
    notes = raw.get("notes", "")

    normalized = {
        "opportunity_name": name.strip(),
        "opportunity_type": opportunity_type,
        "income_symbol": income_symbol.strip().upper() if isinstance(income_symbol, str) else "",
        "growth_symbol": growth_symbol.strip().upper() if isinstance(growth_symbol, str) else "",
        "combined_score": _clamp_score(raw.get("combined_score", 0)),
        "income_score": _clamp_score(raw.get("income_score", 0)),
        "growth_score": _clamp_score(raw.get("growth_score", 0)),
        "total_return_score": _clamp_score(raw.get("total_return_score", 0)),
        "risk_score": _clamp_score(raw.get("risk_score", 0)),
        "sustainability_score": _clamp_score(raw.get("sustainability_score", 0)),
        "volatility_score": _clamp_score(raw.get("volatility_score", 0)),
        "liquidity_score": _clamp_score(raw.get("liquidity_score", 0)),
        "expense_score": _clamp_score(raw.get("expense_score", 0)),
        "allocation_priority": int(_as_number(raw.get("allocation_priority", 0), 0)),
        "recommendation": recommendation if recommendation in RECOMMENDATIONS else WATCHLIST,
        "notes": notes if isinstance(notes, str) else "",
    }
    return normalized


def calculate_opportunity_score(opportunity: Mapping[str, Any], weights: Mapping[str, Any]) -> float:
    """Calculate a combined opportunity score from normalized 0-100 component scores.

    Higher income, growth, total return, sustainability, and liquidity improve score.
    Lower risk, volatility, and expense improve score through penalty adjustments.
    """
    _validate_weights(weights)
    normalized = _normalize_opportunity(opportunity)

    base = 0.0
    for component_name, weight in weights.items():
        value = normalized.get(component_name, 0)
        if component_name == "risk_score":
            value = 100.0 - value
        base += _clamp_score(value) * (float(weight) / 100.0)

    volatility_penalty = normalized["volatility_score"] * 0.05
    expense_penalty = normalized["expense_score"] * 0.05
    combined = base - volatility_penalty - expense_penalty
    return round(max(0.0, min(100.0, combined)), 2)


def classify_opportunity_recommendation(combined_score: Any) -> str:
    score = _as_number(combined_score, 0.0)
    if score >= 85:
        return STRONG_OPPORTUNITY
    if score >= 75:
        return GOOD_OPPORTUNITY
    if score >= 60:
        return WATCHLIST
    if score >= 45:
        return HOLD_ONLY
    return AVOID


def compare_opportunities(opportunity_a: Mapping[str, Any], opportunity_b: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return the better opportunity by combined score, then total return, then growth."""
    a = _normalize_opportunity(opportunity_a)
    b = _normalize_opportunity(opportunity_b)
    for key in ("combined_score", "total_return_score", "growth_score", "income_score", "liquidity_score"):
        if a[key] > b[key]:
            return opportunity_a
        if b[key] > a[key]:
            return opportunity_b
    return opportunity_a


def _build_final_opportunity(raw: Mapping[str, Any], weights: Mapping[str, Any]) -> Dict[str, Any]:
    normalized = _normalize_opportunity(raw)
    combined_score = calculate_opportunity_score(normalized, weights)
    final = InvestmentOpportunity(
        opportunity_name=normalized["opportunity_name"],
        opportunity_type=normalized["opportunity_type"],
        income_symbol=normalized["income_symbol"],
        growth_symbol=normalized["growth_symbol"],
        combined_score=combined_score,
        income_score=normalized["income_score"],
        growth_score=normalized["growth_score"],
        total_return_score=normalized["total_return_score"],
        risk_score=normalized["risk_score"],
        sustainability_score=normalized["sustainability_score"],
        volatility_score=normalized["volatility_score"],
        liquidity_score=normalized["liquidity_score"],
        expense_score=normalized["expense_score"],
        allocation_priority=normalized["allocation_priority"],
        recommendation=classify_opportunity_recommendation(combined_score),
        notes=normalized["notes"],
    )
    return asdict(final)


def rank_opportunities(opportunities: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Return opportunities sorted by best combined score first."""
    ranked = [_build_final_opportunity(item, DEFAULT_SCORE_WEIGHTS) for item in opportunities]
    ranked.sort(
        key=lambda item: (
            -item["combined_score"],
            -item["total_return_score"],
            -item["growth_score"],
            -item["income_score"],
            item["opportunity_name"],
        )
    )
    for index, item in enumerate(ranked, start=1):
        item["allocation_priority"] = index
    return ranked


def build_opportunity_pairing_report(opportunities: Iterable[Mapping[str, Any]] | None = None) -> Dict[str, Any]:
    """Build a valid opportunity report. If no opportunities exist, report is empty."""
    raw_opportunities = list(opportunities or [])
    ranked = rank_opportunities(raw_opportunities)

    report = OpportunityPairingReport(
        module_name=MODULE_NAME,
        module_version=MODULE_VERSION,
        schema_version=SCHEMA_VERSION,
        generated_by=GENERATED_BY,
        generated_at_utc=_utc_now_iso(),
        paper_trade_mode=PAPER_TRADE_MODE,
        live_trading_enabled=LIVE_TRADING_ENABLED,
        broker_execution_enabled=BROKER_EXECUTION_ENABLED,
        reporting_only=REPORTING_ONLY,
        score_weights=dict(DEFAULT_SCORE_WEIGHTS),
        opportunity_types=list(OPPORTUNITY_TYPES),
        recommendation_thresholds=dict(RECOMMENDATION_THRESHOLDS),
        opportunities=ranked,
        opportunity_count=len(ranked),
        warnings=[],
        errors=[],
        safety_guarantees=list(SAFETY_GUARANTEES),
    )
    payload = asdict(report)
    validate_opportunity_pairing_report(payload)
    return payload


def _require_mapping(payload: Any, label: str = "payload") -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{label} must be a mapping/dictionary")
    return payload


def _validate_required(payload: Mapping[str, Any], required_fields: Iterable[str], label: str) -> None:
    missing = [field for field in required_fields if field not in payload]
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


def _validate_score_range(value: Any, field_name: str, minimum: float = 0, maximum: float = 100) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric")
    if value < minimum or value > maximum:
        raise ValueError(f"{field_name} must be between {minimum} and {maximum}")


def _validate_opportunity_entry(entry: Any) -> None:
    entry = _require_mapping(entry, "opportunity")
    _validate_required(entry, OPPORTUNITY_FIELDS, "opportunity")
    if not isinstance(entry["opportunity_name"], str) or not entry["opportunity_name"].strip():
        raise ValueError("opportunity_name must be a non-empty string")
    if entry["opportunity_type"] not in OPPORTUNITY_TYPES:
        raise ValueError("opportunity_type is invalid")
    for field_name in ("income_symbol", "growth_symbol", "recommendation", "notes"):
        if not isinstance(entry[field_name], str):
            raise ValueError(f"{field_name} must be a string")
    for field_name in (
        "combined_score",
        "income_score",
        "growth_score",
        "total_return_score",
        "risk_score",
        "sustainability_score",
        "volatility_score",
        "liquidity_score",
        "expense_score",
    ):
        _validate_score_range(entry[field_name], field_name)
    if not isinstance(entry["allocation_priority"], int) or isinstance(entry["allocation_priority"], bool):
        raise ValueError("allocation_priority must be an integer")
    if entry["recommendation"] not in RECOMMENDATIONS:
        raise ValueError("recommendation is invalid")
    if classify_opportunity_recommendation(entry["combined_score"]) != entry["recommendation"]:
        raise ValueError("recommendation does not match combined_score")


def validate_opportunity_pairing_report(payload: Any) -> bool:
    payload = _require_mapping(payload)
    _validate_required(payload, REPORT_REQUIRED_FIELDS, "payload")

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
    for key, expected_value in expected.items():
        if payload.get(key) != expected_value:
            raise ValueError(f"{key} must be {expected_value!r}")

    if not isinstance(payload["generated_at_utc"], str) or not payload["generated_at_utc"].strip():
        raise ValueError("generated_at_utc must be a non-empty string")
    _validate_weights(payload["score_weights"])
    if payload["opportunity_types"] != OPPORTUNITY_TYPES:
        raise ValueError("opportunity_types must match approved list")
    if payload["recommendation_thresholds"] != RECOMMENDATION_THRESHOLDS:
        raise ValueError("recommendation_thresholds must match approved thresholds")

    for field_name in LIST_FIELDS:
        if field_name == "opportunities":
            if not isinstance(payload[field_name], list):
                raise ValueError("opportunities must be a list")
            continue
        _validate_string_list(payload[field_name], field_name, allow_empty=True)

    if not isinstance(payload["opportunity_count"], int) or isinstance(payload["opportunity_count"], bool):
        raise ValueError("opportunity_count must be an integer")
    if payload["opportunity_count"] != len(payload["opportunities"]):
        raise ValueError("opportunity_count must match opportunities length")

    for entry in payload["opportunities"]:
        _validate_opportunity_entry(entry)

    scores = [entry["combined_score"] for entry in payload["opportunities"]]
    if scores != sorted(scores, reverse=True):
        raise ValueError("opportunities must be sorted by combined_score descending")

    return True


def write_opportunity_pairing_report_json(path: str = "opportunity_pairing_report.json") -> Dict[str, Any]:
    payload = build_opportunity_pairing_report()
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_opportunity_pairing_report_json(path: str = "opportunity_pairing_report.json") -> Dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    validate_opportunity_pairing_report(payload)
    return payload


def write_opportunity_pairing_report_csv(path: str = "opportunity_pairing_report.csv") -> Dict[str, Any]:
    payload = build_opportunity_pairing_report()
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OPPORTUNITY_FIELDS)
        writer.writeheader()
        for entry in payload["opportunities"]:
            writer.writerow({field: entry.get(field, "") for field in OPPORTUNITY_FIELDS})
    return payload


def _format_list(title: str, values: List[str]) -> List[str]:
    lines = [f"## {title}"]
    if values:
        lines.extend(f"- {value}" for value in values)
    else:
        lines.append("- None")
    return lines


def format_opportunity_pairing_report_markdown(payload: Mapping[str, Any]) -> str:
    validate_opportunity_pairing_report(payload)
    lines = [
        "# Opportunity Pairing Report",
        "",
        f"- Module: {payload['module_name']}",
        f"- Generated At UTC: {payload['generated_at_utc']}",
        f"- Paper Trade Mode: {payload['paper_trade_mode']}",
        f"- Reporting Only: {payload['reporting_only']}",
        f"- Opportunity Count: {payload['opportunity_count']}",
        "",
        "## Score Weights",
    ]
    for key, value in payload["score_weights"].items():
        lines.append(f"- {key}: {value}")
    lines.extend([
        "",
        "## Opportunities",
        "",
        "| Priority | Opportunity | Type | Income | Growth | Combined | Income Score | Growth Score | Total Return | Risk | Sustainability | Volatility | Liquidity | Expense | Recommendation | Notes |",
        "|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ])
    if payload["opportunities"]:
        for entry in payload["opportunities"]:
            lines.append(
                "| {allocation_priority} | {opportunity_name} | {opportunity_type} | {income_symbol} | {growth_symbol} | {combined_score} | {income_score} | {growth_score} | {total_return_score} | {risk_score} | {sustainability_score} | {volatility_score} | {liquidity_score} | {expense_score} | {recommendation} | {notes} |".format(**entry)
            )
    else:
        lines.append("|  | None |  |  |  |  |  |  |  |  |  |  |  |  |  |  |")

    lines.append("")
    for title, values in [
        ("Opportunity Types", payload["opportunity_types"]),
        ("Warnings", payload["warnings"]),
        ("Errors", payload["errors"]),
        ("Safety Guarantees", payload["safety_guarantees"]),
    ]:
        lines.extend(_format_list(title, values))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_opportunity_pairing_report_markdown(path: str = "opportunity_pairing_report.md") -> Dict[str, Any]:
    payload = build_opportunity_pairing_report()
    Path(path).write_text(format_opportunity_pairing_report_markdown(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    write_opportunity_pairing_report_json()
    write_opportunity_pairing_report_csv()
    write_opportunity_pairing_report_markdown()
