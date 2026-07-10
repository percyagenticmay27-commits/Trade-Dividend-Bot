"""
Strategy Learning Engine for the Dividend Bot.

Analyzes historical strategy outcomes and produces semi-adaptive improvement
proposals. Recommendations are advisory only and require explicit user approval
before becoming permanent. No production weights or thresholds are modified.
"""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

MODULE_NAME = "strategy_learning_engine"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"
BOT_NAME = "Agentic Robin Dividend Bot"
BOT_TYPE = "paper_dividend_etf_management"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True
LEARNING_MODE = "SEMI_ADAPTIVE"
APPROVAL_REQUIRED = True

MIN_COMPLETED_OPPORTUNITIES = 30
MIN_HISTORY_MONTHS = 6
MIN_OBSERVATIONS_PER_STRATEGY = 10

SUPPORTED_STATUSES = ["OBSERVATION_ONLY", "ELIGIBLE_FOR_REVIEW", "WAITING_FOR_APPROVAL", "APPROVED", "REJECTED"]
SUPPORTED_PROPOSAL_TYPES = ["WEIGHT_ADJUSTMENT", "THRESHOLD_ADJUSTMENT", "STRATEGY_PREFERENCE", "RISK_CONTROL", "NO_CHANGE"]
SUPPORTED_METRICS = [
    "total_return_pct",
    "income_growth_pct",
    "monthly_income",
    "max_drawdown_pct",
    "recovery_days",
    "volatility_score",
    "win_rate_pct",
    "tax_efficiency_score",
    "capital_efficiency_score",
    "self_funding_score",
]

SAFETY_GUARANTEES = [
    "paper_trade_mode is enforced as True",
    "live_trading_enabled is enforced as False",
    "broker_execution_enabled is enforced as False",
    "reporting_only is enforced as True",
    "learning proposals never modify production rules automatically",
    "explicit approval is required before permanent changes",
    "no Robinhood or broker execution is performed",
]

REPORT_REQUIRED_FIELDS = [
    "bot_name", "bot_type", "module_name", "module_version", "schema_version",
    "generated_by", "generated_at_utc", "paper_trade_mode", "live_trading_enabled",
    "broker_execution_enabled", "reporting_only", "learning_mode", "approval_required",
    "minimum_evidence", "evidence_summary", "strategy_summaries", "learning_proposals",
    "proposal_count", "learning_status", "warnings", "errors", "safety_guarantees",
]

PROPOSAL_FIELDS = [
    "proposal_id", "proposal_type", "target", "current_value", "proposed_value",
    "estimated_impact_pct", "evidence_count", "evidence_summary", "status",
    "requires_approval", "approved_by", "approved_at_utc",
]


@dataclass(frozen=True)
class StrategyObservation:
    strategy_name: str
    completed: bool = True
    total_return_pct: float = 0.0
    income_growth_pct: float = 0.0
    monthly_income: float = 0.0
    max_drawdown_pct: float = 0.0
    recovery_days: float = 0.0
    volatility_score: float = 0.0
    win: bool = False
    tax_efficiency_score: float = 0.0
    capital_efficiency_score: float = 0.0
    self_funding_score: float = 0.0


@dataclass(frozen=True)
class LearningProposal:
    proposal_id: str
    proposal_type: str
    target: str
    current_value: float
    proposed_value: float
    estimated_impact_pct: float
    evidence_count: int
    evidence_summary: str
    status: str = "WAITING_FOR_APPROVAL"
    requires_approval: bool = True
    approved_by: str = ""
    approved_at_utc: str = ""


@dataclass(frozen=True)
class StrategyLearningReport:
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
    learning_mode: str
    approval_required: bool
    minimum_evidence: Dict[str, int]
    evidence_summary: Dict[str, Any]
    strategy_summaries: List[Dict[str, Any]]
    learning_proposals: List[Dict[str, Any]]
    proposal_count: int
    learning_status: str
    warnings: List[str]
    errors: List[str]
    safety_guarantees: List[str]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value)


