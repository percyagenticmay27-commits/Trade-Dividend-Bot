"""Professional read-only Holdings UI for Enterprise strategy workspaces.

Current market value is not forced to equal allocated starting capital. A change in
portfolio value is P&L unless explicit strategy evidence says cash is undeployed.
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


def _signed_money(value: Any) -> str:
    number = _number(value)
    if number is None:
        return "Not reported"
    return f"+${number:,.2f}" if number > 0 else f"-${abs(number):,.2f}" if number < 0 else "$0.00"


def _shares(value: Any) -> str:
    number = _number(value)
    if number is None:
        return "Not reported"
    text = f"{number:,.6f}".rstrip("0").rstrip(".")
    return text or "0"


def _percent(value: Any) -> str:
    number = _number(value)
    return f"{number:,.2f}%" if number is not None else "Not reported"


def _missing(value: str) -> str:
    if value == "Not reported":
        return "<span class='not-reported'>Not reported</span>"
    return value


def _holding_status(item: Mapping[str, Any]) -> tuple[str, str]:
    raw = str(item.get("position_status") or item.get("status") or "UNKNOWN").strip().upper()
    if raw == "OPEN": return "OPEN", "status-open"
    if raw in {"PARKED", "CASH", "RESERVE"}: return "PARKED", "status-parked"
    if "LOCK" in raw: return raw, "status-warning"
    if raw in {"CLOSED", "EXITED"}: return raw, "status-closed"
    return raw or "UNKNOWN", "status-neutral"


def _allocation_percent(market_value: Any, total: Any) -> float | None:
    value = _number(market_value); base = _number(total)
    if value is None or base is None or base <= 0: return None
    return value / base * 100.0


def _summary_value(icon: str, label: str, value: str, detail: str = "") -> str:
    detail_html = f"<small>{html.escape(detail)}</small>" if detail else ""
    return (
        "<div class='holdings-summary-card'>"
        f"<span class='summary-icon' aria-hidden='true'>{html.escape(icon)}</span><div>"
        f"<span>{html.escape(label)}</span><strong>{value}</strong>{detail_html}</div></div>"
    )


def _reconciliation_banner(allocated_capital: float | None, current_value: float | None, warning: str | None) -> str:
    if allocated_capital is None or current_value is None:
        return (
            "<div class='capital-reconciliation capital-reconciliation-pending'>"
            "<strong>Capital reconciliation pending</strong>"
            "<span>Allocated capital or current strategy value is not reported.</span></div>"
        )
    change = current_value - allocated_capital
    status_class = "capital-reconciliation-warning" if warning else "capital-reconciliation-ok"
    status_text = warning or (
        f"Allocated basis {_money(allocated_capital)}; current strategy market value {_money(current_value)}; "
        f"value change {_signed_money(change)}. Market gain/loss is not inferred as undeployed cash."
    )
    return (
        f"<div class='capital-reconciliation {status_class}'>"
        "<strong>Capital Reconciliation</strong>"
        f"<span>{html.escape(status_text)}</span></div>"
    )


def _instrument_rows(holdings: list[Mapping[str, Any]], *, allocation_base: float | None, deployed_base: float) -> str:
    rows: list[str] = []
    for item in holdings:
        symbol = html.escape(str(item.get("symbol") or "UNKNOWN"))
        name = html.escape(_first_value(item, ("name", "security_name", "display_name", "instrument_name")))
        sleeve = html.escape(str(item.get("sleeve") or "—"))
        entry_method = html.escape(_first_value(
            item, ("entry_method", "strategy_owner", "active_strategy")
        ))
        status_label, status_class = _holding_status(item)
        market_value = item.get("market_value")
        strategy_weight = _allocation_percent(market_value, allocation_base)
        deployed_weight = _allocation_percent(market_value, deployed_base)
        rows.append(
            "<tr>"
            f"<td><span class='symbol-mark' aria-hidden='true'>●</span><strong class='holding-symbol'>{symbol}</strong></td>"
            f"<td class='holding-name'>{_missing(name)}</td><td><span class='sleeve-badge'>{sleeve}</span></td>"
            f"<td>{_missing(entry_method)}</td>"
            f"<td><span class='holding-status {status_class}'>{html.escape(status_label)}</span></td>"
            f"<td class='num'>{_missing(_shares(item.get('shares')))}</td>"
            f"<td class='num'>{_missing(_money(_first_number(item, ('price', 'current_price', 'market_price'))))}</td>"
            f"<td class='num strong'>{_missing(_money(market_value))}</td>"
            f"<td class='num'>{_missing(_percent(strategy_weight))}</td>"
            f"<td class='num'>{_missing(_percent(deployed_weight))}</td></tr>"
        )
    return "".join(rows)


def _analytics_rows(holdings: list[Mapping[str, Any]]) -> str:
    rows: list[str] = []
    for item in holdings:
        symbol = html.escape(str(item.get("symbol") or "UNKNOWN"))
        cost_basis = _first_number(item, ("cost_basis", "total_cost", "cost_basis_value"))
        avg_cost = _first_number(
            item, ("average_cost", "avg_cost", "cost_per_share", "entry_price")
        )
        unrealized_pnl = _first_number(item, ("unrealized_pnl", "unrealized_gain", "unrealized_pl"))
        total_return = _first_number(
            item,
            (
                "total_return_percent",
                "total_return_pct",
                "return_percent",
                "return_pct",
                "unrealized_pnl_percent",
            ),
        )
        daily_change = _first_number(item, ("daily_change_percent", "daily_change_pct", "day_change_percent", "day_change_pct"))
        pnl_class = "metric-positive" if unrealized_pnl is not None and unrealized_pnl > 0 else "metric-negative" if unrealized_pnl is not None and unrealized_pnl < 0 else ""
        return_class = "metric-positive" if total_return is not None and total_return > 0 else "metric-negative" if total_return is not None and total_return < 0 else ""
        day_class = "metric-positive" if daily_change is not None and daily_change > 0 else "metric-negative" if daily_change is not None and daily_change < 0 else ""
        rows.append(
            "<tr>"f"<td><strong>{symbol}</strong></td>"
            f"<td class='num'>{_missing(_money(cost_basis))}</td><td class='num'>{_missing(_money(avg_cost))}</td>"
            f"<td class='num {pnl_class}'>{_missing(_money(unrealized_pnl))}</td>"
            f"<td class='num {return_class}'>{_missing(_percent(total_return))}</td>"
            f"<td class='num {day_class}'>{_missing(_percent(daily_change))}</td></tr>"
        )
    return "".join(rows)


def _human_reason(value: Any) -> str:
    return str(value).replace("_", " ").strip().capitalize()


def _management_decision(item: Mapping[str, Any]) -> tuple[str, str, str]:
    owner = str(
        item.get("strategy_owner")
        or item.get("entry_method")
        or item.get("active_strategy")
        or "UNASSIGNED"
    ).upper()
    sell_reasons = [_human_reason(value) for value in item.get("sell_reasons", []) if value] if isinstance(item.get("sell_reasons"), list) else []
    warnings = [_human_reason(value) for value in item.get("exit_warning_reasons", []) if value] if isinstance(item.get("exit_warning_reasons"), list) else []
    if item.get("sell_trigger") is True:
        why = "The owning strategy confirmed its exit conditions"
        if sell_reasons:
            why += ": " + "; ".join(sell_reasons)
        return "SELL CONFIRMED", why + ".", "management-sell"
    if owner == "LEGACY_UNASSIGNED" and (item.get("exit_buffered") is True or item.get("exit_warning_active") is True):
        why = "Held because this legacy position requires both Strategy A and Strategy B to confirm an exit"
        if warnings:
            why += "; current warning: " + "; ".join(warnings)
        return "HOLD — CONSENSUS PENDING", why + ".", "management-warning"
    if item.get("exit_buffered") is True or item.get("exit_warning_active") is True:
        why = "The owner has published a warning, but it has not authorized an exit"
        if warnings:
            why += ": " + "; ".join(warnings)
        return "HOLD — WARNING BUFFERED", why + ".", "management-warning"
    if str(item.get("exit_state") or "").upper() == "UNKNOWN":
        return "EVIDENCE PENDING", "Current owner-specific exit evidence is unavailable; no paper sale is authorized.", "management-neutral"
    return "HOLD", f"{owner.replace('_', ' ').title()} remains the owner and has not confirmed a sell trigger.", "management-hold"


def _management_rows(holdings: list[Mapping[str, Any]]) -> str:
    rows: list[str] = []
    for item in holdings:
        symbol = html.escape(str(item.get("symbol") or "UNKNOWN"))
        owner = _first_value(
            item, ("strategy_owner", "entry_method", "active_strategy")
        )
        decision, explanation, css_class = _management_decision(item)
        evidence_source = _first_value(item, ("exit_evidence_source",), "Not reported")
        evidence_at = _first_value(item, ("exit_evidence_generated_at_utc",), "Not reported")
        rows.append(
            "<tr>"
            f"<td><strong>{symbol}</strong></td>"
            f"<td>{_missing(html.escape(owner.replace('_', ' ').title()))}</td>"
            f"<td><span class='management-state {css_class}'>{html.escape(decision)}</span></td>"
            f"<td class='management-explanation'>{html.escape(explanation)}</td>"
            f"<td>{_missing(html.escape(evidence_at))}<small class='evidence-source'>{_missing(html.escape(evidence_source))}</small></td>"
            "</tr>"
        )
    return "".join(rows)


def _yield_audit(item: Mapping[str, Any]) -> str:
    rate = _first_number(item, ("trailing_12m_distribution_rate",))
    payment_count = _first_number(item, ("trailing_12m_payment_count",))
    price = _first_number(item, ("yearly_distribution_yield_price",))
    price_source = _first_value(item, ("yearly_distribution_yield_price_source",), default="")
    price_as_of = _first_value(item, ("yearly_distribution_yield_price_as_of",), default="")
    window_start = _first_value(item, ("trailing_12m_window_start",), default="")
    window_end = _first_value(item, ("trailing_12m_window_end",), default="")
    method = _first_value(item, ("yearly_distribution_yield_method",), default="")
    if rate is None and payment_count is None and price is None and not window_start and not window_end and not method:
        return "<span class='not-reported'>Not reported</span>"
    facts: list[str] = []
    if rate is not None: facts.append(f"T12M distributions: ${rate:,.4f}/share")
    if payment_count is not None: facts.append(f"Payments: {int(payment_count)}")
    if price is not None: facts.append(f"Yield price: ${price:,.2f}")
    if price_source: facts.append(f"Price source: {price_source.replace('_', ' ').title()}")
    if price_as_of: facts.append(f"Price as-of: {price_as_of}")
    if window_start or window_end: facts.append(f"Window: {window_start or '?'} → {window_end or '?'}")
    if method: facts.append(f"Method: {method.replace('_', ' ').title()}")
    return "<details class='yield-audit'><summary>Audit</summary>" + "".join(f"<small>{html.escape(fact)}</small>" for fact in facts) + "</details>"


def _income_rows(holdings: list[Mapping[str, Any]]) -> str:
    rows: list[str] = []
    for item in holdings:
        symbol = html.escape(str(item.get("symbol") or "UNKNOWN"))
        distribution_yield = _first_number(item, ("yearly_distribution_yield_percent", "dividend_yield_percent", "yield_percent", "distribution_yield_percent"))
        annual_income = _first_number(item, ("annual_income", "projected_annual_income", "annual_dividend_income"))
        reported_ex_date = _first_value(item, ("next_ex_dividend_date", "next_ex_date", "ex_dividend_date"), default="")
        estimated_ex_date = _first_value(item, ("estimated_next_ex_dividend_date",), default="")
        if reported_ex_date:
            next_ex_date = html.escape(reported_ex_date) + " <span class='income-date-status'>Reported</span>"
        elif estimated_ex_date:
            next_ex_date = html.escape(estimated_ex_date) + " <span class='income-date-status income-date-estimated'>Estimated</span>"
        else:
            next_ex_date = "<span class='not-reported'>Not reported</span>"
        source = html.escape(str(item.get("income_analytics_source") or item.get("source") or "Enterprise evidence"))
        evidence = (
            "Observed distribution history and current holding price support this projection."
            if distribution_yield is not None or annual_income is not None
            else "No current income projection evidence is available."
        )
        rows.append(
            "<tr>"f"<td><strong>{symbol}</strong></td>"
            f"<td class='num'>{_missing(_percent(distribution_yield))}</td>"
            f"<td class='num'>{_missing(_money(annual_income))}</td>"
            f"<td>{next_ex_date}</td><td>{_yield_audit(item)}</td>"
            f"<td class='holding-evidence-explanation'>{html.escape(evidence)}<details><summary>Audit source</summary>{source}</details></td></tr>"
        )
    return "".join(rows)


def render_holdings_panel(row: Mapping[str, Any]) -> str:
    raw_holdings = row.get("holdings") or row.get("positions")
    holdings: list[Mapping[str, Any]] = ([item for item in raw_holdings if isinstance(item, Mapping)] if isinstance(raw_holdings, Sequence) and not isinstance(raw_holdings, (str, bytes)) else [])

    allocated_capital = _number(row.get("allocated_capital"))
    reserve_value = invested_value = 0.0
    for item in holdings:
        market_value = _number(item.get("market_value")) or 0.0
        symbol = str(item.get("symbol") or "").strip().upper()
        sleeve = str(item.get("sleeve") or "").strip().upper()
        status = str(item.get("position_status") or item.get("status") or "").strip().upper()
        if symbol == "SGOV" or sleeve in {"RESERVE", "CASH"} or status in {"PARKED", "CASH", "RESERVE"}: reserve_value += market_value
        else: invested_value += market_value

    holdings_total = reserve_value + invested_value
    is_swing = str(row.get("strategy_id") or "").upper() == "SWING-001"
    explicit_available_cash = _first_number(
        row,
        (
            "cash_balance",
            "available_cash",
            "undeployed_cash",
            "unallocated_cash",
            "remaining_cash",
            "cash_available",
        ),
    )
    explicit_invested_capital = _number(row.get("invested_capital"))
    explicit_positions_market_value = _number(row.get("positions_market_value"))
    reported_unrealized_pnl = _first_number(
        row, ("unrealized_pnl", "unrealized_gain")
    )

    if is_swing:
        displayed_positions_value = (
            explicit_positions_market_value
            if explicit_positions_market_value is not None
            else invested_value
        )
        displayed_cash = (
            explicit_available_cash
            if explicit_available_cash is not None
            else reserve_value
        )
        current_value = displayed_positions_value + displayed_cash
    else:
        displayed_positions_value = invested_value
        displayed_cash = reserve_value
        current_value = holdings_total + (explicit_available_cash or 0.0)

    reported_portfolio_value = _number(row.get("portfolio_value"))
    reconciliation_warning = None
    if reported_portfolio_value is not None and abs(reported_portfolio_value - current_value) > 0.02:
        reconciliation_warning = (
            f"Visible holdings/cash total {_money(current_value)} does not match reported portfolio value {_money(reported_portfolio_value)}; review strategy evidence."
        )
        current_value = reported_portfolio_value

    count_number = _number(row.get("position_count")); position_count = int(count_number) if count_number is not None else len(holdings)
    value_change = current_value - allocated_capital if allocated_capital is not None else None
    if is_swing:
        summary = "".join((
            _summary_value("◆", "Allocated Capital", _money(allocated_capital), "AI CIO governed strategy allocation"),
            _summary_value("▣", "Current Portfolio Value", _money(current_value), _signed_money(value_change)),
            _summary_value("◈", "Invested Capital", _money(explicit_invested_capital), "Published position cost capital"),
            _summary_value("↗", "Positions Market Value", _money(displayed_positions_value), _percent(_allocation_percent(displayed_positions_value, current_value))),
            _summary_value("▤", "Cash Reserve", _money(displayed_cash), "Explicit Swing cash balance"),
            _summary_value("±", "Unrealized P&L", _signed_money(reported_unrealized_pnl), "Strategy-owned evidence"),
        ))
    else:
        summary = "".join((
            _summary_value("◆", "Allocated Capital", _money(allocated_capital), "Enterprise strategy starting allocation"),
            _summary_value("▣", "Current Portfolio Value", _money(current_value), _signed_money(value_change)),
            _summary_value("↗", "Invested Positions", _money(invested_value), _percent(_allocation_percent(invested_value, current_value))),
            _summary_value("▤", "Cash Reserve (SGOV)", _money(reserve_value), _percent(_allocation_percent(reserve_value, current_value))),
            _summary_value("◌", "Available / Undeployed Cash", _money(explicit_available_cash), "Explicit evidence only"),
        ))
    reconciliation = _reconciliation_banner(allocated_capital, current_value, reconciliation_warning)

    panel_class = "holdings-pro swing-holdings" if is_swing else "holdings-pro"
    heading = "<div class='holdings-heading'><div><h3>Holdings</h3><p>Strategy-owned paper positions, reserve capital, and market-value reconciliation.</p></div>" + f"<span class='holdings-count'>{position_count} positions</span></div>"
    if not holdings:
        return f"<section class='{panel_class}'>" + heading + f"<div class='holdings-summary-grid'>{summary}</div>{reconciliation}<div class='holdings-empty'>No strategy-owned holdings detail is currently reported.</div></section>"

    overview = "<section class='holdings-subsection'><div class='subsection-heading'><h4>Holdings Overview</h4><span>Position identity, owning entry method, and capital weights</span></div><div class='holdings-table-wrap'><table class='holdings-table holdings-overview-table'><thead><tr><th>Symbol</th><th>Name</th><th>Sleeve</th><th>Entry Method</th><th>Status</th><th>Shares</th><th>Market Price</th><th>Market Value</th><th>% Strategy Allocation</th><th>% Deployed Portfolio</th></tr></thead>" + f"<tbody>{_instrument_rows(holdings, allocation_base=allocated_capital, deployed_base=current_value)}</tbody></table></div></section>"
    analytics = "<section class='holdings-subsection'><div class='subsection-heading'><h4>Position Analytics</h4><span>Authoritative cost and performance evidence</span></div><div class='holdings-table-wrap'><table class='holdings-table holdings-analytics-table'><thead><tr><th>Symbol</th><th>Cost Basis</th><th>Avg Cost</th><th>Unrealized P&amp;L</th><th>Total Return</th><th>Daily Change</th></tr></thead>" + f"<tbody>{_analytics_rows(holdings)}</tbody></table></div></section>"
    management = "<section class='holdings-subsection'><div class='subsection-heading'><h4>Position Management</h4><span>Why each position is held and what would authorize an exit</span></div><div class='holdings-table-wrap'><table class='holdings-table holdings-management-table'><thead><tr><th>Symbol</th><th>Owning Strategy</th><th>Current Decision</th><th>Why Held / What Changes It</th><th>Evidence As-Of</th></tr></thead>" + f"<tbody>{_management_rows(holdings)}</tbody></table></div></section>"
    income = "<section class='holdings-subsection'><div class='subsection-heading'><h4>Income</h4><span>Observed yearly distribution and income evidence</span></div><div class='holdings-table-wrap'><table class='holdings-table holdings-income-table'><thead><tr><th>Symbol</th><th>Yearly Distribution Yield</th><th>Annual Income</th><th>Next Ex-Date</th><th>Audit</th><th>Evidence</th></tr></thead>" + f"<tbody>{_income_rows(holdings)}</tbody></table></div></section>"
    return f"<section class='{panel_class}'>" + heading + f"<div class='holdings-summary-grid'>{summary}</div>{reconciliation}{overview}{analytics}{management}{income}<p class='holdings-footnote'>Paper-only positions. Entry Method is strategy-owned lifecycle evidence and is never inferred when missing. Market gain/loss is never labeled as undeployed cash. Yearly Distribution Yield uses observed trailing-365-day distributions and the displayed current holding price when available; open Audit to review inputs.</p></section>"


def holdings_ui_css() -> str:
    return """
