"""Read-only authoritative SWING-001 Alerts renderer."""
from __future__ import annotations

import html
from typing import Any, Mapping


_ZERO_ALERT_MESSAGE = (
    "Current authoritative Swing evidence was evaluated and no actionable alerts were found."
)


def _text(value: Any, default: str = "Not reported") -> str:
    if value in (None, ""):
        return html.escape(default)
    return html.escape(str(value))


def _known_class(value: Any, *, prefix: str, allowed: set[str]) -> str:
    normalized = str(value or "NOT_REPORTED").strip().upper().replace(" ", "_")
    suffix = normalized.lower().replace("_", "-") if normalized in allowed else "neutral"
    return f"{prefix}-{suffix}"


def _alert_cards(alerts: list[Mapping[str, Any]]) -> str:
    cards: list[str] = []
    for item in alerts:
        severity = str(item.get("severity") or "NOT_REPORTED").upper()
        priority = str(item.get("priority") or "NOT_REPORTED").upper()
        severity_class = _known_class(
            severity,
            prefix="swing-alert-severity",
            allowed={"ERROR", "CRITICAL", "WARNING", "HIGH", "MEDIUM", "LOW", "INFO"},
        )
        priority_class = _known_class(
            priority,
            prefix="swing-alert-priority",
            allowed={"URGENT", "HIGH", "MEDIUM", "LOW", "ROUTINE"},
        )
        symbol = item.get("symbol") or "PORTFOLIO"
        cards.append(
            "<article class='swing-alert-card'>"
            "<header>"
            f"<strong>{_text(symbol)}</strong>"
            f"<span class='swing-alert-badge {severity_class}'>{_text(severity)}</span>"
            f"<span class='swing-alert-badge {priority_class}'>{_text(priority)}</span>"
            "</header>"
            "<dl class='swing-alert-fields'>"
            f"<div><dt>Category</dt><dd>{_text(item.get('alert_category'))}</dd></div>"
            f"<div><dt>Status</dt><dd>{_text(item.get('status'))}</dd></div>"
            f"<div><dt>Message</dt><dd>{_text(item.get('message'))}</dd></div>"
            f"<div><dt>Recommended Review</dt><dd>{_text(item.get('recommended_review_action'))}</dd></div>"
            f"<div><dt>Evidence Source</dt><dd>{_text(item.get('evidence_source'))}</dd></div>"
            f"<div><dt>Evidence Timestamp</dt><dd>{_text(item.get('evidence_timestamp'))}</dd></div>"
            "</dl>"
            "</article>"
        )
    return "<div class='swing-alert-list'>" + "".join(cards) + "</div>"


def render_swing_alerts_panel(row: Mapping[str, Any]) -> str:
    """Render only registered, authoritative SWING-001 Alerts evidence."""
    if str(row.get("strategy_id") or "").upper() != "SWING-001":
        return ""

    report = row.get("alerts_report")
    if not isinstance(report, Mapping):
        return (
            "<section class='swing-alerts' aria-label='Swing Alerts'>"
            "<div class='swing-alerts-heading'><div><h3>Alerts</h3>"
            "<p>Current authoritative Swing alert evidence.</p></div>"
            "<div class='swing-alert-safety'><span>PAPER ONLY</span><span>ADVISORY ONLY</span></div></div>"
            "<p class='swing-alert-empty'>Authoritative Swing Alerts evidence is unavailable. "
            "No alerts were fabricated from summary counts or legacy risk flags.</p>"
            "</section>"
        )

    report_strategy = str(report.get("strategy_id") or "SWING-001").upper()
    if report_strategy != "SWING-001":
        return (
            "<section class='swing-alerts' aria-label='Swing Alerts'>"
            "<h3>Alerts unavailable</h3>"
            "<p class='swing-alert-empty'>Cross-strategy Alerts evidence was rejected.</p></section>"
        )

    raw_alerts = report.get("alerts")
    alerts = [item for item in raw_alerts if isinstance(item, Mapping)] if isinstance(raw_alerts, list) else []
    count = report.get("actionable_alert_count")
    zero_verified = count == 0 and not alerts
    warnings = report.get("evidence_warnings")
    disclosures = [str(item) for item in warnings if item not in (None, "")] if isinstance(warnings, list) else []

    actionable_body = (
        f"<p class='swing-alert-zero'>{html.escape(_ZERO_ALERT_MESSAGE)}</p>"
        if zero_verified
        else _alert_cards(alerts)
        if alerts
        else "<p class='swing-alert-empty'>Actionable alert evidence is unavailable; no alert was inferred.</p>"
    )
    disclosure_body = (
        "<ul class='swing-alert-disclosures'>"
        + "".join(f"<li>{html.escape(item)}</li>" for item in disclosures)
        + "</ul>"
        if disclosures
        else "<p class='swing-alert-none'>No evidence disclosures were reported.</p>"
    )

    return (
        "<section class='swing-alerts' aria-label='Swing Alerts'>"
        "<div class='swing-alerts-heading'><div><h3>Alerts</h3>"
        "<p>Current authoritative Swing classifications rendered without host reinterpretation.</p></div>"
        "<div class='swing-alert-safety'><span>PAPER ONLY</span><span>ADVISORY ONLY</span></div></div>"
        "<div class='swing-alert-summary'>"
        f"<div><span>Authority Policy</span><strong>{_text(report.get('alert_authority_policy'))}</strong></div>"
        f"<div><span>Evaluation Status</span><strong>{_text(report.get('evaluation_status'))}</strong></div>"
        f"<div><span>Actionable Alerts</span><strong>{_text(count)}</strong></div>"
        f"<div><span>Evidence Warnings</span><strong>{_text(report.get('evidence_warning_count'))}</strong></div>"
        "</div>"
        "<section class='swing-actionable-alerts'><h4>Actionable Alerts</h4>"
        + actionable_body
        + "</section>"
        "<section class='swing-evidence-disclosures'><h4>Evidence Disclosures</h4>"
        + disclosure_body
        + "</section></section>"
    )


