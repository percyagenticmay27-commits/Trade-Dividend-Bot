"""AI CIO Decision Engine for the Trade Dividend Bot.

Produces one final paper-portfolio instruction from the current allocation,
strongest challenger, Decision Stability result, evidence confidence,
protection rules, and Investment Policy constraints.

This module is paper-only. It never places orders or communicates with a broker.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

MODULE_NAME = "ai_cio_decision_engine"
MODULE_VERSION = "2.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

DEFAULT_OUTPUT_FILES = {
    "json": "ai_cio_decision.json",
    "markdown": "ai_cio_decision.md",
}

VALID_ACTIONS = {
    "KEEP",
    "WAIT",
    "REPLACE",
    "PARK_IN_SGOV",
    "PREPARE_REPLACEMENT",
    "REENTER",
    "INCREASE",
    "REDUCE",
}

PROTECTION_GATES = {
    "EARNINGS_LOCK",
    "HARD_RISK_BREACH",
    "CONFIRMED_SALE_SIGNAL",
    "INVALID_MARKET_DATA",
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


def _label_confidence(score: float) -> str:
    if score >= 90:
        return "VERY_HIGH"
    if score >= 75:
        return "HIGH"
    if score >= 60:
        return "MODERATE"
    return "LOW"


def _title(value: Any) -> str:
    return str(value or "UNKNOWN").replace("_", " ").title()


def _normalize_action(value: Any, default: str = "KEEP") -> str:
    action = str(value or default).strip().upper().replace(" ", "_")
    return action if action in VALID_ACTIONS else default


def _normalize_stability(stability: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    data = dict(stability or {})
    return {
        "recommended_capital_action": _normalize_action(data.get("recommended_capital_action"), "KEEP"),
        "change_allowed": bool(data.get("change_allowed", False)),
        "stability_gate": str(data.get("stability_gate", "KEEP_CURRENT")).upper(),
        "decision_stability_score": _clamp(data.get("decision_stability_score", 0.0)),
        "decision_stability_label": str(data.get("decision_stability_label", "UNKNOWN")).upper(),
        "natural_explanation": str(data.get("natural_explanation", "")).strip(),
    }


def _policy_check(
    *,
    requested_action: str,
    current_candidate_id: str,
    challenger_candidate_id: str,
    challenger_qualified: bool,
    evidence_confidence: float,
    investment_policy_compliant: bool,
    earnings_lock: bool,
    hard_risk_breach: bool,
    sale_signal: bool,
    invalid_market_data: bool,
) -> tuple[bool, list[str], list[str]]:
    passed: list[str] = []
    blocked: list[str] = []

    if investment_policy_compliant:
        passed.append("Investment Policy requirements are satisfied.")
    else:
        blocked.append("The proposed action does not satisfy the approved Investment Policy.")

    if evidence_confidence >= 70.0:
        passed.append("Evidence Confidence is sufficient for a portfolio decision.")
    else:
        blocked.append("Evidence Confidence is below the threshold for a discretionary portfolio change.")

    if requested_action in {"REPLACE", "REENTER", "INCREASE"}:
        if challenger_candidate_id and challenger_qualified:
            passed.append("The proposed allocation is qualified for consideration.")
        else:
            blocked.append("No qualified replacement or entry candidate is available.")

    if current_candidate_id:
        passed.append("The current allocation is identified.")
    else:
        blocked.append("The current allocation is missing.")

    protection_active = earnings_lock or hard_risk_breach or sale_signal or invalid_market_data
    if protection_active:
        passed.append("A mandatory protection condition is active.")

    if requested_action in {"PARK_IN_SGOV", "PREPARE_REPLACEMENT", "REDUCE"} and protection_active:
        return True, passed, blocked

    return not blocked, passed, blocked


def _choose_action(
    *,
    stability: Mapping[str, Any],
    current_candidate_id: str,
    challenger_candidate_id: str,
    challenger_qualified: bool,
    evidence_confidence: float,
    investment_policy_compliant: bool,
    earnings_lock: bool,
    hard_risk_breach: bool,
    sale_signal: bool,
    invalid_market_data: bool,
    reentry_eligible: bool,
    increase_supported: bool,
    reduce_supported: bool,
) -> tuple[str, str]:
    if earnings_lock:
        return "PARK_IN_SGOV", "EARNINGS_LOCK"
    if hard_risk_breach:
        return "PARK_IN_SGOV", "HARD_RISK_BREACH"
    if invalid_market_data:
        return "PARK_IN_SGOV", "INVALID_MARKET_DATA"
    if sale_signal:
        return "PREPARE_REPLACEMENT", "CONFIRMED_SALE_SIGNAL"

    if not investment_policy_compliant:
        return "WAIT", "INVESTMENT_POLICY_BLOCK"
    if evidence_confidence < 60.0:
        return "WAIT", "LOW_ANALYSIS_CONFIDENCE"

    stability_action = _normalize_action(stability.get("recommended_capital_action"), "KEEP")
    change_allowed = bool(stability.get("change_allowed", False))

    if current_candidate_id == "SGOV" and reentry_eligible and challenger_candidate_id and challenger_qualified:
        if change_allowed or stability_action in {"REPLACE", "REENTER"}:
            return "REENTER", "REENTRY_APPROVED"
        return "WAIT", "REENTRY_WAITING_FOR_STABILITY"

    if reduce_supported:
        return "REDUCE", "RISK_REDUCTION_SUPPORTED"
    if increase_supported and evidence_confidence >= 75.0:
        return "INCREASE", "ALLOCATION_INCREASE_SUPPORTED"

    if stability_action == "REPLACE" and change_allowed and challenger_candidate_id and challenger_qualified:
        return "REPLACE", "STABILITY_AUTHORIZED_REPLACEMENT"
    if stability_action in {"WAIT", "PREPARE_REPLACEMENT"}:
        return "WAIT", "STABILITY_REQUIRES_PATIENCE"
    return "KEEP", "CURRENT_ALLOCATION_REMAINS_PREFERRED"


def _build_verdict(
    *,
    action: str,
    current: str,
    challenger: str,
    current_score: float,
    challenger_score: float,
    stability_score: float,
    stability_label: str,
    confidence_score: float,
    confidence_label: str,
    reason_code: str,
) -> str:
    improvement = challenger_score - current_score if challenger else 0.0

    if action == "PARK_IN_SGOV":
        reason = {
            "EARNINGS_LOCK": "an earnings-protection window is active",
            "HARD_RISK_BREACH": "a mandatory risk limit has been breached",
            "INVALID_MARKET_DATA": "the available market data is not reliable enough to support continued exposure",
        }.get(reason_code, "a mandatory protection rule is active")
        return (
            f"Recommendation: Move the affected {current} paper allocation to SGOV because {reason}. "
            "Capital will remain protected while the AI CIO re-evaluates the allocation. The prior investment will not be restored automatically; it must qualify again against all available opportunities."
        )

    if action == "PREPARE_REPLACEMENT":
        return (
            f"Recommendation: Prepare a replacement for {current}. A confirmed sale condition is active, so the current allocation no longer qualifies for an unrestricted hold. "
            "The affected capital should remain protected while the strongest qualified alternative is verified against the Investment Policy and entry requirements."
        )

    if action == "REPLACE":
        return (
            f"Recommendation: Replace {current} with {challenger}. The challenger has a {improvement:.2f}-point higher Capital Efficiency Score, the Decision Stability gate authorizes the change, "
            f"and Evidence Confidence is {_title(confidence_label)} ({confidence_score:.2f} / 100). The expected improvement is meaningful enough to justify the additional Portfolio Turnover."
        )

    if action == "REENTER":
        return (
            f"Recommendation: Re-enter capital from SGOV into {challenger}. The candidate has cleared its protection or waiting period, remains qualified, and now has sufficient Decision Stability and Evidence Confidence to compete for capital again."
        )

    if action == "INCREASE":
        return (
            f"Recommendation: Increase the paper allocation to {current}. The current investment remains qualified, Evidence Confidence is {_title(confidence_label)}, and the available evidence supports assigning additional capital without violating the Investment Policy."
        )

    if action == "REDUCE":
        return (
            f"Recommendation: Reduce the paper allocation to {current}. The position remains investable, but its current risk contribution is too high for the approved Investment Policy. The released capital should be redirected to SGOV or another qualified allocation."
        )

    if action == "WAIT":
        if challenger:
            return (
                f"Recommendation: Continue holding {current} while monitoring {challenger}. The challenger currently has a {improvement:.2f}-point Capital Efficiency Score advantage, "
                "but the evidence is not yet strong or persistent enough to justify changing the portfolio. Waiting avoids unnecessary Portfolio Turnover while the AI CIO confirms whether the improvement is durable."
            )
        return (
            f"Recommendation: Wait and keep the current paper allocation unchanged. The available evidence is not yet strong enough to justify a discretionary portfolio change."
        )

    if challenger and improvement > 0:
        return (
            f"Recommendation: Continue holding {current}. Although {challenger} currently has a {improvement:.2f}-point higher Capital Efficiency Score, the improvement is not large enough to justify replacing the current investment. "
            f"The current recommendation has a Decision Stability Score of {stability_score:.2f} out of 100 ({_title(stability_label)}), and Evidence Confidence is {_title(confidence_label)}. "
            "Changing today would increase Portfolio Turnover without providing a meaningful improvement in the objective of maximizing long-term Total Wealth (growth + income). The alternative will continue to be monitored automatically."
        )

    return (
        f"Recommendation: Continue holding {current}. No qualified challenger currently provides a meaningful Capital Efficiency Score advantage, and no mandatory protection rule requires a change. "
        "The current allocation remains consistent with the objective of maximizing long-term Total Wealth (growth + income) while avoiding unnecessary Portfolio Turnover."
    )


def build_ai_cio_decision(
    *,
    current_candidate_id: str,
    challenger_candidate_id: str = "",
    current_capital_efficiency_score: float = 0.0,
    challenger_capital_efficiency_score: float = 0.0,
    decision_stability: Optional[Mapping[str, Any]] = None,
    evidence_confidence: float = 100.0,
    market_regime: str = "UNKNOWN",
    challenger_qualified: bool = True,
    investment_policy_compliant: bool = True,
    earnings_lock: bool = False,
    hard_risk_breach: bool = False,
    sale_signal: bool = False,
    invalid_market_data: bool = False,
    reentry_eligible: bool = False,
    increase_supported: bool = False,
    reduce_supported: bool = False,
    autonomy_level: str = "LEVEL_1_ADVISOR",
) -> dict[str, Any]:
    """Build one final AI CIO paper-portfolio decision."""
    current = str(current_candidate_id or "").strip().upper()
    if not current:
        raise ValueError("current_candidate_id is required")

    challenger = str(challenger_candidate_id or "").strip().upper()
    current_score = _number(current_capital_efficiency_score)
    challenger_score = _number(challenger_capital_efficiency_score)
    confidence_score = _clamp(evidence_confidence)
    confidence_label = _label_confidence(confidence_score)
    stability = _normalize_stability(decision_stability)

    action, decision_reason = _choose_action(
        stability=stability,
        current_candidate_id=current,
        challenger_candidate_id=challenger,
        challenger_qualified=bool(challenger_qualified),
        evidence_confidence=confidence_score,
        investment_policy_compliant=bool(investment_policy_compliant),
        earnings_lock=bool(earnings_lock),
        hard_risk_breach=bool(hard_risk_breach),
        sale_signal=bool(sale_signal),
        invalid_market_data=bool(invalid_market_data),
        reentry_eligible=bool(reentry_eligible),
        increase_supported=bool(increase_supported),
        reduce_supported=bool(reduce_supported),
    )

    policy_allowed, passed_checks, blocked_checks = _policy_check(
        requested_action=action,
        current_candidate_id=current,
        challenger_candidate_id=challenger,
        challenger_qualified=bool(challenger_qualified),
        evidence_confidence=confidence_score,
        investment_policy_compliant=bool(investment_policy_compliant),
        earnings_lock=bool(earnings_lock),
        hard_risk_breach=bool(hard_risk_breach),
        sale_signal=bool(sale_signal),
        invalid_market_data=bool(invalid_market_data),
    )

    if not policy_allowed and action in {"REPLACE", "REENTER", "INCREASE"}:
        action = "WAIT"
        decision_reason = "POLICY_OR_EVIDENCE_BLOCK"

    protection_reasons = []
    if earnings_lock:
        protection_reasons.append("EARNINGS_LOCK")
    if hard_risk_breach:
        protection_reasons.append("HARD_RISK_BREACH")
    if sale_signal:
        protection_reasons.append("CONFIRMED_SALE_SIGNAL")
    if invalid_market_data:
        protection_reasons.append("INVALID_MARKET_DATA")

    verdict = _build_verdict(
        action=action,
        current=current,
        challenger=challenger,
        current_score=current_score,
        challenger_score=challenger_score,
        stability_score=stability["decision_stability_score"],
        stability_label=stability["decision_stability_label"],
        confidence_score=confidence_score,
        confidence_label=confidence_label,
        reason_code=decision_reason,
    )

    autonomous = str(autonomy_level or "LEVEL_1_ADVISOR").upper() in {
        "LEVEL_2_ASSISTED_CIO",
        "LEVEL_3_AUTONOMOUS_CIO",
    }
    automatic_paper_action_authorized = bool(
        autonomous
        and policy_allowed
        and (
            action in {"KEEP", "WAIT"}
            or decision_reason in PROTECTION_GATES
            or str(autonomy_level).upper() == "LEVEL_3_AUTONOMOUS_CIO"
        )
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
        "autonomy_level": str(autonomy_level or "LEVEL_1_ADVISOR").upper(),
        "current_candidate_id": current,
        "challenger_candidate_id": challenger or None,
        "current_capital_efficiency_score": round(current_score, 4),
        "challenger_capital_efficiency_score": round(challenger_score, 4) if challenger else None,
        "capital_efficiency_score_difference": round(challenger_score - current_score, 4) if challenger else None,
        "decision_stability_score": stability["decision_stability_score"],
        "decision_stability_label": stability["decision_stability_label"],
        "stability_gate": stability["stability_gate"],
        "evidence_confidence_score": confidence_score,
        "evidence_confidence_label": confidence_label,
        "market_regime": str(market_regime or "UNKNOWN").upper(),
        "final_capital_action": action,
        "decision_reason": decision_reason,
        "investment_policy_compliant": bool(investment_policy_compliant),
        "policy_action_allowed": policy_allowed,
        "policy_checks_passed": passed_checks,
        "policy_checks_blocked": blocked_checks,
        "protection_reasons": protection_reasons,
        "automatic_paper_action_authorized": automatic_paper_action_authorized,
        "investor_override_available": True,
        "ai_cio_verdict": verdict,
        "warnings": blocked_checks,
        "errors": [],
    }


def format_ai_cio_decision_markdown(report: Mapping[str, Any]) -> str:
    current = str(report.get("current_candidate_id", "UNKNOWN"))
    challenger = str(report.get("challenger_candidate_id") or "No qualified challenger")
    challenger_score = report.get("challenger_capital_efficiency_score")
    challenger_score_text = "Not available" if challenger_score is None else f"{_number(challenger_score):.2f}"
    difference = report.get("capital_efficiency_score_difference")
    difference_text = "Not available" if difference is None else f"{_number(difference):+.2f}"
    action = _title(report.get("final_capital_action", "KEEP"))
    confidence = _title(report.get("evidence_confidence_label", "UNKNOWN"))
    stability = _title(report.get("decision_stability_label", "UNKNOWN"))

    lines = [
        "# AI CIO Daily Decision",
        "",
        "## AI CIO Verdict",
        "",
        f"**Capital Action:** {action}",
        "",
        str(report.get("ai_cio_verdict", "No verdict available.")),
        "",
        "## Compare Candidates",
        "",
        "| Metric | Current | Challenger |",
        "|---|---:|---:|",
        f"| Investment | {current} | {challenger} |",
        f"| Capital Efficiency Score | {_number(report.get('current_capital_efficiency_score')):.2f} | {challenger_score_text} |",
        f"| Capital Efficiency Score Difference | — | {difference_text} |",
        f"| Decision Stability Score | {_number(report.get('decision_stability_score')):.2f} / 100 ({stability}) | Not yet established |",
        f"| Evidence Confidence | {confidence} ({_number(report.get('evidence_confidence_score')):.2f} / 100) | Requires continued confirmation |",
        f"| Market Regime | {_title(report.get('market_regime'))} | {_title(report.get('market_regime'))} |",
        f"| Portfolio Action | {action} | Monitor |",
        "",
        "## Investment Policy Review",
        "",
        f"- **Investment Policy Compliant:** {'Yes' if report.get('investment_policy_compliant') else 'No'}",
        f"- **Policy Action Allowed:** {'Yes' if report.get('policy_action_allowed') else 'No'}",
        f"- **Automatic Paper Action Authorized:** {'Yes' if report.get('automatic_paper_action_authorized') else 'No'}",
        f"- **Investor Override Available:** {'Yes' if report.get('investor_override_available') else 'No'}",
        "",
        "## Analysis Confidence",
        "",
        f"Evidence Confidence is **{confidence} ({_number(report.get('evidence_confidence_score')):.2f} / 100)**. The Decision Stability Score is **{_number(report.get('decision_stability_score')):.2f} / 100 ({stability})**.",
        "",
        "## Decision Summary",
        "",
        f"- **Current Investment:** {current}",
        f"- **Best Challenger:** {challenger}",
        f"- **Final Capital Action:** {action}",
        f"- **Decision Reason:** {_title(report.get('decision_reason'))}",
        f"- **Market Regime:** {_title(report.get('market_regime'))}",
        "",
        "## Paper-Only Safety",
        "",
        "This decision is advisory and paper-only. It does not place orders or communicate with a brokerage.",
        "",
    ]
    return "\n".join(lines)


def write_ai_cio_decision(
    payload: Mapping[str, Any],
    root_path: str = ".",
    output_files: Optional[Mapping[str, str]] = None,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    report = build_ai_cio_decision(**dict(payload))
    root = Path(root_path)
    files = dict(DEFAULT_OUTPUT_FILES)
    if output_files:
        files.update(output_files)
    (root / files["json"]).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / files["markdown"]).write_text(format_ai_cio_decision_markdown(report), encoding="utf-8")
    return report


if __name__ == "__main__":
    sample = {
        "current_candidate_id": "AMDW + PLTU",
        "challenger_candidate_id": "AMDW + GGLL",
        "current_capital_efficiency_score": 84.3,
        "challenger_capital_efficiency_score": 86.3,
        "decision_stability": {
            "recommended_capital_action": "KEEP",
            "change_allowed": False,
            "stability_gate": "KEEP_CURRENT",
            "decision_stability_score": 82.7,
            "decision_stability_label": "STABLE",
        },
        "evidence_confidence": 94.0,
        "market_regime": "BULL",
        "challenger_qualified": True,
        "investment_policy_compliant": True,
        "autonomy_level": "LEVEL_1_ADVISOR",
    }
    result = write_ai_cio_decision(sample)
    print(f"AI CIO Capital Action: {result['final_capital_action']}")
