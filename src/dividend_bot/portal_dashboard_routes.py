"""Read-only dashboard artifact rendering for the AI CIO allocation portal."""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Mapping

from .enterprise_portal_strategy_ui_v2 import render_left_navigation, render_strategy_workspace, strategy_ui_css

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
REPORTING_ONLY = True


def _load_mapping(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("dashboard artifact must contain a JSON object")
    return value


def _money(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def _percent(value: Any) -> str:
    try:
        return f"{float(value):,.2f}%"
    except (TypeError, ValueError):
        return "0.00%"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text_list(values: Any) -> str:
    if not isinstance(values, list) or not values:
        return "<p>None reported.</p>"
    return "<ul>" + "".join(f"<li>{html.escape(str(value))}</li>" for value in values) + "</ul>"


def _cards(items: tuple[tuple[str, str], ...]) -> str:
    return "".join(
        "<article class='card'>"
        f"<div class='label'>{html.escape(label)}</div>"
        f"<div class='value'>{html.escape(value)}</div>"
        "<div class='scope-card'>Enterprise total</div>"
        "</article>"
        for label, value in items
    )


def _portal_frame(content: str, active: str) -> str:
    return f"{strategy_ui_css()}<div class='portal-frame'>{render_left_navigation(active)}<div class='enterprise-content'>{content}</div></div>"


def render_unavailable_dashboard(title: str, message: str) -> str:
    return (
        f"<section class='panel'><h2>{html.escape(title)}</h2>"
        f"<div class='commentary'>{html.escape(message)}</div>"
        "<p>This page is read-only and does not fabricate portfolio data.</p></section>"
    )


def render_executive_dashboard_body(report: Mapping[str, Any]) -> str:
    portfolio = _mapping(report.get("portfolio_summary"))
    enterprise = _mapping(report.get("enterprise_summary"))
    health = _mapping(report.get("health_summary"))
    runtime = _mapping(report.get("runtime_summary"))
    safety = _mapping(report.get("paper_safety"))
    alerts = _mapping(report.get("alerts"))
    portfolio_value = portfolio.get("portfolio_value", report.get("portfolio_value", 0))
    available_cash = portfolio.get("available_cash", portfolio.get("cash_or_reserve_value", 0))
    allocated_cash = portfolio.get("allocated_cash", 0)
    projected_income = portfolio.get("projected_annual_dividend_income", portfolio.get("projected_annual_income", 0))
    registered = enterprise.get("registered_strategy_count", report.get("registered_strategy_count", len(report.get("strategy_kpis", [])) if isinstance(report.get("strategy_kpis"), list) else 0))
    status = enterprise.get("enterprise_status", report.get("status", "UNKNOWN"))
    generated = report.get("generated_at_utc", "Not available")
    scope = report.get("dashboard_scope", "ENTERPRISE_ALL_REGISTERED_STRATEGIES")

    cards = _cards((
        ("Enterprise Portfolio Value", _money(portfolio_value)),
        ("Enterprise Available Cash", _money(available_cash)),
        ("Enterprise Allocated Capital", _money(allocated_cash)),
        ("Enterprise Projected Annual Income", _money(projected_income)),
        ("Registered Strategies", str(registered)),
        ("Enterprise Status", str(status)),
    ))
    critical = alerts.get("critical", report.get("critical_alerts", []))
    warnings = alerts.get("warnings", report.get("warnings", []))
    informational = alerts.get("informational", [])

    content = f"""
<section class='panel'><h2>Enterprise Scope</h2><p><strong>{html.escape(str(scope))}</strong></p><p>Top-level KPIs aggregate the existing AI CIO host and every registered strategy for which evidence is available. Strategy-specific figures appear below.</p></section>
<section class='grid'>{cards}</section>
<section class='panel'><h2>AI CIO Executive Dashboard</h2><p><strong>Generated:</strong> {html.escape(str(generated))}</p><p>This dashboard is read-only, reporting-only, and paper-only.</p></section>
{render_strategy_workspace(report, audience='executive')}
<section class='two'>
  <article class='panel'><h2>Enterprise Health Summary</h2><ul>
    <li><strong>Healthy:</strong> {html.escape(str(health.get('healthy_count', 0)))}</li>
    <li><strong>Warning:</strong> {html.escape(str(health.get('warning_count', 0)))}</li>
    <li><strong>Degraded:</strong> {html.escape(str(health.get('degraded_count', 0)))}</li>
    <li><strong>Critical:</strong> {html.escape(str(health.get('critical_count', 0)))}</li>
  </ul></article>
  <article class='panel'><h2>Enterprise Runtime Summary</h2><ul>
    <li><strong>Status:</strong> {html.escape(str(runtime.get('runtime_status', 'UNKNOWN')))}</li>
    <li><strong>Running Strategies:</strong> {html.escape(str(runtime.get('running_strategy_count', 0)))}</li>
    <li><strong>Plugin Count:</strong> {html.escape(str(runtime.get('plugin_count', registered)))}</li>
    <li><strong>Paper Safety:</strong> {html.escape(str(safety.get('status', 'UNKNOWN')))}</li>
  </ul></article>
</section>
<section class='two'><article class='panel'><h2>Critical Alerts</h2>{_text_list(critical)}</article><article class='panel'><h2>Warnings</h2>{_text_list(warnings)}</article></section>
<section class='panel'><h2>Informational</h2>{_text_list(informational)}</section>
"""
    return _portal_frame(content, "Executive Dashboard")


def load_executive_dashboard_body(*, html_path: Path, json_path: Path) -> tuple[str, bool]:
    """Render the freshest structured Executive Dashboard evidence when available.

    The JSON artifact is the live reporting contract and is refreshed as upstream
    strategy evidence changes. A pre-rendered HTML artifact is retained strictly
    as a compatibility fallback so an older HTML snapshot cannot mask newer Swing
    watchlist / Promotion Readiness evidence.
    """
    if json_path.is_file():
        return render_executive_dashboard_body(_load_mapping(json_path)), False
    if html_path.is_file():
        return html_path.read_text(encoding="utf-8"), True
    return _portal_frame(render_unavailable_dashboard("Executive Dashboard Unavailable", "Executive dashboard data has not been generated yet."), "Executive Dashboard"), False


def _list_items(rows: Any, *, label_keys: tuple[str, ...]) -> str:
    if not isinstance(rows, list) or not rows:
        return "<p>None reported.</p>"
    items: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        label = next((row.get(key) for key in label_keys if row.get(key) not in (None, "")), "Item")
        details = ", ".join(
            f"{html.escape(str(key).replace('_', ' ').title())}: {html.escape(str(value))}"
            for key, value in row.items() if key not in label_keys and value not in (None, "", [], {})
        )
        items.append(f"<li><strong>{html.escape(str(label))}</strong>{': ' + details if details else ''}</li>")
    return "<ul>" + "".join(items) + "</ul>" if items else "<p>None reported.</p>"


def render_investor_dashboard_body(report: Mapping[str, Any]) -> str:
    summary = _mapping(report.get("investor_summary"))
    reliability = _mapping(report.get("income_reliability"))
    allocation = _mapping(report.get("allocation"))
    holdings = allocation.get("holdings") if isinstance(allocation.get("holdings"), list) else []
    generated = html.escape(str(report.get("generated_at_utc") or "Not available"))
    health = html.escape(str(report.get("portfolio_health") or "UNKNOWN"))
    scope = html.escape(str(report.get("dashboard_scope") or "ENTERPRISE_ALL_REGISTERED_STRATEGIES"))

    cards = _cards((
        ("Enterprise Portfolio Value", _money(summary.get("portfolio_value"))),
        ("Enterprise Capital Appreciation", _money(summary.get("capital_appreciation"))),
        ("Enterprise Projected Annual Income", _money(summary.get("projected_annual_dividend_income"))),
        ("Enterprise Current Yield", _percent(summary.get("current_yield_percent"))),
        ("Enterprise Cash / Reserve", _money(summary.get("cash_or_reserve_value"))),
        ("Enterprise Portfolio Health", health),
    ))
    reliability_rows = "".join(
        f"<li><strong>{html.escape(str(key).replace('_', ' ').title())}:</strong> {html.escape(str(value))}</li>"
        for key, value in reliability.items()
    ) or "<li>No income reliability data is available.</li>"
    holding_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(row.get('symbol') or 'UNKNOWN'))}</td>"
        f"<td>{_money(row.get('market_value'))}</td>"
        f"<td>{_percent(row.get('allocation_percent'))}</td>"
        f"<td>{html.escape(str(row.get('sector') or 'Unclassified'))}</td>"
        "</tr>" for row in holdings if isinstance(row, Mapping)
    ) or "<tr><td colspan='4'>No enterprise holdings data is available.</td></tr>"

    content = f"""
<section class='panel'><h2>Enterprise Scope</h2><p><strong>{scope}</strong></p><p>The top row represents the combined investor view. Select a registered strategy below to see only that strategy's allocated capital and available KPIs.</p></section>
<section class='grid'>{cards}</section>
<section class='panel'><h2>Enterprise Investor Dashboard</h2><p><strong>Generated:</strong> {generated}</p><p>This dashboard is reporting-only and paper-only.</p></section>
{render_strategy_workspace(report, audience='investor')}
<section class='two'><article class='panel'><h2>Enterprise Income Reliability</h2><ul>{reliability_rows}</ul></article><article class='panel'><h2>Upcoming Payments</h2>{_list_items(report.get('upcoming_payments'), label_keys=('symbol','ticker','name','event'))}</article></section>
<section class='panel'><h2>Enterprise Allocation and Holdings</h2><table style='width:100%;border-collapse:collapse'><thead><tr><th align='left'>Holding</th><th align='left'>Market Value</th><th align='left'>Allocation</th><th align='left'>Sector</th></tr></thead><tbody>{holding_rows}</tbody></table></section>
<section class='two'><article class='panel'><h2>Risk Flags</h2>{_list_items(report.get('risk_flags'), label_keys=('code','flag','message'))}</article><article class='panel'><h2>Suggested Actions</h2>{_list_items(report.get('suggested_actions'), label_keys=('action','message'))}</article></section>
<section class='panel'><h2>Warnings</h2>{_text_list(report.get('warnings'))}</section>
"""
    return _portal_frame(content, "Investor Dashboard")


def load_investor_dashboard_body(*, json_path: Path) -> tuple[str, bool]:
    if json_path.is_file():
        return render_investor_dashboard_body(_load_mapping(json_path)), False
    return _portal_frame(render_unavailable_dashboard("Investor Dashboard Unavailable", "Investor dashboard data has not been generated yet."), "Investor Dashboard"), False
