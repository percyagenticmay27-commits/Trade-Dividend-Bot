"""
Dividend Ranking Engine.

Combines dividend quality, momentum, dividend growth, dividend safety, and
valuation scores into a final ranked recommendation report.

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
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional


MODULE_NAME = "dividend_ranking_engine"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

LOW = "LOW"
MEDIUM = "MEDIUM"
HIGH = "HIGH"
VALID_CONFIDENCE_LEVELS = [LOW, MEDIUM, HIGH]

UNKNOWN = "UNKNOWN"
VALID_TREND_DIRECTIONS = ["UP", "DOWN", "SIDEWAYS", "REVERSAL_UP", "REVERSAL_DOWN", UNKNOWN]

STRONG_BUY = "STRONG_BUY"
BUY = "BUY"
HOLD = "HOLD"
WATCHLIST = "WATCHLIST"
AVOID = "AVOID"
VALID_RATINGS = [STRONG_BUY, BUY, HOLD, WATCHLIST, AVOID]

DEFAULT_COMPONENT_WEIGHTS = {
    "dividend_quality": 35,
    "momentum": 20,
    "dividend_growth": 20,
    "dividend_safety": 15,
    "valuation": 10,
}

INPUT_FILES = [
    "dividend_quality_report.json",
    "momentum_score_report.json",
    "dividend_growth_report.json",
    "dividend_safety_report.json",
    "valuation_report.json",
]

ENTRY_FIELDS = [
    "symbol",
    "overall_score",
    "overall_rating",
    "quality_score",
    "momentum_score",
    "growth_score",
    "safety_score",
    "valuation_score",
    "confidence",
    "confidence_level",
    "trend_direction",
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
    "component_weights",
    "input_files",
    "available_input_files",
    "missing_input_files",
    "rankings",
    "ranking_count",
    "warnings",
    "errors",
    "safety_guarantees",
]

LIST_FIELDS = [
    "input_files",
    "available_input_files",
    "missing_input_files",
    "rankings",
    "warnings",
    "errors",
    "safety_guarantees",
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
]


@dataclass(frozen=True)
class DividendRankingComponent:
    """One ranking component score."""

    name: str
    score: float = 0.0
    weight: float = 0.0


@dataclass(frozen=True)
class DividendRankingEntry:
    """One final dividend ranking entry."""

    symbol: str
    overall_score: float
    overall_rating: str
    quality_score: float = 0.0
    momentum_score: float = 0.0
    growth_score: float = 0.0
    safety_score: float = 0.0
    valuation_score: float = 0.0
    confidence: float = 0.0
    confidence_level: str = LOW
    trend_direction: str = UNKNOWN
    recommendation: str = HOLD
    notes: str = ""


@dataclass(frozen=True)
class DividendRankingReport:
    """Full dividend ranking report."""

    module_name: str
    module_version: str
    schema_version: str
    generated_by: str
    generated_at_utc: str
    paper_trade_mode: bool
    live_trading_enabled: bool
    broker_execution_enabled: bool
    reporting_only: bool
    component_weights: Dict[str, float]
    input_files: List[str]
    available_input_files: List[str]
    missing_input_files: List[str]
    rankings: List[Dict[str, Any]]
    ranking_count: int
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


def _normalize_symbol(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    symbol = value.strip().upper()
    return symbol or None


def _validate_weights(weights: Mapping[str, Any]) -> None:
    if not isinstance(weights, Mapping):
        raise ValueError("component_weights must be a mapping")
    if set(weights.keys()) != set(DEFAULT_COMPONENT_WEIGHTS.keys()):
        raise ValueError("component_weights keys must match default component keys")
    total = 0.0
    for key, value in weights.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"component weight {key} must be numeric")
        if value < 0:
            raise ValueError(f"component weight {key} must not be negative")
        total += float(value)
    if abs(total - 100.0) > 1e-9:
        raise ValueError("component weights must total 100")


def calculate_weighted_score(components: Mapping[str, Any], weights: Mapping[str, Any]) -> float:
    """Calculate weighted 0-100 score. Missing component scores default to 0."""
    _validate_weights(weights)
    if not isinstance(components, Mapping):
        raise ValueError("components must be a mapping")

    total = 0.0
    for component_name, weight in weights.items():
        score = _clamp_score(components.get(component_name, 0))
        total += score * (float(weight) / 100.0)
    return round(total, 2)


def classify_overall_rating(overall_score: Any) -> str:
    """Classify overall score into a stable rating."""
    score = _as_number(overall_score, 0.0)
    if score >= 90:
        return STRONG_BUY
    if score >= 80:
        return BUY
    if score >= 65:
        return HOLD
    if score >= 50:
        return WATCHLIST
    return AVOID


def _read_json_file(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _extract_entries(payload: Any) -> List[Mapping[str, Any]]:
    """Extract list-like entries from common report shapes."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, Mapping)]
    if not isinstance(payload, Mapping):
        return []
    for key in ("entries", "rankings", "results", "assets", "signals", "items", "dividend_rankings"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, Mapping)]
    # Single symbol report support.
    if "symbol" in payload:
        return [payload]
    return []


