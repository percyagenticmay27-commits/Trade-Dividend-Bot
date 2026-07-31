"""Read-only dashboard artifact rendering for the AI CIO allocation portal."""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Mapping, Optional

from .enterprise_executive_dashboard import format_dashboard_html

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


def render_unavailable_dashboard(title: str, message: str) -> str:
    safe_title = html.escape(title)
    safe_message = html.escape(message)
    return f"""<section class='panel'><h2>{safe_title}</h2><div class='commentary'>{safe_message}</div><p>This page is read-only and does not fabricate portfolio data.</p></section>"""


def load_executive_dashboard_body(
    *,
    html_path: Path,
    json_path: Path,
) -> tuple[str, bool]:
    """Return executive dashboard HTML and whether it is a complete document."""
    if html_path.is_file():
        return html_path.read_text(encoding="utf-8"), True
    if json_path.is_file():
        report = _load_mapping(json_path)
        return format_dashboard_html(report), True
    return render_unavailable_dashboard(
        "Executive Dashboard Unavailable",
        "Executive dashboard data has not been generated yet.",
    ), False


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
            for key, value in row.items()
            if key not in label_keys and value not in (None, "", [], {})
        )
        items.append(f"<li><strong>{html.escape(str(label))}</strong>{': ' + details if details else ''}</li>")
    return "<ul>" + "".join(items) + "</ul>" if items else "<p>None reported.</p>"


def render_investor_dashboard_body(report: Mapping[str, Any]) -> str:
    summary = report.get("investor_summary") if isinstance(report.get("investor_summary"), Mapping) else {}
    reliability = report.get("income_reliability") if isinstance(report.get("income_reliability"), Mapping) else {}
    allocation = report.get("allocation") if isinstance(report.get("allocation"), Mapping) else {}
    holdings = allocation.get("holdings") if isinstance(allocation.get("holdings"), list) else []
    generated = html.escape(str(report.get("generated_at_utc") or "Not available"))
    health = html.escape(str(report.get("portfolio_health") or "UNKNOWN"))

    summary_cards = (
        ("Portfolio Value", _money(summary.get("portfolio_value"))),
        ("Capital Appreciation", _money(summary.get("capital_appreciation"))),
        ("Projected Annual Income", _money(summary.get("projected_annual_dividend_income"))),
        ("Current Yield", _percent(summary.get("current_yield_percent"))),
        ("Cash / Reserve", _money(summary.get("cash_or_reserve_value"))),
        ("Portfolio Health", health),
    )
    cards = "".join(
        f"<article class='card'><div class='label'>{html.escape(label)}</div><div class='value'>{html.escape(value)}</div></article>"
        for label, value in summary_cards
    )

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
        "</tr>"
        for row in holdings
        if isinstance(row, Mapping)
    ) or "<tr><td colspan='4'>No holdings data is available.</td></tr>"

    warnings = report.get("warnings") if isinstance(report.get("warnings"), list) else []
    warning_html = "<ul>" + "".join(f"<li>{html.escape(str(item))}</li>" for item in warnings) + "</ul>" if warnings else "<p>None reported.</p>"

    return f"""
<section class='grid'>{cards}</section>
<section class='panel'><h2>Investor Dashboard</h2><p><strong>Generated:</strong> {generated}</p><p>This dashboard is reporting-only and paper-only.</p></section>
<section class='two'>
  <article class='panel'><h2>Income Reliability</h2><ul>{reliability_rows}</ul></article>
  <article class='panel'><h2>Upcoming Payments</h2>{_list_items(report.get('upcoming_payments'), label_keys=('symbol', 'ticker', 'name', 'event'))}</article>
</section>
<section class='panel'><h2>Allocation and Holdings</h2><table style='width:100%;border-collapse:collapse'><thead><tr><th align='left'>Holding</th><th align='left'>Market Value</th><th align='left'>Allocation</th><th align='left'>Sector</th></tr></thead><tbody>{holding_rows}</tbody></table></section>
<section class='two'>
  <article class='panel'><h2>Risk Flags</h2>{_list_items(report.get('risk_flags'), label_keys=('code', 'flag', 'message'))}</article>
  <article class='panel'><h2>Suggested Actions</h2>{_list_items(report.get('suggested_actions'), label_keys=('action', 'message'))}</article>
</section>
<section class='panel'><h2>Warnings</h2>{warning_html}</section>
"""


def load_investor_dashboard_body(*, json_path: Path) -> tuple[str, bool]:
    if json_path.is_file():
        report = _load_mapping(json_path)
        return render_investor_dashboard_body(report), True
    return render_unavailable_dashboard(
        "Investor Dashboard Unavailable",
        "Investor dashboard data has not been generated yet.",
    ), False
