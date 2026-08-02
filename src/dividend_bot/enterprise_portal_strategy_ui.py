"""Read-only HTML components for registry-driven Enterprise strategy dashboards."""
from __future__ import annotations

import html
from typing import Any, Mapping


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


def render_strategy_workspace(report: Mapping[str, Any], *, audience: str) -> str:
    strategies = report.get("strategy_kpis")
    if not isinstance(strategies, list) or not strategies:
        return "<section class='panel'><h2>Registered Strategy KPIs</h2><p>No registry-driven strategy KPI evidence is available yet.</p></section>"

    buttons: list[str] = []
    panels: list[str] = []
    for index, row in enumerate(strategies):
        if not isinstance(row, Mapping):
            continue
        sid = html.escape(str(row.get("strategy_id") or f"strategy-{index}"))
        name = html.escape(str(row.get("display_name") or sid))
        active = " active" if index == 0 else ""
        hidden = "" if index == 0 else " hidden"
        buttons.append(
            f"<button type='button' class='strategy-kpi-card{active}' data-strategy-target='{sid}'>"
            f"<strong>{name}</strong><span>{_money(row.get('allocated_capital'))} allocated</span>"
            f"<small>{html.escape(str(row.get('health_status') or 'UNKNOWN'))} · {html.escape(str(row.get('evidence_status') or 'REGISTRY_ONLY'))}</small>"
            f"<small>{html.escape(str(row.get('capability_count') or 0))} capabilities · {html.escape(str(row.get('published_artifact_count') or 0))} artifacts</small>"
            "<em>...more ›</em></button>"
        )
        metrics = (
            ("Allocated Capital", _money(row.get("allocated_capital"))),
            ("Portfolio Value", _money(row.get("portfolio_value"))),
            ("Realized Gain", _money(row.get("realized_gain"))),
            ("Unrealized Gain", _money(row.get("unrealized_gain"))),
            ("Income", _money(row.get("income"))),
            ("Positions / Holdings", _value(row.get("position_count"))),
            ("Watchlist", _value(row.get("watchlist_count"))),
            ("Opportunity Quality", _value(row.get("opportunity_quality"), " / 100")),
            ("Win Rate", _value(row.get("win_rate_percent"), "%")),
        )
        metric_rows = "".join(f"<tr><th>{html.escape(label)}</th><td>{value}</td></tr>" for label, value in metrics)
        paths = row.get("evidence_paths") if isinstance(row.get("evidence_paths"), list) else []
        loaded_evidence = "<ul>" + "".join(f"<li>{html.escape(str(path))}</li>" for path in paths) + "</ul>" if paths else "<p>No declared strategy report is currently readable. Registry identity and allocation remain visible.</p>"
        commentary = (
            f"{name} is registered with the Enterprise AI CIO. Its allocated capital is {_money(row.get('allocated_capital'))}. "
            f"Runtime is {html.escape(str(row.get('runtime_status') or 'UNKNOWN'))}, health is {html.escape(str(row.get('health_status') or 'UNKNOWN'))}, "
            f"and evidence status is {html.escape(str(row.get('evidence_status') or 'REGISTRY_ONLY'))}. "
            f"The registry declares {html.escape(str(row.get('capability_count') or 0))} capabilities and "
            f"{html.escape(str(row.get('published_artifact_count') or 0))} report artifacts."
        )
        panels.append(f"""
<section class='strategy-analysis panel'{hidden} data-strategy-panel='{sid}'>
  <h2>{name} — One View Analysis</h2>
  <p class='scope-note'>This section contains only this registered strategy's evidence. Enterprise totals remain in the KPI row above.</p>
  <div class='strategy-analysis-grid'>
    <div><h3>Strategy KPIs</h3><table class='metric-table'>{metric_rows}</table></div>
    <div><h3>Registry Identity</h3>
      <p><strong>Strategy ID:</strong> {sid}</p>
      <p><strong>Type:</strong> {html.escape(str(row.get('strategy_type') or 'STRATEGY'))}</p>
      <p><strong>Lifecycle:</strong> {html.escape(str(row.get('lifecycle_status') or 'UNKNOWN'))}</p>
      <p><strong>Readiness:</strong> {html.escape(str(row.get('readiness') or 'UNKNOWN'))}</p>
      <p><strong>Runtime:</strong> {html.escape(str(row.get('runtime_status') or 'UNKNOWN'))}</p>
    </div>
  </div>
  <div class='strategy-analysis-grid registry-detail-grid'>
    <div><h3>Declared Capabilities</h3>{_capability_list(row)}</div>
    <div><h3>Published Artifact Contract</h3>{_artifact_list(row)}</div>
  </div>
  <div><h3>Currently Readable Evidence</h3>{loaded_evidence}</div>
  <div class='ai-commentary'><strong>AI CIO Commentary</strong><p>{commentary}</p></div>
</section>""")

    audience_label = "Executive" if audience.lower() == "executive" else "Investor"
    return f"""
<section class='panel'><h2>{audience_label} Strategy KPIs</h2>
<p>Each card is sourced from a strategy plugin discovered through the Enterprise registry. Select <strong>...more</strong> to update the single analysis workspace.</p>
<div class='strategy-kpi-grid'>{''.join(buttons)}</div></section>
{''.join(panels)}
<script>
(function(){{
 const cards=[...document.querySelectorAll('[data-strategy-target]')];
 const panels=[...document.querySelectorAll('[data-strategy-panel]')];
 function select(id){{cards.forEach(c=>c.classList.toggle('active',c.dataset.strategyTarget===id));panels.forEach(p=>p.hidden=p.dataset.strategyPanel!==id);}}
 cards.forEach(c=>c.addEventListener('click',()=>select(c.dataset.strategyTarget)));
 const target=document.getElementById('registered-strategy-links');
 if(target){{cards.forEach(c=>{{const a=document.createElement('button');a.type='button';a.className='side-strategy';a.textContent=c.querySelector('strong').textContent;a.onclick=()=>{{select(c.dataset.strategyTarget);document.querySelector(`[data-strategy-panel="${{c.dataset.strategyTarget}}"]`).scrollIntoView({{behavior:'smooth'}});}};target.appendChild(a);}});}}
}})();
</script>
"""


