"""Opportunity Replacement Manager for the paper-only Trade Dividend Bot.

Determines whether a challenger has earned the right to replace a current
allocation. The manager is opportunity-driven and sector-neutral. Sector data
may inform evidence and risk, but never creates a capital entitlement.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

MODULE_NAME = "opportunity_replacement_manager"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

DEFAULT_OUTPUT_FILES = {
    "json": "opportunity_replacement.json",
    "markdown": "opportunity_replacement.md",
    "html": "opportunity_replacement.html",
}

VALID_RECOMMENDATIONS = {
    "KEEP_CURRENT",
    "WAIT_FOR_PERSISTENCE",
    "PREPARE_REPLACEMENT",
    "REPLACE_CURRENT",
    "PARK_CURRENT_IN_SGOV",
    "NO_QUALIFIED_CHALLENGER",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _clamp(value: Any) -> float:
    return round(max(0.0, min(100.0, _number(value))), 4)


def _title(value: Any) -> str:
    return str(value or "UNKNOWN").replace("_", " ").title()


def _confidence_label(score: float) -> str:
    if score >= 90:
        return "VERY_HIGH"
    if score >= 75:
        return "HIGH"
    if score >= 60:
        return "MODERATE"
    return "LOW"


def _replacement_strength(score_gap: float, persistence_days: int, confidence: float) -> str:
    if score_gap >= 12 and persistence_days >= 7 and confidence >= 85:
        return "VERY_STRONG"
    if score_gap >= 8 and persistence_days >= 5 and confidence >= 75:
        return "STRONG"
    if score_gap >= 5 and persistence_days >= 3 and confidence >= 70:
        return "MODERATE"
    return "WEAK"


def build_opportunity_replacement(
    *,
    current_candidate_id: str,
    challenger_candidate_id: str = "",
    current_capital_efficiency_score: float = 0.0,
    challenger_capital_efficiency_score: float = 0.0,
    decision_stability_score: float = 0.0,
    decision_stability_label: str = "UNKNOWN",
    change_allowed_by_stability: bool = False,
    evidence_confidence: float = 100.0,
    challenger_persistence_days: int = 0,
    minimum_score_improvement: float = 5.0,
    minimum_persistence_days: int = 3,
    challenger_qualified: bool = True,
    investment_policy_compliant: bool = True,
    current_lifecycle_state: str = "ACTIVE",
    current_replacement_eligible: bool = True,
    current_earnings_lock: bool = False,
    current_hard_risk_breach: bool = False,
    current_sale_signal: bool = False,
    invalid_market_data: bool = False,
    challenger_event_risk: bool = False,
    challenger_stale_data: bool = False,
    same_underlying_concentration: bool = False,
    sector_context_current: str = "UNKNOWN",
    sector_context_challenger: str = "UNKNOWN",
) -> dict[str, Any]:
    """Build one replacement decision without placing or simulating an order."""
    current = str(current_candidate_id or "").strip().upper()
    if not current:
        raise ValueError("current_candidate_id is required")

    challenger = str(challenger_candidate_id or "").strip().upper()
    current_score = _number(current_capital_efficiency_score)
    challenger_score = _number(challenger_capital_efficiency_score)
    score_gap = round(challenger_score - current_score, 4) if challenger else None
    confidence = _clamp(evidence_confidence)
    confidence_label = _confidence_label(confidence)
    persistence_days = max(0, int(_number(challenger_persistence_days)))
    minimum_gap = max(0.0, _number(minimum_score_improvement, 5.0))
    minimum_days = max(0, int(_number(minimum_persistence_days, 3)))

    gates: dict[str, bool] = {
        "challenger_present": bool(challenger),
        "challenger_qualified": bool(challenger and challenger_qualified),
        "investment_policy_compliant": bool(investment_policy_compliant),
        "evidence_confidence_sufficient": confidence >= 70.0,
        "score_improvement_sufficient": bool(challenger and score_gap is not None and score_gap >= minimum_gap),
        "persistence_sufficient": persistence_days >= minimum_days,
        "decision_stability_allows_change": bool(change_allowed_by_stability),
        "current_replacement_eligible": bool(current_replacement_eligible),
        "challenger_event_risk_clear": not bool(challenger_event_risk),
        "challenger_data_fresh": not bool(challenger_stale_data),
        "concentration_risk_clear": not bool(same_underlying_concentration),
        "market_data_valid": not bool(invalid_market_data),
    }

    protection_reason: Optional[str] = None
    if current_earnings_lock:
        protection_reason = "EARNINGS_LOCK"
    elif current_hard_risk_breach:
        protection_reason = "HARD_RISK_BREACH"
    elif invalid_market_data:
        protection_reason = "INVALID_MARKET_DATA"
    elif current_sale_signal:
        protection_reason = "CONFIRMED_SALE_SIGNAL"

    if protection_reason in {"EARNINGS_LOCK", "HARD_RISK_BREACH", "INVALID_MARKET_DATA"}:
        recommendation = "PARK_CURRENT_IN_SGOV"
        decision_reason = protection_reason
    elif not challenger:
        recommendation = "NO_QUALIFIED_CHALLENGER"
        decision_reason = "NO_CHALLENGER_AVAILABLE"
    elif not challenger_qualified or not investment_policy_compliant:
        recommendation = "KEEP_CURRENT"
        decision_reason = "CHALLENGER_NOT_QUALIFIED"
    elif current_sale_signal:
        if all(
            gates[name]
            for name in (
                "evidence_confidence_sufficient",
                "challenger_event_risk_clear",
                "challenger_data_fresh",
                "concentration_risk_clear",
            )
        ):
            recommendation = "PREPARE_REPLACEMENT"
            decision_reason = "SALE_SIGNAL_REQUIRES_REPLACEMENT_REVIEW"
        else:
            recommendation = "PARK_CURRENT_IN_SGOV"
            decision_reason = "SALE_SIGNAL_WITHOUT_SAFE_REPLACEMENT"
    else:
        required = (
            "challenger_qualified",
            "investment_policy_compliant",
            "evidence_confidence_sufficient",
            "score_improvement_sufficient",
            "persistence_sufficient",
            "decision_stability_allows_change",
            "current_replacement_eligible",
            "challenger_event_risk_clear",
            "challenger_data_fresh",
            "concentration_risk_clear",
            "market_data_valid",
        )
        passed = all(gates[name] for name in required)
        if passed:
            recommendation = "REPLACE_CURRENT"
            decision_reason = "CHALLENGER_EARNED_REPLACEMENT"
        elif gates["score_improvement_sufficient"] and not gates["persistence_sufficient"]:
            recommendation = "WAIT_FOR_PERSISTENCE"
            decision_reason = "IMPROVEMENT_NOT_YET_PERSISTENT"
        elif gates["score_improvement_sufficient"] and not gates["decision_stability_allows_change"]:
            recommendation = "WAIT_FOR_PERSISTENCE"
            decision_reason = "DECISION_STABILITY_BLOCKS_CHANGE"
        else:
            recommendation = "KEEP_CURRENT"
            decision_reason = "IMPROVEMENT_NOT_MEANINGFUL_ENOUGH"

    blockers = [name for name, passed in gates.items() if not passed]
    strength = _replacement_strength(score_gap or 0.0, persistence_days, confidence)

    if recommendation == "REPLACE_CURRENT":
        explanation = (
            f"Replace {current} with {challenger}. The challenger has maintained a "
            f"{score_gap:.2f}-point Capital Efficiency Score advantage for {persistence_days} days, "
            "has sufficient Evidence Confidence, satisfies the Investment Policy, and has passed "
            "the Decision Stability replacement gate. The improvement is meaningful enough to justify Portfolio Turnover."
        )
    elif recommendation == "WAIT_FOR_PERSISTENCE":
        explanation = (
            f"Continue holding {current} while monitoring {challenger}. The challenger currently leads by "
            f"{(score_gap or 0.0):.2f} Capital Efficiency Score points, but the improvement has not yet passed "
            "all persistence and Decision Stability requirements. Waiting protects the portfolio from unnecessary churn."
        )
    elif recommendation == "PARK_CURRENT_IN_SGOV":
        explanation = (
            f"Move the affected {current} paper allocation to SGOV because {decision_reason.replace('_', ' ').lower()}. "
            "Capital remains protected until the condition clears and the strongest qualified opportunity is re-evaluated."
        )
    elif recommendation == "PREPARE_REPLACEMENT":
        explanation = (
            f"Prepare to replace {current}. A confirmed sale condition is active, and {challenger} is the strongest "
            "qualified alternative currently available. Final entry and lifecycle checks must still pass before capital is reassigned."
        )
    elif recommendation == "NO_QUALIFIED_CHALLENGER":
        explanation = (
            f"Continue holding {current}. No qualified challenger is currently available, and no mandatory protection rule requires a change."
        )
    else:
        explanation = (
            f"Continue holding {current}. Although {challenger or 'another opportunity'} may be under review, it has not demonstrated "
            "a sufficiently large, persistent, stable, and policy-compliant improvement to earn replacement."
        )

    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "reporting_only": True,
        "current_candidate_id": current,
        "challenger_candidate_id": challenger or None,
        "current_capital_efficiency_score": round(current_score, 4),
        "challenger_capital_efficiency_score": round(challenger_score, 4) if challenger else None,
        "capital_efficiency_score_difference": score_gap,
        "decision_stability_score": _clamp(decision_stability_score),
        "decision_stability_label": str(decision_stability_label or "UNKNOWN").upper(),
        "evidence_confidence_score": confidence,
        "evidence_confidence_label": confidence_label,
        "challenger_persistence_days": persistence_days,
        "minimum_score_improvement": minimum_gap,
        "minimum_persistence_days": minimum_days,
        "current_lifecycle_state": str(current_lifecycle_state or "UNKNOWN").upper(),
        "sector_context_current": str(sector_context_current or "UNKNOWN").upper(),
        "sector_context_challenger": str(sector_context_challenger or "UNKNOWN").upper(),
        "sector_allocation_entitlement_used": False,
        "replacement_gates": gates,
        "replacement_blockers": blockers,
        "replacement_strength": strength,
        "protection_reason": protection_reason,
        "recommendation": recommendation,
        "decision_reason": decision_reason,
        "natural_explanation": explanation,
        "investor_override_available": True,
        "warnings": [],
        "errors": [],
    }


def format_opportunity_replacement_markdown(report: Mapping[str, Any]) -> str:
    current = str(report.get("current_candidate_id", "UNKNOWN"))
    challenger = str(report.get("challenger_candidate_id") or "No qualified challenger")
    gap = report.get("capital_efficiency_score_difference")
    gap_text = "Not available" if gap is None else f"{_number(gap):+.2f}"
    gates = dict(report.get("replacement_gates") or {})

    lines = [
        "# Opportunity Replacement Review",
        "",
        "## Recommendation",
        "",
        f"**{_title(report.get('recommendation'))}**",
        "",
        str(report.get("natural_explanation", "No explanation available.")),
        "",
        "## Compare Current and Challenger",
        "",
        "| Metric | Current | Challenger |",
        "|---|---:|---:|",
        f"| Investment | {current} | {challenger} |",
        f"| Capital Efficiency Score | {_number(report.get('current_capital_efficiency_score')):.2f} | "
        f"{('Not available' if report.get('challenger_capital_efficiency_score') is None else f'{_number(report.get("challenger_capital_efficiency_score")):.2f}')} |",
        f"| Score Difference | — | {gap_text} |",
        f"| Decision Stability Score | {_number(report.get('decision_stability_score')):.2f} / 100 | Must authorize change |",
        f"| Evidence Confidence | {_title(report.get('evidence_confidence_label'))} | Same evidence standard |",
        f"| Sector Context | {_title(report.get('sector_context_current'))} | {_title(report.get('sector_context_challenger'))} |",
        "",
        "## Replacement Gates",
        "",
    ]
    for name, passed in gates.items():
        lines.append(f"- **{_title(name)}:** {'Passed' if passed else 'Not passed'}")
    lines.extend(
        [
            "",
            "## Replacement Strength",
            "",
            f"**{_title(report.get('replacement_strength'))}**",
            "",
            "Sector context is supporting evidence only. No sector receives guaranteed capital.",
            "",
            "## Paper-Only Safety",
            "",
            "This report is advisory and paper-only. It does not place orders or communicate with a brokerage.",
            "",
        ]
    )
    return "\n".join(lines)


def _html_from_markdown(markdown: str) -> str:
    escaped = (
        markdown.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return (
        "<!doctype html><html><head><meta charset='utf-8'><title>Opportunity Replacement Review</title>"
        "<style>body{font-family:Arial,sans-serif;margin:2rem;line-height:1.5;background:#f4f6f8;}"
        "pre{white-space:pre-wrap;background:white;padding:1.5rem;border-radius:10px;}</style></head>"
        f"<body><pre>{escaped}</pre></body></html>"
    )


def write_opportunity_replacement(
    payload: Mapping[str, Any],
    root_path: str = ".",
    output_files: Optional[Mapping[str, str]] = None,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    report = build_opportunity_replacement(**dict(payload))
    root = Path(root_path)
    files = dict(DEFAULT_OUTPUT_FILES)
    if output_files:
        files.update(output_files)
    markdown = format_opportunity_replacement_markdown(report)
    (root / files["json"]).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / files["markdown"]).write_text(markdown, encoding="utf-8")
    (root / files["html"]).write_text(_html_from_markdown(markdown), encoding="utf-8")
    return report


def build_and_write_opportunity_replacement(
    payload: Mapping[str, Any],
    root_path: str = ".",
    output_files: Optional[Mapping[str, str]] = None,
) -> dict[str, Any]:
    return write_opportunity_replacement(payload, root_path=root_path, output_files=output_files)


if __name__ == "__main__":
    sample = {
        "current_candidate_id": "AMDW + PLTU",
        "challenger_candidate_id": "AMDW + GGLL",
        "current_capital_efficiency_score": 84.3,
        "challenger_capital_efficiency_score": 93.1,
        "decision_stability_score": 78.0,
        "decision_stability_label": "STABLE",
        "change_allowed_by_stability": True,
        "evidence_confidence": 92.0,
        "challenger_persistence_days": 7,
        "minimum_score_improvement": 5.0,
        "minimum_persistence_days": 3,
        "challenger_qualified": True,
        "investment_policy_compliant": True,
        "current_lifecycle_state": "ACTIVE",
        "current_replacement_eligible": True,
        "sector_context_current": "TECHNOLOGY",
        "sector_context_challenger": "TECHNOLOGY",
    }
    result = write_opportunity_replacement(sample)
    print(f"Opportunity Replacement Recommendation: {result['recommendation']}")
