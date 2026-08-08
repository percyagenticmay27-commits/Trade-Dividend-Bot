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
        # Sales history is for positions that actually owned ETF exposure.
        # NEVER_ENTERED belongs to watchlist/decision evidence, not realized P&L.
        if status in {"OPEN", "REENTERED", "RESERVE", "NEVER_ENTERED"}:
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
            "No strategy-owned completed position exits are currently reported."
            "</div>"
        )
    else:
        rows = []
        for item in history:
            gain, gain_class = _gain_loss(item.get("realized_gain_loss"))
            rows.append(
                "<tr>"
                f"<td><strong>{_text(item.get('symbol'))}</strong><div class='position-history-pair'>{_text(item.get('pair'))}</div></td>"
                f"<td>{_text(item.get('sleeve'))}</td>"
                f"<td><span class='position-history-status'>{_text(item.get('lifecycle_status'))}</span></td>"
                f"<td>{_text(item.get('first_purchase_date'))}</td>"
                f"<td>{_text(item.get('last_exit_date'))}</td>"
                f"<td class='money'>{_money(item.get('entry_value'))}</td>"
                f"<td class='money'>{_money(item.get('last_exit_value'))}</td>"
                f"<td class='money {gain_class}'>{gain}</td>"
                f"<td>{_text(item.get('last_exit_action'))}</td>"
                f"<td>{_text(item.get('reentry_count'))}</td>"
                f"<td>{_text(item.get('evidence_source'))}</td>"
                "</tr>"
            )
        body = (
            "<div class='position-history-scroll'><table class='position-history-table'>"
            "<thead><tr><th>Symbol / Pair</th><th>Sleeve</th><th>Status</th>"
            "<th>Entry Date</th><th>Exit Date</th><th>Entry Value</th><th>Exit Value</th>"
            "<th>Gain / Loss</th><th>Exit Action</th><th>Re-entry</th><th>Evidence</th>"
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"
        )

    return (
        "<section class='position-history-pro' aria-label='Position sales history'>"
        "<div class='position-history-heading'><div><h3>Position / Sales History</h3>"
        "<p>Completed strategy-owned paper positions only. Candidates that never entered remain outside realized trade history.</p>"
        "</div></div>" + summary + body + "</section>"
    )


def position_history_ui_css() -> str:
    return """
.position-history-pro{margin-top:24px}.position-history-heading h3{margin:0 0 4px;font-size:18px}.position-history-heading p{margin:0 0 14px;color:#667085}.position-history-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:12px 0}.position-history-summary>div{border:1px solid #e4e7ec;border-radius:10px;padding:12px;background:#fff}.position-history-summary span{display:block;color:#667085;font-size:12px}.position-history-summary strong{display:block;margin-top:4px;font-size:18px}.position-history-scroll{overflow-x:auto;border:1px solid #e4e7ec;border-radius:12px;background:#fff}.position-history-table{width:100%;border-collapse:separate;border-spacing:0;min-width:1180px}.position-history-table th{position:sticky;top:0;background:#f8fafc;color:#475467;text-align:left;padding:11px 12px;font-size:12px;border-bottom:1px solid #e4e7ec;white-space:nowrap}.position-history-table td{padding:11px 12px;border-bottom:1px solid #f0f2f5;vertical-align:top}.position-history-table tbody tr:nth-child(even){background:#fcfcfd}.position-history-table tbody tr:hover{background:#f8fafc}.position-history-table .money{text-align:right;white-space:nowrap}.position-history-pair{font-size:12px;color:#667085;margin-top:3px}.position-history-status{display:inline-block;border-radius:999px;padding:3px 8px;background:#eef2f6;font-size:11px;font-weight:700}.positive{color:#027a48}.negative{color:#b42318}.neutral{color:#475467}.position-history-empty{padding:20px;border:1px dashed #d0d5dd;border-radius:10px;color:#667085}@media(max-width:900px){.position-history-summary{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:560px){.position-history-summary{grid-template-columns:1fr}}
"""
