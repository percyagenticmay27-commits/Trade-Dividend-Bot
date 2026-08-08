"""Read-only Enterprise Position / Sales History renderer."""
from __future__ import annotations

import html
from typing import Any, Mapping


def _money(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "Not reported"


def _text(value: Any) -> str:
    if value in (None, ""):
        return "Not reported"
    return html.escape(str(value))


def _gain_loss(value: Any) -> tuple[str, str]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "Not reported", "neutral"
    css_class = "positive" if number > 0 else "negative" if number < 0 else "neutral"
    prefix = "+" if number > 0 else ""
    return f"{prefix}${number:,.2f}" if number >= 0 else f"-${abs(number):,.2f}", css_class


def _history_rows(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    performance = row.get("performance_detail")
    if not isinstance(performance, Mapping):
        return []
    lifecycle = performance.get("position_lifecycle")
    if not isinstance(lifecycle, list):
        return []
    result: list[dict[str, Any]] = []
    for item in lifecycle:
        if not isinstance(item, Mapping):
            continue
        status = str(item.get("lifecycle_status") or "").upper()
        if status in {"OPEN", "REENTERED", "RESERVE"}:
            continue
        result.append(dict(item))
    return sorted(
        result,
        key=lambda item: (
            str(item.get("last_exit_date") or ""),
            str(item.get("symbol") or ""),
        ),
        reverse=True,
    )


def render_position_history_panel(row: Mapping[str, Any]) -> str:
    history = _history_rows(row)
    parked = sum(1 for item in history if item.get("lifecycle_status") == "PARKED_IN_SGOV")
    closed = sum(1 for item in history if item.get("lifecycle_status") == "CLOSED")
    reported_pnl = [
        float(item["realized_gain_loss"])
        for item in history
        if item.get("realized_gain_loss") is not None
    ]
    total_realized = round(sum(reported_pnl), 2) if reported_pnl else None
    total_label, total_class = _gain_loss(total_realized)

    summary = (
        "<div class='position-history-summary'>"
        f"<div><span>Historical Positions</span><strong>{len(history)}</strong></div>"
        f"<div><span>Parked in SGOV</span><strong>{parked}</strong></div>"
        f"<div><span>Closed</span><strong>{closed}</strong></div>"
        f"<div><span>Reported Realized P&amp;L</span><strong class='position-history-pnl {total_class}'>{total_label}</strong></div>"
        "</div>"
    )

    if not history:
        body = (
            "<div class='position-history-empty'>"
            "No strategy-owned position exits are currently reported."
            "</div>"
        )
    else:
        rows = []
        for item in history:
            status = str(item.get("lifecycle_status") or "CLOSED").upper()
            status_class = "parked" if status == "PARKED_IN_SGOV" else "closed"
            pnl_text, pnl_class = _gain_loss(item.get("realized_gain_loss"))
            rows.append(
                "<tr>"
                f"<td class='symbol-cell'><strong>{_text(item.get('symbol'))}</strong><small>{_text(item.get('pair'))}</small></td>"
                f"<td class='center-cell'>{_text(item.get('sleeve'))}</td>"
                f"<td><span class='position-history-status {status_class}'>{_text(status.replace('_', ' '))}</span></td>"
                f"<td class='date-cell'>{_text(item.get('first_purchase_date'))}</td>"
                f"<td class='date-cell'>{_text(item.get('last_exit_date'))}</td>"
                f"<td class='money-cell'>{_money(item.get('entry_value'))}</td>"
                f"<td class='money-cell'>{_money(item.get('last_exit_value'))}</td>"
                f"<td class='money-cell position-history-pnl {pnl_class}'>{pnl_text}</td>"
                f"<td class='action-cell'>{_text(item.get('last_exit_action'))}</td>"
                f"<td class='center-cell'>{_text(item.get('reentry_count'))}</td>"
                f"<td class='evidence-cell'>{_text(item.get('evidence_source'))}</td>"
                "</tr>"
            )
        body = (
            "<div class='position-history-table-wrap'><table class='position-history-table'>"
            "<thead><tr>"
            "<th>Symbol / Pair</th><th>Sleeve</th><th>Status</th>"
            "<th>Entry Date</th><th>Exit Date</th><th class='money-head'>Entry Value</th>"
            "<th class='money-head'>Exit Value</th><th class='money-head'>Gain / Loss</th>"
            "<th>Exit Action</th><th>Re-entry</th><th>Evidence</th>"
            "</tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table></div>"
        )

    return (
        "<section class='position-history-pro' aria-label='Position and sales history'>"
        "<div class='position-history-heading'>"
        "<div><h3>Position / Sales History</h3>"
        "<p>Historical paper positions are retained separately from current holdings and dividend income.</p></div>"
        "</div>"
        f"{summary}{body}"
        "<p class='position-history-note'>"
        "Entry Value is the paper capital committed to the most recently completed position cycle. "
        "Gain / Loss is Exit Value minus Entry Value when both values are reported. "
        "PARKED IN SGOV means the position proceeds were redirected into reserve capital."
        "</p></section>"
    )


def position_history_ui_css() -> str:
    return """
.position-history-pro{margin-top:20px;border-top:1px solid #e5e7eb;padding-top:18px}.position-history-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.position-history-heading h3{margin:0 0 4px;font-size:17px;color:#101828}.position-history-heading p,.position-history-note{margin:0;color:#667085;font-size:11px;line-height:1.45}.position-history-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:14px 0}.position-history-summary>div{border:1px solid #e4e7ec;border-radius:10px;padding:10px 12px;background:#fff;box-shadow:0 1px 2px rgba(16,24,40,.03)}.position-history-summary span{display:block;color:#667085;font-size:10px;margin-bottom:3px}.position-history-summary strong{font-size:17px;color:#101828}.position-history-table-wrap{overflow-x:auto;border:1px solid #e4e7ec;border-radius:10px;background:#fff;box-shadow:0 1px 3px rgba(16,24,40,.04)}.position-history-table{width:100%;border-collapse:separate;border-spacing:0;min-width:1180px;table-layout:auto}.position-history-table thead th{position:sticky;top:0;z-index:1;background:#f8fafc;color:#475467;font-size:9px;text-transform:uppercase;letter-spacing:.035em;text-align:left;padding:9px 10px;border-bottom:1px solid #e4e7ec;white-space:nowrap}.position-history-table tbody tr:nth-child(even){background:#fcfcfd}.position-history-table tbody tr:hover{background:#f9fafb}.position-history-table td{padding:9px 10px;border-bottom:1px solid #eef2f6;font-size:11px;vertical-align:middle;color:#344054}.position-history-table tbody tr:last-child td{border-bottom:0}.symbol-cell{min-width:105px}.symbol-cell strong{display:block;color:#101828;font-size:12px}.symbol-cell small{display:block;color:#667085;font-size:9px;margin-top:2px;white-space:nowrap}.center-cell{text-align:center;white-space:nowrap}.date-cell{white-space:nowrap;font-variant-numeric:tabular-nums}.money-cell,.money-head{text-align:right!important;white-space:nowrap;font-variant-numeric:tabular-nums}.action-cell{white-space:nowrap;font-size:10px!important;color:#475467!important}.evidence-cell{white-space:nowrap;font-size:9px!important;color:#667085!important}.position-history-status{display:inline-block;padding:4px 7px;border-radius:999px;font-size:9px;font-weight:700;line-height:1.15;white-space:nowrap}.position-history-status.parked{background:#eef2ff;color:#4338ca}.position-history-status.closed{background:#f2f4f7;color:#475467}.position-history-pnl.positive{color:#067647!important}.position-history-pnl.negative{color:#b42318!important}.position-history-pnl.neutral{color:#475467!important}.position-history-empty{padding:22px;border:1px dashed #d0d5dd;border-radius:10px;text-align:center;color:#667085;background:#fcfcfd}.position-history-note{margin-top:10px}@media(max-width:900px){.position-history-summary{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:720px){.position-history-summary{grid-template-columns:1fr}.position-history-pro{margin-top:12px}.position-history-table{min-width:1080px}}
"""
