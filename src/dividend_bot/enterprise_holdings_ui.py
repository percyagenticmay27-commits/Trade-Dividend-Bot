"""Professional read-only Holdings UI for Enterprise strategy workspaces.

This module is presentation-only. It never mutates portfolio state, places orders,
or invents missing financial evidence. Strategy-owned holdings supplied by the
Enterprise KPI adapter are rendered as a professional financial table with an
explicit capital-reconciliation summary.
"""
from __future__ import annotations

import html
from typing import Any, Mapping, Sequence


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_number(item: Mapping[str, Any], keys: Sequence[str]) -> float | None:
    for key in keys:
        value = _number(item.get(key))
        if value is not None:
            return value
    return None


def _first_value(item: Mapping[str, Any], keys: Sequence[str], default: str = "Not reported") -> str:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return str(value)
    return default


def _money(value: Any) -> str:
    number = _number(value)
    return f"${number:,.2f}" if number is not None else "Not reported"


def _shares(value: Any) -> str:
    number = _number(value)
    if number is None:
        return "Not reported"
    text = f"{number:,.6f}".rstrip("0").rstrip(".")
    return text or "0"


def _percent(value: Any) -> str:
    number = _number(value)
    return f"{number:,.2f}%" if number is not None else "Not reported"


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


def _allocation_percent(market_value: Any, allocated_capital: Any) -> float | None:
    value = _number(market_value)
    total = _number(allocated_capital)
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


def _reconciliation_banner(
    allocated_capital: float | None,
    deployed_value: float,
    available_cash: float | None,
    warning: str | None,
) -> str:
    if allocated_capital is None:
        return (
            "<div class='capital-reconciliation capital-reconciliation-pending'>"
            "<strong>Capital reconciliation pending</strong>"
            "<span>Strategy allocation is not reported, so undeployed cash cannot be reconciled.</span>"
            "</div>"
        )
    reconciled_total = deployed_value + (available_cash or 0.0)
    status_class = "capital-reconciliation-warning" if warning else "capital-reconciliation-ok"
    status_text = warning or (
        f"Allocated capital reconciles: {_money(deployed_value)} deployed holdings + "
        f"{_money(available_cash)} undeployed cash = {_money(reconciled_total)}."
    )
    return (
        f"<div class='capital-reconciliation {status_class}'>"
        "<strong>Capital Reconciliation</strong>"
        f"<span>{html.escape(status_text)}</span>"
        "</div>"
    )


