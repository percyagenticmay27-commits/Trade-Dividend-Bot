"""Decision Stability Engine for the Trade Dividend Bot AI CIO layer.

Measures whether a recommendation is stable enough to preserve the current paper
portfolio or whether persistent evidence supports preparing or allowing a change.
This module is reporting-only and never places orders.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

MODULE_NAME = "decision_stability_engine"
MODULE_VERSION = "2.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

DEFAULT_OUTPUT_FILES = {
    "json": "decision_stability.json",
    "markdown": "decision_stability.md",
}

DEFAULT_REPLACEMENT_THRESHOLD = 5.0
DEFAULT_MIN_PERSISTENCE_DAYS = 3


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


def _label(score: float) -> str:
    if score >= 90:
        return "VERY_STABLE"
    if score >= 75:
        return "STABLE"
    if score >= 60:
        return "TRANSITION_WATCH"
    if score >= 40:
        return "UNSTABLE"
    return "CRITICAL"


def _history_values(history: Sequence[Mapping[str, Any]], field: str) -> list[float]:
    values: list[float] = []
    for item in history:
        value = _number(item.get(field), float("nan"))
        if math.isfinite(value):
            values.append(value)
    return values


def _persistence_score(history: Sequence[Mapping[str, Any]], current_action: str) -> tuple[float, int]:
    action = str(current_action or "KEEP").upper()
    consecutive = 0
    for item in reversed(history):
        prior = str(item.get("capital_action", item.get("action", ""))).upper()
        if prior == action:
            consecutive += 1
        else:
            break
    return _clamp(45.0 + min(55.0, consecutive * 10.0)), consecutive


def _gap_score(current_score: float, challenger_score: float, replacement_threshold: float) -> tuple[float, float]:
    gap = round(challenger_score - current_score, 4)
    if gap <= 0:
        return 100.0, gap
    if gap < replacement_threshold:
        return _clamp(85.0 - (gap / max(replacement_threshold, 0.1)) * 25.0), gap
    return _clamp(50.0 - (gap - replacement_threshold) * 6.0), gap


def _trend_score(history: Sequence[Mapping[str, Any]]) -> float:
    current_values = _history_values(history, "current_capital_efficiency_score")
    challenger_values = _history_values(history, "challenger_capital_efficiency_score")
    if len(current_values) < 2 or len(challenger_values) < 2:
        return 60.0
    prior_gap = challenger_values[-2] - current_values[-2]
    latest_gap = challenger_values[-1] - current_values[-1]
    if latest_gap <= prior_gap:
        return 80.0
    widening = latest_gap - prior_gap
    return _clamp(70.0 - widening * 8.0)


def _regime_score(regime_history: Sequence[str], current_regime: str) -> tuple[float, int]:
    normalized = [str(value).upper() for value in regime_history if str(value).strip()]
    current = str(current_regime or "UNKNOWN").upper()
    if not normalized:
        return (55.0 if current == "UNKNOWN" else 70.0), 0
    consecutive = 0
    for value in reversed(normalized):
        if value == current:
            consecutive += 1
        else:
            break
    return _clamp(45.0 + min(55.0, consecutive * 12.0)), consecutive


def _event_score(earnings_lock: bool, hard_risk_breach: bool, sale_signal: bool) -> float:
    if hard_risk_breach:
        return 0.0
    if earnings_lock:
        return 15.0
    if sale_signal:
        return 30.0
    return 100.0


def _threshold_distance_score(distance_to_sale_threshold: float) -> float:
    distance = _number(distance_to_sale_threshold, 100.0)
    if distance <= 0:
        return 10.0
    if distance >= 20:
        return 100.0
    return _clamp(35.0 + distance * 3.25)


def calculate_decision_stability(
    *,
    current_candidate_id: str,
    challenger_candidate_id: str = "",
    current_capital_efficiency_score: float,
    challenger_capital_efficiency_score: float = 0.0,
    current_action: str = "KEEP",
    decision_history: Optional[Sequence[Mapping[str, Any]]] = None,
    evidence_confidence: float = 100.0,
    market_regime: str = "UNKNOWN",
    market_regime_history: Optional[Sequence[str]] = None,
    sector_persistence_days: int = 0,
    earnings_lock: bool = False,
    hard_risk_breach: bool = False,
    sale_signal: bool = False,
    distance_to_sale_threshold: float = 100.0,
    stale_data: bool = False,
    replacement_threshold: float = DEFAULT_REPLACEMENT_THRESHOLD,
    minimum_persistence_days: int = DEFAULT_MIN_PERSISTENCE_DAYS,
) -> dict[str, Any]:
    """Calculate the Decision Stability Score and anti-churn gate result."""
    current_id = str(current_candidate_id or "").strip().upper()
    if not current_id:
        raise ValueError("current_candidate_id is required")
    challenger_id = str(challenger_candidate_id or "").strip().upper()
    history = list(decision_history or [])
    regime_history = list(market_regime_history or [])
    current_score = _number(current_capital_efficiency_score)
    challenger_score = _number(challenger_capital_efficiency_score)
    threshold = max(0.1, _number(replacement_threshold, DEFAULT_REPLACEMENT_THRESHOLD))

    persistence_component, consecutive_action_days = _persistence_score(history, current_action)
    separation_component, improvement = _gap_score(current_score, challenger_score, threshold)
    trend_component = _trend_score(history)
    regime_component, regime_persistence_days = _regime_score(regime_history, market_regime)
    confidence_component = _clamp(evidence_confidence - (20.0 if stale_data else 0.0))
    event_component = _event_score(earnings_lock, hard_risk_breach, sale_signal)
    threshold_component = _threshold_distance_score(distance_to_sale_threshold)
    sector_component = _clamp(45.0 + min(55.0, max(0, int(sector_persistence_days)) * 10.0))

    components = {
        "decision_persistence": persistence_component,
        "score_separation": separation_component,
        "score_gap_trend": trend_component,
        "market_regime_stability": regime_component,
        "sector_persistence": sector_component,
        "evidence_confidence": confidence_component,
        "event_stability": event_component,
        "sale_threshold_distance": threshold_component,
    }
    weights = {
        "decision_persistence": 0.18,
        "score_separation": 0.20,
        "score_gap_trend": 0.10,
        "market_regime_stability": 0.12,
        "sector_persistence": 0.10,
        "evidence_confidence": 0.12,
        "event_stability": 0.10,
        "sale_threshold_distance": 0.08,
    }
    score = round(sum(components[name] * weights[name] for name in weights), 4)

    hard_exit = bool(earnings_lock or hard_risk_breach or sale_signal)
    challenger_exceeds_threshold = bool(challenger_id and improvement >= threshold)
    persistence_met = max(consecutive_action_days, int(sector_persistence_days), regime_persistence_days) >= int(minimum_persistence_days)
    confidence_met = confidence_component >= 70.0

    if hard_exit:
        gate = "CHANGE_AUTHORIZED_BY_PROTECTION_RULE"
        recommended_action = "PARK_IN_SGOV" if earnings_lock or hard_risk_breach else "PREPARE_REPLACEMENT"
        change_allowed = True
    elif challenger_exceeds_threshold and persistence_met and confidence_met and score < 75.0:
        gate = "CHANGE_ALLOWED"
        recommended_action = "REPLACE"
        change_allowed = True
    elif challenger_exceeds_threshold:
        gate = "WAIT_FOR_PERSISTENCE"
        recommended_action = "WAIT"
        change_allowed = False
    else:
        gate = "KEEP_CURRENT"
        recommended_action = "KEEP"
        change_allowed = False

    explanation = _build_explanation(
        current_id=current_id,
        challenger_id=challenger_id,
        current_score=current_score,
        challenger_score=challenger_score,
        improvement=improvement,
        threshold=threshold,
        stability_score=score,
        stability_label=_label(score),
        gate=gate,
        persistence_met=persistence_met,
        confidence_component=confidence_component,
        earnings_lock=earnings_lock,
        hard_risk_breach=hard_risk_breach,
        sale_signal=sale_signal,
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
        "current_candidate_id": current_id,
        "challenger_candidate_id": challenger_id or None,
        "current_capital_efficiency_score": round(current_score, 4),
        "challenger_capital_efficiency_score": round(challenger_score, 4) if challenger_id else None,
        "challenger_improvement_points": improvement if challenger_id else None,
        "replacement_threshold_points": threshold,
        "decision_stability_score": score,
        "decision_stability_label": _label(score),
        "components": components,
        "consecutive_action_days": consecutive_action_days,
        "market_regime_persistence_days": regime_persistence_days,
        "sector_persistence_days": max(0, int(sector_persistence_days)),
        "persistence_requirement_met": persistence_met,
        "evidence_confidence_requirement_met": confidence_met,
        "change_allowed": change_allowed,
        "stability_gate": gate,
        "recommended_capital_action": recommended_action,
        "natural_explanation": explanation,
        "warnings": ["Market data is stale; confidence was reduced."] if stale_data else [],
        "errors": [],
    }


def _build_explanation(**values: Any) -> str:
    current_id = values["current_id"]
    challenger_id = values["challenger_id"]
    improvement = values["improvement"]
    threshold = values["threshold"]
    stability_score = values["stability_score"]
    stability_label = str(values["stability_label"]).replace("_", " ").title()
    gate = values["gate"]
    if values["earnings_lock"]:
        return (
            f"{current_id} is under an earnings lock, so the affected paper allocation should be parked in SGOV. "
            "This protection rule overrides the normal anti-churn threshold. The instrument may compete for re-entry after the event ends."
        )
    if values["hard_risk_breach"]:
        return (
            f"{current_id} has breached a mandatory risk limit. The affected paper allocation should move to SGOV while the AI CIO evaluates qualified replacements."
        )
    if values["sale_signal"]:
        return (
            f"{current_id} has a confirmed sale signal. A replacement may now be prepared, but any new instrument must still pass entry, risk, and Investment Policy requirements."
        )
    if gate == "CHANGE_ALLOWED":
        return (
            f"{challenger_id} exceeds {current_id} by {improvement:.2f} Capital Efficiency Score points, which is above the required "
            f"{threshold:.2f}-point improvement. The advantage has sufficient persistence and evidence confidence, while the Decision Stability Score is "
            f"{stability_score:.2f} out of 100 ({stability_label}), indicating that the current recommendation is no longer stable enough to block a change."
        )
    if gate == "WAIT_FOR_PERSISTENCE":
        return (
            f"{challenger_id} currently exceeds {current_id} by {improvement:.2f} Capital Efficiency Score points, above the required "
            f"{threshold:.2f}-point improvement. However, the advantage has not yet satisfied all persistence and evidence requirements. "
            "The paper portfolio should remain unchanged while the bot confirms that this is a durable improvement rather than short-term market noise."
        )
    challenger_text = (
        f" The strongest challenger, {challenger_id}, leads by only {improvement:.2f} points, below the required {threshold:.2f}-point replacement threshold."
        if challenger_id and improvement > 0
        else " No qualified challenger currently provides a meaningful advantage."
    )
    return (
        f"Keep {current_id}. The Decision Stability Score is {stability_score:.2f} out of 100 ({stability_label}), and no mandatory exit condition is active."
        f"{challenger_text} Changing the paper portfolio now would create unnecessary turnover without enough expected Total Wealth improvement."
    )


def build_decision_stability_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    return calculate_decision_stability(**dict(payload))


def format_decision_stability_markdown(report: Mapping[str, Any]) -> str:
    challenger = report.get("challenger_candidate_id") or "None"
    return "\n".join([
        "# AI CIO Decision Stability Review",
        "",
        f"- Current Strategy: {report.get('current_candidate_id', 'UNKNOWN')}",
        f"- Strongest Challenger: {challenger}",
        f"- Decision Stability Score: {report.get('decision_stability_score', 0):.2f} / 100",
        f"- Stability State: {str(report.get('decision_stability_label', 'UNKNOWN')).replace('_', ' ').title()}",
        f"- Recommended Capital Action: {str(report.get('recommended_capital_action', 'KEEP')).replace('_', ' ')}",
        f"- Change Allowed: {'Yes' if report.get('change_allowed') else 'No'}",
        "",
        "## Natural Explanation",
        "",
        str(report.get("natural_explanation", "No explanation available.")),
        "",
        "## What the Score Means",
        "",
        "The Decision Stability Score measures how likely the current recommendation is to remain valid. It combines persistence, score separation, market-regime stability, sector persistence, evidence quality, event risk, and proximity to mandatory sale thresholds.",
        "",
    ])


def write_decision_stability(
    payload: Mapping[str, Any],
    root_path: str = ".",
    output_files: Optional[Mapping[str, str]] = None,
) -> dict[str, Any]:
    report = build_decision_stability_report(payload)
    root = Path(root_path)
    files = dict(DEFAULT_OUTPUT_FILES)
    if output_files:
        files.update(output_files)
    (root / files["json"]).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / files["markdown"]).write_text(format_decision_stability_markdown(report), encoding="utf-8")
    return report


if __name__ == "__main__":
    sample = {
        "current_candidate_id": "SGOV",
        "current_capital_efficiency_score": 50.0,
        "current_action": "KEEP",
        "decision_history": [],
    }
    result = write_decision_stability(sample)
    print(f"Decision Stability Score: {result['decision_stability_score']:.2f}")
