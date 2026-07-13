"""Paper-only AI CIO Missed Opportunity Review Engine.

Traces rejected, deferred, or temporarily blocked opportunities through the AI CIO
pipeline and determines whether later positive performance reflects a justified
investment decision, normal uncertainty, or a workflow deficiency.
"""
from __future__ import annotations

import html
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

MODULE_NAME = "ai_cio_missed_opportunity_review"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

DEFAULT_OUTPUT_FILES = {
    "json": "ai_cio_missed_opportunity_review.json",
    "markdown": "ai_cio_missed_opportunity_review.md",
    "html": "ai_cio_missed_opportunity_review.html",
}

PIPELINE_STAGES = (
    "DISCOVERY",
    "WATCHLIST",
    "RANKING",
    "OPPORTUNITY_QUALITY",
    "DECISION_STABILITY",
    "EARNINGS_REVIEW",
    "REQUALIFICATION",
    "REPLACEMENT_REVIEW",
)

DETAILS = {
    "significant_missed_opportunity": {
        "label": "Significant Missed Opportunity",
        "definition": "A rejected, deferred, or blocked opportunity that later produced a meaningful positive result.",
        "calculation": "Compares the opportunity's subsequent return with the configured meaningful-return threshold.",
        "why_it_matters": "The AI CIO should learn from future winners it did not own without assuming every missed gain was an error.",
    },
    "decision_path": {
        "label": "Decision Path",
        "definition": "The chronological record of how an opportunity moved through Discovery, Watchlist, Ranking, Earnings, and Replacement Review.",
        "calculation": "Orders supplied stage records and identifies the first failed, blocked, skipped, or missing stage.",
        "why_it_matters": "It reveals exactly where an opportunity stopped being reconsidered.",
    },
    "workflow_deficiency": {
        "label": "Workflow Deficiency",
        "definition": "A process failure that prevented a still-qualified opportunity from being reconsidered after a temporary block or material improvement.",
        "calculation": "Flags missing required follow-up stages, especially absent requalification or replacement review after earnings or score improvement.",
        "why_it_matters": "Improving workflow can recover future wealth without weakening investment standards.",
    },
    "justified_rejection": {
        "label": "Justified Rejection",
        "definition": "A rejection supported by the evidence available at the time, even though the opportunity later performed well.",
        "calculation": "Requires a documented failed gate, sufficient contemporaneous reason, and no missing mandatory reconsideration step.",
        "why_it_matters": "Good investment processes will still miss some winners; hindsight alone must not rewrite policy.",
    },
    "potential_wealth_missed": {
        "label": "Potential Wealth Missed",
        "definition": "An estimate of the dollar value not captured by the paper portfolio.",
        "calculation": "Uses eligible capital multiplied by the positive return difference versus the selected or replacement investment.",
        "why_it_matters": "It helps prioritize process improvements by economic importance rather than by return percentage alone.",
    },
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


def _sequence(value: Any) -> list[Any]:
    return list(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) else []


def _pick(source: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in source and source[key] is not None:
            return source[key]
    return default


def _normalize_status(value: Any) -> str:
    text = str(value or "UNKNOWN").strip().upper().replace(" ", "_")
    aliases = {
        "PASSED": "PASS",
        "FAILED": "FAIL",
        "REJECTED": "FAIL",
        "DEFERRED": "BLOCKED",
        "NOT_RUN": "MISSING",
        "NOT_PERFORMED": "MISSING",
    }
    return aliases.get(text, text)


def _normalize_path(path: Any) -> list[dict[str, Any]]:
    supplied = [row for row in _sequence(path) if isinstance(row, Mapping)]
    by_stage = {}
    extras = []
    for row in supplied:
        stage = str(_pick(row, "stage", "name", default="UNKNOWN")).upper().replace(" ", "_")
        normalized = {
            "stage": stage,
            "status": _normalize_status(_pick(row, "status", "result", default="UNKNOWN")),
            "reason": str(_pick(row, "reason", "explanation", default="No reason supplied.")),
            "score": round(_number(_pick(row, "score", "value", default=0.0)), 4),
            "date": str(_pick(row, "date", "review_date", default="Not supplied")),
        }
        if stage in PIPELINE_STAGES:
            by_stage[stage] = normalized
        else:
            extras.append(normalized)
    ordered = [by_stage[stage] for stage in PIPELINE_STAGES if stage in by_stage]
    return ordered + extras


def _first_exit(path: Sequence[Mapping[str, Any]]) -> tuple[str, str, str]:
    for row in path:
        status = str(row.get("status", "UNKNOWN"))
        if status in {"FAIL", "BLOCKED", "SKIPPED", "MISSING"}:
            return str(row.get("stage", "UNKNOWN")), status, str(row.get("reason", "No reason supplied."))
    return "NONE", "PASS", "No failed or blocked stage was supplied."


def _stage_status(path: Sequence[Mapping[str, Any]], stage: str) -> Optional[str]:
    for row in path:
        if row.get("stage") == stage:
            return str(row.get("status"))
    return None


def _classify(record: Mapping[str, Any], path: Sequence[Mapping[str, Any]], meaningful: bool) -> tuple[str, list[str]]:
    findings: list[str] = []
    if not meaningful:
        return "NOT_SIGNIFICANT", findings

    earnings_block = _stage_status(path, "EARNINGS_REVIEW") == "BLOCKED"
    requalification = _stage_status(path, "REQUALIFICATION")
    replacement = _stage_status(path, "REPLACEMENT_REVIEW")
    qualified_after = bool(_pick(record, "qualified_after_block", "later_qualified", default=False))
    later_score = _number(_pick(record, "later_opportunity_score", "later_rank_score", default=0.0))
    selected_score = _number(_pick(record, "selected_opportunity_score", "replacement_score", default=0.0))

    if earnings_block and requalification in {None, "MISSING", "SKIPPED"}:
        findings.append("No post-earnings requalification was performed after the temporary earnings block.")
        return "WORKFLOW_DEFICIENCY", findings

    if qualified_after and replacement in {None, "MISSING", "SKIPPED"}:
        findings.append("The opportunity later qualified but did not receive a replacement review.")
        return "WORKFLOW_DEFICIENCY", findings

    if later_score > selected_score and replacement in {None, "MISSING", "SKIPPED"}:
        findings.append("The opportunity later outranked the selected investment but was not reconsidered.")
        return "WORKFLOW_DEFICIENCY", findings

    first_stage, first_status, reason = _first_exit(path)
    if first_status in {"FAIL", "BLOCKED"} and reason and reason != "No reason supplied.":
        findings.append(f"The original exit at {first_stage} was documented: {reason}")
        return "JUSTIFIED_REJECTION", findings

    findings.append("The available history is insufficient to determine whether the missed gain resulted from process or normal uncertainty.")
    return "INSUFFICIENT_EVIDENCE", findings


def build_ai_cio_missed_opportunity_review(
    *,
    opportunities: Sequence[Mapping[str, Any]],
    meaningful_return_threshold_percent: float = 15.0,
    meaningful_relative_advantage_percent: float = 5.0,
) -> dict[str, Any]:
    if not isinstance(opportunities, Sequence) or isinstance(opportunities, (str, bytes)):
        raise ValueError("opportunities must be a sequence")

    threshold = max(0.0, _number(meaningful_return_threshold_percent, 15.0))
    relative_threshold = max(0.0, _number(meaningful_relative_advantage_percent, 5.0))
    reviews = []
    warnings = []

    for index, raw in enumerate(opportunities):
        if not isinstance(raw, Mapping):
            warnings.append(f"Opportunity record {index + 1} was ignored because it was not a mapping.")
            continue

        symbol = str(_pick(raw, "symbol", "allocation_id", "candidate", default=f"OPPORTUNITY_{index + 1}")).upper()
        subsequent_return = _number(_pick(raw, "subsequent_return_percent", "future_return_percent", default=0.0))
        selected_return = _number(_pick(raw, "selected_return_percent", "replacement_return_percent", default=0.0))
        relative_advantage = subsequent_return - selected_return
        meaningful = subsequent_return >= threshold and relative_advantage >= relative_threshold
        path = _normalize_path(_pick(raw, "decision_path", "stages", default=[]))
        classification, findings = _classify(raw, path, meaningful)
        first_stage, first_status, first_reason = _first_exit(path)
        eligible_capital = max(0.0, _number(_pick(raw, "eligible_capital", "capital_available", default=0.0)))
        missed_value = eligible_capital * max(0.0, relative_advantage) / 100.0

        recommendation = "No process change recommended."
        if classification == "WORKFLOW_DEFICIENCY":
            if _stage_status(path, "EARNINGS_REVIEW") == "BLOCKED":
                recommendation = "Require automatic post-earnings requalification and renewed replacement competition."
            else:
                recommendation = "Require qualified rejected opportunities to re-enter ranking and replacement review when their evidence materially improves."
        elif classification == "INSUFFICIENT_EVIDENCE":
            recommendation = "Improve decision-path logging before proposing a policy or workflow change."

        reviews.append({
            "symbol": symbol,
            "underlying_stock": str(_pick(raw, "underlying_stock", "underlying", default=symbol)).upper(),
            "sector": str(_pick(raw, "sector", "sector_context", default="UNKNOWN")).upper(),
            "subsequent_return_percent": round(subsequent_return, 4),
            "selected_return_percent": round(selected_return, 4),
            "relative_advantage_percent": round(relative_advantage, 4),
            "eligible_capital": round(eligible_capital, 2),
            "potential_wealth_missed": round(missed_value, 2),
            "significant_missed_opportunity": meaningful,
            "classification": classification,
            "first_exit_stage": first_stage,
            "first_exit_status": first_status,
            "first_exit_reason": first_reason,
            "decision_path": path,
            "findings": findings,
            "recommendation": recommendation,
        })

    significant = [row for row in reviews if row["significant_missed_opportunity"]]
    workflow_deficiencies = [row for row in reviews if row["classification"] == "WORKFLOW_DEFICIENCY"]
    justified = [row for row in reviews if row["classification"] == "JUSTIFIED_REJECTION"]
    insufficient = [row for row in reviews if row["classification"] == "INSUFFICIENT_EVIDENCE"]
    stage_counts = Counter(row["first_exit_stage"] for row in significant)
    total_missed = round(sum(row["potential_wealth_missed"] for row in significant), 2)

    recommendations = []
    if workflow_deficiencies:
        earnings_count = sum(1 for row in workflow_deficiencies if row["first_exit_stage"] == "EARNINGS_REVIEW")
        if earnings_count:
            recommendations.append({
                "title": "Strengthen post-earnings requalification",
                "evidence_count": earnings_count,
                "recommended_action": "Automatically return temporarily blocked candidates to Watchlist, Ranking, and Replacement Review after the cooling period.",
                "status": "AWAITING_INVESTOR_REVIEW",
            })
        other = len(workflow_deficiencies) - earnings_count
        if other:
            recommendations.append({
                "title": "Strengthen candidate revisit rules",
                "evidence_count": other,
                "recommended_action": "Revisit rejected candidates when their ranking, Opportunity Quality, or relative advantage materially improves.",
                "status": "AWAITING_INVESTOR_REVIEW",
            })

    commentary = (
        f"The review analyzed {len(reviews)} rejected or deferred opportunity record(s). "
        f"{len(significant)} later became significant positive opportunities. "
        f"{len(workflow_deficiencies)} were classified as workflow deficiencies, while {len(justified)} remained justified decisions based on the evidence available at the time. "
        "The objective is not to eliminate every missed winner, but to identify candidates that should reasonably have re-entered the ranking and replacement process."
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
        "meaningful_return_threshold_percent": threshold,
        "meaningful_relative_advantage_percent": relative_threshold,
        "opportunities_reviewed": len(reviews),
        "significant_missed_opportunity_count": len(significant),
        "workflow_deficiency_count": len(workflow_deficiencies),
        "justified_rejection_count": len(justified),
        "insufficient_evidence_count": len(insufficient),
        "estimated_total_potential_wealth_missed": total_missed,
        "exit_stage_summary": dict(sorted(stage_counts.items())),
        "reviews": reviews,
        "improvement_recommendations": recommendations,
        "ai_cio_commentary": commentary,
        "governance": {
            "automatic_policy_changes_allowed": False,
            "automatic_workflow_changes_allowed": False,
            "investor_approval_required": True,
            "historical_outperformance_alone_proves_error": False,
            "paper_only": True,
        },
        "details": DETAILS,
        "warnings": warnings,
        "errors": [],
    }


def format_ai_cio_missed_opportunity_review_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# AI CIO Missed Opportunity Review",
        "",
        "## Executive Summary",
        "",
        f"- **Opportunities Reviewed:** {report.get('opportunities_reviewed', 0)}",
        f"- **Significant Missed Opportunities:** {report.get('significant_missed_opportunity_count', 0)}",
        f"- **Workflow Deficiencies:** {report.get('workflow_deficiency_count', 0)}",
        f"- **Justified Rejections:** {report.get('justified_rejection_count', 0)}",
        f"- **Estimated Potential Wealth Missed:** ${_number(report.get('estimated_total_potential_wealth_missed')):,.2f}",
        "",
        "## Opportunity Reviews",
        "",
        "| Opportunity | Underlying | Return | Relative Advantage | Classification | Exit Stage | Potential Wealth Missed |",
        "|---|---|---:|---:|---|---|---:|",
    ]
    for row in _sequence(report.get("reviews")):
        if isinstance(row, Mapping):
            lines.append(
                f"| {row.get('symbol')} | {row.get('underlying_stock')} | {_number(row.get('subsequent_return_percent')):.2f}% | "
                f"{_number(row.get('relative_advantage_percent')):.2f}% | {str(row.get('classification')).replace('_', ' ').title()} | "
                f"{str(row.get('first_exit_stage')).replace('_', ' ').title()} | ${_number(row.get('potential_wealth_missed')):,.2f} |"
            )
            lines.extend(["", f"### {row.get('symbol')} Decision Path", "", "| Stage | Status | Score | Date | Reason |", "|---|---|---:|---|---|"])
            for step in _sequence(row.get("decision_path")):
                if isinstance(step, Mapping):
                    lines.append(f"| {str(step.get('stage')).replace('_', ' ').title()} | {step.get('status')} | {_number(step.get('score')):.2f} | {step.get('date')} | {step.get('reason')} |")
            lines.extend(["", f"**Recommendation:** {row.get('recommendation')}", ""])

    lines.extend(["## AI CIO Commentary", "", str(report.get("ai_cio_commentary", "No commentary available.")), "", "## Improvement Recommendations", ""])
    recommendations = _sequence(report.get("improvement_recommendations"))
    if recommendations:
        for item in recommendations:
            if isinstance(item, Mapping):
                lines.extend([f"### {item.get('title')}", "", f"- **Evidence Count:** {item.get('evidence_count', 0)}", f"- **Recommended Action:** {item.get('recommended_action')}", f"- **Status:** {item.get('status')}", ""])
    else:
        lines.append("No workflow change is recommended from the supplied evidence.")

    for detail in DETAILS.values():
        lines.extend(["", f"## {detail['label']}", "", f"**What it means:** {detail['definition']}", "", f"**How it is calculated:** {detail['calculation']}", "", f"**Why it matters:** {detail['why_it_matters']}"])

    lines.extend(["", "## Governance and Paper-Only Safety", "", "This engine reviews missed opportunities and recommends process improvements only. It cannot change policy, alter workflow rules, place orders, or communicate with a brokerage. Historical outperformance alone does not prove that the original decision was wrong.", ""])
    return "\n".join(lines)


def format_ai_cio_missed_opportunity_review_html(report: Mapping[str, Any]) -> str:
    markdown = format_ai_cio_missed_opportunity_review_markdown(report)
    return "<!doctype html><html><head><meta charset='utf-8'><title>AI CIO Missed Opportunity Review</title><style>body{font-family:Arial,sans-serif;max-width:1200px;margin:0 auto;padding:32px;background:#f5f7fb;color:#172033}pre{white-space:pre-wrap;background:white;padding:30px;border-radius:14px;box-shadow:0 4px 18px rgba(0,0,0,.08);line-height:1.55}</style></head><body><pre>" + html.escape(markdown) + "</pre></body></html>"


def write_ai_cio_missed_opportunity_review(payload: Mapping[str, Any], root_path: str = ".", output_files: Optional[Mapping[str, str]] = None) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    report = build_ai_cio_missed_opportunity_review(**dict(payload))
    root = Path(root_path)
    files = dict(DEFAULT_OUTPUT_FILES)
    if output_files:
        files.update(output_files)
    (root / files["json"]).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / files["markdown"]).write_text(format_ai_cio_missed_opportunity_review_markdown(report), encoding="utf-8")
    (root / files["html"]).write_text(format_ai_cio_missed_opportunity_review_html(report), encoding="utf-8")
    return report