def render_holdings_panel(row: Mapping[str, Any]) -> str:
    """Render a professional, strategy-scoped Holdings panel.

    Calculated display values are limited to arithmetic from already-published
    strategy evidence. Missing analytics remain explicitly unreported rather than
    being estimated. Enterprise allocated capital is reconciled against visible
    holdings and undeployed cash so capital never silently disappears in the UI.
    """

    raw_holdings = row.get("holdings") or row.get("positions")
    holdings: list[Mapping[str, Any]] = (
        [item for item in raw_holdings if isinstance(item, Mapping)]
        if isinstance(raw_holdings, Sequence) and not isinstance(raw_holdings, (str, bytes))
        else []
    )

    allocated_capital = _number(row.get("allocated_capital"))
    reported_portfolio_value = _number(row.get("portfolio_value"))
    reserve_value = 0.0
    invested_value = 0.0
    for item in holdings:
        market_value = _number(item.get("market_value")) or 0.0
        symbol = str(item.get("symbol") or "").strip().upper()
        sleeve = str(item.get("sleeve") or "").strip().upper()
        status = str(item.get("position_status") or item.get("status") or "").strip().upper()
        if symbol == "SGOV" or sleeve in {"RESERVE", "CASH"} or status in {"PARKED", "CASH", "RESERVE"}:
            reserve_value += market_value
        else:
            invested_value += market_value

    holdings_total = reserve_value + invested_value
    deployed_value = reported_portfolio_value if reported_portfolio_value is not None else holdings_total

    explicit_available_cash = _first_number(
        row,
        (
            "available_cash",
            "undeployed_cash",
            "unallocated_cash",
            "remaining_cash",
            "cash_available",
        ),
    )
    available_cash: float | None = explicit_available_cash
    reconciliation_warning: str | None = None
    if allocated_capital is not None:
        derived_available = allocated_capital - holdings_total
        if explicit_available_cash is None:
            if derived_available >= -0.01:
                available_cash = max(0.0, derived_available)
            else:
                reconciliation_warning = (
                    f"Visible holdings {_money(holdings_total)} exceed allocated capital "
                    f"{_money(allocated_capital)}; review strategy evidence."
                )
                available_cash = None
        else:
            explicit_total = holdings_total + explicit_available_cash
            if abs(explicit_total - allocated_capital) > 0.01:
                reconciliation_warning = (
                    f"Reported cash and holdings total {_money(explicit_total)}, which does not match "
                    f"allocated capital {_money(allocated_capital)}."
                )

    count_number = _number(row.get("position_count"))
    position_count = int(count_number) if count_number is not None else len(holdings)

    allocation_base = allocated_capital
    summary = "".join((
        _summary_value("Allocated Capital", _money(allocated_capital), "Enterprise strategy allocation"),
        _summary_value(
            "Deployed Holdings",
            _money(holdings_total),
            _percent(_allocation_percent(holdings_total, allocation_base)),
        ),
        _summary_value(
            "Invested Positions",
            _money(invested_value),
            _percent(_allocation_percent(invested_value, allocation_base)),
        ),
        _summary_value(
            "Cash Reserve (SGOV)",
            _money(reserve_value),
            _percent(_allocation_percent(reserve_value, allocation_base)),
        ),
        _summary_value(
            "Available / Undeployed Cash",
            _money(available_cash),
            _percent(_allocation_percent(available_cash, allocation_base)),
        ),
    ))
    reconciliation = _reconciliation_banner(
        allocated_capital,
        holdings_total,
        available_cash,
        reconciliation_warning,
    )

    if not holdings:
        return (
            "<section class='holdings-pro'>"
            "<div class='holdings-heading'><div><h3>Holdings</h3>"
            "<p>Strategy-owned paper positions, reserve capital, and allocation reconciliation.</p></div>"
            f"<span class='holdings-count'>{position_count} positions</span></div>"
            f"<div class='holdings-summary-grid'>{summary}</div>"
            f"{reconciliation}"
            "<div class='holdings-empty'>No strategy-owned holdings detail is currently reported.</div>"
            "</section>"
        )

    rows: list[str] = []
    for item in holdings:
        symbol = html.escape(str(item.get("symbol") or "UNKNOWN"))
        name = html.escape(_first_value(item, ("name", "security_name", "display_name", "instrument_name")))
        sleeve = html.escape(str(item.get("sleeve") or "—"))
        status_label, status_class = _holding_status(item)
        market_value = item.get("market_value")
        allocation_weight = _allocation_percent(market_value, allocation_base)
        source = html.escape(str(item.get("source") or "Enterprise evidence"))
        cost_basis = _first_number(item, ("cost_basis", "total_cost", "cost_basis_value"))
        avg_cost = _first_number(item, ("average_cost", "avg_cost", "cost_per_share"))
        unrealized_pnl = _first_number(item, ("unrealized_pnl", "unrealized_gain", "unrealized_pl"))
        total_return = _first_number(item, ("total_return_percent", "total_return_pct", "return_percent", "return_pct"))
        daily_change = _first_number(item, ("daily_change_percent", "daily_change_pct", "day_change_percent", "day_change_pct"))
        dividend_yield = _first_number(item, ("dividend_yield_percent", "yield_percent", "distribution_yield_percent"))
        annual_income = _first_number(item, ("annual_income", "projected_annual_income", "annual_dividend_income"))
        next_ex_date = html.escape(_first_value(item, ("next_ex_dividend_date", "next_ex_date", "ex_dividend_date")))
        rows.append(
            "<tr>"
            f"<td><strong class='holding-symbol'>{symbol}</strong></td>"
            f"<td class='holding-name'>{name}</td>"
            f"<td><span class='sleeve-badge'>{sleeve}</span></td>"
            f"<td><span class='holding-status {status_class}'>{html.escape(status_label)}</span></td>"
            f"<td class='num'>{_shares(item.get('shares'))}</td>"
            f"<td class='num'>{_money(item.get('price'))}</td>"
            f"<td class='num strong'>{_money(market_value)}</td>"
            f"<td class='num'>{_percent(allocation_weight)}</td>"
            f"<td class='num'>{_money(cost_basis)}</td>"
            f"<td class='num'>{_money(avg_cost)}</td>"
            f"<td class='num'>{_money(unrealized_pnl)}</td>"
            f"<td class='num'>{_percent(total_return)}</td>"
            f"<td class='num'>{_percent(daily_change)}</td>"
            f"<td class='num'>{_percent(dividend_yield)}</td>"
            f"<td class='num'>{_money(annual_income)}</td>"
            f"<td>{next_ex_date}</td>"
            "<td><span class='evidence-badge' title='Read-only strategy evidence'>✓ Verified</span>"
            f"<small class='evidence-source'>{source}</small></td>"
            "</tr>"
        )

    return (
        "<section class='holdings-pro'>"
        "<div class='holdings-heading'><div><h3>Holdings</h3>"
        "<p>Strategy-owned paper positions, reserve capital, and allocation reconciliation.</p></div>"
        f"<span class='holdings-count'>{position_count} positions</span></div>"
        f"<div class='holdings-summary-grid'>{summary}</div>"
        f"{reconciliation}"
        "<div class='holdings-table-wrap'><table class='holdings-table'>"
        "<thead><tr><th>Symbol</th><th>Name</th><th>Sleeve</th><th>Position Status</th>"
        "<th>Shares</th><th>Market Price</th><th>Market Value</th><th>% Allocation</th>"
        "<th>Cost Basis</th><th>Avg Cost</th><th>Unrealized P&amp;L</th><th>Total Return</th>"
        "<th>Daily Change</th><th>Yield</th><th>Annual Income</th><th>Next Ex-Date</th><th>Evidence</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
        "<p class='holdings-footnote'>Paper-only positions. Allocation percentages use strategy allocated capital. Missing analytics remain Not reported until authoritative strategy evidence is published.</p>"
        "</section>"
    )


