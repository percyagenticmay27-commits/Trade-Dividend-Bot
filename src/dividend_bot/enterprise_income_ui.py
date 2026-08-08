"""Professional, read-only income workspace for Enterprise strategy dashboards."""
from __future__ import annotations

import html
from typing import Any, Mapping


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _money(value: Any) -> str:
    number = _number(value)
    return f"${number:,.2f}" if number is not None else "Not reported"


def _percent(value: Any) -> str:
    number = _number(value)
    return f"{number:,.2f}%" if number is not None else "Not reported"


def _text(value: Any) -> str:
    if value in (None, ""):
        return "Not reported"
    return html.escape(str(value))


def _holdings(row: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    value = row.get("holdings")
    return [item for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


def _events(row: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    value = row.get("income_events")
    return [item for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


def _projected_monthly_income(row: Mapping[str, Any]) -> float | None:
    annual = _number(row.get("projected_annual_income"))
    return round(annual / 12.0, 2) if annual is not None else None


def _income_position_count(row: Mapping[str, Any]) -> int:
    return sum(1 for item in _holdings(row) if (_number(item.get("annual_income")) or 0.0) > 0)


def _income_holding_rows(row: Mapping[str, Any]) -> str:
    rendered: list[str] = []
    for item in _holdings(row):
        annual_income = _number(item.get("annual_income"))
        yearly_yield = _number(
            item.get("yearly_distribution_yield_percent")
            if item.get("yearly_distribution_yield_percent") is not None
            else item.get("dividend_yield_percent")
        )
        if annual_income is None and yearly_yield is None:
            continue
        symbol = _text(item.get("symbol"))
        name = _text(item.get("name"))
        source = _text(item.get("income_analytics_source") or item.get("source"))
        rendered.append(
            "<tr>"
            f"<td><strong>{symbol}</strong></td>"
            f"<td>{name}</td>"
            f"<td>{_percent(yearly_yield)}</td>"
            f"<td><strong>{_money(annual_income)}</strong></td>"
            f"<td>{_text(item.get('payment_frequency'))}</td>"
            f"<td>{_text(item.get('next_ex_dividend_date'))}</td>"
            f"<td>{source}</td>"
            "</tr>"
        )
    if not rendered:
        return "<tr><td colspan='7' class='income-empty-cell'>No strategy-owned income projection evidence is currently reported.</td></tr>"
    return "".join(rendered)


def _event_rows(row: Mapping[str, Any]) -> str:
    rendered: list[str] = []
    for event in reversed(_events(row)):
        rendered.append(
            "<tr>"
            f"<td>{_text(event.get('date'))}</td>"
            f"<td><strong>{_text(event.get('symbol'))}</strong></td>"
            f"<td>{_text(event.get('event_type'))}</td>"
            f"<td><strong>{_money(event.get('amount'))}</strong></td>"
            f"<td>{_text(event.get('source'))}</td>"
            "</tr>"
        )
    if not rendered:
        return "<tr><td colspan='5' class='income-empty-cell'>No realized strategy-owned income events have been recorded yet.</td></tr>"
    return "".join(rendered)


def render_income_panel(row: Mapping[str, Any]) -> str:
    """Render strategy-owned realized and projected income without fabrication."""
    received = row.get("income")
    annual = row.get("projected_annual_income")
    monthly = _projected_monthly_income(row)
    event_count = len(_events(row))
    income_positions = _income_position_count(row)

    return (
        "<section class='income-pro' aria-label='Strategy income'>"
        "<div class='income-heading'>"
        "<div><h3>Income</h3><p>Strategy-owned realized distributions and current annual income projection.</p></div>"
        f"<span class='income-event-badge'>{event_count} realized event{'s' if event_count != 1 else ''}</span>"
        "</div>"
        "<div class='income-summary-grid'>"
        f"<article><span>Income Received</span><strong>{_money(received)}</strong><small>Recorded paper distributions</small></article>"
        f"<article><span>Projected Annual Income</span><strong>{_money(annual)}</strong><small>Current holdings projection</small></article>"
        f"<article><span>Projected Monthly Income</span><strong>{_money(monthly)}</strong><small>Annual projection ÷ 12</small></article>"
        f"<article><span>Income-Producing Positions</span><strong>{income_positions}</strong><small>Holdings with published income evidence</small></article>"
        "</div>"
        "<div class='income-section-heading'><h4>Income by Holding</h4><span>Observed distribution evidence and current projections</span></div>"
        "<div class='income-table-wrap'><table class='income-table'>"
        "<thead><tr><th>Symbol</th><th>Name</th><th>Yearly Distribution Yield</th><th>Annual Income</th><th>Frequency</th><th>Next Ex-Date</th><th>Evidence</th></tr></thead>"
        f"<tbody>{_income_holding_rows(row)}</tbody></table></div>"
        "<div class='income-section-heading'><h4>Distribution History</h4><span>Realized paper income only</span></div>"
        "<div class='income-table-wrap'><table class='income-table income-history-table'>"
        "<thead><tr><th>Date</th><th>Symbol</th><th>Event</th><th>Amount</th><th>Evidence</th></tr></thead>"
        f"<tbody>{_event_rows(row)}</tbody></table></div>"
        "<p class='income-footnote'>Projected income is not treated as realized income. Missing payment dates or analytics remain Not reported until authoritative strategy evidence is published.</p>"
        "</section>"
    )


def income_ui_css() -> str:
    return """
<style>
.income-pro{min-width:0}.income-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:14px}.income-heading h3{margin:0}.income-heading p{margin:5px 0 0;color:#64748b}.income-event-badge{white-space:nowrap;background:#ecfdf3;color:#047857;border:1px solid #a7f3d0;border-radius:999px;padding:6px 10px;font-size:12px;font-weight:800}.income-summary-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:12px 0 18px}.income-summary-grid article{border:1px solid #dbe4ef;background:linear-gradient(180deg,#fff,#f8fbff);border-radius:12px;padding:12px}.income-summary-grid span,.income-summary-grid small{display:block;color:#64748b}.income-summary-grid strong{display:block;margin:5px 0;font-size:18px;color:#0f5132}.income-summary-grid small{font-size:10px}.income-section-heading{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin:18px 0 8px}.income-section-heading h4{margin:0;color:#0b1d3a}.income-section-heading span{font-size:11px;color:#64748b}.income-table-wrap{overflow-x:auto;border:1px solid #dbe4ef;border-radius:11px}.income-table{width:100%;border-collapse:collapse;min-width:820px}.income-history-table{min-width:620px}.income-table th{padding:9px 10px;background:#f4f7fb;color:#475569;text-align:left;text-transform:uppercase;font-size:10px;letter-spacing:.03em}.income-table td{padding:10px;border-top:1px solid #e5eaf1;font-size:12px}.income-table tbody tr:hover{background:#fbfdff}.income-empty-cell{text-align:center!important;color:#64748b;padding:22px!important}.income-footnote{margin:12px 0 0;color:#64748b;font-size:11px}.income-footnote strong{color:#334155}@media(max-width:900px){.income-summary-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:520px){.income-summary-grid{grid-template-columns:1fr}.income-heading,.income-section-heading{display:block}.income-event-badge{display:inline-block;margin-top:8px}}
</style>"""