def strategy_ui_css() -> str:
    return """
<style>
.portal-frame{display:grid;grid-template-columns:230px minmax(0,1fr);gap:20px;align-items:start}
.enterprise-sidebar{position:sticky;top:16px;background:#0b1d3a;color:#fff;border-radius:14px;padding:18px;min-height:520px}
.side-title{font-size:20px;font-weight:800;margin-bottom:18px}.side-link,.side-strategy{display:block;width:100%;text-align:left;color:#d9e2f2;background:transparent;border:0;text-decoration:none;padding:10px 8px;border-radius:8px;font-weight:700}.side-link.active,.side-link:hover,.side-strategy:hover{background:#5d18d6;color:#fff}.side-group{margin:24px 8px 8px;color:#9fb0c8;font-size:12px;font-weight:800;text-transform:uppercase}.side-strategy{cursor:pointer}
.enterprise-content{min-width:0}.scope-note{padding:10px 12px;background:#eef4ff;border-left:4px solid #5d18d6}.strategy-kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}.strategy-kpi-card{background:#fff;border:1px solid #dfe3ec;border-radius:14px;padding:18px;text-align:left;color:#101828;cursor:pointer}.strategy-kpi-card.active{outline:3px solid #8b5cf6}.strategy-kpi-card span,.strategy-kpi-card small,.strategy-kpi-card em{display:block;margin-top:8px}.strategy-kpi-card em{color:#5d18d6;font-style:normal;font-weight:800}.strategy-analysis-grid{display:grid;grid-template-columns:1fr 1fr;gap:22px}.registry-detail-grid{margin-top:18px}.metric-table{width:100%;border-collapse:collapse}.metric-table th{text-align:left}.metric-table td{text-align:right}.ai-commentary{margin-top:18px;background:#fffaf0;border:1px solid #f4cc73;border-radius:12px;padding:18px}.ai-commentary strong{color:#e66b00}
@media(max-width:900px){.portal-frame{grid-template-columns:1fr}.enterprise-sidebar{position:static;min-height:0}.strategy-analysis-grid{grid-template-columns:1fr}}
</style>"""