def _first_present(mapping: Mapping[str, Any], names: Iterable[str], default: Any = None) -> Any:
    for name in names:
        if name in mapping:
            return mapping[name]
    return default


def _merge_component_entry(merged: Dict[str, Dict[str, Any]], component_key: str, entry: Mapping[str, Any]) -> None:
    symbol = _normalize_symbol(entry.get("symbol"))
    if symbol is None:
        return

    target = merged.setdefault(
        symbol,
        {
            "symbol": symbol,
            "quality_score": 0.0,
            "momentum_score": 0.0,
            "growth_score": 0.0,
            "safety_score": 0.0,
            "valuation_score": 0.0,
            "confidence": 0.0,
            "confidence_level": LOW,
            "trend_direction": UNKNOWN,
            "recommendation": HOLD,
            "notes": "",
        },
    )

    score_field = {
        "dividend_quality": "quality_score",
        "momentum": "momentum_score",
        "dividend_growth": "growth_score",
        "dividend_safety": "safety_score",
        "valuation": "valuation_score",
    }[component_key]

    possible_score_names = {
        "dividend_quality": ("quality_score", "dividend_quality_score", "score", "overall_score"),
        "momentum": ("momentum_score", "score", "overall_score"),
        "dividend_growth": ("growth_score", "dividend_growth_score", "score", "overall_score"),
        "dividend_safety": ("safety_score", "dividend_safety_score", "score", "overall_score"),
        "valuation": ("valuation_score", "score", "overall_score"),
    }[component_key]

    target[score_field] = _clamp_score(_first_present(entry, possible_score_names, 0))

    confidence = _first_present(entry, ("confidence", "overall_confidence"), None)
    if confidence is not None:
        target["confidence"] = max(target["confidence"], min(1.0, max(0.0, _as_number(confidence, 0.0))))

    confidence_level = _first_present(entry, ("confidence_level", "overall_confidence_level"), None)
    if confidence_level in VALID_CONFIDENCE_LEVELS:
        order = {LOW: 0, MEDIUM: 1, HIGH: 2}
        if order[confidence_level] > order[target["confidence_level"]]:
            target["confidence_level"] = confidence_level

    trend_direction = _first_present(entry, ("trend_direction", "trend"), None)
    if trend_direction in VALID_TREND_DIRECTIONS and target["trend_direction"] == UNKNOWN:
        target["trend_direction"] = trend_direction

    recommendation = entry.get("recommendation")
    if isinstance(recommendation, str) and recommendation.strip():
        target["recommendation"] = recommendation.strip().upper()

    notes = entry.get("notes")
    if isinstance(notes, str) and notes.strip():
        if target["notes"]:
            target["notes"] += " | "
        target["notes"] += notes.strip()


def _load_component_inputs(root_path: str = ".") -> tuple[Dict[str, Dict[str, Any]], List[str], List[str], List[str]]:
    root = Path(root_path)
    merged: Dict[str, Dict[str, Any]] = {}
    available: List[str] = []
    missing: List[str] = []
    warnings: List[str] = []

    component_by_file = {
        "dividend_quality_report.json": "dividend_quality",
        "momentum_score_report.json": "momentum",
        "dividend_growth_report.json": "dividend_growth",
        "dividend_safety_report.json": "dividend_safety",
        "valuation_report.json": "valuation",
    }

    for filename in INPUT_FILES:
        path = root / filename
        if not path.exists():
            missing.append(filename)
            continue
        available.append(filename)
        try:
            payload = _read_json_file(path)
        except (OSError, json.JSONDecodeError) as exc:
            warnings.append(f"Could not read {filename}: {exc}")
            continue
        for entry in _extract_entries(payload):
            _merge_component_entry(merged, component_by_file[filename], entry)

    return merged, available, missing, warnings