def swing_alerts_ui_css() -> str:
    return """
<style>
.swing-alerts{color:#10213b}.swing-alerts-heading{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:14px}.swing-alerts-heading h3{margin:0 0 5px}.swing-alerts-heading p{margin:0;color:#64748b}.swing-alert-safety{display:flex;gap:6px}.swing-alert-safety span,.swing-alert-badge{display:inline-block;border-radius:999px;padding:5px 8px;font-size:.72rem;font-weight:800}.swing-alert-safety span{background:#eef2ff;color:#4f46e5}.swing-alert-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin-bottom:18px}.swing-alert-summary>div{background:#f8faff;border:1px solid #dbe4f0;border-radius:10px;padding:10px}.swing-alert-summary span{display:block;color:#64748b;font-size:.75rem}.swing-alert-summary strong{display:block;margin-top:5px;overflow-wrap:anywhere}.swing-actionable-alerts,.swing-evidence-disclosures{margin-top:18px}.swing-actionable-alerts h4,.swing-evidence-disclosures h4{margin:0 0 9px}.swing-alert-list{display:grid;gap:10px}.swing-alert-card{border:1px solid #dbe4f0;border-radius:12px;background:#fff;padding:13px}.swing-alert-card header{display:flex;align-items:center;gap:7px;margin-bottom:10px}.swing-alert-card header strong{margin-right:auto}.swing-alert-fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:0}.swing-alert-fields div{background:#f8fafc;border-radius:8px;padding:8px}.swing-alert-fields dt{color:#64748b;font-size:.72rem}.swing-alert-fields dd{margin:3px 0 0;overflow-wrap:anywhere}.swing-alert-severity-error,.swing-alert-severity-critical,.swing-alert-priority-urgent{background:#fff0f0;color:#b42318}.swing-alert-severity-warning,.swing-alert-severity-high,.swing-alert-priority-high{background:#fff7df;color:#8a4b08}.swing-alert-severity-medium,.swing-alert-priority-medium{background:#fef3c7;color:#92400e}.swing-alert-severity-low,.swing-alert-severity-info,.swing-alert-priority-low,.swing-alert-priority-routine,.swing-alert-severity-neutral,.swing-alert-priority-neutral{background:#eef2ff;color:#4f46e5}.swing-alert-zero{padding:15px;border:1px solid #86d9ad;border-radius:10px;background:#ecfdf3;color:#065f46;font-weight:700}.swing-alert-empty,.swing-alert-none{padding:15px;border:1px dashed #b9c7db;border-radius:10px;background:#f8fafc;color:#64748b}.swing-alert-disclosures{margin:0;padding:13px 13px 13px 30px;border:1px solid #dbe4f0;border-radius:10px;background:#f8fafc;color:#475569}.swing-alert-disclosures li+li{margin-top:7px}@media(max-width:800px){.swing-alert-summary,.swing-alert-fields{grid-template-columns:1fr 1fr}}@media(max-width:520px){.swing-alerts-heading{display:block}.swing-alert-safety{margin-top:10px}.swing-alert-summary,.swing-alert-fields{grid-template-columns:1fr}}
</style>
"""


__all__ = ["render_swing_alerts_panel", "swing_alerts_ui_css"]
