"""Master Portfolio Strategy Engine for the paper-only Dividend Bot."""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

MODULE_NAME = "master_portfolio_strategy_engine"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

SUPPORTED_ACTIONS = ["EXIT_TO_SGOV", "REALLOCATE", "INCREASE", "REINVEST", "HOLD", "WATCH", "NO_ACTION"]
SUPPORTED_PRIORITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE"]
SUPPORTED_CONFIDENCE_LEVELS = ["LOW", "MEDIUM", "HIGH"]
ACTION_PRECEDENCE = {"EXIT_TO_SGOV": 0, "REALLOCATE": 1, "INCREASE": 2, "REINVEST": 3, "HOLD": 4, "WATCH": 5, "NO_ACTION": 6}
STRATEGY_WEIGHTS = {"portfolio_health_score": 25, "portfolio_intelligence_score": 20, "portfolio_forecast_score": 15, "average_conviction_score": 15, "average_opportunity_score": 15, "cash_reserve_health_score": 10}
SAFETY_GUARANTEES = [
    "paper_trade_mode is enforced as True",
    "live_trading_enabled is enforced as False",
    "broker_execution_enabled is enforced as False",
    "reporting_only is enforced as True",
    "no brokerage execution",
    "no Robinhood execution",
    "no live trading",
    "no order placement",
]
INPUT_FILES = [
    "daily_portfolio_command_center.json",
    "portfolio_lifecycle_report.json",
    "portfolio_rebalance_report.json",
    "income_reinvestment_report.json",
    "portfolio_health_report.json",
    "portfolio_intelligence_report.json",
    "portfolio_forecast_report.json",
]
ACTION_FIELDS = ["symbol", "action", "priority", "score", "source_engine", "reason", "review_required"]
REPORT_REQUIRED_FIELDS = [
    "module_name", "module_version", "schema_version", "generated_by", "generated_at_utc",
    "paper_trade_mode", "live_trading_enabled", "broker_execution_enabled", "reporting_only",
    "strategy_objective", "strategy_score", "strategy_grade", "confidence", "confidence_level",
    "strategy_weights", "available_input_files", "missing_input_files", "final_actions", "action_count",
    "executive_recommendation", "conflicts_resolved", "warnings", "errors", "safety_guarantees",
]

@dataclass(frozen=True)
class MasterStrategyAction:
    symbol: str
    action: str = "NO_ACTION"
    priority: str = "NONE"
    score: float = 0.0
    source_engine: str = "deterministic_fallback"
    reason: List[str] = field(default_factory=list)
    review_required: bool = True

@dataclass(frozen=True)
class MasterPortfolioStrategyReport:
    module_name: str
    module_version: str
    schema_version: str
    generated_by: str
    generated_at_utc: str
    paper_trade_mode: bool
    live_trading_enabled: bool
    broker_execution_enabled: bool
    reporting_only: bool
    strategy_objective: str
    strategy_score: float
    strategy_grade: str
    confidence: float
    confidence_level: str
    strategy_weights: Dict[str, float]
    available_input_files: List[str]
    missing_input_files: List[str]
    final_actions: List[Dict[str, Any]]
    action_count: int
    executive_recommendation: str
    conflicts_resolved: List[str]
    warnings: List[str]
    errors: List[str]
    safety_guarantees: List[str]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _number(value: Any, default: float = 0.0) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else default


def _score(value: Any) -> float:
    return max(0.0, min(100.0, _number(value)))


def _symbol(value: Any) -> str:
    return value.strip().upper() if isinstance(value, str) and value.strip() else "UNKNOWN"


def calculate_strategy_score(metrics: Mapping[str, Any], weights: Mapping[str, Any] = STRATEGY_WEIGHTS) -> float:
    if not isinstance(metrics, Mapping) or not isinstance(weights, Mapping):
        raise ValueError("metrics and weights must be mappings")
    if set(weights) != set(STRATEGY_WEIGHTS) or abs(sum(float(v) for v in weights.values()) - 100.0) > 1e-9:
        raise ValueError("strategy weights must match approved keys and total 100")
    return round(sum(_score(metrics.get(name, 0.0)) * float(weight) / 100.0 for name, weight in weights.items()), 2)