def _build_entry(raw: Mapping[str, Any], weights: Mapping[str, Any]) -> Dict[str, Any]:
    components = {
        "dividend_quality": _clamp_score(raw.get("quality_score", 0)),
        "momentum": _clamp_score(raw.get("momentum_score", 0)),
        "dividend_growth": _clamp_score(raw.get("growth_score", 0)),
        "dividend_safety": _clamp_score(raw.get("safety_score", 0)),
        "valuation": _clamp_score(raw.get("valuation_score", 0)),
    }
    overall_score = calculate_weighted_score(components, weights)
    overall_rating = classify_overall_rating(overall_score)
    recommendation = raw.get("recommendation", HOLD)
    if not isinstance(recommendation, str) or not recommendation.strip():
        recommendation = HOLD

    entry = DividendRankingEntry(
        symbol=str(raw["symbol"]).upper(),
        overall_score=overall_score,
        overall_rating=overall_rating,
        quality_score=components["dividend_quality"],
        momentum_score=components["momentum"],
        growth_score=components["dividend_growth"],
        safety_score=components["dividend_safety"],
        valuation_score=components["valuation"],
        confidence=min(1.0, max(0.0, _as_number(raw.get("confidence", 0.0), 0.0))),
        confidence_level=raw.get("confidence_level") if raw.get("confidence_level") in VALID_CONFIDENCE_LEVELS else LOW,
        trend_direction=raw.get("trend_direction") if raw.get("trend_direction") in VALID_TREND_DIRECTIONS else UNKNOWN,
        recommendation=recommendation.strip().upper(),
        notes=raw.get("notes") if isinstance(raw.get("notes"), str) else "",
    )
    return asdict(entry)


def build_dividend_ranking_report(root_path: str = ".") -> Dict[str, Any]:
    """Build the dividend ranking report. If no inputs exist, report is valid and empty."""
    merged, available, missing, warnings = _load_component_inputs(root_path=root_path)
    weights = dict(DEFAULT_COMPONENT_WEIGHTS)
    rankings = [_build_entry(raw, weights) for raw in merged.values()]
    rankings.sort(key=lambda item: (-item["overall_score"], item["symbol"]))

    report = DividendRankingReport(
        module_name=MODULE_NAME,
        module_version=MODULE_VERSION,
        schema_version=SCHEMA_VERSION,
        generated_by=GENERATED_BY,
        generated_at_utc=_utc_now_iso(),
        paper_trade_mode=PAPER_TRADE_MODE,
        live_trading_enabled=LIVE_TRADING_ENABLED,
        broker_execution_enabled=BROKER_EXECUTION_ENABLED,
        reporting_only=REPORTING_ONLY,
        component_weights=weights,
        input_files=list(INPUT_FILES),
        available_input_files=available,
        missing_input_files=missing,
        rankings=rankings,
        ranking_count=len(rankings),
        warnings=warnings,
        errors=[],
        safety_guarantees=list(SAFETY_GUARANTEES),
    )
    payload = asdict(report)
    validate_dividend_ranking_report(payload)
    return payload


def _require_mapping(payload: Any, label: str = "payload") -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{label} must be a mapping/dictionary")
    return payload


def _validate_string_list(value: Any, field_name: str, allow_empty: bool = True) -> None:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    if not allow_empty and not value:
        raise ValueError(f"{field_name} must not be empty")
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name}[{index}] must be a non-empty string")


def _validate_required(payload: Mapping[str, Any], fields: Iterable[str], label: str) -> None:
    missing = [field for field in fields if field not in payload]
    if missing:
        raise ValueError(f"{label} missing required field(s): {', '.join(missing)}")


def _validate_entry(entry: Any) -> None:
    entry = _require_mapping(entry, "ranking entry")
    _validate_required(entry, ENTRY_FIELDS, "ranking entry")
    symbol = _normalize_symbol(entry["symbol"])
    if symbol is None or symbol != entry["symbol"]:
        raise ValueError("entry symbol must be non-empty uppercase string")

    for field_name in ("overall_score", "quality_score", "momentum_score", "growth_score", "safety_score", "valuation_score"):
        _validate_score_range(entry[field_name], field_name, 0, 100)

    if entry["overall_rating"] not in VALID_RATINGS:
        raise ValueError("overall_rating is invalid")
    if classify_overall_rating(entry["overall_score"]) != entry["overall_rating"]:
        raise ValueError("overall_rating does not match overall_score")

    _validate_score_range(entry["confidence"], "confidence", 0.0, 1.0)
    if entry["confidence_level"] not in VALID_CONFIDENCE_LEVELS:
        raise ValueError("confidence_level is invalid")
    if entry["trend_direction"] not in VALID_TREND_DIRECTIONS:
        raise ValueError("trend_direction is invalid")
    if not isinstance(entry["recommendation"], str) or not entry["recommendation"].strip():
        raise ValueError("recommendation must be a non-empty string")
    if not isinstance(entry["notes"], str):
        raise ValueError("notes must be a string")