def build_and_write_ai_cio_missed_opportunity_review(payload: Mapping[str, Any], root_path: str = ".", output_files: Optional[Mapping[str, str]] = None) -> dict[str, Any]:
    return write_ai_cio_missed_opportunity_review(payload, root_path, output_files)


if __name__ == "__main__":
    sample = {
        "opportunities": [
            {
                "symbol": "AMDW + PLTU",
                "underlying_stock": "PLTR",
                "sector": "Technology",
                "subsequent_return_percent": 38.0,
                "selected_return_percent": 12.0,
                "eligible_capital": 10000,
                "qualified_after_block": True,
                "later_opportunity_score": 95,
                "selected_opportunity_score": 86,
                "decision_path": [
                    {"stage": "DISCOVERY", "status": "PASS", "score": 84, "date": "2026-05-01", "reason": "Discovered and eligible."},
                    {"stage": "WATCHLIST", "status": "PASS", "score": 86, "date": "2026-05-03", "reason": "Promoted to watchlist."},
                    {"stage": "RANKING", "status": "PASS", "score": 91, "date": "2026-05-10", "reason": "Rank improved."},
                    {"stage": "EARNINGS_REVIEW", "status": "BLOCKED", "score": 0, "date": "2026-05-12", "reason": "PLTR earnings event within protection window."},
                    {"stage": "REQUALIFICATION", "status": "MISSING", "score": 0, "date": "Not supplied", "reason": "Post-earnings requalification was not performed."},
                ],
            },
            {
                "symbol": "XYZI",
                "underlying_stock": "XYZ",
                "sector": "Healthcare",
                "subsequent_return_percent": 22.0,
                "selected_return_percent": 18.0,
                "eligible_capital": 5000,
                "decision_path": [
                    {"stage": "DISCOVERY", "status": "PASS", "score": 76, "date": "2026-04-01", "reason": "Discovered."},
                    {"stage": "DECISION_STABILITY", "status": "FAIL", "score": 58, "date": "2026-04-03", "reason": "Evidence confidence was below the required threshold."},
                ],
            },
        ]
    }
    result = write_ai_cio_missed_opportunity_review(sample)
    print(f"Workflow deficiencies: {result['workflow_deficiency_count']}")
