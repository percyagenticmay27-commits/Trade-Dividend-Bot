"""AI CIO Performance Analytics Engine.

Paper-only, read-only self-evaluation of AI CIO decisions. The module measures
whether decisions improved Total Wealth and proposes evidence-based maintenance
ideas. It never changes policy, thresholds, production code, or portfolio state.
"""

from __future__ import annotations

import html
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

MODULE_NAME = "ai_cio_performance_analytics"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False

DEFAULT_JSON_PATH = Path("ai_cio_performance_analytics.json")
DEFAULT_MARKDOWN_PATH = Path("ai_cio_performance_analytics.md")
DEFAULT_HTML_PATH = Path("ai_cio_performance_analytics.html")

METRIC_DETAILS = {
    "total_decisions": {
        "label": "Total Decisions Reviewed",
        "definition": "The number of AI CIO decision records included in this review.",
        "calculation": "Count of valid decision records supplied to the engine.",
        "why_it_matters": "A larger sample provides a more reliable basis for self-evaluation.",
    },
    "portfolio_change_rate": {
        "label": "Portfolio Change Rate",
        "definition": "The percentage of reviewed decisions that changed the paper portfolio.",
        "calculation": "Portfolio-changing decisions divided by total decisions reviewed.",
        "why_it_matters": "This shows how frequently the AI CIO turns over capital instead of holding.",
    },
    "replacement_success_rate": {
        "label": "Replacement Success Rate",
        "definition": "The percentage of completed replacements that produced positive measured replacement value.",
        "calculation": "Positive completed replacement outcomes divided by all completed replacement outcomes.",
        "why_it_matters": "This tests whether replacement decisions actually improved Total Wealth after the change.",
    },
    "false_positive_replacement_rate": {
        "label": "False-Positive Replacement Rate",
        "definition": "The percentage of completed replacements that later produced negative measured replacement value.",
        "calculation": "Negative completed replacement outcomes divided by all completed replacement outcomes.",
        "why_it_matters": "A high rate may indicate that replacement thresholds, persistence, or evidence gates need review.",
    },
    "average_capital_efficiency_improvement": {
        "label": "Average Capital Efficiency Score Improvement",
        "definition": "The average score advantage recorded when replacements were approved.",
        "calculation": "Mean challenger score minus current score for completed replacement records.",
        "why_it_matters": "This shows how much measured opportunity improvement normally justified portfolio turnover.",
    },
    "average_decision_stability_score": {
        "label": "Average Decision Stability Score",
        "definition": "The average stability score across reviewed AI CIO decisions.",
        "calculation": "Arithmetic mean of valid Decision Stability Score values.",
        "why_it_matters": "This indicates whether decisions were generally made from stable or fragile evidence.",
    },
    "average_evidence_confidence": {
        "label": "Average Evidence Confidence",
        "definition": "The average confidence in the evidence used by reviewed decisions.",
        "calculation": "Arithmetic mean of valid Evidence Confidence percentages.",
        "why_it_matters": "This reveals whether the system is acting with complete, current, and consistent evidence.",
    },
    "average_holding_period_days": {
        "label": "Average Holding Period",
        "definition": "The average number of days allocations remained active before closure or replacement.",
        "calculation": "Arithmetic mean of valid holding-period values in lifecycle records.",
        "why_it_matters": "This helps identify excessive churn or overly slow capital rotation.",
    },
    "average_sgov_parking_days": {
        "label": "Average SGOV Parking Duration",
        "definition": "The average number of days capital remained temporarily parked in SGOV.",
        "calculation": "Arithmetic mean of completed SGOV parking durations.",
        "why_it_matters": "This shows how long protected capital waited before re-entry or reassignment.",
    },
    "estimated_protection_value": {
        "label": "Estimated Protection Value",
        "definition": "An estimate of value preserved by approved protection decisions.",
        "calculation": "Sum of measured estimated protection-value records.",
        "why_it_matters": "This evaluates whether earnings locks and other protection rules helped preserve capital.",
        "estimated": True,
    },
    "replacement_value_created": {
        "label": "Replacement Value Created",
        "definition": "Measured value added or lost by completed replacement decisions.",
        "calculation": "Sum of measured replacement-value outcomes.",
        "why_it_matters": "This tests whether changing investments improved results compared with keeping the prior allocation.",
    },
    "portfolio_turnover_cost": {
        "label": "Portfolio Turnover Cost",
        "definition": "Estimated drag caused by changing allocations.",
        "calculation": "Sum of supplied spread, slippage, fee, and other turnover-cost estimates.",
        "why_it_matters": "A replacement must create enough value to overcome the cost of making the change.",
        "estimated": True,
    },
    "net_decision_value": {
        "label": "Net Decision Value",
        "definition": "The combined measured benefit of protection and replacement decisions after turnover cost.",
        "calculation": "Estimated Protection Value plus Replacement Value Created minus Portfolio Turnover Cost.",
        "why_it_matters": "This summarizes whether AI CIO management decisions added value beyond passive holding.",
    },
    "self_assessment_score": {
        "label": "AI CIO Self-Assessment Score",
        "definition": "A transparent summary score for the quality of reviewed paper decisions.",
        "calculation": "Weighted combination of replacement results, Decision Stability, Evidence Confidence, protection value, and turnover discipline.",
        "why_it_matters": "This gives the investor a simple view of how well the AI CIO decision process performed.",
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _mean(values: Iterable[float]) -> float | None:
    items = list(values)
    return sum(items) / len(items) if items else None


def _records(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        for key in ("entries", "decisions", "records", "allocations", "events", "items"):
            nested = value.get(key)
            if isinstance(nested, Sequence) and not isinstance(nested, (str, bytes)):
                return [dict(item) for item in nested if isinstance(item, Mapping)]
        return [dict(value)]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _first_number(record: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        number = _finite_number(record.get(key))
        if number is not None:
            return number
    return None


def _first_text(record: Mapping[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _decision_changed(record: Mapping[str, Any]) -> bool:
    explicit = record.get("applied_to_paper_portfolio", record.get("portfolio_changed"))
    if isinstance(explicit, bool):
        return explicit
    action = _first_text(record, "capital_action", "action", "decision", "recommendation").upper()
    return action in {
        "REPLACE", "REPLACE_CURRENT", "PARK IN SGOV", "PARK_CURRENT_IN_SGOV",
        "INCREASE", "REDUCE", "REENTER", "CLOSE",
    }


def _recommendations(metrics: Mapping[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    def add(severity: str, title: str, evidence: str, recommendation: str) -> None:
        findings.append({
            "severity": severity,
            "title": title,
            "evidence": evidence,
            "recommendation": recommendation,
            "automatic_change_allowed": False,
            "requires_human_review": True,
        })

    completed = int(metrics["completed_replacements"])
    success = metrics["replacement_success_rate"]
    false_positive = metrics["false_positive_replacement_rate"]
    change_rate = metrics["portfolio_change_rate"]
    confidence = metrics["average_evidence_confidence"]
    stability = metrics["average_decision_stability_score"]
    turnover = metrics["portfolio_turnover_cost"]
    replacement_value = metrics["replacement_value_created"]

    if completed < 5:
        add("INFO", "More replacement history is needed", f"Only {completed} completed replacement outcomes were available.", "Continue collecting paper outcomes before changing replacement thresholds.")
    elif success is not None and success < 60:
        add("HIGH", "Replacement outcomes need review", f"Replacement Success Rate was {success:.1f}%.", "Review persistence, minimum score improvement, and event-risk gates before approving any policy adjustment.")

    if false_positive is not None and false_positive > 25:
        add("HIGH", "False-positive replacements are elevated", f"False-Positive Replacement Rate was {false_positive:.1f}%.", "Investigate whether challengers need a larger sustained advantage or stronger evidence confirmation.")

    if change_rate is not None and change_rate > 35:
        add("MEDIUM", "Portfolio activity may be too frequent", f"Portfolio Change Rate was {change_rate:.1f}%.", "Review Decision Stability and persistence behavior for signs of unnecessary turnover.")

    if confidence is not None and confidence < 75:
        add("HIGH", "Evidence quality should improve", f"Average Evidence Confidence was {confidence:.1f}%.", "Improve data freshness and completeness before considering more autonomous decisions.")

    if stability is not None and stability < 65:
        add("MEDIUM", "Decisions were made with limited stability", f"Average Decision Stability Score was {stability:.1f}.", "Review why decisions remained fragile and whether additional confirmation time is appropriate.")

    if turnover > 0 and replacement_value <= turnover:
        add("MEDIUM", "Turnover consumed replacement value", f"Replacement Value Created was ${replacement_value:.2f} while Portfolio Turnover Cost was ${turnover:.2f}.", "Review whether the minimum expected replacement benefit adequately exceeds estimated trading friction.")

    if not findings:
        add("INFO", "No immediate policy weakness detected", "Reviewed metrics remained within the current monitoring ranges.", "Continue paper operation and collect additional evidence; do not change production rules automatically.")
    return findings


def build_ai_cio_performance_analytics(
    decisions: Any = None,
    replacements: Any = None,
    protection_events: Any = None,
    lifecycle_records: Any = None,
    wealth_attribution: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a read-only self-evaluation report from existing paper artifacts."""
    decision_rows = _records(decisions)
    replacement_rows = _records(replacements)
    protection_rows = _records(protection_events)
    lifecycle_rows = _records(lifecycle_records)
    wealth = dict(wealth_attribution or {})
    warnings: list[str] = []

    changed_count = sum(_decision_changed(row) for row in decision_rows)
    action_counts = Counter(
        _first_text(row, "capital_action", "action", "decision", default="UNKNOWN").upper()
        for row in decision_rows
    )

    stability_values = [v for row in decision_rows if (v := _first_number(row, "decision_stability_score", "stability_score")) is not None]
    confidence_values = [v for row in decision_rows if (v := _first_number(row, "evidence_confidence", "confidence")) is not None]
    holding_values = [v for row in lifecycle_rows if (v := _first_number(row, "days_held", "holding_period_days")) is not None and v >= 0]
    sgov_days = [v for row in lifecycle_rows + protection_rows if (v := _first_number(row, "sgov_parking_days", "parking_days", "duration_days")) is not None and v >= 0]

    completed_replacements: list[dict[str, Any]] = []
    pending_replacements = 0
    score_differences: list[float] = []
    replacement_values: list[float] = []
    turnover_costs: list[float] = []
    for row in replacement_rows:
        status = _first_text(row, "status", "outcome_status", default="COMPLETED").upper()
        value = _first_number(row, "replacement_value", "replacement_value_created", "outcome_value")
        if status in {"PENDING", "OPEN", "PREPARED"} or value is None:
            pending_replacements += 1
            continue
        completed_replacements.append(row)
        replacement_values.append(value)
        difference = _first_number(row, "score_difference", "capital_efficiency_score_difference", "ces_improvement")
        if difference is not None:
            score_differences.append(difference)
        cost = _first_number(row, "turnover_cost", "portfolio_turnover_cost")
        if cost is not None:
            turnover_costs.append(abs(cost))

    positive_replacements = sum(value > 0 for value in replacement_values)
    negative_replacements = sum(value < 0 for value in replacement_values)
    completed_count = len(completed_replacements)

    protection_values = [v for row in protection_rows if (v := _first_number(row, "estimated_protection_value", "protection_value")) is not None]
    if not protection_values:
        fallback = _finite_number(wealth.get("estimated_protection_value"))
        if fallback is not None:
            protection_values = [fallback]
    if not replacement_values:
        fallback = _finite_number(wealth.get("replacement_value_created"))
        if fallback is not None:
            replacement_values = [fallback]
    if not turnover_costs:
        fallback = _finite_number(wealth.get("portfolio_turnover_cost"))
        if fallback is not None:
            turnover_costs = [abs(fallback)]

    total_decisions = len(decision_rows)
    replacement_success_rate = (positive_replacements / completed_count * 100.0) if completed_count else None
    false_positive_rate = (negative_replacements / completed_count * 100.0) if completed_count else None
    portfolio_change_rate = (changed_count / total_decisions * 100.0) if total_decisions else 0.0
    protection_total = sum(protection_values)
    replacement_total = sum(replacement_values)
    turnover_total = sum(turnover_costs)
    net_decision_value = protection_total + replacement_total - turnover_total

    success_component = 50.0 if replacement_success_rate is None else replacement_success_rate
    stability_component = _mean(stability_values) if stability_values else 50.0
    confidence_component = _mean(confidence_values) if confidence_values else 50.0
    protection_component = 100.0 if protection_total > 0 else 50.0
    turnover_component = 100.0 if turnover_total <= max(replacement_total + protection_total, 0.01) * 0.25 else 40.0
    self_score = max(0.0, min(100.0,
        success_component * 0.30
        + stability_component * 0.20
        + confidence_component * 0.20
        + protection_component * 0.15
        + turnover_component * 0.15
    ))
    grade = "A" if self_score >= 90 else "B" if self_score >= 80 else "C" if self_score >= 70 else "D" if self_score >= 60 else "F"

    if not decision_rows:
        warnings.append("No decision records were supplied; decision metrics use neutral or zero defaults.")
    if completed_count == 0:
        warnings.append("No completed replacement outcomes were available for success-rate evaluation.")

    metrics = {
        "total_decisions": total_decisions,
        "portfolio_changes": changed_count,
        "portfolio_change_rate": round(portfolio_change_rate, 2),
        "action_counts": dict(sorted(action_counts.items())),
        "completed_replacements": completed_count,
        "pending_replacements": pending_replacements,
        "successful_replacements": positive_replacements,
        "unsuccessful_replacements": negative_replacements,
        "replacement_success_rate": None if replacement_success_rate is None else round(replacement_success_rate, 2),
        "false_positive_replacement_rate": None if false_positive_rate is None else round(false_positive_rate, 2),
        "average_capital_efficiency_improvement": None if not score_differences else round(_mean(score_differences) or 0.0, 2),
        "average_decision_stability_score": None if not stability_values else round(_mean(stability_values) or 0.0, 2),
        "average_evidence_confidence": None if not confidence_values else round(_mean(confidence_values) or 0.0, 2),
        "average_holding_period_days": None if not holding_values else round(_mean(holding_values) or 0.0, 2),
        "average_sgov_parking_days": None if not sgov_days else round(_mean(sgov_days) or 0.0, 2),
        "estimated_protection_value": round(protection_total, 2),
        "replacement_value_created": round(replacement_total, 2),
        "portfolio_turnover_cost": round(turnover_total, 2),
        "net_decision_value": round(net_decision_value, 2),
        "self_assessment_score": round(self_score, 2),
        "self_assessment_grade": grade,
    }

    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_iso(),
        "paper_trade_mode": PAPER_TRADE_MODE,
        "live_trading_enabled": LIVE_TRADING_ENABLED,
        "broker_execution_enabled": BROKER_EXECUTION_ENABLED,
        "analysis_scope": "READ_ONLY_SELF_EVALUATION",
        "automatic_policy_changes_allowed": False,
        "metrics": metrics,
        "metric_details": METRIC_DETAILS,
        "improvement_findings": _recommendations(metrics),
        "warnings": warnings,
        "errors": [],
    }


def format_ai_cio_performance_analytics_markdown(report: Mapping[str, Any]) -> str:
    metrics = report["metrics"]
    lines = [
        "# AI CIO Performance Analytics",
        "",
        "## Executive Self-Assessment",
        "",
        f"- **AI CIO Self-Assessment Score:** {metrics['self_assessment_score']:.2f} / 100",
        f"- **Grade:** {metrics['self_assessment_grade']}",
        f"- **Net Decision Value:** ${metrics['net_decision_value']:.2f}",
        "- **Automatic Policy Changes:** Not allowed",
        "",
        "## Decision Performance",
        "",
        "| Metric | Result | Details |",
        "|---|---:|---|",
    ]
    rows = [
        ("total_decisions", str(metrics["total_decisions"])),
        ("portfolio_change_rate", f"{metrics['portfolio_change_rate']:.2f}%"),
        ("replacement_success_rate", "Not enough history" if metrics["replacement_success_rate"] is None else f"{metrics['replacement_success_rate']:.2f}%"),
        ("false_positive_replacement_rate", "Not enough history" if metrics["false_positive_replacement_rate"] is None else f"{metrics['false_positive_replacement_rate']:.2f}%"),
        ("average_capital_efficiency_improvement", "Not available" if metrics["average_capital_efficiency_improvement"] is None else f"{metrics['average_capital_efficiency_improvement']:.2f} points"),
        ("average_decision_stability_score", "Not available" if metrics["average_decision_stability_score"] is None else f"{metrics['average_decision_stability_score']:.2f} / 100"),
        ("average_evidence_confidence", "Not available" if metrics["average_evidence_confidence"] is None else f"{metrics['average_evidence_confidence']:.2f}%"),
        ("average_holding_period_days", "Not available" if metrics["average_holding_period_days"] is None else f"{metrics['average_holding_period_days']:.2f} days"),
        ("average_sgov_parking_days", "Not available" if metrics["average_sgov_parking_days"] is None else f"{metrics['average_sgov_parking_days']:.2f} days"),
        ("estimated_protection_value", f"${metrics['estimated_protection_value']:.2f}"),
        ("replacement_value_created", f"${metrics['replacement_value_created']:.2f}"),
        ("portfolio_turnover_cost", f"${metrics['portfolio_turnover_cost']:.2f}"),
        ("net_decision_value", f"${metrics['net_decision_value']:.2f}"),
    ]
    for key, value in rows:
        label = METRIC_DETAILS[key]["label"]
        lines.append(f"| {label} | {value} | [More...](#{key.replace('_', '-')}) |")

    lines += ["", "## Improvement Findings", ""]
    for finding in report["improvement_findings"]:
        lines += [
            f"### {finding['severity']}: {finding['title']}",
            "",
            f"**Evidence:** {finding['evidence']}",
            "",
            f"**Recommended review:** {finding['recommendation']}",
            "",
            "No production rule or threshold is changed automatically.",
            "",
        ]

    lines += ["## Metric Reference", ""]
    for key, detail in METRIC_DETAILS.items():
        lines += [
            f"### {detail['label']}",
            f"<a id=\"{key.replace('_', '-')}\"></a>",
            "",
            f"**What is it?** {detail['definition']}",
            "",
            f"**How is it calculated?** {detail['calculation']}",
            "",
            f"**Why does it matter?** {detail['why_it_matters']}",
            "",
        ]
    lines += [
        "## Paper-Only Safety",
        "",
        "This engine analyzes existing paper records only. It does not place orders, contact a broker, or modify production policy automatically.",
    ]
    return "\n".join(lines) + "\n"


def format_ai_cio_performance_analytics_html(report: Mapping[str, Any]) -> str:
    markdown = format_ai_cio_performance_analytics_markdown(report)
    return (
        "<!doctype html><html><head><meta charset='utf-8'><title>AI CIO Performance Analytics</title>"
        "<style>body{font-family:Arial,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;line-height:1.5}"
        "pre{white-space:pre-wrap;background:#f5f7fa;padding:1.5rem;border-radius:10px}</style></head><body>"
        "<pre>" + html.escape(markdown) + "</pre></body></html>"
    )


def write_ai_cio_performance_analytics(
    report: Mapping[str, Any],
    json_path: str | Path = DEFAULT_JSON_PATH,
    markdown_path: str | Path = DEFAULT_MARKDOWN_PATH,
    html_path: str | Path = DEFAULT_HTML_PATH,
) -> dict[str, str]:
    Path(json_path).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    Path(markdown_path).write_text(format_ai_cio_performance_analytics_markdown(report), encoding="utf-8")
    Path(html_path).write_text(format_ai_cio_performance_analytics_html(report), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(markdown_path), "html": str(html_path)}


def build_and_write_ai_cio_performance_analytics(**kwargs: Any) -> dict[str, Any]:
    report = build_ai_cio_performance_analytics(**kwargs)
    report["output_files"] = write_ai_cio_performance_analytics(report)
    return report


def _sample() -> dict[str, Any]:
    decisions = [
        {"action": "KEEP", "decision_stability_score": 84, "evidence_confidence": 94, "portfolio_changed": False},
        {"action": "REPLACE", "decision_stability_score": 81, "evidence_confidence": 92, "portfolio_changed": True},
        {"action": "PARK IN SGOV", "decision_stability_score": 88, "evidence_confidence": 96, "portfolio_changed": True},
    ]
    replacements = [
        {"status": "COMPLETED", "score_difference": 10.2, "replacement_value": 3.05, "turnover_cost": 0.65},
    ]
    protection = [{"estimated_protection_value": 3.70, "parking_days": 4}]
    lifecycle = [{"days_held": 61}, {"days_held": 47}]
    return build_and_write_ai_cio_performance_analytics(
        decisions=decisions,
        replacements=replacements,
        protection_events=protection,
        lifecycle_records=lifecycle,
    )


if __name__ == "__main__":
    result = _sample()
    print(f"AI CIO Performance Analytics: {result['metrics']['self_assessment_score']:.2f} ({result['metrics']['self_assessment_grade']})")
