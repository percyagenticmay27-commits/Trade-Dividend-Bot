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


_EXIT_REASON_LABELS = {
    "PRICE_BELOW_EMA20": "Price fell below its 20-day exponential moving average.",
    "STOCH_RSI_D_CROSSED_ABOVE_K": "Stochastic RSI turned bearish.",
    "STOCH_OSC_D_CROSSED_ABOVE_K": "Stochastic oscillator confirmed a bearish crossover.",
    "STOCH_OSC_D_CROSSED_ABOVE_K_BELOW_80": "Stochastic oscillator confirmed a bearish crossover below 80.",
    "SCHEDULED_PRE_EARNINGS_EXIT": "Position was moved to SGOV before the underlying company earnings event.",
    "QUALIFIED_ENTRY_GATE_FAILED": "The position no longer satisfied the qualified-entry rules.",
}


def _exit_reason(value: Any) -> str:
    if value in (None, ""):
        return "Not reported"
    raw = str(value).strip()
    upper = raw.upper()
    for code, label in _EXIT_REASON_LABELS.items():
        if code in upper:
            return html.escape(label)
    if "STRATEGY-OWNER EXIT:" in upper:
        raw = raw.split(":", maxsplit=2)[-1].strip()
    return html.escape(raw.replace("_", " ").strip().capitalize())


def _evidence_explanation(value: Any) -> str:
    source = str(value or "").strip()
    labels = {
        "paper_state.json": "Persisted strategy-owner exit record",
        "paper_trade_log.csv": "Paper transaction ledger",
        "entry_score_report.json": "Current technical strategy evidence",
    }
    explanation = labels.get(source, "Strategy-owned lifecycle evidence" if source else "Not reported")
    if not source:
        return explanation
    return (
        f"{html.escape(explanation)}"
        f"<details class='position-history-evidence'><summary>Audit source</summary>{html.escape(source)}</details>"
    )


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
                f"<td>{_text(item.get('entry_method'))}</td>"
                f"<td>{_text(item.get('first_purchase_date'))}</td>"
                f"<td>{_text(item.get('last_exit_date'))}</td>"
                f"<td class='money'>{_money(item.get('entry_value'))}</td>"
                f"<td class='money'>{_money(item.get('last_exit_value'))}</td>"
                f"<td class='money {gain_class}'>{gain}</td>"
                f"<td>{_text(item.get('exit_method') or item.get('last_exit_strategy_owner'))}</td>"
                f"<td class='position-history-reason'>{_exit_reason(item.get('last_exit_reason'))}</td>"
                f"<td>{_text(item.get('last_exit_action'))}</td>"
                f"<td>{_text(item.get('reentry_count'))}</td>"
                f"<td class='position-history-evidence-cell'>{_evidence_explanation(item.get('strategy_exit_evidence_source') or item.get('evidence_source'))}</td>"
                "</tr>"
            )
        body = (
            "<div class='position-history-scroll'><table class='position-history-table'>"
            "<thead><tr><th>Symbol / Pair</th><th>Sleeve</th><th>Status</th><th>Entry Method</th>"
            "<th>Entry Date</th><th>Exit Date</th><th>Entry Value</th><th>Exit Value</th>"
            "<th>Gain / Loss</th><th>Exit Method</th><th>Why Sold</th><th>Ledger Action</th><th>Re-entry</th><th>Evidence</th>"
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"
        )

    return (
        "<section class='position-history-pro' aria-label='Position sales history'>"
        "<div class='position-history-heading'><div><h3>Position / Sales History</h3>"
        "<p>Completed strategy-owned paper positions with entry methodology, owner-controlled exit evidence, and realized P&amp;L.</p>"
        "</div></div>" + summary + body + "</section>"
    )


def position_history_ui_css() -> str:
    return """<style>
.position-history-pro{margin-top:24px}.position-history-heading h3{margin:0 0 4px;font-size:18px}.position-history-heading p{margin:0 0 14px;color:#667085}.position-history-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:12px 0}.position-history-summary>div{border:1px solid #e4e7ec;border-radius:10px;padding:12px;background:#fff}.position-history-summary span{display:block;color:#667085;font-size:12px}.position-history-summary strong{display:block;margin-top:4px;font-size:18px}.position-history-scroll{overflow-x:auto;border:1px solid #e4e7ec;border-radius:12px;background:#fff}.position-history-table{width:100%;border-collapse:separate;border-spacing:0;min-width:1580px}.position-history-table th{position:sticky;top:0;background:#f8fafc;color:#475467;text-align:left;padding:11px 12px;font-size:12px;border-bottom:1px solid #e4e7ec;white-space:nowrap}.position-history-table td{padding:11px 12px;border-bottom:1px solid #f0f2f5;vertical-align:top}.position-history-table tbody tr:nth-child(even){background:#fcfcfd}.position-history-table tbody tr:hover{background:#f8fafc}.position-history-table .money{text-align:right;white-space:nowrap}.position-history-reason{min-width:260px;max-width:420px;white-space:normal!important;line-height:1.35}.position-history-evidence-cell{min-width:230px;white-space:normal!important;line-height:1.35}.position-history-evidence{margin-top:5px;color:#64748b}.position-history-evidence summary{cursor:pointer;color:#5b21b6;font-weight:700}.position-history-pair{font-size:12px;color:#667085;margin-top:3px}.position-history-status{display:inline-block;border-radius:999px;padding:3px 8px;background:#eef2f6;font-size:11px;font-weight:700}.positive{color:#027a48}.negative{color:#b42318}.neutral{color:#475467}.position-history-empty{padding:20px;border:1px dashed #d0d5dd;border-radius:10px;color:#667085}@media(max-width:900px){.position-history-summary{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:560px){.position-history-summary{grid-template-columns:1fr}}
</style>"""
