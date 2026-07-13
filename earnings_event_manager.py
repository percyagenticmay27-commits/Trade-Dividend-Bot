"""Paper-only Earnings Event Manager for the Trade Dividend Bot AI CIO.

Coordinates earnings-event detection, protection windows, SGOV parking,
release conditions, re-entry review, replacement competition, lifecycle
updates, and decision-journal records. It never places orders or communicates
with a brokerage.
"""
from __future__ import annotations

import html
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

MODULE_NAME = "earnings_event_manager"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

DEFAULT_OUTPUT_FILES = {
    "json": "earnings_event_manager.json",
    "markdown": "earnings_event_manager.md",
    "html": "earnings_event_manager.html",
}

ACTIONS = (
    "NO_ACTION",
    "MONITOR",
    "PREPARE_SGOV",
    "PARK_IN_SGOV",
    "HOLD_IN_SGOV",
    "REENTRY_REVIEW",
    "REENTER_PRIOR",
    "ALLOCATE_TO_BEST_CANDIDATE",
)

DETAILS = {
    "earnings_status": {
        "label": "Earnings Status",
        "definition": "Shows where an allocation is in relation to an upcoming or recently completed earnings event.",
        "calculation": "Compares the event date with the evaluation date and the configured protection and release windows.",
        "why_it_matters": "Earnings can create sudden price gaps that may not be reflected in normal daily risk measurements.",
    },
    "event_risk_score": {
        "label": "Event Risk Score",
        "definition": "A 0 to 100 estimate of near-term earnings-event exposure.",
        "calculation": "Combines event proximity, allocation weight, leverage, data confidence, and supplied event-risk evidence.",
        "why_it_matters": "It helps determine whether monitoring is sufficient or temporary protection should be considered.",
    },
    "sgov_status": {
        "label": "SGOV Protection Status",
        "definition": "Shows whether capital is active, scheduled for protection, or temporarily parked in SGOV.",
        "calculation": "Derived from event timing, mandatory protection rules, and the current lifecycle state.",
        "why_it_matters": "It explains where protected capital is held and what must occur before it can be redeployed.",
    },
    "release_condition": {
        "label": "Release Condition",
        "definition": "The evidence requirements that must pass before protected capital may leave SGOV.",
        "calculation": "Requires the earnings event to be complete, data to be valid, the post-event cooling period to pass, and a current opportunity to qualify.",
        "why_it_matters": "Capital does not automatically return to its prior allocation after earnings.",
    },
    "reentry_status": {
        "label": "Re-entry Status",
        "definition": "Shows whether the prior allocation or another candidate currently qualifies for the released capital.",
        "calculation": "Compares current candidates using their qualification, risk, evidence confidence, and opportunity ranking.",
        "why_it_matters": "The strongest current opportunity should receive capital after protection clears, without loyalty to the prior holding.",
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


def _clamp(value: Any) -> float:
    return round(max(0.0, min(100.0, _number(value))), 4)


def _as_date(value: Any) -> Optional[date]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None


def _normalize_allocations(allocations: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(allocations or []):
        if not isinstance(item, Mapping):
            continue
        allocation_id = str(item.get("allocation_id") or item.get("name") or f"ALLOCATION_{index + 1}").strip().upper()
        symbols = item.get("symbols") or item.get("components") or []
        if isinstance(symbols, str):
            symbols = [part.strip().upper() for part in symbols.replace("+", ",").split(",") if part.strip()]
        elif isinstance(symbols, Sequence):
            symbols = [str(part).strip().upper() for part in symbols if str(part).strip()]
        else:
            symbols = []
        normalized.append({
            "allocation_id": allocation_id,
            "symbols": symbols,
            "allocation_percent": max(0.0, _number(item.get("allocation_percent", item.get("weight_percent", 0.0)))),
            "paper_value": max(0.0, _number(item.get("paper_value", 0.0))),
            "lifecycle_state": str(item.get("lifecycle_state") or "ACTIVE").upper(),
            "currently_in_sgov": bool(item.get("currently_in_sgov", False) or str(item.get("lifecycle_state", "")).upper() == "PARKED_IN_SGOV"),
            "leverage_multiplier": max(0.0, _number(item.get("leverage_multiplier", 1.0), 1.0)),
            "current_candidate_score": _clamp(item.get("current_candidate_score", item.get("capital_efficiency_score", 0.0))),
        })
    return normalized


def _normalize_events(events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(events or []):
        if not isinstance(item, Mapping):
            continue
        event_date = _as_date(item.get("earnings_date") or item.get("event_date"))
        normalized.append({
            "event_id": str(item.get("event_id") or f"EARNINGS_{index + 1}").strip(),
            "symbol": str(item.get("symbol") or item.get("underlying_symbol") or "UNKNOWN").strip().upper(),
            "earnings_date": event_date,
            "confirmed": bool(item.get("confirmed", event_date is not None)),
            "event_risk": _clamp(item.get("event_risk", item.get("risk_score", 50.0))),
            "evidence_confidence": _clamp(item.get("evidence_confidence", 100.0)),
            "data_stale": bool(item.get("data_stale", False)),
            "completed": bool(item.get("completed", False)),
            "post_event_data_valid": bool(item.get("post_event_data_valid", True)),
        })
    return normalized


def _best_candidate(candidates: Sequence[Mapping[str, Any]]) -> Optional[dict[str, Any]]:
    valid: list[dict[str, Any]] = []
    for item in candidates or []:
        if not isinstance(item, Mapping):
            continue
        if not bool(item.get("qualified", True)):
            continue
        if bool(item.get("earnings_lock", False)) or bool(item.get("mandatory_risk_breach", False)) or bool(item.get("data_stale", False)):
            continue
        confidence = _clamp(item.get("evidence_confidence", 0.0))
        score = _clamp(item.get("capital_efficiency_score", item.get("score", 0.0)))
        if confidence < 70.0:
            continue
        valid.append({
            "candidate_id": str(item.get("candidate_id") or item.get("allocation_id") or item.get("name") or "UNKNOWN").strip().upper(),
            "capital_efficiency_score": score,
            "evidence_confidence": confidence,
            "is_prior_allocation": bool(item.get("is_prior_allocation", False)),
        })
    if not valid:
        return None
    return sorted(valid, key=lambda row: (row["capital_efficiency_score"], row["evidence_confidence"]), reverse=True)[0]


def _event_for_allocation(allocation: Mapping[str, Any], events: Sequence[Mapping[str, Any]]) -> Optional[dict[str, Any]]:
    symbols = set(allocation.get("symbols") or [])
    if not symbols:
        symbols.add(str(allocation.get("allocation_id", "")).upper())
    matches = [event for event in events if event.get("symbol") in symbols]
    if not matches:
        return None
    dated = [event for event in matches if event.get("earnings_date") is not None]
    return sorted(dated or matches, key=lambda event: event.get("earnings_date") or date.max)[0]


def _evaluate_record(
    allocation: Mapping[str, Any],
    event: Optional[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    evaluation_date: date,
    protection_window_days: int,
    prepare_window_days: int,
    post_event_cooling_days: int,
) -> dict[str, Any]:
    best = _best_candidate(candidates)
    action = "NO_ACTION"
    status = "NO_EVENT"
    days_to_event: Optional[int] = None
    event_risk = 0.0
    release_condition = "No earnings protection is active."
    next_review = None
    reason = "No confirmed earnings event is currently associated with this allocation."
    journal_event = None
    lifecycle_update = None

    if event is not None:
        event_date = event.get("earnings_date")
        if event_date is None or not event.get("confirmed") or event.get("data_stale"):
            status = "DATA_REVIEW_REQUIRED"
            action = "MONITOR"
            event_risk = max(50.0, _clamp(event.get("event_risk", 50.0)))
            reason = "The earnings record is incomplete, unconfirmed, or stale; no automatic protection decision is made from unreliable data."
            next_review = evaluation_date.isoformat()
        else:
            days_to_event = (event_date - evaluation_date).days
            proximity = 100.0 if days_to_event <= 0 else max(0.0, 100.0 - (days_to_event / max(protection_window_days, 1)) * 60.0)
            leverage = max(1.0, _number(allocation.get("leverage_multiplier"), 1.0))
            weight = min(100.0, _number(allocation.get("allocation_percent")))
            event_risk = _clamp(_number(event.get("event_risk")) * 0.55 + proximity * 0.25 + min(100.0, weight * leverage) * 0.20)

            if event.get("completed") or days_to_event < 0:
                status = "POST_EVENT_REVIEW"
                release_condition = (
                    f"Earnings must be complete, post-event data must be valid, the {post_event_cooling_days}-day cooling period must pass, "
                    "and the strongest current candidate must satisfy all qualification and risk gates."
                )
                cooling_complete = days_to_event <= -post_event_cooling_days
                if allocation.get("currently_in_sgov"):
                    if not event.get("post_event_data_valid", True):
                        action = "HOLD_IN_SGOV"
                        reason = "Earnings are complete, but post-event evidence is not yet valid enough to redeploy protected capital."
                    elif not cooling_complete:
                        action = "HOLD_IN_SGOV"
                        reason = "Earnings are complete, but the post-event cooling period has not yet finished."
                    elif best is None:
                        action = "REENTRY_REVIEW"
                        reason = "Protection has cleared, but no qualified opportunity currently earns the released capital."
                    elif best.get("is_prior_allocation"):
                        action = "REENTER_PRIOR"
                        reason = "The prior allocation requalified and is the strongest current opportunity after earnings protection cleared."
                    else:
                        action = "ALLOCATE_TO_BEST_CANDIDATE"
                        reason = f"Protection cleared and {best['candidate_id']} is now the strongest qualified opportunity for the released capital."
                    next_review = (event_date).isoformat()
                else:
                    action = "MONITOR"
                    reason = "The earnings event is complete; the allocation should be reviewed using current post-event evidence."
                    next_review = evaluation_date.isoformat()
            elif days_to_event <= protection_window_days:
                status = "PROTECTION_WINDOW"
                release_condition = (
                    f"Remain protected until earnings are complete, post-event data is valid, the {post_event_cooling_days}-day cooling period passes, "
                    "and a qualified opportunity wins the new ranking."
                )
                next_review = event_date.isoformat()
                if allocation.get("currently_in_sgov"):
                    action = "HOLD_IN_SGOV"
                    reason = "Capital is already protected in SGOV while the earnings event remains active."
                else:
                    action = "PARK_IN_SGOV"
                    reason = "The allocation entered the mandatory earnings-protection window; its paper capital should be temporarily parked in SGOV."
                    journal_event = "EARNINGS_PROTECTION_STARTED"
                    lifecycle_update = "PARKED_IN_SGOV"
            elif days_to_event <= prepare_window_days:
                status = "PREPARE_WINDOW"
                action = "PREPARE_SGOV"
                next_review = (event_date).isoformat()
                reason = "The earnings event is approaching; prepare the SGOV protection workflow but do not move capital yet."
            else:
                status = "MONITORING"
                action = "MONITOR"
                next_review = (event_date).isoformat()
                reason = "A confirmed earnings event exists outside the active preparation window."

    return {
        "allocation_id": allocation.get("allocation_id"),
        "symbols": list(allocation.get("symbols") or []),
        "allocation_percent": round(_number(allocation.get("allocation_percent")), 4),
        "earnings_status": status,
        "earnings_date": event.get("earnings_date").isoformat() if event and event.get("earnings_date") else None,
        "days_to_event": days_to_event,
        "event_risk_score": event_risk,
        "recommended_action": action,
        "sgov_status": "PARKED" if allocation.get("currently_in_sgov") else ("PARK_RECOMMENDED" if action == "PARK_IN_SGOV" else "NOT_PARKED"),
        "release_condition": release_condition,
        "next_review": next_review,
        "best_candidate": best,
        "reason": reason,
        "decision_journal_event": journal_event,
        "lifecycle_update": lifecycle_update,
        "investor_control": "No action is required in autonomous paper mode. Review, override, defer, or revert remains available.",
    }


def build_earnings_event_manager(
    *,
    allocations: Sequence[Mapping[str, Any]],
    earnings_events: Sequence[Mapping[str, Any]],
    candidates_by_allocation: Optional[Mapping[str, Sequence[Mapping[str, Any]]]] = None,
    evaluation_date: Any = None,
    protection_window_days: int = 2,
    prepare_window_days: int = 7,
    post_event_cooling_days: int = 1,
) -> dict[str, Any]:
    """Build the current paper-only earnings-event management report."""
    if not isinstance(allocations, Sequence) or isinstance(allocations, (str, bytes)):
        raise ValueError("allocations must be a sequence")
    if not isinstance(earnings_events, Sequence) or isinstance(earnings_events, (str, bytes)):
        raise ValueError("earnings_events must be a sequence")
    if candidates_by_allocation is not None and not isinstance(candidates_by_allocation, Mapping):
        raise ValueError("candidates_by_allocation must be a mapping")

    normalized_allocations = _normalize_allocations(allocations)
    normalized_events = _normalize_events(earnings_events)
    as_of = _as_date(evaluation_date) or datetime.now(timezone.utc).date()
    protection = max(0, int(_number(protection_window_days, 2)))
    prepare = max(protection, int(_number(prepare_window_days, 7)))
    cooling = max(0, int(_number(post_event_cooling_days, 1)))
    candidate_map = candidates_by_allocation or {}

    records = []
    for allocation in normalized_allocations:
        event = _event_for_allocation(allocation, normalized_events)
        candidates = candidate_map.get(allocation["allocation_id"], [])
        records.append(_evaluate_record(allocation, event, candidates, as_of, protection, prepare, cooling))

    counts = {action: 0 for action in ACTIONS}
    for record in records:
        counts[record["recommended_action"]] = counts.get(record["recommended_action"], 0) + 1

    warnings: list[str] = []
    if not normalized_allocations:
        warnings.append("No allocation records were supplied; no earnings workflows were evaluated.")
    if not normalized_events:
        warnings.append("No earnings-event records were supplied; all allocations default to no-event status.")

    active = [record for record in records if record["recommended_action"] in {"PREPARE_SGOV", "PARK_IN_SGOV", "HOLD_IN_SGOV", "REENTRY_REVIEW", "REENTER_PRIOR", "ALLOCATE_TO_BEST_CANDIDATE"}]
    commentary = (
        f"The Earnings Event Manager reviewed {len(records)} paper allocations and identified {len(active)} active earnings workflows. "
        f"{counts.get('PARK_IN_SGOV', 0)} allocations require temporary SGOV protection, and {counts.get('REENTRY_REVIEW', 0) + counts.get('REENTER_PRIOR', 0) + counts.get('ALLOCATE_TO_BEST_CANDIDATE', 0)} require post-event capital review. "
        "After earnings, capital does not automatically return to the prior investment; all qualified opportunities compete again using current evidence."
    )

    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "evaluation_date": as_of.isoformat(),
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "reporting_only": True,
        "protection_window_days": protection,
        "prepare_window_days": prepare,
        "post_event_cooling_days": cooling,
        "allocation_count": len(normalized_allocations),
        "event_count": len(normalized_events),
        "active_workflow_count": len(active),
        "action_counts": counts,
        "records": records,
        "details": DETAILS,
        "ai_cio_commentary": commentary,
        "warnings": warnings,
        "errors": [],
    }


def format_earnings_event_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Earnings Event Manager",
        "",
        "## Executive Summary",
        "",
        f"- **Allocations Reviewed:** {report.get('allocation_count', 0)}",
        f"- **Active Earnings Workflows:** {report.get('active_workflow_count', 0)}",
        f"- **Evaluation Date:** {report.get('evaluation_date', 'Unknown')}",
        "",
        "## Earnings Actions",
        "",
        "| Allocation | Earnings Status | Event Date | Risk Score | Recommended Action | SGOV Status | Next Review |",
        "|---|---|---|---:|---|---|---|",
    ]
    for record in report.get("records") or []:
        lines.append(
            f"| {record.get('allocation_id')} | {str(record.get('earnings_status')).replace('_', ' ').title()} | "
            f"{record.get('earnings_date') or 'Not available'} | {_number(record.get('event_risk_score')):.2f} / 100 | "
            f"{str(record.get('recommended_action')).replace('_', ' ').title()} | {str(record.get('sgov_status')).replace('_', ' ').title()} | "
            f"{record.get('next_review') or 'As needed'} |"
        )
    lines.extend(["", "## AI CIO Commentary", "", str(report.get("ai_cio_commentary", "No commentary available.")), ""])
    for record in report.get("records") or []:
        lines.extend([
            f"## {record.get('allocation_id')} Review",
            "",
            f"**Recommendation:** {str(record.get('recommended_action')).replace('_', ' ').title()}",
            "",
            f"**Why:** {record.get('reason')}",
            "",
            f"**Release Condition:** {record.get('release_condition')}",
            "",
            f"**Investor Control:** {record.get('investor_control')}",
            "",
        ])
    lines.extend(["## Metric Reference", ""])
    for key, detail in DETAILS.items():
        lines.extend([
            f"### {detail['label']}",
            "",
            f"**What it means:** {detail['definition']}",
            "",
            f"**How it is calculated:** {detail['calculation']}",
            "",
            f"**Why it matters:** {detail['why_it_matters']}",
            "",
        ])
    lines.extend([
        "## Paper-Only Safety",
        "",
        "This manager creates advisory and autonomous paper-management instructions only. It does not place orders or communicate with a brokerage.",
        "",
    ])
    return "\n".join(lines)


def format_earnings_event_html(report: Mapping[str, Any]) -> str:
    escaped = html.escape(format_earnings_event_markdown(report))
    return (
        "<!doctype html><html><head><meta charset='utf-8'><title>Earnings Event Manager</title>"
        "<style>body{font-family:Arial,sans-serif;max-width:1200px;margin:0 auto;padding:32px;background:#f5f7fb;color:#172033}"
        "pre{white-space:pre-wrap;background:white;padding:28px;border-radius:14px;box-shadow:0 4px 18px rgba(0,0,0,.08);line-height:1.5}</style>"
        "</head><body><pre>" + escaped + "</pre></body></html>"
    )


def write_earnings_event_manager(
    payload: Mapping[str, Any],
    root_path: str = ".",
    output_files: Optional[Mapping[str, str]] = None,
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    report = build_earnings_event_manager(**dict(payload))
    root = Path(root_path)
    files = dict(DEFAULT_OUTPUT_FILES)
    if output_files:
        files.update(output_files)
    (root / files["json"]).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / files["markdown"]).write_text(format_earnings_event_markdown(report), encoding="utf-8")
    (root / files["html"]).write_text(format_earnings_event_html(report), encoding="utf-8")
    return report


def build_and_write_earnings_event_manager(
    payload: Mapping[str, Any],
    root_path: str = ".",
    output_files: Optional[Mapping[str, str]] = None,
) -> dict[str, Any]:
    return write_earnings_event_manager(payload, root_path, output_files)


if __name__ == "__main__":
    today = datetime.now(timezone.utc).date()
    sample = {
        "evaluation_date": today.isoformat(),
        "allocations": [
            {"allocation_id": "AMDW + PLTU", "symbols": ["AMD", "PLTR"], "allocation_percent": 40, "paper_value": 200, "leverage_multiplier": 1.5},
            {"allocation_id": "QQQI + TQQQ", "symbols": ["QQQI", "TQQQ"], "allocation_percent": 30, "paper_value": 150},
        ],
        "earnings_events": [
            {"event_id": "PLTR_Q2", "symbol": "PLTR", "earnings_date": today.isoformat(), "confirmed": True, "event_risk": 85, "evidence_confidence": 98},
        ],
        "candidates_by_allocation": {
            "AMDW + PLTU": [
                {"candidate_id": "AMDW + PLTU", "capital_efficiency_score": 84.3, "evidence_confidence": 94, "qualified": True, "is_prior_allocation": True},
                {"candidate_id": "AMDW + GGLL", "capital_efficiency_score": 86.3, "evidence_confidence": 92, "qualified": True},
            ]
        },
    }
    result = write_earnings_event_manager(sample)
    print(f"Active earnings workflows: {result['active_workflow_count']}")