def _normalize_observation(raw: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("observation must be a mapping")
    strategy_name = raw.get("strategy_name", "UNKNOWN")
    if not isinstance(strategy_name, str) or not strategy_name.strip():
        strategy_name = "UNKNOWN"
    return {
        "strategy_name": strategy_name.strip().upper(),
        "completed": bool(raw.get("completed", True)),
        "total_return_pct": _number(raw.get("total_return_pct", 0.0)),
        "income_growth_pct": _number(raw.get("income_growth_pct", 0.0)),
        "monthly_income": max(0.0, _number(raw.get("monthly_income", 0.0))),
        "max_drawdown_pct": max(0.0, _number(raw.get("max_drawdown_pct", 0.0))),
        "recovery_days": max(0.0, _number(raw.get("recovery_days", 0.0))),
        "volatility_score": max(0.0, min(100.0, _number(raw.get("volatility_score", 0.0)))),
        "win": bool(raw.get("win", False)),
        "tax_efficiency_score": max(0.0, min(100.0, _number(raw.get("tax_efficiency_score", 0.0)))),
        "capital_efficiency_score": max(0.0, min(100.0, _number(raw.get("capital_efficiency_score", 0.0)))),
        "self_funding_score": max(0.0, min(100.0, _number(raw.get("self_funding_score", 0.0)))),
    }


def summarize_strategies(observations: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for raw in observations:
        item = _normalize_observation(raw)
        if not item["completed"]:
            continue
        grouped.setdefault(item["strategy_name"], []).append(item)

    summaries: List[Dict[str, Any]] = []
    for strategy_name, rows in grouped.items():
        count = len(rows)
        avg_return = sum(r["total_return_pct"] for r in rows) / count
        avg_income_growth = sum(r["income_growth_pct"] for r in rows) / count
        avg_drawdown = sum(r["max_drawdown_pct"] for r in rows) / count
        avg_recovery = sum(r["recovery_days"] for r in rows) / count
        win_rate = 100.0 * sum(1 for r in rows if r["win"]) / count
        avg_self_funding = sum(r["self_funding_score"] for r in rows) / count
        score = (
            avg_return * 0.45
            + avg_income_growth * 0.20
            + win_rate * 0.15
            + avg_self_funding * 0.10
            + max(0.0, 100.0 - avg_drawdown) * 0.10
        )
        summaries.append({
            "strategy_name": strategy_name,
            "observation_count": count,
            "average_total_return_pct": round(avg_return, 2),
            "average_income_growth_pct": round(avg_income_growth, 2),
            "average_max_drawdown_pct": round(avg_drawdown, 2),
            "average_recovery_days": round(avg_recovery, 2),
            "win_rate_pct": round(win_rate, 2),
            "average_self_funding_score": round(avg_self_funding, 2),
            "learning_score": round(score, 2),
        })
    summaries.sort(key=lambda item: (-item["learning_score"], item["strategy_name"]))
    return summaries


def evidence_is_sufficient(completed_opportunities: int, history_months: int, strategy_summaries: Iterable[Mapping[str, Any]]) -> bool:
    if completed_opportunities < MIN_COMPLETED_OPPORTUNITIES or history_months < MIN_HISTORY_MONTHS:
        return False
    summaries = list(strategy_summaries)
    return bool(summaries) and all(int(item.get("observation_count", 0)) >= MIN_OBSERVATIONS_PER_STRATEGY for item in summaries)


def generate_learning_proposals(strategy_summaries: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    summaries = list(strategy_summaries)
    if not summaries:
        return []
    proposals: List[Dict[str, Any]] = []
    best = summaries[0]
    worst = summaries[-1]

    if len(summaries) > 1 and best["learning_score"] >= worst["learning_score"] + 5.0:
        proposals.append(asdict(LearningProposal(
            proposal_id="SL-001",
            proposal_type="STRATEGY_PREFERENCE",
            target=best["strategy_name"],
            current_value=0.0,
            proposed_value=5.0,
            estimated_impact_pct=round((best["learning_score"] - worst["learning_score"]) / 10.0, 2),
            evidence_count=int(best["observation_count"]),
            evidence_summary=f"{best['strategy_name']} leads {worst['strategy_name']} by {round(best['learning_score'] - worst['learning_score'], 2)} learning-score points.",
        )))

    if best["average_max_drawdown_pct"] > 20.0:
        proposals.append(asdict(LearningProposal(
            proposal_id="SL-002",
            proposal_type="RISK_CONTROL",
            target="maximum_position_size",
            current_value=1.0,
            proposed_value=0.9,
            estimated_impact_pct=1.0,
            evidence_count=int(best["observation_count"]),
            evidence_summary="Leading strategy still shows elevated average drawdown; consider a 10% position-size reduction during similar regimes.",
        )))

    if best["average_total_return_pct"] > 0 and best["average_self_funding_score"] >= 70:
        proposals.append(asdict(LearningProposal(
            proposal_id="SL-003",
            proposal_type="WEIGHT_ADJUSTMENT",
            target="self_funding_score_weight",
            current_value=10.0,
            proposed_value=12.0,
            estimated_impact_pct=0.5,
            evidence_count=int(best["observation_count"]),
            evidence_summary="High-return observations also show strong self-funding performance; consider a small weight increase.",
        )))

    if not proposals:
        proposals.append(asdict(LearningProposal(
            proposal_id="SL-000",
            proposal_type="NO_CHANGE",
            target="strategy_rules",
            current_value=0.0,
            proposed_value=0.0,
            estimated_impact_pct=0.0,
            evidence_count=sum(int(item["observation_count"]) for item in summaries),
            evidence_summary="No material improvement proposal is supported by the available evidence.",
        )))
    return proposals


def approve_learning_proposal(proposal: Mapping[str, Any], approved_by: str, approved_at_utc: str | None = None) -> Dict[str, Any]:
    if not isinstance(proposal, Mapping):
        raise ValueError("proposal must be a mapping")
    if not isinstance(approved_by, str) or not approved_by.strip():
        raise ValueError("approved_by must be a non-empty string")
    result = dict(proposal)
    for field in PROPOSAL_FIELDS:
        if field not in result:
            raise ValueError(f"proposal missing required field: {field}")
    result["status"] = "APPROVED"
    result["approved_by"] = approved_by.strip()
    result["approved_at_utc"] = approved_at_utc or _utc_now()
    return result


def build_strategy_learning_report(
    observations: Iterable[Mapping[str, Any]] | None = None,
    history_months: int = 0,
) -> Dict[str, Any]:
    rows = list(observations or [])
    summaries = summarize_strategies(rows)
    completed = sum(1 for row in rows if bool(row.get("completed", True)))
    sufficient = evidence_is_sufficient(completed, int(history_months), summaries)
    proposals = generate_learning_proposals(summaries) if sufficient else []
    status = "ELIGIBLE_FOR_REVIEW" if sufficient else "OBSERVATION_ONLY"
    warnings: List[str] = []
    if not sufficient:
        warnings.append("Minimum evidence requirements have not been met; learning remains observation-only.")
    payload = asdict(StrategyLearningReport(
        bot_name=BOT_NAME,
        bot_type=BOT_TYPE,
        module_name=MODULE_NAME,
        module_version=MODULE_VERSION,
        schema_version=SCHEMA_VERSION,
        generated_by=GENERATED_BY,
        generated_at_utc=_utc_now(),
        paper_trade_mode=True,
        live_trading_enabled=False,
        broker_execution_enabled=False,
        reporting_only=True,
        learning_mode=LEARNING_MODE,
        approval_required=True,
        minimum_evidence={
            "completed_opportunities": MIN_COMPLETED_OPPORTUNITIES,
            "history_months": MIN_HISTORY_MONTHS,
            "observations_per_strategy": MIN_OBSERVATIONS_PER_STRATEGY,
        },
        evidence_summary={
            "completed_opportunities": completed,
            "history_months": int(history_months),
            "strategy_count": len(summaries),
            "evidence_sufficient": sufficient,
        },
        strategy_summaries=summaries,
        learning_proposals=proposals,
        proposal_count=len(proposals),
        learning_status=status,
        warnings=warnings,
        errors=[],
        safety_guarantees=list(SAFETY_GUARANTEES),
    ))
    validate_strategy_learning_report(payload)
    return payload


def validate_strategy_learning_report(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    for field in REPORT_REQUIRED_FIELDS:
        if field not in payload:
            raise ValueError(f"missing required field: {field}")
    expected = {
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "reporting_only": True,
        "learning_mode": LEARNING_MODE,
        "approval_required": True,
    }
    for field, value in expected.items():
        if payload[field] != value:
            raise ValueError(f"{field} must be {value!r}")
    if payload["learning_status"] not in SUPPORTED_STATUSES:
        raise ValueError("unsupported learning_status")
    for list_field in ["strategy_summaries", "learning_proposals", "warnings", "errors", "safety_guarantees"]:
        if not isinstance(payload[list_field], list):
            raise ValueError(f"{list_field} must be a list")
    if payload["proposal_count"] != len(payload["learning_proposals"]):
        raise ValueError("proposal_count mismatch")
    for proposal in payload["learning_proposals"]:
        for field in PROPOSAL_FIELDS:
            if field not in proposal:
                raise ValueError(f"proposal missing required field: {field}")
        if proposal["proposal_type"] not in SUPPORTED_PROPOSAL_TYPES:
            raise ValueError("unsupported proposal_type")
        if proposal["status"] not in SUPPORTED_STATUSES:
            raise ValueError("unsupported proposal status")
        if proposal["requires_approval"] is not True:
            raise ValueError("all proposals must require approval")
    return True


def write_strategy_learning_report_json(path: str = "strategy_learning_report.json") -> Dict[str, Any]:
    payload = build_strategy_learning_report()
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_strategy_learning_report_json(path: str = "strategy_learning_report.json") -> Dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_strategy_learning_report(payload)
    return payload


def write_strategy_learning_report_csv(path: str = "strategy_learning_report.csv") -> Dict[str, Any]:
    payload = build_strategy_learning_report()
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PROPOSAL_FIELDS)
        writer.writeheader()
        for proposal in payload["learning_proposals"]:
            writer.writerow({field: proposal.get(field, "") for field in PROPOSAL_FIELDS})
    return payload


def format_strategy_learning_report_markdown(payload: Mapping[str, Any]) -> str:
    validate_strategy_learning_report(payload)
    lines = [
        "# Strategy Learning Report",
        "",
        f"- Learning Mode: {payload['learning_mode']}",
        f"- Learning Status: {payload['learning_status']}",
        f"- Approval Required: {payload['approval_required']}",
        f"- Completed Opportunities: {payload['evidence_summary']['completed_opportunities']}",
        f"- History Months: {payload['evidence_summary']['history_months']}",
        "",
        "## Strategy Summaries",
        "",
        "| Strategy | Observations | Avg Return | Win Rate | Learning Score |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in payload["strategy_summaries"]:
        lines.append(f"| {row['strategy_name']} | {row['observation_count']} | {row['average_total_return_pct']} | {row['win_rate_pct']} | {row['learning_score']} |")
    lines.extend(["", "## Learning Proposals"])
    if payload["learning_proposals"]:
        for proposal in payload["learning_proposals"]:
            lines.append(f"- **{proposal['proposal_id']}** — {proposal['proposal_type']} for `{proposal['target']}`: {proposal['evidence_summary']} Status: {proposal['status']}.")
    else:
        lines.append("- None. Evidence requirements are not yet satisfied.")
    lines.extend(["", "## Safety Guarantees"] + [f"- {item}" for item in payload["safety_guarantees"]])
    return "\n".join(lines) + "\n"


def write_strategy_learning_report_markdown(path: str = "strategy_learning_report.md") -> Dict[str, Any]:
    payload = build_strategy_learning_report()
    Path(path).write_text(format_strategy_learning_report_markdown(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    write_strategy_learning_report_json()
    write_strategy_learning_report_csv()
    write_strategy_learning_report_markdown()