def holdings_ui_css() -> str:
    """Return Holdings-specific CSS used by the Enterprise portal renderer."""
    return """
.holdings-pro{color:#10213b}.holdings-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:16px}.holdings-heading h3{margin:0 0 5px;font-size:1.2rem}.holdings-heading p{margin:0;color:#64748b}.holdings-count{background:#eef2ff;color:#5b21b6;border:1px solid #d8ccff;border-radius:999px;padding:7px 11px;font-weight:800;white-space:nowrap}.holdings-summary-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin-bottom:14px}.holdings-summary-card{background:linear-gradient(180deg,#fff,#f8faff);border:1px solid #dbe4f0;border-radius:12px;padding:13px 14px;box-shadow:0 5px 14px rgba(23,43,77,.06)}.holdings-summary-card span,.holdings-summary-card small{display:block;color:#64748b}.holdings-summary-card strong{display:block;margin-top:5px;font-size:1.15rem;color:#10213b}.holdings-summary-card small{margin-top:3px}.capital-reconciliation{display:flex;align-items:flex-start;gap:12px;margin:0 0 18px;padding:12px 14px;border:1px solid;border-radius:11px}.capital-reconciliation strong{white-space:nowrap}.capital-reconciliation-ok{background:#ecfdf3;border-color:#86d9ad;color:#065f46}.capital-reconciliation-warning{background:#fff7df;border-color:#efc66b;color:#8a4b08}.capital-reconciliation-pending{background:#f8fafc;border-color:#cbd5e1;color:#475569}.holdings-table-wrap{overflow-x:auto;border:1px solid #dbe4f0;border-radius:13px;background:#fff;box-shadow:0 7px 18px rgba(23,43,77,.06)}.holdings-table{width:100%;min-width:2050px;border-collapse:collapse}.holdings-table th{padding:11px 12px;text-align:left;background:#f4f7fc;color:#53627a;font-size:.72rem;text-transform:uppercase;letter-spacing:.035em;border-bottom:1px solid #dbe4f0;white-space:nowrap}.holdings-table td{padding:12px;border-bottom:1px solid #edf1f6;vertical-align:middle;white-space:nowrap}.holdings-table tbody tr:last-child td{border-bottom:0}.holdings-table tbody tr:hover{background:#fafbff}.holdings-table td.num,.holdings-table th.num{text-align:right;font-variant-numeric:tabular-nums}.holdings-table td.strong{font-weight:800}.holding-symbol{display:block;font-size:.95rem}.holding-name{max-width:220px;white-space:normal!important;line-height:1.3;color:#334155}.sleeve-badge,.holding-status,.evidence-badge{display:inline-block;border-radius:999px;padding:5px 8px;font-size:.75rem;font-weight:800}.sleeve-badge{background:#eef2ff;color:#4f46e5}.holding-status.status-open{background:#e9f9f0;color:#087443}.holding-status.status-parked{background:#edf2f7;color:#475569}.holding-status.status-warning{background:#fff7df;color:#a15c00}.holding-status.status-closed{background:#fff0f0;color:#b42318}.holding-status.status-neutral{background:#f1f5f9;color:#475569}.evidence-badge{background:#ecfdf3;color:#087443}.evidence-source{display:block;margin-top:4px;color:#8a97aa}.holdings-footnote{margin:12px 2px 0;color:#718096;font-size:.8rem}.holdings-empty{padding:24px;border:1px dashed #b9c7db;border-radius:12px;background:#f8fafc;text-align:center;color:#64748b}@media(max-width:1100px){.holdings-summary-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:850px){.holdings-summary-grid{grid-template-columns:repeat(2,minmax(0,1fr));}.capital-reconciliation{display:block}.capital-reconciliation strong{display:block;margin-bottom:5px}}@media(max-width:520px){.holdings-heading{display:block}.holdings-count{display:inline-block;margin-top:10px}.holdings-summary-grid{grid-template-columns:1fr}}
"""
