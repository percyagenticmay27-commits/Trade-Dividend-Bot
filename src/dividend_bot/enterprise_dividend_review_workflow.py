"""Governed Enterprise Dividend Review Workflow.

Routes paper-only dividend alerts into structured, traceable human-review records.
The module is workflow and reporting only. It cannot contact a broker, place an
order, move capital, approve an investment action, or silently change policy.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

MODULE_NAME = "enterprise_dividend_review_workflow"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True
ADVISORY_ONLY = True
HUMAN_APPROVAL_REQUIRED = True

REVIEW_STATUSES = {"OPEN", "UNDER_REVIEW", "RESOLVED", "DEFERRED", "ESCALATED"}
TERMINAL_STATUSES = {"RESOLVED"}
ACTIVE_STATUSES = REVIEW_STATUSES - TERMINAL_STATUSES

VALID_TRANSITIONS = {
    "OPEN": {"UNDER_REVIEW", "DEFERRED", "ESCALATED", "RESOLVED"},
    "UNDER_REVIEW": {"DEFERRED", "ESCALATED", "RESOLVED"},
    "DEFERRED": {"UNDER_REVIEW", "ESCALATED", "RESOLVED"},
    "ESCALATED": {"UNDER_REVIEW", "DEFERRED", "RESOLVED"},
    "RESOLVED": set(),
}

DEFAULT_OUTPUT_FILES = {
    "json": "enterprise_dividend_reviews.json",
    "markdown": "enterprise_dividend_reviews.md",
}


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _upper(value: Any, default: str = "UNKNOWN") -> str:
    text = str(value or default).strip()
    return text.upper() if text else default


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, Sequence):
        return []
    return sorted({str(item).strip() for item in value if str(item).strip()})


def _review_key(alert: Mapping[str, Any]) -> str:
    source = str(
        alert.get("deduplication_key")
        or alert.get("alert_id")
        or "|".join(
            (
                _upper(alert.get("symbol"), "PORTFOLIO"),
                _upper(alert.get("alert_type"), "REVIEW_REQUIRED"),
                str(alert.get("source_module") or "unknown_source"),
                str(alert.get("reporting_period") or "CURRENT"),
            )
        )
    )
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _review_id(review_key: str) -> str:
    return f"DIV-REVIEW-{review_key[:16].upper()}"


def _priority_from_severity(severity: str) -> str:
    return {
        "CRITICAL": "URGENT",
        "HIGH": "HIGH",
        "MEDIUM": "MEDIUM",
        "LOW": "LOW",
        "INFO": "ROUTINE",
    }.get(severity, "MEDIUM")


def _history_event(
    *,
    from_status: Optional[str],
    to_status: str,
    timestamp: str,
    actor: str,
    reason: str,
    decision_reference: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "from_status": from_status,
        "to_status": to_status,
        "timestamp_utc": timestamp,
        "actor": actor,
        "reason": reason,
        "decision_reference": decision_reference,
    }


def _new_review(alert: Mapping[str, Any], generated_at: str) -> dict[str, Any]:
    key = _review_key(alert)
    severity = _upper(alert.get("severity"), "MEDIUM")
    alert_id = str(alert.get("alert_id") or "")
    evidence_links = _string_list(alert.get("evidence_links") or alert.get("evidence"))
    source_report = str(alert.get("source_report") or "")
    analytics_links = _string_list(
        alert.get("analytics_links")
        or alert.get("originating_analytics")
        or alert.get("analytics_references")
    )
    report_links = _string_list(alert.get("report_links") or ([source_report] if source_report else []))
    decision_links = _string_list(alert.get("decision_links") or alert.get("decision_references"))

    return {
        "review_id": _review_id(key),
        "review_key": key,
        "status": "OPEN",
        "priority": _priority_from_severity(severity),
        "symbol": _upper(alert.get("symbol"), "PORTFOLIO"),
        "alert_id": alert_id,
        "alert_type": _upper(alert.get("alert_type"), "REVIEW_REQUIRED"),
        "alert_severity": severity,
        "title": str(alert.get("message") or "Dividend finding requires governed review."),
        "recommended_review_action": str(
            alert.get("recommended_action")
            or "Review the originating evidence before approving any portfolio action."
        ),
        "source_module": str(alert.get("source_module") or "enterprise_dividend_alert_integration"),
        "source_report": source_report,
        "reporting_period": str(alert.get("reporting_period") or "CURRENT"),
        "originating_analytics_links": analytics_links,
        "originating_report_links": report_links,
        "originating_evidence_links": evidence_links,
        "decision_links": decision_links,
        "assigned_reviewer": None,
        "review_notes": [],
        "resolution": None,
        "deferred_until_utc": None,
        "escalation_reason": None,
        "created_at_utc": generated_at,
        "last_updated_at_utc": generated_at,
        "status_history": [
            _history_event(
                from_status=None,
                to_status="OPEN",
                timestamp=generated_at,
                actor="SYSTEM",
                reason="Created from governed dividend alert.",
            )
        ],
        "paper_trade_mode": True,
        "advisory_only": True,
        "human_approval_required": True,
    }


def _merge_existing_review(
    candidate: Mapping[str, Any], existing: Mapping[str, Any], generated_at: str
) -> dict[str, Any]:
    merged = dict(candidate)
    status = _upper(existing.get("status"), "OPEN")
    if status not in REVIEW_STATUSES:
        status = "OPEN"
    for field in (
        "review_id",
        "created_at_utc",
        "assigned_reviewer",
        "review_notes",
        "resolution",
        "deferred_until_utc",
        "escalation_reason",
        "status_history",
        "decision_links",
    ):
        if field in existing:
            merged[field] = existing[field]
    merged["status"] = status
    merged["last_updated_at_utc"] = generated_at
    merged["originating_analytics_links"] = _string_list(
        list(merged.get("originating_analytics_links") or [])
        + list(existing.get("originating_analytics_links") or [])
    )
    merged["originating_report_links"] = _string_list(
        list(merged.get("originating_report_links") or [])
        + list(existing.get("originating_report_links") or [])
    )
    merged["originating_evidence_links"] = _string_list(
        list(merged.get("originating_evidence_links") or [])
        + list(existing.get("originating_evidence_links") or [])
    )
    merged["decision_links"] = _string_list(merged.get("decision_links"))
    merged["review_notes"] = _rows(merged.get("review_notes"))
    merged["status_history"] = _rows(merged.get("status_history"))
    return merged


def build_enterprise_dividend_reviews(
    *,
    alert_report: Optional[Mapping[str, Any]] = None,
    alerts: Optional[Sequence[Mapping[str, Any]]] = None,
    existing_reviews: Optional[Sequence[Mapping[str, Any]]] = None,
    include_resolved_alerts: bool = False,
    generated_at_utc: Optional[str] = None,
) -> dict[str, Any]:
    """Create or refresh one governed review record per unique dividend alert."""
    generated_at = generated_at_utc or _now_utc()
    source_report = dict(alert_report or {})
    alert_rows = _rows(alerts if alerts is not None else source_report.get("alerts") or [])
    previous_rows = _rows(existing_reviews or [])
    previous_by_key = {
        str(item.get("review_key")): item for item in previous_rows if item.get("review_key")
    }

    warnings: list[str] = []
    if alert_report is None and alerts is None:
        warnings.append("Enterprise dividend alert input was not supplied.")

    candidates: dict[str, dict[str, Any]] = {}
    ignored_resolved_alerts = 0
    for alert in alert_rows:
        alert_status = _upper(alert.get("status"), "OPEN")
        if alert_status == "RESOLVED" and not include_resolved_alerts:
            ignored_resolved_alerts += 1
            continue
        candidate = _new_review(alert, generated_at)
        candidates[candidate["review_key"]] = candidate

    reviews: list[dict[str, Any]] = []
    for key, candidate in candidates.items():
        existing = previous_by_key.get(key)
        reviews.append(
            _merge_existing_review(candidate, existing, generated_at) if existing else candidate
        )

    priority_order = {"URGENT": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "ROUTINE": 4}
    reviews.sort(
        key=lambda row: (
            priority_order.get(str(row.get("priority")), 9),
            str(row.get("symbol")),
            str(row.get("review_id")),
        )
    )
    status_counts = {
        status.lower(): sum(1 for item in reviews if item.get("status") == status)
        for status in sorted(REVIEW_STATUSES)
    }

    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "reporting_only": True,
        "advisory_only": True,
        "human_approval_required": True,
        "workflow_status": "READY" if alert_report is not None or alerts is not None else "PARTIAL",
        "summary": {
            "total_reviews": len(reviews),
            "active_reviews": sum(1 for item in reviews if item.get("status") in ACTIVE_STATUSES),
            "urgent_reviews": sum(1 for item in reviews if item.get("priority") == "URGENT"),
            "ignored_resolved_alerts": ignored_resolved_alerts,
            **status_counts,
        },
        "reviews": reviews,
        "warnings": warnings,
        "governance_notes": [
            "Review records preserve originating alert, analytics, report, evidence, and decision links.",
            "No review state authorizes brokerage execution or capital movement.",
            "Resolution records a human-governed conclusion only; downstream action requires separate approval.",
        ],
    }


def transition_review(
    review: Mapping[str, Any],
    *,
    to_status: str,
    actor: str,
    reason: str,
    generated_at_utc: Optional[str] = None,
    assigned_reviewer: Optional[str] = None,
    note: Optional[str] = None,
    resolution: Optional[str] = None,
    deferred_until_utc: Optional[str] = None,
    escalation_reason: Optional[str] = None,
    decision_reference: Optional[str] = None,
) -> dict[str, Any]:
    """Return a new review snapshot with one validated append-only transition."""
    item = dict(review)
    current = _upper(item.get("status"), "OPEN")
    target = _upper(to_status)
    if current not in REVIEW_STATUSES:
        raise ValueError(f"Unsupported current review status: {current}")
    if target not in REVIEW_STATUSES:
        raise ValueError(f"Unsupported target review status: {target}")
    if target == current:
        raise ValueError("Review transition must change status.")
    if target not in VALID_TRANSITIONS[current]:
        raise ValueError(f"Invalid review transition: {current} -> {target}")
    if not str(actor).strip():
        raise ValueError("actor is required for review transitions.")
    if not str(reason).strip():
        raise ValueError("reason is required for review transitions.")
    if target == "RESOLVED" and not str(resolution or "").strip():
        raise ValueError("resolution is required when resolving a review.")
    if target == "DEFERRED" and not str(deferred_until_utc or "").strip():
        raise ValueError("deferred_until_utc is required when deferring a review.")
    if target == "ESCALATED" and not str(escalation_reason or "").strip():
        raise ValueError("escalation_reason is required when escalating a review.")

    timestamp = generated_at_utc or _now_utc()
    history = _rows(item.get("status_history"))
    history.append(
        _history_event(
            from_status=current,
            to_status=target,
            timestamp=timestamp,
            actor=str(actor).strip(),
            reason=str(reason).strip(),
            decision_reference=decision_reference,
        )
    )
    notes = _rows(item.get("review_notes"))
    if note and str(note).strip():
        notes.append({"timestamp_utc": timestamp, "actor": str(actor).strip(), "note": str(note).strip()})

    item.update(
        {
            "status": target,
            "last_updated_at_utc": timestamp,
            "status_history": history,
            "review_notes": notes,
        }
    )
    if assigned_reviewer is not None:
        item["assigned_reviewer"] = str(assigned_reviewer).strip() or None
    if target == "RESOLVED":
        item["resolution"] = str(resolution).strip()
    if target == "DEFERRED":
        item["deferred_until_utc"] = str(deferred_until_utc).strip()
    if target == "ESCALATED":
        item["escalation_reason"] = str(escalation_reason).strip()
    if decision_reference and str(decision_reference).strip():
        item["decision_links"] = _string_list(
            list(item.get("decision_links") or []) + [str(decision_reference).strip()]
        )
    return item


def render_enterprise_dividend_reviews_markdown(payload: Mapping[str, Any]) -> str:
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    reviews = _rows(payload.get("reviews"))
    lines = [
        "# Enterprise Dividend Review Workflow",
        "",
        f"- Module: `{payload.get('module_name', MODULE_NAME)}`",
        f"- Version: `{payload.get('module_version', MODULE_VERSION)}`",
        f"- Generated: `{payload.get('generated_at_utc', '')}`",
        f"- Paper trade mode: `{str(bool(payload.get('paper_trade_mode', True))).lower()}`",
        f"- Human approval required: `{str(bool(payload.get('human_approval_required', True))).lower()}`",
        "",
        "## Review Summary",
        "",
        f"- Total reviews: {summary.get('total_reviews', 0)}",
        f"- Active reviews: {summary.get('active_reviews', 0)}",
        f"- Urgent reviews: {summary.get('urgent_reviews', 0)}",
        "",
        "## Review Queue",
        "",
    ]
    if not reviews:
        lines.append("No governed dividend reviews are currently queued.")
    else:
        lines.extend(["| Priority | Status | Symbol | Alert Type | Review ID |", "|---|---|---|---|---|"])
        for item in reviews:
            lines.append(
                f"| {item.get('priority')} | {item.get('status')} | {item.get('symbol')} | "
                f"{item.get('alert_type')} | `{item.get('review_id')}` |"
            )
    warnings = _string_list(payload.get("warnings"))
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {warning}" for warning in warnings] or ["- None"])
    lines.extend(["", "## Governance Notes", ""])
    lines.extend([f"- {note}" for note in _string_list(payload.get("governance_notes"))])
    return "\n".join(lines).rstrip() + "\n"


def write_enterprise_dividend_reviews(
    payload: Mapping[str, Any], output_dir: str | Path = "results"
) -> dict[str, str]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / DEFAULT_OUTPUT_FILES["json"]
    markdown_path = directory / DEFAULT_OUTPUT_FILES["markdown"]
    json_path.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_enterprise_dividend_reviews_markdown(payload), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(markdown_path)}


def build_and_write_enterprise_dividend_reviews(
    *,
    output_dir: str | Path = "results",
    **kwargs: Any,
) -> dict[str, Any]:
    payload = build_enterprise_dividend_reviews(**kwargs)
    output_files = write_enterprise_dividend_reviews(payload, output_dir)
    result = dict(payload)
    result["output_files"] = output_files
    return result


__all__ = [
    "MODULE_NAME",
    "MODULE_VERSION",
    "SCHEMA_VERSION",
    "PAPER_TRADE_MODE",
    "LIVE_TRADING_ENABLED",
    "BROKER_EXECUTION_ENABLED",
    "REPORTING_ONLY",
    "ADVISORY_ONLY",
    "HUMAN_APPROVAL_REQUIRED",
    "REVIEW_STATUSES",
    "VALID_TRANSITIONS",
    "build_enterprise_dividend_reviews",
    "transition_review",
    "render_enterprise_dividend_reviews_markdown",
    "write_enterprise_dividend_reviews",
    "build_and_write_enterprise_dividend_reviews",
]
