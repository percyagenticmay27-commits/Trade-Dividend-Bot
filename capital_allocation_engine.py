"""
Capital Allocation Engine for the Dividend Bot.

Determines the optimal number of paper-only holdings and dollar allocations based
on current portfolio value, available cash, portfolio tier, scores, cash reserve,
minimum practical position size, and allocation caps.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

MODULE_NAME = "capital_allocation_engine"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"
BOT_NAME = "Agentic Robin Dividend Bot"
BOT_TYPE = "paper_dividend_etf_management"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

TIER_1 = "TIER_1_FOUNDATION"
TIER_2 = "TIER_2_DIVERSIFICATION"
TIER_3 = "TIER_3_GROWTH_AND_INCOME"
TIER_4 = "TIER_4_OPTIMIZATION"
TIER_5 = "TIER_5_ADVANCED_OPTIMIZATION"
SUPPORTED_PORTFOLIO_TIERS = [TIER_1, TIER_2, TIER_3, TIER_4, TIER_5]

CASH_SHIELD_SYMBOL = "SGOV"
SUPPORTED_ALLOCATION_ACTIONS = ["ALLOCATE", "HOLD_CASH", "SKIP_SMALL_POSITION", "WATCH", "UNKNOWN"]
CONFIDENCE_LEVELS = ["LOW", "MEDIUM", "HIGH"]

TIER_RULES = {
    TIER_1: {"min_value": 500, "max_value": 999.99, "target_holdings": 2, "cash_reserve_pct": 0.20, "max_position_pct": 0.40, "min_position_dollars": 75},
    TIER_2: {"min_value": 1000, "max_value": 4999.99, "target_holdings": 5, "cash_reserve_pct": 0.15, "max_position_pct": 0.25, "min_position_dollars": 100},
    TIER_3: {"min_value": 5000, "max_value": 24999.99, "target_holdings": 10, "cash_reserve_pct": 0.12, "max_position_pct": 0.18, "min_position_dollars": 150},
    TIER_4: {"min_value": 25000, "max_value": 99999.99, "target_holdings": 18, "cash_reserve_pct": 0.10, "max_position_pct": 0.12, "min_position_dollars": 250},
    TIER_5: {"min_value": 100000, "max_value": None, "target_holdings": 25, "cash_reserve_pct": 0.08, "max_position_pct": 0.08, "min_position_dollars": 500},
}

SAFETY_GUARANTEES = [
    "paper_trade_mode is enforced as True",
    "reporting_only is enforced as True",
    "live_trading_enabled is enforced as False",
    "broker_execution_enabled is enforced as False",
    "no Robinhood execution is performed",
    "no brokerage execution is performed",
    "no order placement is performed",
    "no portfolio state mutation is performed",
    "allocations are dollar recommendations only",
]

SCORING_MODEL = [
    "Allocation score range is 0 to 100.",
    "Higher decision_score, conviction_score, opportunity_score, entry_score, self_funding_score, and confidence increase allocation priority.",
    "Current version accepts explicit scored candidates and produces paper-only allocation recommendations.",
]

REPORT_REQUIRED_FIELDS = [
    "bot_name", "bot_type", "module_name", "module_version", "schema_version", "generated_by", "generated_at_utc",
    "paper_trade_mode", "live_trading_enabled", "broker_execution_enabled", "reporting_only", "starting_capital",
    "current_portfolio_value", "available_cash", "portfolio_tier", "tier_rules", "target_holding_count",
    "cash_reserve_target_pct", "cash_reserve_target_dollars", "investable_cash", "max_position_pct", "min_position_dollars",
    "cash_shield_symbol", "allocations", "allocation_count", "unallocated_cash", "warnings", "errors", "scoring_model", "safety_guarantees",
]

ALLOCATION_FIELDS = [
    "symbol", "opportunity_name", "allocation_score", "allocation_action", "allocation_priority", "target_allocation_pct",
    "target_allocation_dollars", "decision_score", "conviction_score", "opportunity_score", "entry_score", "self_funding_score",
    "confidence", "confidence_level", "notes",
]


@dataclass(frozen=True)
class CapitalAllocationInput:
    starting_capital: float = 500.0
    current_portfolio_value: float = 500.0
    available_cash: float = 500.0
    reinvest_dividends: bool = True
    compound_growth: bool = True


@dataclass(frozen=True)
class CapitalAllocation:
    symbol: str
    opportunity_name: str = ""
    allocation_score: float = 0.0
    allocation_action: str = "UNKNOWN"
    allocation_priority: int = 0
    target_allocation_pct: float = 0.0
    target_allocation_dollars: float = 0.0
    decision_score: float = 0.0
    conviction_score: float = 0.0
    opportunity_score: float = 0.0
    entry_score: float = 0.0
    self_funding_score: float = 0.0
    confidence: float = 0.0
    confidence_level: str = "LOW"
    notes: str = ""


@dataclass(frozen=True)
class CapitalAllocationReport:
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
    starting_capital: float
    current_portfolio_value: float
    available_cash: float
    portfolio_tier: str
    tier_rules: Dict[str, Dict[str, Any]]
    target_holding_count: int
    cash_reserve_target_pct: float
    cash_reserve_target_dollars: float
    investable_cash: float
    max_position_pct: float
    min_position_dollars: float
    cash_shield_symbol: str
    allocations: List[Dict[str, Any]]
    allocation_count: int
    unallocated_cash: float
    warnings: List[str]
    errors: List[str]
    scoring_model: List[str]
    safety_guarantees: List[str]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _num(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _clamp(value: Any, low: float, high: float) -> float:
    return max(low, min(high, _num(value, low)))


def determine_portfolio_tier(portfolio_value: float) -> str:
    value = _num(portfolio_value, 0.0)
    if value < 1000:
        return TIER_1
    if value < 5000:
        return TIER_2
    if value < 25000:
        return TIER_3
    if value < 100000:
        return TIER_4
    return TIER_5


def calculate_allocation_score(candidate: Mapping[str, Any]) -> float:
    if not isinstance(candidate, Mapping):
        raise ValueError("candidate must be a mapping")
    score = (
        _clamp(candidate.get("decision_score", 0), 0, 100) * 0.30
        + _clamp(candidate.get("conviction_score", 0), 0, 100) * 0.25
        + _clamp(candidate.get("opportunity_score", candidate.get("combined_score", 0)), 0, 100) * 0.20
        + _clamp(candidate.get("entry_score", 0), 0, 100) * 0.10
        + _clamp(candidate.get("self_funding_score", 0), 0, 100) * 0.10
        + (_clamp(candidate.get("confidence", 0), 0, 1) * 100) * 0.05
    )
    return round(score, 2)


def _normalize_candidate(candidate: Mapping[str, Any]) -> Dict[str, Any]:
    symbol = candidate.get("symbol", "UNKNOWN")
    if not isinstance(symbol, str) or not symbol.strip():
        symbol = "UNKNOWN"
    confidence_level = candidate.get("confidence_level", "LOW")
    if confidence_level not in CONFIDENCE_LEVELS:
        confidence_level = "LOW"
    return {
        "symbol": symbol.strip().upper(),
        "opportunity_name": str(candidate.get("opportunity_name", "")),
        "decision_score": _clamp(candidate.get("decision_score", 0), 0, 100),
        "conviction_score": _clamp(candidate.get("conviction_score", 0), 0, 100),
        "opportunity_score": _clamp(candidate.get("opportunity_score", candidate.get("combined_score", 0)), 0, 100),
        "entry_score": _clamp(candidate.get("entry_score", 0), 0, 100),
        "self_funding_score": _clamp(candidate.get("self_funding_score", 0), 0, 100),
        "confidence": _clamp(candidate.get("confidence", 0), 0, 1),
        "confidence_level": confidence_level,
        "notes": str(candidate.get("notes", "")),
    }


def build_allocations(candidates: Iterable[Mapping[str, Any]], portfolio_value: float, available_cash: float) -> List[Dict[str, Any]]:
    tier = determine_portfolio_tier(portfolio_value)
    rules = TIER_RULES[tier]
    cash_reserve = round(portfolio_value * rules["cash_reserve_pct"], 2)
    investable_cash = max(0.0, round(min(available_cash, portfolio_value - cash_reserve), 2))
    max_position = round(portfolio_value * rules["max_position_pct"], 2)
    min_position = float(rules["min_position_dollars"])
    target_count = int(rules["target_holdings"])

    rows = []
    for raw in candidates:
        item = _normalize_candidate(raw)
        item["allocation_score"] = calculate_allocation_score(item)
        rows.append(item)
    rows.sort(key=lambda row: (-row["allocation_score"], row["symbol"]))
    rows = rows[:target_count]
    total_score = sum(row["allocation_score"] for row in rows)

    allocations: List[Dict[str, Any]] = []
    used = 0.0
    for priority, row in enumerate(rows, start=1):
        if total_score <= 0 or investable_cash <= 0:
            dollars = 0.0
        else:
            dollars = round(investable_cash * (row["allocation_score"] / total_score), 2)
        dollars = min(dollars, max_position)
        if dollars < min_position:
            action = "SKIP_SMALL_POSITION"
            dollars = 0.0
        else:
            action = "ALLOCATE"
            used += dollars
        pct = round(dollars / portfolio_value, 4) if portfolio_value > 0 else 0.0
        allocations.append(asdict(CapitalAllocation(
            symbol=row["symbol"], opportunity_name=row["opportunity_name"], allocation_score=row["allocation_score"],
            allocation_action=action, allocation_priority=priority, target_allocation_pct=pct,
            target_allocation_dollars=round(dollars, 2), decision_score=row["decision_score"], conviction_score=row["conviction_score"],
            opportunity_score=row["opportunity_score"], entry_score=row["entry_score"], self_funding_score=row["self_funding_score"],
            confidence=row["confidence"], confidence_level=row["confidence_level"], notes=row["notes"],
        )))
    return allocations


def build_capital_allocation_report(
    candidates: Iterable[Mapping[str, Any]] | None = None,
    starting_capital: float = 500.0,
    current_portfolio_value: float = 500.0,
    available_cash: float = 500.0,
) -> Dict[str, Any]:
    if starting_capital <= 0 or current_portfolio_value <= 0 or available_cash < 0:
        raise ValueError("capital values must be positive, and available_cash must be non-negative")
    tier = determine_portfolio_tier(current_portfolio_value)
    rules = TIER_RULES[tier]
    cash_reserve = round(current_portfolio_value * rules["cash_reserve_pct"], 2)
    investable_cash = max(0.0, round(min(available_cash, current_portfolio_value - cash_reserve), 2))
    allocations = build_allocations(list(candidates or []), current_portfolio_value, available_cash)
    allocated = round(sum(row["target_allocation_dollars"] for row in allocations), 2)
    warnings = []
    if not allocations:
        warnings.append("No allocation candidates supplied; generated valid empty paper-only report.")
    payload = asdict(CapitalAllocationReport(
        bot_name=BOT_NAME, bot_type=BOT_TYPE, module_name=MODULE_NAME, module_version=MODULE_VERSION,
        schema_version=SCHEMA_VERSION, generated_by=GENERATED_BY, generated_at_utc=_utc_now_iso(),
        paper_trade_mode=True, live_trading_enabled=False, broker_execution_enabled=False, reporting_only=True,
        starting_capital=float(starting_capital), current_portfolio_value=float(current_portfolio_value), available_cash=float(available_cash),
        portfolio_tier=tier, tier_rules=TIER_RULES, target_holding_count=int(rules["target_holdings"]),
        cash_reserve_target_pct=float(rules["cash_reserve_pct"]), cash_reserve_target_dollars=cash_reserve,
        investable_cash=investable_cash, max_position_pct=float(rules["max_position_pct"]), min_position_dollars=float(rules["min_position_dollars"]),
        cash_shield_symbol=CASH_SHIELD_SYMBOL, allocations=allocations, allocation_count=len(allocations),
        unallocated_cash=round(max(0.0, available_cash - allocated), 2), warnings=warnings, errors=[],
        scoring_model=SCORING_MODEL, safety_guarantees=SAFETY_GUARANTEES,
    ))
    validate_capital_allocation_report(payload)
    return payload


def _validate_list(value: Any, name: str, strings: bool = True) -> None:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list")
    if strings:
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"{name} entries must be non-empty strings")


def validate_capital_allocation_report(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    for field in REPORT_REQUIRED_FIELDS:
        if field not in payload:
            raise ValueError(f"missing required field: {field}")
    for key, expected in {"paper_trade_mode": True, "live_trading_enabled": False, "broker_execution_enabled": False, "reporting_only": True}.items():
        if payload[key] is not expected:
            raise ValueError(f"{key} must be {expected}")
    if payload["portfolio_tier"] not in SUPPORTED_PORTFOLIO_TIERS:
        raise ValueError("portfolio_tier must be supported")
    for numeric in ["starting_capital", "current_portfolio_value", "available_cash", "cash_reserve_target_pct", "cash_reserve_target_dollars", "investable_cash", "max_position_pct", "min_position_dollars", "unallocated_cash"]:
        if isinstance(payload[numeric], bool) or not isinstance(payload[numeric], (int, float)) or payload[numeric] < 0:
            raise ValueError(f"{numeric} must be a non-negative number")
    if not isinstance(payload["target_holding_count"], int) or payload["target_holding_count"] <= 0:
        raise ValueError("target_holding_count must be positive integer")
    if payload["cash_shield_symbol"] != CASH_SHIELD_SYMBOL:
        raise ValueError("cash_shield_symbol must be SGOV")
    for list_name in ["allocations", "warnings", "errors", "scoring_model", "safety_guarantees"]:
        _validate_list(payload[list_name], list_name, strings=(list_name != "allocations"))
    if payload["allocation_count"] != len(payload["allocations"]):
        raise ValueError("allocation_count must match allocations length")
    previous = 10**9
    for row in payload["allocations"]:
        if not isinstance(row, Mapping):
            raise ValueError("allocation rows must be mappings")
        for field in ALLOCATION_FIELDS:
            if field not in row:
                raise ValueError(f"allocation missing field: {field}")
        if row["allocation_action"] not in SUPPORTED_ALLOCATION_ACTIONS:
            raise ValueError("allocation_action must be supported")
        if row["confidence_level"] not in CONFIDENCE_LEVELS:
            raise ValueError("confidence_level must be supported")
        if row["symbol"] != row["symbol"].upper() or not row["symbol"].strip():
            raise ValueError("symbol must be uppercase non-empty string")
        if row["allocation_score"] > previous:
            raise ValueError("allocations must be sorted by allocation_score descending")
        previous = row["allocation_score"]
    return True


def write_capital_allocation_report_json(path: str = "capital_allocation_report.json") -> Dict[str, Any]:
    payload = build_capital_allocation_report()
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_capital_allocation_report_json(path: str = "capital_allocation_report.json") -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_capital_allocation_report(payload)
    return payload


def write_capital_allocation_report_csv(path: str = "capital_allocations.csv") -> Dict[str, Any]:
    payload = build_capital_allocation_report()
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ALLOCATION_FIELDS)
        writer.writeheader()
        for row in payload["allocations"]:
            writer.writerow({field: row.get(field, "") for field in ALLOCATION_FIELDS})
    return payload


def format_capital_allocation_report_markdown(payload: Mapping[str, Any]) -> str:
    validate_capital_allocation_report(payload)
    lines = ["# Capital Allocation Report", "", f"- Portfolio Tier: {payload['portfolio_tier']}", f"- Current Portfolio Value: ${payload['current_portfolio_value']:.2f}", f"- Available Cash: ${payload['available_cash']:.2f}", f"- Target Holdings: {payload['target_holding_count']}", f"- Cash Reserve Target: ${payload['cash_reserve_target_dollars']:.2f}", f"- Investable Cash: ${payload['investable_cash']:.2f}", "", "## Allocations", "", "| Symbol | Score | Action | Priority | Dollars | Percent |", "|---|---:|---|---:|---:|---:|"]
    if payload["allocations"]:
        for row in payload["allocations"]:
            lines.append(f"| {row['symbol']} | {row['allocation_score']} | {row['allocation_action']} | {row['allocation_priority']} | {row['target_allocation_dollars']} | {row['target_allocation_pct']} |")
    else:
        lines.append("| None |  |  |  |  |  |")
    lines.extend(["", "## Scoring Model"] + [f"- {x}" for x in payload["scoring_model"]] + ["", "## Safety Guarantees"] + [f"- {x}" for x in payload["safety_guarantees"]])
    return "\n".join(lines) + "\n"


def write_capital_allocation_report_markdown(path: str = "capital_allocation_report.md") -> Dict[str, Any]:
    payload = build_capital_allocation_report()
    Path(path).write_text(format_capital_allocation_report_markdown(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    write_capital_allocation_report_json()
    write_capital_allocation_report_csv()
    write_capital_allocation_report_markdown()
