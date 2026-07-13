"""Paper-only AI CIO Learning Engine.

Studies historical paper decisions and completed outcomes to identify evidence-based
patterns for investor review. It never changes production policy automatically.
"""
from __future__ import annotations

import html
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

MODULE_NAME = "ai_cio_learning_engine"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

DEFAULT_OUTPUT_FILES = {
    "json": "ai_cio_learning_engine.json",
    "markdown": "ai_cio_learning_engine.md",
    "html": "ai_cio_learning_engine.html",
}

MIN_HISTORY_DAYS_FOR_RECOMMENDATIONS = 180
MIN_COMPLETED_DECISIONS_FOR_RECOMMENDATIONS = 500
MIN_COMPLETED_REPLACEMENTS_FOR_RECOMMENDATIONS = 100
MIN_EARNINGS_CYCLES_FOR_RECOMMENDATIONS = 2
MIN_EVIDENCE_CONFIDENCE = 90.0


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


def _sequence(value: Any) -> list[Any]:
    return list(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) else []


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _pick(source: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in source and source[key] is not None:
            return source[key]
    return default


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _rate(numerator: int, denominator: int) -> float:
    return (numerator / denominator * 100.0) if denominator else 0.0


def _maturity_stage(history_days: int, decisions: int, replacements: int, earnings_cycles: int, confidence: float) -> str:
    if history_days < MIN_HISTORY_DAYS_FOR_RECOMMENDATIONS or decisions < MIN_COMPLETED_DECISIONS_FOR_RECOMMENDATIONS or replacements < MIN_COMPLETED_REPLACEMENTS_FOR_RECOMMENDATIONS or earnings_cycles < MIN_EARNINGS_CYCLES_FOR_RECOMMENDATIONS:
        return "LEARNING"
    if confidence < MIN_EVIDENCE_CONFIDENCE:
        return "OBSERVATION"
    return "RECOMMENDATION_ELIGIBLE"


def build_ai_cio_learning_engine(
    *,
    history_days: int = 0,
    completed_decisions: Optional[Sequence[Mapping[str, Any]]] = None,
    completed_replacements: Optional[Sequence[Mapping[str, Any]]] = None,
    earnings_outcomes: Optional[Sequence[Mapping[str, Any]]] = None,
    evidence_source_outcomes: Optional[Sequence[Mapping[str, Any]]] = None,
    threshold_trials: Optional[Sequence[Mapping[str, Any]]] = None,
    observed_market_regimes: Optional[Sequence[str]] = None,
    evidence_confidence: float = 0.0,
) -> dict[str, Any]:
    decisions = [row for row in _sequence(completed_decisions) if isinstance(row, Mapping)]
    replacements = [row for row in _sequence(completed_replacements) if isinstance(row, Mapping)]
    earnings = [row for row in _sequence(earnings_outcomes) if isinstance(row, Mapping)]
    sources = [row for row in _sequence(evidence_source_outcomes) if isinstance(row, Mapping)]
    trials = [row for row in _sequence(threshold_trials) if isinstance(row, Mapping)]
    regimes = sorted({str(item).upper() for item in _sequence(observed_market_regimes) if str(item).strip()})

    confidence = max(0.0, min(100.0, _number(evidence_confidence)))
    successful_replacements = sum(1 for row in replacements if bool(_pick(row, "successful", "improved_total_wealth", default=False)))
    false_positive_replacements = sum(1 for row in replacements if bool(_pick(row, "false_positive", default=False)))
    replacement_values = [_number(_pick(row, "net_total_wealth_effect", "replacement_value", default=0.0)) for row in replacements]
    decision_values = [_number(_pick(row, "net_total_wealth_effect", "outcome_value", default=0.0)) for row in decisions]
    earnings_protection_values = [_number(_pick(row, "protection_value", "estimated_loss_prevented", default=0.0)) for row in earnings]

    source_analysis = []
    for row in sources:
        name = str(_pick(row, "source", "name", default="Unknown"))
        uses = int(_number(_pick(row, "uses", "sample_size", default=0)))
        wins = int(_number(_pick(row, "successful_outcomes", "wins", default=0)))
        source_analysis.append({
            "source": name,
            "sample_size": uses,
            "success_rate": round(_rate(wins, uses), 2),
            "average_total_wealth_effect": round(_number(_pick(row, "average_total_wealth_effect", "average_value", default=0.0)), 4),
        })
    source_analysis.sort(key=lambda item: (item["success_rate"], item["average_total_wealth_effect"]), reverse=True)

    trial_analysis = []
    for row in trials:
        current_rule = str(_pick(row, "current_rule", default="Current Policy"))
        candidate_rule = str(_pick(row, "candidate_rule", default="Candidate Policy"))
        current_value = _number(_pick(row, "current_total_wealth", default=0.0))
        candidate_value = _number(_pick(row, "candidate_total_wealth", default=0.0))
        trial_analysis.append({
            "current_rule": current_rule,
            "candidate_rule": candidate_rule,
            "current_total_wealth": round(current_value, 4),
            "candidate_total_wealth": round(candidate_value, 4),
            "difference": round(candidate_value - current_value, 4),
            "status": str(_pick(row, "status", default="SHADOW_ONLY")).upper(),
        })

    stage = _maturity_stage(int(history_days), len(decisions), len(replacements), len(earnings), confidence)
    findings = []
    if len(replacements) < MIN_COMPLETED_REPLACEMENTS_FOR_RECOMMENDATIONS:
        findings.append({"severity": "INFO", "finding": "More completed replacement outcomes are required before recommending threshold changes.", "recommended_review": "Continue collecting paper outcomes."})
    elif _rate(successful_replacements, len(replacements)) < 55.0:
        findings.append({"severity": "HIGH", "finding": "Replacement success rate is below the preferred learning benchmark.", "recommended_review": "Review replacement persistence, evidence confidence, and turnover gates."})
    if replacements and _rate(false_positive_replacements, len(replacements)) > 15.0:
        findings.append({"severity": "MEDIUM", "finding": "False-positive replacement rate is elevated.", "recommended_review": "Evaluate whether replacement confirmation requirements are too permissive."})
    if earnings and _mean(earnings_protection_values) <= 0:
        findings.append({"severity": "MEDIUM", "finding": "Earnings protection has not yet demonstrated positive measured value.", "recommended_review": "Continue measuring post-event protection outcomes before changing the protection window."})
    if source_analysis:
        best = source_analysis[0]
        findings.append({"severity": "INFO", "finding": f"{best['source']} currently has the strongest measured evidence contribution.", "recommended_review": "Preserve as supporting evidence and continue validating across regimes."})
    if not findings:
        findings.append({"severity": "INFO", "finding": "No material learning weakness was detected in the supplied history.", "recommended_review": "Continue collecting evidence without changing production policy."})

    recommendation_allowed = stage == "RECOMMENDATION_ELIGIBLE"
    recommendations = []
    if recommendation_allowed:
        for trial in trial_analysis:
            if trial["difference"] > 0:
                recommendations.append({
                    "type": "POLICY_REVIEW",
                    "recommendation": f"Consider investor review of {trial['candidate_rule']}.",
                    "evidence": f"Shadow result exceeded {trial['current_rule']} by {trial['difference']:.2f} Total Wealth units.",
                    "status": "AWAITING_INVESTOR_APPROVAL",
                    "automatic_change_allowed": False,
                })
    if not recommendations:
        recommendations.append({
            "type": "CONTINUE_LEARNING",
            "recommendation": "Do not change production policy at this time.",
            "evidence": "Evidence maturity or validated shadow-test superiority is insufficient.",
            "status": "NO_CHANGE_RECOMMENDED",
            "automatic_change_allowed": False,
        })

    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "reporting_only": True,
        "maturity": {
            "stage": stage,
            "history_days": int(history_days),
            "completed_decisions": len(decisions),
            "completed_replacements": len(replacements),
            "earnings_cycles": len(earnings),
            "observed_market_regimes": regimes,
            "evidence_confidence": round(confidence, 2),
            "policy_recommendations_allowed": recommendation_allowed,
        },
        "learning_metrics": {
            "replacement_success_rate": round(_rate(successful_replacements, len(replacements)), 2),
            "false_positive_replacement_rate": round(_rate(false_positive_replacements, len(replacements)), 2),
            "average_replacement_total_wealth_effect": round(_mean(replacement_values), 4),
            "average_decision_total_wealth_effect": round(_mean(decision_values), 4),
            "average_earnings_protection_value": round(_mean(earnings_protection_values), 4),
        },
        "evidence_source_analysis": source_analysis,
        "shadow_trial_analysis": trial_analysis,
        "learning_findings": findings,
        "recommendations": recommendations,
        "governance": {
            "automatic_policy_changes_allowed": False,
            "investor_approval_required": True,
            "shadow_validation_required": True,
            "production_policy_modified": False,
        },
        "warnings": [] if decisions or replacements or earnings else ["No completed historical outcomes were supplied; the engine remains in learning mode."],
        "errors": [],
    }