def classify_strategy_grade(score: Any) -> str:
    value = _score(score)
    if value >= 90: return "A"
    if value >= 80: return "B"
    if value >= 70: return "C"
    if value >= 60: return "D"
    if value >= 50: return "E"
    return "F"


def classify_confidence(value: Any) -> str:
    number = max(0.0, min(1.0, _number(value)))
    if number >= 0.75: return "HIGH"
    if number >= 0.40: return "MEDIUM"
    return "LOW"


def resolve_action_conflicts(actions: Iterable[Mapping[str, Any]]) -> tuple[List[Dict[str, Any]], List[str]]:
    winners: Dict[str, Dict[str, Any]] = {}
    conflicts: List[str] = []
    for raw in actions:
        if not isinstance(raw, Mapping):
            continue
        symbol = _symbol(raw.get("symbol"))
        action = raw.get("action", "NO_ACTION")
        if action not in SUPPORTED_ACTIONS:
            action = "NO_ACTION"
        normalized = asdict(MasterStrategyAction(
            symbol=symbol,
            action=action,
            priority=raw.get("priority", "NONE") if raw.get("priority", "NONE") in SUPPORTED_PRIORITIES else "NONE",
            score=_score(raw.get("score", 0.0)),
            source_engine=str(raw.get("source_engine", "unknown")),
            reason=[x for x in raw.get("reason", []) if isinstance(x, str) and x.strip()] if isinstance(raw.get("reason", []), list) else [],
            review_required=True,
        ))
        previous = winners.get(symbol)
        if previous is None:
            winners[symbol] = normalized
        elif ACTION_PRECEDENCE[normalized["action"]] < ACTION_PRECEDENCE[previous["action"]]:
            conflicts.append(f"{symbol}: {normalized['action']} overrode {previous['action']} by precedence.")
            winners[symbol] = normalized
        else:
            conflicts.append(f"{symbol}: retained {previous['action']} over {normalized['action']} by precedence.")
    final_actions = sorted(winners.values(), key=lambda row: (ACTION_PRECEDENCE[row["action"]], -row["score"], row["symbol"]))
    return final_actions, conflicts


def build_master_portfolio_strategy_report(
    metrics: Mapping[str, Any] | None = None,
    proposed_actions: Iterable[Mapping[str, Any]] | None = None,
    root_path: str = ".",
) -> Dict[str, Any]:
    root = Path(root_path)
    available = [name for name in INPUT_FILES if (root / name).exists()]
    missing = [name for name in INPUT_FILES if name not in available]
    metrics = dict(metrics or {})
    score = calculate_strategy_score(metrics)
    confidence = max(0.0, min(1.0, _number(metrics.get("confidence", 0.0))))
    actions, conflicts = resolve_action_conflicts(list(proposed_actions or []))
    warnings = []
    if missing:
        warnings.append("One or more optional engine output files are missing.")
    if not actions:
        warnings.append("No proposed actions supplied; generated valid no-action strategy report.")
    recommendation = "Maintain paper-only monitoring."
    if any(a["action"] == "EXIT_TO_SGOV" for a in actions):
        recommendation = "Review exit signals and stage released capital in SGOV."
    elif any(a["action"] == "REALLOCATE" for a in actions):
        recommendation = "Review approved merit-based reallocations."
    elif any(a["action"] == "INCREASE" for a in actions):
        recommendation = "Direct eligible excess cash toward the strongest approved opportunities."
    payload = asdict(MasterPortfolioStrategyReport(
        module_name=MODULE_NAME,
        module_version=MODULE_VERSION,
        schema_version=SCHEMA_VERSION,
        generated_by=GENERATED_BY,
        generated_at_utc=_utc_now(),
        paper_trade_mode=True,
        live_trading_enabled=False,
        broker_execution_enabled=False,
        reporting_only=True,
        strategy_objective="BALANCED_INCOME_AND_GROWTH",
        strategy_score=score,
        strategy_grade=classify_strategy_grade(score),
        confidence=confidence,
        confidence_level=classify_confidence(confidence),
        strategy_weights=dict(STRATEGY_WEIGHTS),
        available_input_files=available,
        missing_input_files=missing,
        final_actions=actions,
        action_count=len(actions),
        executive_recommendation=recommendation,
        conflicts_resolved=conflicts,
        warnings=warnings,
        errors=[],
        safety_guarantees=list(SAFETY_GUARANTEES),
    ))
    validate_master_portfolio_strategy_report(payload)
    return payload


