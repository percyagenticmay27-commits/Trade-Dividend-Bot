"""Scan-first read-only UI for the Enterprise AI CIO staging portal."""
from __future__ import annotations

import html
from typing import Any, Mapping

from .enterprise_portal_strategy_ui import render_left_navigation, strategy_ui_css


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _money(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "Not reported"


def _percent(value: Any) -> str:
    try:
        return f"{float(value):,.2f}%"
    except (TypeError, ValueError):
        return "Not reported"


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _status_tone(status: Any) -> str:
    normalized = str(status or "UNKNOWN").upper()
    if normalized in {"HEALTHY", "GOOD", "READY", "RUNNING", "PROFITABLE", "POSITIVE"}:
        return "good"
    if normalized in {"WARNING", "PARTIAL", "MONITORING", "FAIR", "UNKNOWN"}:
        return "watch"
    if normalized in {"CRITICAL", "DEGRADED", "ERROR", "LOSING", "NEGATIVE"}:
        return "danger"
    return "neutral"


def _profit_state(report: Mapping[str, Any]) -> tuple[str, str, str]:
    investor = _mapping(report.get("investor_summary"))
    portfolio = _mapping(report.get("portfolio_summary"))
    realized = _number(investor.get("realized_pnl", portfolio.get("realized_gain")))
    unrealized = _number(investor.get("unrealized_pnl", portfolio.get("unrealized_gain")))
    appreciation = _number(investor.get("capital_appreciation"))
    known = [value for value in (realized, unrealized, appreciation) if value is not None]
    if not known:
        return "Performance not fully reported", "watch", "More evidence is needed before enterprise profitability can be confirmed."
    total = sum(known)
    if total > 0:
        return f"Profitable {_money(total)}", "good", "Reported gains are positive across the available enterprise evidence."
    if total < 0:
        return f"Loss {_money(total)}", "danger", "Reported gains are negative and require review."
    return "Break-even", "watch", "Reported gains are currently neutral."


def _strategy_rows(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = report.get("strategy_kpis")
    return [dict(row) for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _strategy_concern(row: Mapping[str, Any]) -> tuple[int, str, str]:
    health = str(row.get("health_status") or "UNKNOWN").upper()
    runtime = str(row.get("runtime_status") or "UNKNOWN").upper()
    evidence = str(row.get("evidence_status") or "NOT_REPORTED").upper()
    pnl = _number(row.get("realized_gain"))
    unrealized = _number(row.get("unrealized_gain"))
    reasons: list[str] = []
    score = 0
    if health in {"CRITICAL", "DEGRADED", "ERROR"}:
        score += 100
        reasons.append(f"health {health}")
    elif health not in {"HEALTHY", "GOOD"}:
        score += 35
        reasons.append(f"health {health}")
    if runtime not in {"RUNNING", "READY", "ONLINE"}:
        score += 30
        reasons.append(f"runtime {runtime}")
    if evidence in {"NOT_REPORTED", "REGISTRY_ONLY", "MISSING", "PARTIAL"}:
        score += 25
        reasons.append(f"evidence {evidence}")
    if (pnl or 0) + (unrealized or 0) < 0:
        score += 50
        reasons.append("negative reported P&L")
    label = ", ".join(reasons) if reasons else "No immediate concern detected"
    tone = "danger" if score >= 75 else "watch" if score >= 25 else "good"
    return score, tone, label


def _summary_card(label: str, value: str, tone: str, detail: str) -> str:
    return (
        f"<article class='scan-card {tone}'><div class='scan-label'>{html.escape(label)}</div>"
        f"<div class='scan-value'>{html.escape(value)}</div>"
        f"<div class='scan-detail'>{html.escape(detail)}</div></article>"
    )


def _strategy_cards(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<div class='empty-state'>No registered strategy KPI evidence is available.</div>"
    ranked = sorted(rows, key=lambda row: _strategy_concern(row)[0], reverse=True)
    cards: list[str] = []
    for row in ranked:
        _, tone, reason = _strategy_concern(row)
        sid = html.escape(str(row.get("strategy_id") or "UNKNOWN"))
        name = html.escape(str(row.get("display_name") or sid))
        pnl_values = [_number(row.get("realized_gain")), _number(row.get("unrealized_gain"))]
        pnl = sum(value for value in pnl_values if value is not None) if any(value is not None for value in pnl_values) else None
        cards.append(
            f"<button type='button' class='scan-strategy-card {tone}' data-scan-target='{sid}'>"
            f"<span class='strategy-name'>{name}</span>"
            f"<span class='strategy-result'>{_money(pnl) if pnl is not None else 'P&L not reported'}</span>"
            f"<span class='strategy-health'>{html.escape(str(row.get('health_status') or 'UNKNOWN'))}</span>"
            f"<span class='strategy-reason'>{html.escape(reason)}</span>"
            "<span class='strategy-action'>View strategy KPI →</span></button>"
        )
    return "".join(cards)


def _strategy_details(rows: list[dict[str, Any]]) -> str:
    panels: list[str] = []
    for index, row in enumerate(rows):
        sid = html.escape(str(row.get("strategy_id") or f"strategy-{index}"))
        name = html.escape(str(row.get("display_name") or sid))
        hidden = "" if index == 0 else " hidden"
        metrics = (
            ("Allocated Capital", _money(row.get("allocated_capital"))),
            ("Portfolio Value", _money(row.get("portfolio_value"))),
            ("Income", _money(row.get("income"))),
            ("Realized P&L", _money(row.get("realized_gain"))),
            ("Unrealized P&L", _money(row.get("unrealized_gain"))),
            ("Win Rate", _percent(row.get("win_rate_percent"))),
            ("Watchlist", str(row.get("watchlist_count") if row.get("watchlist_count") is not None else "Not reported")),
            ("Positions / Holdings", str(row.get("position_count") if row.get("position_count") is not None else "Not reported")),
            ("Opportunity Quality", str(row.get("opportunity_quality") if row.get("opportunity_quality") is not None else "Not reported")),
        )
        metric_html = "".join(
            f"<article class='mini-metric'><span>{html.escape(label)}</span><strong>{html.escape(value)}</strong></article>"
            for label, value in metrics
        )
        evidence_paths = row.get("evidence_paths") if isinstance(row.get("evidence_paths"), list) else []
        evidence = "".join(f"<li>{html.escape(str(path))}</li>" for path in evidence_paths) or "<li>No readable strategy evidence reported.</li>"
        panels.append(
            f"<section class='scan-detail-panel'{hidden} data-scan-panel='{sid}'>"
            f"<div class='detail-heading'><div><p class='eyebrow'>Strategy KPI</p><h2>{name}</h2></div>"
            f"<span class='status-pill {_status_tone(row.get('health_status'))}'>{html.escape(str(row.get('health_status') or 'UNKNOWN'))}</span></div>"
            f"<div class='mini-grid'>{metric_html}</div>"
            "<div class='detail-columns'>"
            "<article><h3>What to review next</h3><p>Select this strategy's portfolio or watchlist instrument to inspect performance, income contribution, committee scores, and decision evidence. Instrument drill-down is the next UI development unit.</p></article>"
            f"<article><h3>Evidence readiness</h3><p><strong>Runtime:</strong> {html.escape(str(row.get('runtime_status') or 'UNKNOWN'))}</p>"
            f"<p><strong>Evidence:</strong> {html.escape(str(row.get('evidence_status') or 'NOT_REPORTED'))}</p>"
            f"<details><summary>Technical evidence paths</summary><ul>{evidence}</ul></details></article></div>"
            "</section>"
        )
    return "".join(panels)


def render_scan_first_dashboard(report: Mapping[str, Any], *, audience: str) -> str:
    rows = _strategy_rows(report)
    profit_label, profit_tone, profit_detail = _profit_state(report)
    investor = _mapping(report.get("investor_summary"))
    portfolio = _mapping(report.get("portfolio_summary"))
    enterprise = _mapping(report.get("enterprise_summary"))
    health = report.get("portfolio_health") or enterprise.get("enterprise_status") or "UNKNOWN"
    income = investor.get("projected_annual_dividend_income", portfolio.get("projected_annual_income"))
    value = investor.get("portfolio_value", portfolio.get("portfolio_value"))
    concerns = sorted(((row, _strategy_concern(row)) for row in rows), key=lambda item: item[1][0], reverse=True)
    top_row = concerns[0] if concerns else None
    concern_name = str(top_row[0].get("display_name") or top_row[0].get("strategy_id")) if top_row else "No strategy evidence"
    concern_reason = top_row[1][2] if top_row else "No strategy KPI evidence is available."
    concern_tone = top_row[1][1] if top_row else "watch"
    overall_action = "Immediate review required" if profit_tone == "danger" or concern_tone == "danger" else "Review priority concern" if concern_tone == "watch" else "Continue monitoring"
    action_tone = "danger" if "Immediate" in overall_action else "watch" if "priority" in overall_action else "good"

    cards = "".join((
        _summary_card("Profit / Loss", profit_label, profit_tone, profit_detail),
        _summary_card("Portfolio Value", _money(value), "neutral", "Combined reported enterprise value."),
        _summary_card("Projected Income", _money(income), "good" if _number(income) not in (None, 0) else "watch", "Combined reported annual income."),
        _summary_card("Overall Health", str(health), _status_tone(health), "Enterprise operating condition."),
        _summary_card("Action Needed", overall_action, action_tone, concern_reason),
    ))
    title = "Executive Summary" if audience.lower() == "executive" else "Investor Summary"
    content = f"""
<section class='scan-hero'>
  <div><p class='eyebrow'>Enterprise AI CIO</p><h1>{title}</h1><p>Start here. This view answers whether the enterprise is profitable, healthy, and where attention is needed before showing technical detail.</p></div>
  <div class='hero-status {action_tone}'><span>Highest concern</span><strong>{html.escape(concern_name)}</strong><small>{html.escape(concern_reason)}</small></div>
</section>
<section class='scan-summary-grid'>{cards}</section>
<section class='scan-section'><div class='section-heading'><div><p class='eyebrow'>Strategy comparison</p><h2>Where should I look?</h2></div><p>Strategies are ordered by concern. Select one to open only its KPI data.</p></div><div class='scan-strategy-grid'>{_strategy_cards(rows)}</div></section>
<section class='scan-section'><div class='section-heading'><div><p class='eyebrow'>Selected strategy</p><h2>Strategy KPI workspace</h2></div><p>Portfolio, watchlist, analytics, performance, and evidence remain isolated to the selected strategy.</p></div>{_strategy_details(rows)}</section>
<details class='diagnostic-details'><summary>Enterprise diagnostics and technical metadata</summary><p>Registry identity, declared capabilities, artifact contracts, raw evidence paths, and other deployment diagnostics belong here so they remain available without overwhelming the investor scan.</p></details>
<script>
(function(){
 const cards=[...document.querySelectorAll('[data-scan-target]')];
 const panels=[...document.querySelectorAll('[data-scan-panel]')];
 function select(id){cards.forEach(c=>c.classList.toggle('active',c.dataset.scanTarget===id));panels.forEach(p=>p.hidden=p.dataset.scanPanel!==id);}
 cards.forEach(c=>c.addEventListener('click',()=>{select(c.dataset.scanTarget);const panel=document.querySelector(`[data-scan-panel="${c.dataset.scanTarget}"]`);if(panel)panel.scrollIntoView({behavior:'smooth',block:'start'});}));
 if(cards.length){select(cards[0].dataset.scanTarget);}
})();
</script>
"""
    css = strategy_ui_css() + """
<style>
body{background:#07111f;color:#e8eef7}.enterprise-content{padding:22px}.scan-hero{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:20px;align-items:stretch;margin-bottom:20px}.scan-hero h1{font-size:34px;margin:4px 0 10px}.scan-hero p{max-width:780px;color:#aebcd0}.eyebrow{text-transform:uppercase;letter-spacing:.11em;font-size:11px;font-weight:800;color:#8fa8c8;margin:0}.hero-status{border-radius:16px;padding:20px;border:1px solid #2a3d58;display:flex;flex-direction:column;gap:8px}.hero-status span{font-size:12px;text-transform:uppercase}.hero-status strong{font-size:22px}.hero-status small{line-height:1.4}.good{border-color:#2f9e65!important}.watch{border-color:#d49a2d!important}.danger{border-color:#d94a4a!important}.neutral{border-color:#49627f!important}.scan-summary-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin-bottom:24px}.scan-card{background:#101d2f;border:1px solid #2a3d58;border-radius:14px;padding:16px;min-height:125px}.scan-label{font-size:12px;color:#9db0c9;text-transform:uppercase;font-weight:800}.scan-value{font-size:23px;font-weight:800;margin:12px 0 8px}.scan-detail{font-size:12px;color:#aebcd0;line-height:1.4}.scan-section{background:#0c1828;border:1px solid #223752;border-radius:18px;padding:20px;margin-bottom:20px}.section-heading{display:flex;justify-content:space-between;gap:24px;align-items:end;margin-bottom:16px}.section-heading h2{margin:4px 0 0}.section-heading>p{max-width:460px;color:#9db0c9}.scan-strategy-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}.scan-strategy-card{background:#101d2f;color:#e8eef7;border:1px solid #2a3d58;border-radius:14px;padding:16px;text-align:left;cursor:pointer;display:flex;flex-direction:column;gap:8px}.scan-strategy-card.active{outline:3px solid #7c5cff}.strategy-name{font-weight:800;font-size:17px}.strategy-result{font-size:21px;font-weight:800}.strategy-health,.strategy-reason{color:#aebcd0;font-size:12px}.strategy-action{color:#b7a7ff;font-weight:800;margin-top:6px}.scan-detail-panel{scroll-margin-top:100px}.detail-heading{display:flex;justify-content:space-between;align-items:center}.status-pill{padding:7px 11px;border:1px solid;border-radius:999px;font-size:12px;font-weight:800}.mini-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:16px 0}.mini-metric{background:#101d2f;border:1px solid #223752;border-radius:12px;padding:14px}.mini-metric span{display:block;color:#9db0c9;font-size:11px;text-transform:uppercase}.mini-metric strong{display:block;margin-top:8px;font-size:17px}.detail-columns{display:grid;grid-template-columns:1fr 1fr;gap:14px}.detail-columns article,.diagnostic-details{background:#101d2f;border:1px solid #223752;border-radius:12px;padding:16px}.diagnostic-details summary{cursor:pointer;font-weight:800}.empty-state{padding:18px;background:#101d2f;border-radius:12px;color:#aebcd0}
@media(max-width:1100px){.scan-summary-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.scan-hero{grid-template-columns:1fr}}@media(max-width:700px){.scan-summary-grid,.detail-columns{grid-template-columns:1fr}.section-heading{display:block}.enterprise-content{padding:12px}}
</style>"""
    return f"{css}<div class='portal-frame'>{render_left_navigation('Executive Dashboard' if audience.lower() == 'executive' else 'Investor Dashboard')}<main class='enterprise-content'>{content}</main></div>"