def format_ai_cio_learning_engine_markdown(report: Mapping[str, Any]) -> str:
    maturity = _mapping(report.get("maturity"))
    metrics = _mapping(report.get("learning_metrics"))
    lines = [
        "# AI CIO Learning Engine", "",
        "## Executive Learning Status", "",
        f"- **Maturity Stage:** {maturity.get('stage', 'UNKNOWN')}",
        f"- **History:** {maturity.get('history_days', 0)} days",
        f"- **Completed Decisions:** {maturity.get('completed_decisions', 0)}",
        f"- **Completed Replacements:** {maturity.get('completed_replacements', 0)}",
        f"- **Evidence Confidence:** {maturity.get('evidence_confidence', 0):.2f}%", "",
        "## Learning Metrics", "",
        "| Metric | Result |", "|---|---:|",
        f"| Replacement Success Rate | {metrics.get('replacement_success_rate', 0):.2f}% |",
        f"| False-Positive Replacement Rate | {metrics.get('false_positive_replacement_rate', 0):.2f}% |",
        f"| Average Replacement Total Wealth Effect | {metrics.get('average_replacement_total_wealth_effect', 0):.2f} |",
        f"| Average Decision Total Wealth Effect | {metrics.get('average_decision_total_wealth_effect', 0):.2f} |",
        f"| Average Earnings Protection Value | {metrics.get('average_earnings_protection_value', 0):.2f} |", "",
        "## Evidence Source Analysis", "",
        "| Source | Sample Size | Success Rate | Average Total Wealth Effect |", "|---|---:|---:|---:|",
    ]
    for row in _sequence(report.get("evidence_source_analysis")):
        lines.append(f"| {row.get('source', 'Unknown')} | {row.get('sample_size', 0)} | {row.get('success_rate', 0):.2f}% | {row.get('average_total_wealth_effect', 0):.2f} |")
    lines.extend(["", "## What the AI CIO Learned", ""])
    for finding in _sequence(report.get("learning_findings")):
        lines.append(f"- **{finding.get('severity', 'INFO')}:** {finding.get('finding', '')}  ")
        lines.append(f"  **Recommended Review:** {finding.get('recommended_review', '')}")
    lines.extend(["", "## Recommendations", ""])
    for item in _sequence(report.get("recommendations")):
        lines.append(f"- **{item.get('status', 'REVIEW')}:** {item.get('recommendation', '')}  ")
        lines.append(f"  **Evidence:** {item.get('evidence', '')}")
    lines.extend(["", "## Governance", "", "The AI CIO may study and recommend, but it may not modify production rules, thresholds, weightings, or policy automatically. Shadow validation and investor approval are required before any policy change.", ""])
    return "\n".join(lines)