def validate_master_portfolio_strategy_report(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    for field_name in REPORT_REQUIRED_FIELDS:
        if field_name not in payload:
            raise ValueError(f"missing required field: {field_name}")
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
    for key, value in expected.items():
        if payload[key] != value:
            raise ValueError(f"{key} must be {value!r}")
    if payload["strategy_grade"] not in list("ABCDEF"):
        raise ValueError("strategy_grade must be A through F")
    if payload["confidence_level"] not in SUPPORTED_CONFIDENCE_LEVELS:
        raise ValueError("unsupported confidence level")
    if payload["strategy_weights"] != STRATEGY_WEIGHTS:
        raise ValueError("strategy_weights must match approved weights")
    if payload["action_count"] != len(payload["final_actions"]):
        raise ValueError("action_count mismatch")
    for list_name in ["available_input_files", "missing_input_files", "final_actions", "conflicts_resolved", "warnings", "errors", "safety_guarantees"]:
        if not isinstance(payload[list_name], list):
            raise ValueError(f"{list_name} must be a list")
    for action in payload["final_actions"]:
        for field_name in ACTION_FIELDS:
            if field_name not in action:
                raise ValueError(f"action missing field: {field_name}")
        if action["action"] not in SUPPORTED_ACTIONS:
            raise ValueError("unsupported action")
        if action["priority"] not in SUPPORTED_PRIORITIES:
            raise ValueError("unsupported priority")
    return True


def write_master_portfolio_strategy_report_json(path: str = "master_portfolio_strategy_report.json") -> Dict[str, Any]:
    payload = build_master_portfolio_strategy_report()
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_master_portfolio_strategy_report_json(path: str = "master_portfolio_strategy_report.json") -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_master_portfolio_strategy_report(payload)
    return payload


def write_master_portfolio_strategy_report_csv(path: str = "master_portfolio_strategy_report.csv") -> Dict[str, Any]:
    payload = build_master_portfolio_strategy_report()
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ACTION_FIELDS)
        writer.writeheader()
        for action in payload["final_actions"]:
            writer.writerow({field_name: action.get(field_name, "") for field_name in ACTION_FIELDS})
    return payload


def format_master_portfolio_strategy_report_markdown(payload: Mapping[str, Any]) -> str:
    validate_master_portfolio_strategy_report(payload)
    lines = [
        "# Master Portfolio Strategy Report",
        "",
        f"- Strategy Score: {payload['strategy_score']}",
        f"- Strategy Grade: {payload['strategy_grade']}",
        f"- Confidence Level: {payload['confidence_level']}",
        f"- Executive Recommendation: {payload['executive_recommendation']}",
        "",
        "## Final Actions",
        "",
        "| Symbol | Action | Priority | Score | Source |",
        "|---|---|---|---:|---|",
    ]
    for action in payload["final_actions"]:
        lines.append(f"| {action['symbol']} | {action['action']} | {action['priority']} | {action['score']} | {action['source_engine']} |")
    if not payload["final_actions"]:
        lines.append("| None | NO_ACTION | NONE | 0 | deterministic_fallback |")
    lines += ["", "## Conflicts Resolved"] + [f"- {item}" for item in payload["conflicts_resolved"] or ["None"]]
    lines += ["", "## Safety Guarantees"] + [f"- {item}" for item in payload["safety_guarantees"]]
    return "\n".join(lines) + "\n"


def write_master_portfolio_strategy_report_markdown(path: str = "master_portfolio_strategy_report.md") -> Dict[str, Any]:
    payload = build_master_portfolio_strategy_report()
    Path(path).write_text(format_master_portfolio_strategy_report_markdown(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    write_master_portfolio_strategy_report_json()
    write_master_portfolio_strategy_report_csv()
    write_master_portfolio_strategy_report_markdown()
