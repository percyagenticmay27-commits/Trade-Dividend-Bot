"""Professional read-only Holdings UI for Enterprise strategy workspaces.

This module is presentation-only. It never mutates portfolio state, places orders,
or invents missing P&L evidence. Strategy-owned holdings supplied by the Enterprise
KPI adapter are rendered as a compact financial table with portfolio summary cards.
"""
from __future__ import annotations

import html
from typing import Any, Mapping, Sequence


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _money(value: Any) -> str:
    number = _number(value)
    return f"${number:,.2f}" if number is not None else "Not reported"


def _shares(value: Any) -> str:
    number = _number(value)
    if number is None:
        return "—"
    text = f"{number:,.6f}".rstrip("0").rstrip(".")
    return text or "0"


def _percent(value: Any) -> str:
    number = _number(value)
    return f"{number:,.2f}%" if number is not None else "—"


def _holding_status(item: Mapping[str, Any]) -> tuple[str, str]:
    raw = str(item.get("position_status") or item.get("status") or "UNKNOWN").strip().upper()
    if raw == "OPEN":
        return "OPEN", "status-open"
    if raw in {"PARKED", "CASH", "RESERVE"}:
        return "PARKED", "status-parked"
    if "LOCK" in raw:
        return raw, "status-warning"
    if raw in {"CLOSED", "EXITED"}:
        return raw, "status-closed"
    return raw or "UNKNOWN", "status-neutral"


def _portfolio_percent(market_value: Any, portfolio_value: Any) -> float | None:
    value = _number(market_value)
    total = _number(portfolio_value)
    if value is None or total is None or total <= 0:
        return None
    return value / total * 100.0


def _summary_value(label: str, value: str, detail: str = "") -> str:
    detail_html = f"<small>{html.escape(detail)}</small>" if detail else ""
    return (
        "<div class='holdings-summary-card'>"
        f"<span>{html.escape(label)}</span>"
        f"<strong>{value}</strong>"
        f"{detail_html}</div>"
    )


def render_holdings_panel(row: Mapping[str, Any]) -> str:
    """Render a professional, strategy-scoped Holdings panel.

    Calculated display values are limited to arithmetic from already-published
    strategy evidence (for example percentage of portfolio). Missing P&L fields
    remain explicitly unreported rather than being estimated.
    """

    raw_holdings = row.get("holdings") or row.get("positions")
    holdings: list[Mapping[str, Any]] = [
        item for item in raw_holdings
        if isinstance(raw_holdings, Sequence)
        and not isinstance(raw_holdings, (str, bytes))
        and isinstance(item, Mapping)
    ] if isinstance(raw_holdings, Sequence) and not isinstance(raw_holdings, (str, bytes)) else []

    portfolio_value = _number(row.get("portfolio_value"))
    reserve_value = 0.0
    invested_value = 0.0
    for item in holdings:
        market_value = _number(item.get("market_value")) or 0.0
        symbol = str(item.get("symbol") or "").strip().upper()
        sleeve = str(item.get("sleeve") or "").strip().upper()
        status = str(item.get("position_status") or "").strip().upper()
        if symbol == "SGOV" or sleeve == "RESERVE" or status == "PARKED":
            reserve_value += market_value
        else:
            invested_value += market_value

    if portfolio_value is None and holdings:
        portfolio_value = reserve_value + invested_value

    count = row.get("position_count")
    count_number = _number(count)
    position_count = int(count_number) if count_number is not None else len(holdings)

    summary = "".join((
        _summary_value("Portfolio Value", _money(portfolio_value)),
        _summary_value(
            "Cash Reserve (SGOV)",
            _money(reserve_value),
            _percent(_portfolio_percent(reserve_value, portfolio_value)),
        ),
        _summary_value(
            "Invested", _money(invested_value),
            _percent(_portfolio_percent(invested_value, portfolio_value)),
        ),
        _summary_value("Positions", str(position_count)),
    ))

    if not holdings:
        return (
            "<section class='holdings-pro'>"
            "<div class='holdings-heading'><div><h3>Holdings</h3>"
            "<p>Strategy-owned paper positions and reserve capital.</p></div>"
            f"<span class='holdings-count'>0 positions</span></div>"
            f"<div class='holdings-summary-grid'>{summary}</div>"
            "<div class='holdings-empty'>No strategy-owned holdings detail is currently reported.</div>"
            "</section>"
        )

    rows: list[str] = []
    for item in holdings:
        symbol = html.escape(str(item.get("symbol") or "UNKNOWN"))
        pair = html.escape(str(item.get("pair") or "—"))
        sleeve = html.escape(str(item.get("sleeve") or "—"))
        status_label, status_class = _holding_status(item)
        market_value = item.get("market_value")
        weight = _portfolio_percent(market_value, portfolio_value)
        source = html.escape(str(item.get("source") or "Enterprise evidence"))
        rows.append(
            "<tr>"
            f"<td><strong class='holding-symbol'>{symbol}</strong><small>{pair}</small></td>"
            f"<td><span class='sleeve-badge'>{sleeve}</span></td>"
            f"<td><span class='holding-status {status_class}'>{html.escape(status_label)}</span></td>"
            f"<td class='num'>{_shares(item.get('shares'))}</td>"
            f"<td class='num'>{_money(item.get('price'))}</td>"
            f"<td class='num strong'>{_money(market_value)}</td>"
            f"<td class='num'>{_percent(weight)}</td>"
            "<td><span class='evidence-badge' title='Read-only strategy evidence'>✓ Verified</span>"
            f"<small class='evidence-source'>{source}</small></td>"
            "</tr>"
        )

    return (
        "<section class='holdings-pro'>"
        "<div class='holdings-heading'><div><h3>Holdings</h3>"
        "<p>Strategy-owned paper positions and reserve capital.</p></div>"
        f"<span class='holdings-count'>{position_count} positions</span></div>"
        f"<div class='holdings-summary-grid'>{summary}</div>"
        "<div class='holdings-table-wrap'><table class='holdings-table'>"
        "<thead><tr><th>Symbol / Pair</th><th>Sleeve</th><th>Status</th>"
        "<th>Shares</th><th>Market Price</th><th>Market Value</th>"
        "<th>% Portfolio</th><th>Evidence</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
        "<p class='holdings-footnote'>Paper-only positions. Values are rendered from strategy-owned Enterprise evidence; missing analytics are not fabricated.</p>"
        "</section>"
    )