def format_ai_cio_learning_engine_html(report: Mapping[str, Any]) -> str:
    markdown = format_ai_cio_learning_engine_markdown(report)
    return "<!doctype html><html><head><meta charset='utf-8'><title>AI CIO Learning Engine</title><style>body{font-family:Arial,sans-serif;max-width:1100px;margin:0 auto;padding:32px;background:#f5f7fb;color:#172033}pre{white-space:pre-wrap;background:white;padding:30px;border-radius:14px;box-shadow:0 4px 18px rgba(0,0,0,.08);line-height:1.55}</style></head><body><pre>" + html.escape(markdown) + "</pre></body></html>"


def write_ai_cio_learning_engine(payload: Mapping[str, Any], root_path: str = ".", output_files: Optional[Mapping[str, str]] = None) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    report = build_ai_cio_learning_engine(**dict(payload))
    root = Path(root_path)
    files = dict(DEFAULT_OUTPUT_FILES)
    if output_files:
        files.update(output_files)
    (root / files["json"]).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / files["markdown"]).write_text(format_ai_cio_learning_engine_markdown(report), encoding="utf-8")
    (root / files["html"]).write_text(format_ai_cio_learning_engine_html(report), encoding="utf-8")
    return report


def build_and_write_ai_cio_learning_engine(payload: Mapping[str, Any], root_path: str = ".", output_files: Optional[Mapping[str, str]] = None) -> dict[str, Any]:
    return write_ai_cio_learning_engine(payload, root_path, output_files)


if __name__ == "__main__":
    sample = {
        "history_days": 220,
        "completed_decisions": [{"net_total_wealth_effect": 1.1}] * 520,
        "completed_replacements": [{"successful": True, "net_total_wealth_effect": 0.8}] * 104,
        "earnings_outcomes": [{"protection_value": 2.4}, {"protection_value": 1.8}],
        "evidence_source_outcomes": [{"source": "Market Intelligence", "uses": 120, "successful_outcomes": 84, "average_total_wealth_effect": 0.7}],
        "threshold_trials": [{"current_rule": "Replacement Threshold 8.0", "candidate_rule": "Replacement Threshold 7.5", "current_total_wealth": 100.0, "candidate_total_wealth": 101.2}],
        "observed_market_regimes": ["BULL", "BEAR", "SIDEWAYS"],
        "evidence_confidence": 94.0,
    }
    result = write_ai_cio_learning_engine(sample)
    print(f"AI CIO Learning Engine: {result['maturity']['stage']}")