def _validate_score_range(value: Any, field_name: str, minimum: float, maximum: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric")
    if value < minimum or value > maximum:
        raise ValueError(f"{field_name} must be between {minimum} and {maximum}")


def validate_dividend_ranking_report(payload: Any) -> bool:
    """Validate a dividend ranking report payload."""
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

    _validate_weights(payload["component_weights"])

    for field_name in LIST_FIELDS:
        if field_name == "rankings":
            if not isinstance(payload[field_name], list):
                raise ValueError("rankings must be a list")
            continue
        _validate_string_list(payload[field_name], field_name, allow_empty=True)

    if not isinstance(payload["ranking_count"], int) or isinstance(payload["ranking_count"], bool):
        raise ValueError("ranking_count must be an integer")
    if payload["ranking_count"] != len(payload["rankings"]):
        raise ValueError("ranking_count must match rankings length")

    seen = set()
    for entry in payload["rankings"]:
        _validate_entry(entry)
        if entry["symbol"] in seen:
            raise ValueError(f"duplicate ranking symbol: {entry['symbol']}")
        seen.add(entry["symbol"])

    return True


def write_dividend_ranking_report_json(path: str = "dividend_rankings.json") -> Dict[str, Any]:
    payload = build_dividend_ranking_report()
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_dividend_ranking_report_json(path: str = "dividend_rankings.json") -> Dict[str, Any]:
    payload = _read_json_file(Path(path))
    validate_dividend_ranking_report(payload)
    return payload


def write_dividend_ranking_report_csv(path: str = "dividend_rankings.csv") -> Dict[str, Any]:
    payload = build_dividend_ranking_report()
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ENTRY_FIELDS)
        writer.writeheader()
        for entry in payload["rankings"]:
            writer.writerow({field: entry.get(field, "") for field in ENTRY_FIELDS})
    return payload


def _format_list(title: str, values: List[str]) -> List[str]:
    lines = [f"## {title}"]
    if values:
        lines.extend(f"- {value}" for value in values)
    else:
        lines.append("- None")
    return lines


def format_dividend_ranking_report_markdown(payload: Mapping[str, Any]) -> str:
    validate_dividend_ranking_report(payload)
    lines = [
        "# Dividend Ranking Report",
        "",
        f"- Module: {payload['module_name']}",
        f"- Generated At UTC: {payload['generated_at_utc']}",
        f"- Paper Trade Mode: {payload['paper_trade_mode']}",
        f"- Reporting Only: {payload['reporting_only']}",
        f"- Ranking Count: {payload['ranking_count']}",
        "",
        "## Component Weights",
    ]
    for key, value in payload["component_weights"].items():
        lines.append(f"- {key}: {value}")
    lines.extend([
        "",
        "## Rankings",
        "",
        "| Symbol | Overall Score | Rating | Quality | Momentum | Growth | Safety | Valuation | Confidence | Level | Trend | Recommendation | Notes |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---|---|---|---|",
    ])
    if payload["rankings"]:
        for entry in payload["rankings"]:
            lines.append(
                "| {symbol} | {overall_score} | {overall_rating} | {quality_score} | {momentum_score} | {growth_score} | {safety_score} | {valuation_score} | {confidence} | {confidence_level} | {trend_direction} | {recommendation} | {notes} |".format(**entry)
            )
    else:
        lines.append("| None |  |  |  |  |  |  |  |  |  |  |  |  |")

    lines.append("")
    for title, values in [
        ("Input Files", payload["input_files"]),
        ("Available Input Files", payload["available_input_files"]),
        ("Missing Input Files", payload["missing_input_files"]),
        ("Warnings", payload["warnings"]),
        ("Errors", payload["errors"]),
        ("Safety Guarantees", payload["safety_guarantees"]),
    ]:
        lines.extend(_format_list(title, values))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_dividend_ranking_report_markdown(path: str = "dividend_rankings.md") -> Dict[str, Any]:
    payload = build_dividend_ranking_report()
    Path(path).write_text(format_dividend_ranking_report_markdown(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    write_dividend_ranking_report_json()
    write_dividend_ranking_report_csv()
    write_dividend_ranking_report_markdown()