<style>
.holdings-pro{color:#10213b}.holdings-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:16px}.holdings-heading h3{margin:0 0 5px;font-size:1.2rem}.holdings-heading p{margin:0;color:#64748b}.holdings-count{background:#eef2ff;color:#5b21b6;border:1px solid #d8ccff;border-radius:999px;padding:7px 11px;font-weight:800;white-space:nowrap}.holdings-summary-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin-bottom:14px}.swing-holdings .holdings-summary-grid{grid-template-columns:repeat(6,minmax(0,1fr))}.holdings-summary-card{display:flex;align-items:flex-start;gap:10px;background:linear-gradient(180deg,#fff,#f8faff);border:1px solid #dbe4f0;border-radius:12px;padding:13px 14px;box-shadow:0 5px 14px rgba(23,43,77,.06)}.summary-icon{display:grid!important;place-items:center;width:30px;height:30px;flex:0 0 30px;border-radius:9px;background:#f0eaff;color:#5b21b6;font-weight:900}.holdings-summary-card span,.holdings-summary-card small{display:block;color:#64748b}.holdings-summary-card strong{display:block;margin-top:5px;font-size:1.15rem;color:#10213b}.holdings-summary-card small{margin-top:3px}.capital-reconciliation{display:flex;align-items:flex-start;gap:12px;margin:0 0 18px;padding:12px 14px;border:1px solid;border-radius:11px}.capital-reconciliation strong{white-space:nowrap}.capital-reconciliation-ok{background:#ecfdf3;border-color:#86d9ad;color:#065f46}.capital-reconciliation-warning{background:#fff7df;border-color:#efc66b;color:#8a4b08}.capital-reconciliation-pending{background:#f8fafc;border-color:#cbd5e1;color:#475569}.holdings-subsection{margin:18px 0}.subsection-heading{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin:0 2px 8px}.subsection-heading h4{margin:0;font-size:1rem}.subsection-heading span{color:#64748b;font-size:.8rem}.holdings-table-wrap{overflow-x:auto;border:1px solid #dbe4f0;border-radius:13px;background:#fff;box-shadow:0 7px 18px rgba(23,43,77,.06)}.holdings-table{width:100%;border-collapse:collapse;table-layout:auto}.holdings-overview-table{min-width:1240px}.holdings-analytics-table{min-width:760px}.holdings-management-table{min-width:980px}.holdings-income-table{min-width:900px}.holdings-table th{padding:11px 12px;text-align:left;background:#f4f7fc;color:#53627a;font-size:.72rem;text-transform:uppercase;letter-spacing:.035em;border-bottom:1px solid #dbe4f0;white-space:nowrap}.holdings-table td{padding:12px;border-bottom:1px solid #edf1f6;vertical-align:middle;white-space:nowrap}.holdings-table tbody tr:last-child td{border-bottom:0}.holdings-table tbody tr:hover{background:#fafbff}.holdings-table td.num{text-align:right;font-variant-numeric:tabular-nums}.holdings-table td.strong{font-weight:800}.holding-symbol{display:inline-block;font-size:.95rem}.symbol-mark{display:inline-block;margin-right:8px;color:#6d3be8}.holding-name{min-width:180px;max-width:220px;white-space:normal!important;line-height:1.3;color:#334155}.sleeve-badge,.holding-status,.evidence-badge,.not-reported{display:inline-block;border-radius:999px;padding:5px 8px;font-size:.75rem;font-weight:800}.sleeve-badge{background:#eef2ff;color:#4f46e5}.holding-status.status-open{background:#e9f9f0;color:#087443}.holding-status.status-parked{background:#edf2f7;color:#475569}.holding-status.status-warning{background:#fff7df;color:#a15c00}.holding-status.status-closed{background:#fff0f0;color:#b42318}.holding-status.status-neutral{background:#f1f5f9;color:#475569}.evidence-badge{background:#ecfdf3;color:#087443}.not-reported{background:#f1f5f9;color:#7a8798;font-weight:700}.metric-positive{color:#087443;font-weight:800}.metric-negative{color:#b42318;font-weight:800}.management-state{display:inline-block;border-radius:999px;padding:5px 8px;font-size:.75rem;font-weight:800}.management-hold{background:#e9f9f0;color:#087443}.management-warning{background:#fff7df;color:#8a4b08}.management-sell{background:#fff0f0;color:#b42318}.management-neutral{background:#f1f5f9;color:#64748b}.management-explanation{min-width:320px;max-width:520px;white-space:normal!important;line-height:1.35}.evidence-source{display:block;margin-top:4px;color:#8a97aa}.holding-evidence-explanation{min-width:280px;max-width:380px;white-space:normal!important;line-height:1.35}.holding-evidence-explanation details{margin-top:5px;color:#64748b}.holding-evidence-explanation summary{cursor:pointer;color:#5b21b6;font-weight:700}.income-date-status{display:inline-block;margin-left:4px;padding:3px 6px;border-radius:999px;background:#ecfdf3;color:#047857;font-size:9px;font-weight:800}.income-date-estimated{background:#fff7df;color:#8a4b08}.yield-audit{min-width:190px}.yield-audit summary{cursor:pointer;color:#5b21b6;font-weight:800}.yield-audit small{display:block;color:#64748b;white-space:normal;margin-top:4px;line-height:1.25}.holdings-footnote{margin:12px 2px 0;color:#718096;font-size:.8rem}.holdings-empty{padding:24px;border:1px dashed #b9c7db;border-radius:12px;background:#f8fafc;text-align:center;color:#64748b}@media(max-width:1100px){.holdings-summary-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:850px){.holdings-summary-grid{grid-template-columns:repeat(2,minmax(0,1fr));}.capital-reconciliation,.subsection-heading{display:block}.capital-reconciliation strong,.subsection-heading h4{display:block;margin-bottom:5px}}@media(max-width:520px){.holdings-heading{display:block}.holdings-count{display:inline-block;margin-top:10px}.holdings-summary-grid{grid-template-columns:1fr}}
</style>
"""
