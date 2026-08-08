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

    summary = (
        "<div class='position-history-summary'>"
        f"<div><span>Historical Positions</span><strong>{len(history)}</strong></div>"
        f"<div><span>Parked in SGOV</span><strong>{parked}</strong></div>"
        f"<div><span>Closed</span><strong>{closed}</strong></div>"
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
            rows.append(
                "<tr>"
                f"<td><strong>{_text(item.get('symbol'))}</strong></td>"
                f"<td>{_text(item.get('pair'))}</td>"
                f"<td>{_text(item.get('sleeve'))}</td>"
                f"<td><span class='position-history-status {status_class}'>{_text(status.replace('_', ' '))}</span></td>"
                f"<td>{_text(item.get('first_purchase_date'))}</td>"
                f"<td>{_text(item.get('last_exit_date'))}</td>"
                f"<td>{_text(item.get('last_exit_action'))}</td>"
                f"<td>{_money(item.get('last_exit_value'))}</td>"
                f"<td>{_text(item.get('reentry_count'))}</td>"
                f"<td>{_text(item.get('evidence_source'))}</td>"
                "</tr>"
            )
        body = (
            "<div class='position-history-table-wrap'><table class='position-history-table'>"
            "<thead><tr>"
            "<th>Symbol</th><th>Pair</th><th>Sleeve</th><th>Status</th>"
            "<th>Purchase Date</th><th>Exit Date</th><th>Exit Action</th>"
            "<th>Exit / Parked Value</th><th>Re-entry Count</th><th>Evidence</th>"
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
        "PARKED IN SGOV means the strategy exited or redirected the position into reserve capital. "
        "This history does not represent dividend distributions and does not alter current holding counts."
        "</p></section>"
    )


def position_history_ui_css() -> str:
    return """
.position-history-pro{margin-top:18px;border-top:1px solid #e5e7eb;padding-top:16px}.position-history-heading h3{margin:0 0 4px}.position-history-heading p,.position-history-note{color:#667085;font-size:12px}.position-history-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:12px 0}.position-history-summary>div{border:1px solid #e5e7eb;border-radius:10px;padding:10px;background:#fff}.position-history-summary span{display:block;color:#667085;font-size:11px}.position-history-summary strong{font-size:18px}.position-history-table-wrap{overflow-x:auto;border:1px solid #e5e7eb;border-radius:10px}.position-history-table{width:100%;border-collapse:collapse;min-width:1050px}.position-history-table th{background:#f8fafc;color:#475467;font-size:10px;text-transform:uppercase;letter-spacing:.02em;text-align:left;padding:9px}.position-history-table td{padding:10px 9px;border-top:1px solid #eef2f6;font-size:12px;vertical-align:top}.position-history-status{display:inline-block;padding:3px 7px;border-radius:999px;font-size:10px;font-weight:700}.position-history-status.parked{background:#eef2ff;color:#4338ca}.position-history-status.closed{background:#f2f4f7;color:#475467}.position-history-empty{padding:20px;border:1px dashed #d0d5dd;border-radius:10px;text-align:center;color:#667085}@media(max-width:720px){.position-history-summary{grid-template-columns:1fr}.position-history-pro{margin-top:12px}}
"""
