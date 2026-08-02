"""Read-only HTML components for registry-driven Enterprise strategy dashboards."""
from __future__ import annotations

import html
from typing import Any, Mapping

from .strategy_decision_journal_renderer import render_strategy_decision_journal


def _money(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "Not reported"


def _value(value: Any, suffix: str = "") -> str:
    if value in (None, ""):
        return "Not reported"
    return f"{html.escape(str(value))}{suffix}"


def render_left_navigation(active: str) -> str:
    items = (
        ("Cash Account", "/cash"),
        ("Strategy Allocation", "/allocation"),
        ("Executive Dashboard", "/executive-dashboard"),
        ("Investor Dashboard", "/investor-dashboard"),
    )
    links = "".join(
        f"<a class='side-link {'active' if label == active else ''}' href='{url}'>{html.escape(label)}</a>"
        for label, url in items
    )
    return f"<aside class='enterprise-sidebar'><div class='side-title'>Enterprise AI CIO</div>{links}<div class='side-group'>Registered Strategies</div><div id='registered-strategy-links'></div></aside>"


def _artifact_list(row: Mapping[str, Any]) -> str:
    artifacts = row.get("published_artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        return "<p>No artifact declaration was published by this strategy.</p>"
    items: list[str] = []
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            continue
        artifact_id = html.escape(str(artifact.get("artifact_id") or "UNKNOWN"))
        artifact_type = html.escape(str(artifact.get("artifact_type") or "UNKNOWN"))
        artifact_format = html.escape(str(artifact.get("format") or "UNKNOWN"))
        authority = "authoritative" if artifact.get("authoritative") else "non-authoritative"
        requirement = "required" if artifact.get("required") else "optional"
        items.append(
            f"<li><strong>{artifact_id}</strong> — {artifact_type}, {artifact_format}, "
            f"{authority}, {requirement}</li>"
        )
    return "<ul>" + "".join(items) + "</ul>" if items else "<p>No artifact declaration was published by this strategy.</p>"


def _capability_list(row: Mapping[str, Any]) -> str:
    capabilities = row.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        return "<p>No capabilities declared.</p>"
    return "<ul>" + "".join(
        f"<li>{html.escape(str(capability))}</li>" for capability in capabilities
    ) + "</ul>"



def _decision_journal(row: Mapping[str, Any]) -> str:
    journal = row.get("decision_journal")
    strategy_id = str(row.get("strategy_id") or "").strip()
    status = html.escape(str(row.get("decision_journal_status") or "NOT_REPORTED"))
    if not isinstance(journal, Mapping):
        return (
            "<section class='strategy-decision-panel'>"
            "<h3>Decisions</h3>"
            f"<p class='scope-note'>Decision Journal status: {status}.</p>"
            "<p>No strategy-owned decisions are currently available.</p>"
            "</section>"
        )
    journal_strategy_id = str(journal.get("strategy_id") or "").strip()
    if journal_strategy_id != strategy_id:
        return (
            "<section class='strategy-decision-panel'>"
            "<h3>Decisions unavailable</h3>"
            "<p>Cross-strategy Decision Journal evidence was rejected.</p>"
            "</section>"
        )
    try:
        rendered = render_strategy_decision_journal(journal)
    except (TypeError, ValueError):
        return (
            "<section class='strategy-decision-panel'>"
            "<h3>Decisions unavailable</h3>"
            "<p>The strategy Decision Journal could not be rendered safely.</p>"
            "</section>"
        )
    return (
        "<section class='strategy-decision-panel'>"
        f"{rendered}"
        "</section>"
    )

def _list_rows(value: Any, *, empty: str) -> str:
    if not isinstance(value, list) or not value:
        return f"<p class='empty-state'>{html.escape(empty)}</p>"
    items: list[str] = []
    for item in value:
        if isinstance(item, Mapping):
            label = (
                item.get("symbol")
                or item.get("name")
                or item.get("title")
                or item.get("alert_type")
                or item.get("status")
                or "Item"
            )
            details = ", ".join(
                f"{str(key).replace('_', ' ').title()}: {value}"
                for key, value in item.items()
                if key not in {"symbol", "name", "title"}
                and value not in (None, "", [], {})
            )
            text = f"{label}: {details}" if details else str(label)
        else:
            text = str(item)
        items.append(f"<li>{html.escape(text)}</li>")
    return "<ul>" + "".join(items) + "</ul>"


def _metric_table(items: tuple[tuple[str, str], ...]) -> str:
    rows = "".join(
        f"<tr><th>{html.escape(label)}</th><td>{value}</td></tr>"
        for label, value in items
    )
    return f"<table class='metric-table'>{rows}</table>"


def _workspace_tab(
    *,
    strategy_id: str,
    tab_id: str,
    label: str,
    body: str,
    active: bool = False,
) -> tuple[str, str]:
    active_class = " active" if active else ""
    hidden = "" if active else " hidden"
    button = (
        f"<button type='button' class='workspace-tab{active_class}' "
        f"data-workspace-strategy='{strategy_id}' data-workspace-tab-target='{tab_id}'>"
        f"{html.escape(label)}</button>"
    )
    panel = (
        f"<section class='workspace-tab-panel'{hidden} "
        f"data-workspace-strategy-panel='{strategy_id}' "
        f"data-workspace-tab-panel='{tab_id}'>{body}</section>"
    )
    return button, panel


def render_strategy_workspace(report: Mapping[str, Any], *, audience: str) -> str:
    strategies = report.get("strategy_kpis")
    if not isinstance(strategies, list) or not strategies:
        return "<section class='panel'><h2>Registered Strategy KPIs</h2><p>No registry-driven strategy KPI evidence is available yet.</p></section>"

    buttons: list[str] = []
    panels: list[str] = []
    for index, row in enumerate(strategies):
        if not isinstance(row, Mapping):
            continue
        raw_sid = str(row.get("strategy_id") or f"strategy-{index}")
        sid = html.escape(raw_sid)
        name = html.escape(str(row.get("display_name") or raw_sid))
        active = " active" if index == 0 else ""
        hidden = "" if index == 0 else " hidden"
        buttons.append(
            f"<button type='button' class='strategy-kpi-card{active}' data-strategy-target='{sid}'>"
            f"<strong>{name}</strong><span>{_money(row.get('allocated_capital'))} allocated</span>"
            f"<small>{html.escape(str(row.get('health_status') or 'UNKNOWN'))} · {html.escape(str(row.get('evidence_status') or 'REGISTRY_ONLY'))}</small>"
            f"<small>{html.escape(str(row.get('capability_count') or 0))} capabilities · {html.escape(str(row.get('published_artifact_count') or 0))} artifacts</small>"
            "<em>...more ›</em></button>"
        )

        identity = (
            "<h3>Registry Identity</h3>"
            f"<p><strong>Strategy ID:</strong> {sid}</p>"
            f"<p><strong>Type:</strong> {html.escape(str(row.get('strategy_type') or 'STRATEGY'))}</p>"
            f"<p><strong>Lifecycle:</strong> {html.escape(str(row.get('lifecycle_status') or 'UNKNOWN'))}</p>"
            f"<p><strong>Readiness:</strong> {html.escape(str(row.get('readiness') or 'UNKNOWN'))}</p>"
            f"<p><strong>Runtime:</strong> {html.escape(str(row.get('runtime_status') or 'UNKNOWN'))}</p>"
        )
        summary_metrics = _metric_table((
            ("Allocated Capital", _money(row.get("allocated_capital"))),
            ("Portfolio Value", _money(row.get("portfolio_value"))),
            ("Positions / Holdings", _value(row.get("position_count"))),
            ("Watchlist", _value(row.get("watchlist_count"))),
            ("Opportunity Quality", _value(row.get("opportunity_quality"), " / 100")),
            ("Win Rate", _value(row.get("win_rate_percent"), "%")),
        ))
        executive_body = (
            "<h3>Executive Summary</h3>"
            "<p class='scope-note'>Only the selected strategy's KPI evidence is shown.</p>"
            "<div class='strategy-analysis-grid'>"
            f"<div>{summary_metrics}</div><div>{identity}</div></div>"
            "<div class='strategy-analysis-grid registry-detail-grid'>"
            f"<div><h3>Declared Capabilities</h3>{_capability_list(row)}</div>"
            f"<div><h3>Published Artifact Contract</h3>{_artifact_list(row)}</div>"
            "</div>"
        )
        portfolio_body = (
            "<h3>Portfolio</h3>"
            + _metric_table((
                ("Allocated Capital", _money(row.get("allocated_capital"))),
                ("Portfolio Value", _money(row.get("portfolio_value"))),
                ("Realized Gain", _money(row.get("realized_gain"))),
                ("Unrealized Gain", _money(row.get("unrealized_gain"))),
            ))
        )
        watchlist_body = (
            "<h3>Watchlist</h3>"
            + _metric_table((("Watchlist Count", _value(row.get("watchlist_count"))),))
            + _list_rows(
                row.get("watchlist"),
                empty="No strategy-owned watchlist detail is currently reported.",
            )
        )
        holdings_body = (
            "<h3>Holdings</h3>"
            + _metric_table((("Position / Holding Count", _value(row.get("position_count"))),))
            + _list_rows(
                row.get("holdings") or row.get("positions"),
                empty="No strategy-owned holdings detail is currently reported.",
            )
        )
        income_body = (
            "<h3>Income</h3>"
            + _metric_table((("Reported Strategy Income", _money(row.get("income"))),))
            + _list_rows(
                row.get("income_events"),
                empty="No strategy-owned income events are currently reported.",
            )
        )
        performance_body = (
            "<h3>Performance</h3>"
            + _metric_table((
                ("Realized Gain", _money(row.get("realized_gain"))),
                ("Unrealized Gain", _money(row.get("unrealized_gain"))),
                ("Win Rate", _value(row.get("win_rate_percent"), "%")),
                ("Opportunity Quality", _value(row.get("opportunity_quality"), " / 100")),
            ))
        )
        alerts_body = (
            "<h3>Alerts</h3>"
            + _list_rows(
                row.get("alerts") or row.get("risk_flags"),
                empty="No strategy-owned alerts are currently reported.",
            )
        )
        decisions_body = _decision_journal(row)

        tab_definitions = (
            ("executive-summary", "Executive Summary", executive_body),
            ("portfolio", "Portfolio", portfolio_body),
            ("watchlist", "Watchlist", watchlist_body),
            ("holdings", "Holdings", holdings_body),
            ("income", "Income", income_body),
            ("performance", "Performance", performance_body),
            ("alerts", "Alerts", alerts_body),
            ("decisions", "Decisions", decisions_body),
        )
        tab_buttons: list[str] = []
        tab_panels: list[str] = []
        for tab_index, (tab_id, tab_label, tab_body) in enumerate(tab_definitions):
            tab_button, tab_panel = _workspace_tab(
                strategy_id=sid,
                tab_id=tab_id,
                label=tab_label,
                body=tab_body,
                active=tab_index == 0,
            )
            tab_buttons.append(tab_button)
            tab_panels.append(tab_panel)

        paths = row.get("evidence_paths") if isinstance(row.get("evidence_paths"), list) else []
        loaded_evidence = (
            "<ul>" + "".join(f"<li>{html.escape(str(path))}</li>" for path in paths) + "</ul>"
            if paths
            else "<p>No declared strategy report is currently readable. Registry identity and allocation remain visible.</p>"
        )
        commentary = (
            f"{name} is registered with the Enterprise AI CIO. Its allocated capital is {_money(row.get('allocated_capital'))}. "
            f"Runtime is {html.escape(str(row.get('runtime_status') or 'UNKNOWN'))}, health is {html.escape(str(row.get('health_status') or 'UNKNOWN'))}, "
            f"and evidence status is {html.escape(str(row.get('evidence_status') or 'REGISTRY_ONLY'))}."
        )
        panels.append(f"""
<section class='strategy-analysis panel'{hidden} data-strategy-panel='{sid}'>
  <h2>{name} — KPI Workspace</h2>
  <p class='scope-note'>This workspace contains only this registered strategy's evidence. Enterprise totals remain above.</p>
  <nav class='workspace-tabs' aria-label='{name} KPI workspace tabs'>{''.join(tab_buttons)}</nav>
  <div class='workspace-tab-content'>{''.join(tab_panels)}</div>
  <details class='readable-evidence'><summary>Currently Readable Evidence</summary>{loaded_evidence}</details>
  <div class='ai-commentary'><strong>AI CIO Commentary</strong><p>{commentary}</p></div>
</section>""")

    audience_label = "Executive" if audience.lower() == "executive" else "Investor"
    return f"""
<section class='panel'><h2>{audience_label} Strategy KPIs</h2>
<p>Each card is sourced from a strategy plugin discovered through the Enterprise registry. Select <strong>...more</strong> to update the KPI workspace.</p>
<div class='strategy-kpi-grid'>{''.join(buttons)}</div></section>
{''.join(panels)}
<script>
(function(){{
 const cards=[...document.querySelectorAll('[data-strategy-target]')];
 const panels=[...document.querySelectorAll('[data-strategy-panel]')];
 function select(id){{cards.forEach(c=>c.classList.toggle('active',c.dataset.strategyTarget===id));panels.forEach(p=>p.hidden=p.dataset.strategyPanel!==id);}}
 cards.forEach(c=>c.addEventListener('click',()=>select(c.dataset.strategyTarget)));
 const tabButtons=[...document.querySelectorAll('[data-workspace-tab-target]')];
 tabButtons.forEach(button=>button.addEventListener('click',()=>{{
   const strategy=button.dataset.workspaceStrategy;
   const tab=button.dataset.workspaceTabTarget;
   document.querySelectorAll('[data-workspace-tab-target][data-workspace-strategy="'+strategy+'"]').forEach(item=>item.classList.toggle('active',item===button));
   document.querySelectorAll('[data-workspace-tab-panel][data-workspace-strategy-panel="'+strategy+'"]').forEach(item=>item.hidden=item.dataset.workspaceTabPanel!==tab);
 }}));
 const target=document.getElementById('registered-strategy-links');
 if(target){{cards.forEach(c=>{{const a=document.createElement('button');a.type='button';a.className='side-strategy';a.textContent=c.querySelector('strong').textContent;a.onclick=()=>{{select(c.dataset.strategyTarget);document.querySelector('[data-strategy-panel="'+c.dataset.strategyTarget+'"]').scrollIntoView({{behavior:'smooth'}});}};target.appendChild(a);}});}}
}})();
</script>
"""

def strategy_ui_css() -> str:
    return """
<style>
.portal-frame{display:grid;grid-template-columns:230px minmax(0,1fr);gap:20px;align-items:start}
.enterprise-sidebar{position:sticky;top:16px;background:#0b1d3a;color:#fff;border-radius:14px;padding:18px;min-height:520px}
.side-title{font-size:20px;font-weight:800;margin-bottom:18px}.side-link,.side-strategy{display:block;width:100%;text-align:left;color:#d9e2f2;background:transparent;border:0;text-decoration:none;padding:10px 8px;border-radius:8px;font-weight:700}.side-link.active,.side-link:hover,.side-strategy:hover{background:#5d18d6;color:#fff}.side-group{margin:24px 8px 8px;color:#9fb0c8;font-size:12px;font-weight:800;text-transform:uppercase}.side-strategy{cursor:pointer}
.enterprise-content{min-width:0}.scope-note{padding:10px 12px;background:#eef4ff;border-left:4px solid #5d18d6}.workspace-tabs{display:flex;gap:8px;overflow-x:auto;padding:4px 0 14px;margin:14px 0;border-bottom:1px solid #dfe3ec}.workspace-tab{white-space:nowrap;padding:9px 13px;border:1px solid #cbd5e1;background:#fff;border-radius:9px;cursor:pointer;font-weight:700;color:#344054}.workspace-tab.active{background:#5d18d6;color:#fff;border-color:#5d18d6}.workspace-tab-panel{min-height:180px}.readable-evidence{margin-top:18px}.readable-evidence summary{font-weight:800;cursor:pointer}.strategy-kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}.strategy-kpi-card{background:#fff;border:1px solid #dfe3ec;border-radius:14px;padding:18px;text-align:left;color:#101828;cursor:pointer}.strategy-kpi-card.active{outline:3px solid #8b5cf6}.strategy-kpi-card span,.strategy-kpi-card small,.strategy-kpi-card em{display:block;margin-top:8px}.strategy-kpi-card em{color:#5d18d6;font-style:normal;font-weight:800}.strategy-analysis-grid{display:grid;grid-template-columns:1fr 1fr;gap:22px}.registry-detail-grid{margin-top:18px}.metric-table{width:100%;border-collapse:collapse}.metric-table th{text-align:left}.metric-table td{text-align:right}.strategy-decision-panel{margin-top:18px;border-top:1px solid #dfe3ec;padding-top:18px}.strategy-decision-panel .strategy-decision-journal{max-width:none}.strategy-decision-panel .journal-heading,.strategy-decision-panel .decision-card{background:#fff;border:1px solid #dbe3ef;border-radius:14px;padding:18px;margin-bottom:14px}.strategy-decision-panel .journal-heading{display:flex;justify-content:space-between;gap:18px}.strategy-decision-panel .journal-meta span,.strategy-decision-panel .status,.strategy-decision-panel .decision-type{display:inline-block;padding:5px 9px;border-radius:999px;background:#eef2ff;margin:3px;font-size:12px;font-weight:700}.strategy-decision-panel table{width:100%;border-collapse:collapse}.strategy-decision-panel th,.strategy-decision-panel td{border-bottom:1px solid #e5e7eb;padding:9px;text-align:left}.strategy-decision-panel .image-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}.strategy-decision-panel img{max-width:100%;height:auto}.ai-commentary{margin-top:18px;background:#fffaf0;border:1px solid #f4cc73;border-radius:12px;padding:18px}.ai-commentary strong{color:#e66b00}
@media(max-width:900px){.portal-frame{grid-template-columns:1fr}.enterprise-sidebar{position:static;min-height:0}.strategy-analysis-grid{grid-template-columns:1fr}}
</style>"""