def holdings_ui_css() -> str:
    """Return Holdings-specific CSS used by the Enterprise portal renderer."""
    return """
.holdings-pro{color:#10213b}.holdings-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:16px}.holdings-heading h3{margin:0 0 5px;font-size:1.2rem}.holdings-heading p{margin:0;color:#64748b}.holdings-count{background:#eef2ff;color:#5b21b6;border:1px solid #d8ccff;border-radius:999px;padding:7px 11px;font-weight:800;white-space:nowrap}.holdings-summary-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:18px}.holdings-summary-card{background:linear-gradient(180deg,#fff,#f8faff);border:1px solid #dbe4f0;border-radius:12px;padding:13px 14px;box-shadow:0 5px 14px rgba(23,43,77,.06)}.holdings-summary-card span,.holdings-summary-card small{display:block;color:#64748b}.holdings-summary-card strong{display:block;margin-top:5px;font-size:1.15rem;color:#10213b}.holdings-summary-card small{margin-top:3px}.holdings-table-wrap{overflow-x:auto;border:1px solid #dbe4f0;border-radius:13px;background:#fff;box-shadow:0 7px 18px rgba(23,43,77,.06)}.holdings-table{width:100%;min-width:920px;border-collapse:collapse}.holdings-table th{padding:11px 12px;text-align:left;background:#f4f7fc;color:#53627a;font-size:.75rem;text-transform:uppercase;letter-spacing:.035em;border-bottom:1px solid #dbe4f0}.holdings-table td{padding:12px;border-bottom:1px solid #edf1f6;vertical-align:middle}.holdings-table tbody tr:last-child td{border-bottom:0}.holdings-table tbody tr:hover{background:#fafbff}.holdings-table td.num,.holdings-table th.num{text-align:right;font-variant-numeric:tabular-nums}.holdings-table td.strong{font-weight:800}.holding-symbol{display:block;font-size:.95rem}.holding-symbol+small{display:block;margin-top:3px;color:#718096}.sleeve-badge,.holding-status,.evidence-badge{display:inline-block;border-radius:999px;padding:5px 8px;font-size:.75rem;font-weight:800}.sleeve-badge{background:#eef2ff;color:#4f46e5}.holding-status.status-open{background:#e9f9f0;color:#087443}.holding-status.status-parked{background:#edf2f7;color:#475569}.holding-status.status-warning{background:#fff7df;color:#a15c00}.holding-status.status-closed{background:#fff0f0;color:#b42318}.holding-status.status-neutral{background:#f1f5f9;color:#475569}.evidence-badge{background:#ecfdf3;color:#087443}.evidence-source{display:block;margin-top:4px;color:#8a97aa}.holdings-footnote{margin:12px 2px 0;color:#718096;font-size:.8rem}.holdings-empty{padding:24px;border:1px dashed #b9c7db;border-radius:12px;background:#f8fafc;text-align:center;color:#64748b}@media(max-width:850px){.holdings-summary-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:520px){.holdings-heading{display:block}.holdings-count{display:inline-block;margin-top:10px}.holdings-summary-grid{grid-template-columns:1fr}}
"""
