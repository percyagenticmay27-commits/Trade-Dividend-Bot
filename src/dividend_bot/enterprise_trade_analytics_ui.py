"""Read-only Swing trade analytics renderer for Enterprise strategy workspaces."""
from __future__ import annotations

import html
from typing import Any, Mapping, Sequence


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _money(value: Any, *, signed: bool = False) -> str:
    number = _number(value)
    if number is None:
        return "Unavailable"
    if signed and number > 0:
        return f"+${number:,.2f}"
    if signed and number < 0:
        return f"-${abs(number):,.2f}"
    return f"${number:,.2f}"


def _percent(value: Any, *, signed: bool = False) -> str:
    number = _number(value)
    if number is None:
        return "Unavailable"
    prefix = "+" if signed and number > 0 else ""
    return f"{prefix}{number:,.2f}%"


def _shares(value: Any) -> str:
    number = _number(value)
    if number is None:
        return "Unavailable"
    return f"{number:,.8f}".rstrip("0").rstrip(".")


def _text(value: Any) -> str:
    if value in (None, ""):
        return "<span class='trade-unavailable'>Unavailable</span>"
    return html.escape(str(value))


def _metric(value: str) -> str:
    if value == "Unavailable":
        return "<span class='trade-unavailable'>Unavailable</span>"
    return html.escape(value)


def _gain_class(value: Any) -> str:
    number = _number(value)
    if number is None or number == 0:
        return "trade-neutral"
    return "trade-gain" if number > 0 else "trade-loss"


def _rows(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _open_rows(rows: list[Mapping[str, Any]]) -> str:
    output: list[str] = []
    for row in rows:
        pnl = row.get("gain_loss_amount", row.get("unrealized_pnl"))
        pnl_percent = row.get("gain_loss_percent", row.get("unrealized_pnl_percent"))
        drawdown = row.get("max_drawdown_amount")
        drawdown_percent = row.get("max_drawdown_percent")
        output.append(
            "<tr>"
            f"<td><strong>{_text(row.get('symbol'))}</strong></td>"
            f"<td>{_text(row.get('entry_date'))}</td>"
            f"<td class='num'>{_metric(_money(row.get('entry_price')))}</td>"
            f"<td class='num'>{_metric(_money(row.get('current_price')))}</td>"
            f"<td class='num'>{_metric(_shares(row.get('shares')))}</td>"
            f"<td class='num'>{_metric(_money(row.get('cost_basis')))}</td>"
            f"<td class='num'>{_metric(_money(row.get('current_or_exit_value', row.get('market_value'))))}</td>"
            f"<td class='num {_gain_class(pnl)}'>{_metric(_money(pnl, signed=True))}</td>"
            f"<td class='num {_gain_class(pnl_percent)}'>{_metric(_percent(pnl_percent, signed=True))}</td>"
            f"<td class='num trade-loss'>{_metric(_money(drawdown))}</td>"
            f"<td class='num trade-loss'>{_metric(_percent(drawdown_percent))}</td>"
            f"<td class='num'>{_text(row.get('days_held'))}</td>"
            f"<td>{_text(row.get('active_strategy'))}</td>"
            f"<td><span class='trade-status trade-status-open'>{_text(row.get('position_status', 'OPEN'))}</span></td>"
            "</tr>"
        )
    return "".join(output)


def _closed_rows(rows: list[Mapping[str, Any]]) -> str:
    output: list[str] = []
    for row in rows:
        pnl = row.get("gain_loss_amount", row.get("realized_pnl"))
        pnl_percent = row.get("gain_loss_percent", row.get("realized_pnl_percent"))
        output.append(
            "<tr>"
            f"<td><strong>{_text(row.get('symbol'))}</strong></td>"
            f"<td>{_text(row.get('entry_date'))}</td>"
            f"<td>{_text(row.get('exit_date'))}</td>"
            f"<td class='num'>{_metric(_money(row.get('entry_price')))}</td>"
            f"<td class='num'>{_metric(_money(row.get('exit_price')))}</td>"
            f"<td class='num'>{_metric(_shares(row.get('shares')))}</td>"
            f"<td class='num'>{_metric(_money(row.get('cost_basis')))}</td>"
            f"<td class='num'>{_metric(_money(row.get('current_or_exit_value', row.get('proceeds'))))}</td>"
            f"<td class='num {_gain_class(pnl)}'>{_metric(_money(pnl, signed=True))}</td>"
            f"<td class='num {_gain_class(pnl_percent)}'>{_metric(_percent(pnl_percent, signed=True))}</td>"
            f"<td class='num trade-loss'>{_metric(_money(row.get('max_drawdown_amount')))}</td>"
            f"<td class='num trade-loss'>{_metric(_percent(row.get('max_drawdown_percent')))}</td>"
            f"<td class='num'>{_text(row.get('days_held', row.get('holding_days')))}</td>"
            f"<td>{_text(row.get('active_strategy'))}</td>"
            f"<td>{_text(row.get('exit_reason'))}</td>"
            f"<td><span class='trade-status trade-status-closed'>{_text(row.get('position_status', 'CLOSED'))}</span></td>"
            "</tr>"
        )
    return "".join(output)


def render_trade_analytics_panel(row: Mapping[str, Any]) -> str:
    """Render only authoritative SWING-001 trade analytics evidence."""
    if str(row.get("strategy_id") or "").upper() != "SWING-001":
        return "<section class='trade-analytics-empty'><h3>Trade Analytics</h3><p>Not applicable to this strategy.</p></section>"

    analytics = row.get("trade_analytics")
    if not isinstance(analytics, Mapping):
        return (
            "<section class='trade-analytics'>"
            "<div class='trade-analytics-heading'><div><h3>Trade Analytics / Position Performance</h3>"
            "<p>Strategy-owned Swing lifecycle performance.</p></div>"
            "<div class='trade-safety'><span>PAPER ONLY</span><span>READ ONLY</span></div></div>"
            "<div class='trade-empty'>Trade analytics evidence is unavailable. No position or exit detail was inferred.</div>"
            "</section>"
        )

    open_positions = _rows(analytics.get("open_positions"))
    closed_positions = _rows(analytics.get("closed_positions"))
    policy = analytics.get("max_drawdown_policy")
    inference = analytics.get("max_drawdown_inference_allowed")
    generated_at = analytics.get("generated_at")

    open_section = (
        "<section class='trade-position-section'><h4>Open Position Performance</h4>"
        "<div class='trade-table-wrap'><table class='trade-table trade-open-table'><thead><tr>"
        "<th>Symbol</th><th>Entry Date</th><th>Entry Price</th><th>Current Price</th>"
        "<th>Shares</th><th>Cost Basis</th><th>Market Value</th>"
        "<th>Unrealized Gain/Loss $</th><th>Unrealized Gain/Loss %</th>"
        "<th>Maximum Drawdown $</th><th>Maximum Drawdown %</th><th>Days Held</th>"
        "<th>Active Strategy</th><th>Status</th></tr></thead>"
        f"<tbody>{_open_rows(open_positions)}</tbody></table></div></section>"
        if open_positions
        else "<section class='trade-position-section'><h4>Open Position Performance</h4><p class='trade-empty'>No authentic open positions are reported.</p></section>"
    )
    closed_section = (
        "<section class='trade-position-section'><h4>Closed Position Performance</h4>"
        "<div class='trade-table-wrap'><table class='trade-table trade-closed-table'><thead><tr>"
        "<th>Symbol</th><th>Entry Date</th><th>Exit Date</th><th>Entry Price</th>"
        "<th>Exit/Sale Price</th><th>Shares</th><th>Cost Basis</th><th>Final Proceeds</th>"
        "<th>Realized Gain/Loss $</th><th>Realized Gain/Loss %</th>"
        "<th>Maximum Drawdown $</th><th>Maximum Drawdown %</th><th>Holding Days</th>"
        "<th>Active Strategy</th><th>Exit Reason</th><th>Status</th></tr></thead>"
        f"<tbody>{_closed_rows(closed_positions)}</tbody></table></div></section>"
        if closed_positions
        else "<section class='trade-position-section'><h4>Closed Position Performance</h4><p class='trade-empty'>No authentic closed positions are reported. Exit fields are not fabricated.</p></section>"
    )

    return (
        "<section class='trade-analytics'>"
        "<div class='trade-analytics-heading'><div><h3>Trade Analytics / Position Performance</h3>"
        "<p>Authoritative Swing position history; no host-side drawdown calculation or trade inference.</p></div>"
        "<div class='trade-safety'><span>PAPER ONLY</span><span>READ ONLY</span></div></div>"
        "<div class='trade-analytics-summary'>"
        f"<div><span>Open Positions</span><strong>{len(open_positions)}</strong></div>"
        f"<div><span>Closed Positions</span><strong>{len(closed_positions)}</strong></div>"
        f"<div><span>Drawdown Policy</span><strong>{_text(policy)}</strong></div>"
        f"<div><span>Inference Allowed</span><strong>{'No' if inference is False else _text(inference)}</strong></div>"
        f"<div><span>Evidence As-Of</span><strong>{_text(generated_at)}</strong></div>"
        "</div>"
        + open_section
        + closed_section
        + "</section>"
    )


def trade_analytics_ui_css() -> str:
    return """
<style>
.trade-analytics{color:#10213b}.trade-analytics-heading{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:14px}.trade-analytics-heading h3{margin:0 0 5px}.trade-analytics-heading p{margin:0;color:#64748b}.trade-safety{display:flex;gap:6px}.trade-safety span,.trade-status{display:inline-block;border-radius:999px;padding:5px 8px;font-size:.72rem;font-weight:800}.trade-safety span{background:#eef2ff;color:#4f46e5}.trade-analytics-summary{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:9px;margin-bottom:17px}.trade-analytics-summary>div{background:#f8faff;border:1px solid #dbe4f0;border-radius:10px;padding:10px}.trade-analytics-summary span{display:block;color:#64748b;font-size:.75rem}.trade-analytics-summary strong{display:block;margin-top:5px;overflow-wrap:anywhere}.trade-position-section{margin:18px 0}.trade-position-section h4{margin:0 0 8px}.trade-table-wrap{overflow-x:auto;border:1px solid #dbe4f0;border-radius:12px}.trade-table{width:100%;border-collapse:collapse;min-width:1650px;background:#fff}.trade-table th{padding:10px;background:#f4f7fc;color:#53627a;font-size:.7rem;text-transform:uppercase;white-space:nowrap;text-align:left}.trade-table td{padding:11px;border-top:1px solid #edf1f6;white-space:nowrap}.trade-table .num{text-align:right;font-variant-numeric:tabular-nums}.trade-gain{color:#087443;font-weight:800}.trade-loss{color:#b42318;font-weight:800}.trade-neutral{color:#475569}.trade-status-open{background:#e9f9f0;color:#087443}.trade-status-closed{background:#eef2ff;color:#4f46e5}.trade-unavailable{color:#7a8798;font-style:italic}.trade-empty{padding:18px;border:1px dashed #b9c7db;border-radius:10px;background:#f8fafc;color:#64748b}@media(max-width:1000px){.trade-analytics-summary{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:560px){.trade-analytics-heading{display:block}.trade-safety{margin-top:10px}.trade-analytics-summary{grid-template-columns:1fr}}
</style>
"""
