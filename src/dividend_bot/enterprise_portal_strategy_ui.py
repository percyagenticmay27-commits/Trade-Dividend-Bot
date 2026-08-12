"""Read-only HTML components for registry-driven Enterprise strategy dashboards."""
from __future__ import annotations

import html
from typing import Any, Mapping
from urllib.parse import quote

from .enterprise_holdings_ui import holdings_ui_css, render_holdings_panel
from .enterprise_watchlist_ui import render_watchlist_panel, watchlist_ui_css
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


def _gain_loss_money(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "Not reported"
    css_class = "metric-positive" if number > 0 else "metric-negative" if number < 0 else "metric-neutral"
    prefix = "+" if number > 0 else ""
    formatted = f"{prefix}${number:,.2f}" if number >= 0 else f"-${abs(number):,.2f}"
    return f"<strong class='{css_class}'>{formatted}</strong>"


def render_left_navigation(active: str) -> str:
    items = (
        ("Cash Account", "/cash"),
        ("Strategy Allocation", "/allocation"),
        ("Executive Dashboard", "/executive-dashboard"),
        ("Investor Dashboard", "/investor-dashboard"),
    )
    links = "".join(
        f"<a class='side-link {'active' if label == active else ''}' href='{url}'"
        f"{' aria-current=\'page\'' if label == active else ''}>"
        f"{html.escape(label)}</a>"
        for label, url in items
    )
    return (
        "<aside class='enterprise-sidebar' aria-label='Enterprise navigation'>"
        "<div class='side-title'>Enterprise AI CIO</div>"
        f"<nav class='primary-navigation' aria-label='Portal pages'>{links}</nav>"
        "<div class='side-group'>Registered Strategies</div>"
        "<div id='registered-strategy-links' class='registered-strategy-links' "
        "aria-label='Registered strategies'></div></aside>"
    )


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


_REASON_EXPLANATIONS = {
    "PRICE_BELOW_EMA20": (
        "Price is below the 20-day EMA. This is Strategy B's sell condition; "
        "it is not, by itself, authorization to exit a legacy-unassigned position."
    ),
    "PRICE_ABOVE_EMA20": (
        "Price is above the 20-day EMA, so Strategy B's sell condition is not active."
    ),
    "LEGACY_CONSENSUS_PENDING": (
        "This legacy-unassigned position remains held until both Strategy A and "
        "Strategy B independently confirm a sell."
    ),
}


def _alert_rows(value: Any, *, empty: str) -> str:
    if not isinstance(value, list) or not value:
        return f"<p class='empty-state'>{html.escape(empty)}</p>"
    cards: list[str] = []
    for item in value:
        if not isinstance(item, Mapping):
            cards.append(
                "<article class='strategy-alert-card'>"
                f"<p>{html.escape(str(item))}</p></article>"
            )
            continue
        symbol = html.escape(str(item.get("symbol") or item.get("pair") or "Strategy alert"))
        severity = html.escape(str(item.get("severity") or "MONITOR").replace("_", " ").title())
        message = html.escape(str(item.get("message") or "No plain-language explanation was reported."))
        reasons = item.get("reasons")
        if not isinstance(reasons, list):
            reasons = []
        explanations = [
            _REASON_EXPLANATIONS.get(
                str(reason),
                str(reason).replace("_", " ").capitalize(),
            )
            for reason in reasons
        ]
        evidence = (
            "<ul class='strategy-alert-evidence'>"
            + "".join(f"<li>{html.escape(explanation)}</li>" for explanation in explanations)
            + "</ul>"
            if explanations
            else ""
        )
        cards.append(
            "<article class='strategy-alert-card'>"
            f"<header><strong>{symbol}</strong><span>{severity}</span></header>"
            f"<p>{message}</p>{evidence}</article>"
        )
    return "<div class='strategy-alert-list'>" + "".join(cards) + "</div>"


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
        f"data-workspace-strategy='{strategy_id}' data-workspace-tab-target='{tab_id}' "
        f"id='tab-{strategy_id}-{tab_id}' role='tab' "
        f"aria-controls='panel-{strategy_id}-{tab_id}' "
        f"aria-selected='{'true' if active else 'false'}' "
        f"tabindex='{'0' if active else '-1'}'>"
        f"{html.escape(label)}</button>"
    )
    panel = (
        f"<section class='workspace-tab-panel'{hidden} "
        f"data-workspace-strategy-panel='{strategy_id}' "
        f"data-workspace-tab-panel='{tab_id}' "
        f"id='panel-{strategy_id}-{tab_id}' role='tabpanel' "
        f"aria-labelledby='tab-{strategy_id}-{tab_id}'>{body}</section>"
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
        sid = html.escape(raw_sid, quote=True)
        encoded_sid = quote(raw_sid, safe="")
        name = html.escape(str(row.get("display_name") or raw_sid))
        active = " active" if index == 0 else ""
        hidden = "" if index == 0 else " hidden"
        buttons.append(
            f"<button type='button' class='strategy-kpi-card{active}' data-strategy-target='{sid}' "
            f"aria-controls='strategy-{sid}' aria-pressed='{'true' if index == 0 else 'false'}'>"
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
                ("Realized Gain", _gain_loss_money(row.get("realized_gain"))),
                ("Unrealized Gain", _gain_loss_money(row.get("unrealized_gain"))),
            ))
        )
        watchlist_body = render_watchlist_panel(row)
        holdings_body = render_holdings_panel(row)
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
                ("Realized Gain", _gain_loss_money(row.get("realized_gain"))),
                ("Unrealized Gain", _gain_loss_money(row.get("unrealized_gain"))),
                ("Win Rate", _value(row.get("win_rate_percent"), "%")),
                ("Opportunity Quality", _value(row.get("opportunity_quality"), " / 100")),
            ))
        )
        alerts_body = (
            "<h3>Alerts</h3>"
            + _alert_rows(
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
        evidence_status = str(row.get("evidence_status") or "REGISTRY_ONLY").upper()
        availability_banner = (
            "<div class='data-availability data-availability-pending'>"
            "<strong>Strategy data pending</strong>"
            "<span>Allocation and registry identity are verified. The remaining fields stay "
            "<em>Not reported</em> until this strategy publishes Enterprise KPI evidence.</span>"
            "</div>"
            if evidence_status in {"REGISTRY_ONLY", "EVIDENCE_PENDING", "NOT_REPORTED"}
            else "<div class='data-availability data-availability-ready'><strong>Strategy evidence available</strong><span>Published KPI evidence is loaded for this workspace.</span></div>"
        )
        commentary = (
            f"{name} is registered with the Enterprise AI CIO. Its allocated capital is {_money(row.get('allocated_capital'))}. "
            f"Runtime is {html.escape(str(row.get('runtime_status') or 'UNKNOWN'))}, health is {html.escape(str(row.get('health_status') or 'UNKNOWN'))}, "
            f"and evidence status is {html.escape(str(row.get('evidence_status') or 'REGISTRY_ONLY'))}."
        )
        panels.append(f"""
<section id='strategy-{sid}' class='strategy-analysis panel'{hidden} data-strategy-panel='{sid}'>
  <h2>{name} — One View Analysis KPI Workspace</h2>
  <p class='scope-note'>This workspace contains only this registered strategy's evidence. Enterprise totals remain above.</p>
  {availability_banner}
  <nav class='strategy-cross-links' aria-label='{name} Enterprise links'>
    <a href='/executive-dashboard?strategy={encoded_sid}#strategy-{sid}'>Executive Dashboard</a>
    <a href='/investor-dashboard?strategy={encoded_sid}#strategy-{sid}'>Investor Dashboard</a>
    <a href='?strategy={encoded_sid}#strategy-{sid}'>Strategy Workspace</a>
    <a href='?strategy={encoded_sid}&amp;tab=decisions#strategy-{sid}'>Decision Journal</a>
  </nav>
  <nav class='workspace-tabs' role='tablist' aria-label='{name} KPI workspace tabs'>{''.join(tab_buttons)}</nav>
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
 function updateUrl(strategy,tab){{
   const url=new URL(window.location.href);
   if(strategy) url.searchParams.set('strategy',strategy);
   if(tab) url.searchParams.set('tab',tab);
   url.hash='strategy-'+strategy;
   window.history.replaceState({{}},'',url);
 }}
 function select(id,updateState=false){{
   cards.forEach(c=>{{const active=c.dataset.strategyTarget===id;c.classList.toggle('active',active);c.setAttribute('aria-pressed',active?'true':'false');}});
   panels.forEach(p=>p.hidden=p.dataset.strategyPanel!==id);
   document.querySelectorAll('.side-strategy[data-strategy-target]').forEach(item=>{{const active=item.dataset.strategyTarget===id;item.classList.toggle('active',active);item.setAttribute('aria-pressed',active?'true':'false');}});
   if(updateState) updateUrl(id,null);
 }}
 cards.forEach(c=>c.addEventListener('click',()=>select(c.dataset.strategyTarget,true)));
 const tabButtons=[...document.querySelectorAll('[data-workspace-tab-target]')];
 function selectTab(strategy,tab,updateState=false){{
   const strategyTabs=[...document.querySelectorAll('[data-workspace-tab-target][data-workspace-strategy="'+strategy+'"]')];
   strategyTabs.forEach(item=>{{const active=item.dataset.workspaceTabTarget===tab;item.classList.toggle('active',active);item.setAttribute('aria-selected',active?'true':'false');item.tabIndex=active?0:-1;}});
   document.querySelectorAll('[data-workspace-tab-panel][data-workspace-strategy-panel="'+strategy+'"]').forEach(item=>item.hidden=item.dataset.workspaceTabPanel!==tab);
   if(updateState) updateUrl(strategy,tab);
 }}
 tabButtons.forEach(button=>{{
   button.addEventListener('click',()=>selectTab(button.dataset.workspaceStrategy,button.dataset.workspaceTabTarget,true));
   button.addEventListener('keydown',event=>{{
     const strategy=button.dataset.workspaceStrategy;
     const tabs=[...document.querySelectorAll('[data-workspace-tab-target][data-workspace-strategy="'+strategy+'"]')];
     const current=tabs.indexOf(button);
     let next=current;
     if(event.key==='ArrowRight') next=(current+1)%tabs.length;
     else if(event.key==='ArrowLeft') next=(current-1+tabs.length)%tabs.length;
     else if(event.key==='Home') next=0;
     else if(event.key==='End') next=tabs.length-1;
     else return;
     event.preventDefault();
     tabs[next].focus();
     selectTab(strategy,tabs[next].dataset.workspaceTabTarget,true);
   }});
 }});
 const target=document.getElementById('registered-strategy-links');
 if(target){{cards.forEach(c=>{{const a=document.createElement('button');a.type='button';a.className='side-strategy';a.dataset.strategyTarget=c.dataset.strategyTarget;a.setAttribute('aria-controls','strategy-'+c.dataset.strategyTarget);a.setAttribute('aria-pressed',c.classList.contains('active')?'true':'false');a.textContent=c.querySelector('strong').textContent;a.onclick=()=>{{select(c.dataset.strategyTarget,true);document.querySelector('[data-strategy-panel="'+c.dataset.strategyTarget+'"]').scrollIntoView({{behavior:'smooth'}});}};target.appendChild(a);}});}}
 document.querySelectorAll('.strategy-decision-journal').forEach(root=>{{
   if(root.dataset.filtersReady==='true') return;
   root.dataset.filtersReady='true';
   const search=root.querySelector('[data-journal-search]');
   const type=root.querySelector('[data-journal-type]');
   const clear=root.querySelector('[data-journal-clear]');
   const count=root.querySelector('[data-journal-count]');
   const decisionCards=[...root.querySelectorAll('.decision-card')];
   function applyJournalFilters(){{
     const query=search?search.value.trim().toLowerCase():'';
     const selected=type?type.value:'ALL';
     let visible=0;
     decisionCards.forEach(card=>{{
       const matchesQuery=!query||(card.dataset.journalSearchText||'').includes(query);
       const matchesType=selected==='ALL'||card.dataset.decisionType===selected;
       card.hidden=!(matchesQuery&&matchesType);
       if(!card.hidden) visible+=1;
     }});
     if(count) count.textContent=visible+(visible===1?' decision shown':' decisions shown');
   }}
   const lifecycleFilter=root.querySelector('[data-lifecycle-filter]');
   const lifecycleStage=root.querySelector('[data-lifecycle-stage]');
   const lifecycleCards=[...root.querySelectorAll('[data-lifecycle-card]')];
   let lifecyclePage=0;
   const lifecyclePageSize=6;
   function applyLifecycleOverview(resetPage){{
     if(resetPage) lifecyclePage=0;
     const query=lifecycleFilter?lifecycleFilter.value.trim().toLowerCase():'';
     const stage=lifecycleStage?lifecycleStage.value:'ALL';
     const matches=lifecycleCards.filter(card=>(!query||(card.dataset.lifecycleSearchText||'').includes(query))&&(stage==='ALL'||card.dataset.lifecycleStatus===stage));
     const pages=Math.max(1,Math.ceil(matches.length/lifecyclePageSize));
     lifecyclePage=Math.min(lifecyclePage,pages-1);
     lifecycleCards.forEach(card=>card.hidden=true);
     matches.slice(lifecyclePage*lifecyclePageSize,(lifecyclePage+1)*lifecyclePageSize).forEach(card=>card.hidden=false);
     const pageText=root.querySelector('[data-lifecycle-page]');
     const lifecycleCount=root.querySelector('[data-lifecycle-count]');
     const previous=root.querySelector('[data-lifecycle-prev]');
     const next=root.querySelector('[data-lifecycle-next]');
     if(pageText) pageText.textContent='Page '+(lifecyclePage+1)+' of '+pages;
     if(lifecycleCount) lifecycleCount.textContent=matches.length+' pairs';
     if(previous) previous.disabled=lifecyclePage===0;
     if(next) next.disabled=lifecyclePage>=pages-1;
   }}
   if(lifecycleFilter) lifecycleFilter.addEventListener('input',()=>applyLifecycleOverview(true));
   if(lifecycleStage) lifecycleStage.addEventListener('change',()=>applyLifecycleOverview(true));
   const lifecyclePrevious=root.querySelector('[data-lifecycle-prev]');
   const lifecycleNext=root.querySelector('[data-lifecycle-next]');
   if(lifecyclePrevious) lifecyclePrevious.addEventListener('click',()=>{{lifecyclePage-=1;applyLifecycleOverview(false);}});
   if(lifecycleNext) lifecycleNext.addEventListener('click',()=>{{lifecyclePage+=1;applyLifecycleOverview(false);}});
   applyLifecycleOverview(true);
   root.querySelectorAll('[data-lifecycle-search]').forEach(button=>button.addEventListener('click',()=>{{
     if(search) search.value=button.dataset.lifecycleSearch||'';
     if(type) type.value='ALL';
     applyJournalFilters();
     if(search) search.scrollIntoView({{behavior:'smooth',block:'center'}});
   }}));
   if(search) search.addEventListener('input',applyJournalFilters);
   if(type) type.addEventListener('change',applyJournalFilters);
   root.querySelectorAll('[data-filter]').forEach(button=>button.addEventListener('click',()=>{{
     if(type) type.value=button.dataset.filter||'ALL';
     applyJournalFilters();
   }}));
   if(clear) clear.addEventListener('click',()=>{{
     if(search) search.value='';
     if(type) type.value='ALL';
     applyJournalFilters();
     if(search) search.focus();
   }});
   applyJournalFilters();
 }});
 const params=new URLSearchParams(window.location.search);
 const requestedStrategy=params.get('strategy');
 const requestedTab=params.get('tab')||'executive-summary';
 if(requestedStrategy && cards.some(c=>c.dataset.strategyTarget===requestedStrategy)){{
   select(requestedStrategy);
   selectTab(requestedStrategy,requestedTab);
 }}
}})();
</script>
"""


def strategy_ui_css() -> str:
    base_css = """
<style>
.portal-frame{display:grid;grid-template-columns:230px minmax(0,1fr);gap:20px;align-items:start}
.enterprise-sidebar{position:sticky;top:16px;background:#0b1d3a;color:#fff;border-radius:14px;padding:18px;min-height:520px}
.side-title{font-size:20px;font-weight:800;margin-bottom:18px}.side-link,.side-strategy{display:block;width:100%;text-align:left;color:#d9e2f2;background:transparent;border:0;text-decoration:none;padding:10px 8px;border-radius:8px;font-weight:700}.side-link.active,.side-link:hover,.side-link:focus-visible,.side-strategy.active,.side-strategy:hover,.side-strategy:focus-visible{background:#5d18d6;color:#fff}.side-group{margin:24px 8px 8px;color:#9fb0c8;font-size:12px;font-weight:800;text-transform:uppercase}.side-strategy{cursor:pointer}
.enterprise-content{min-width:0}.scope-note{padding:10px 12px;background:#eef4ff;border-left:4px solid #5d18d6}.strategy-cross-links{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}.strategy-cross-links a{display:inline-block;padding:8px 11px;border:1px solid #cbd5e1;border-radius:9px;color:#5d18d6;background:#fff;text-decoration:none;font-weight:700}.strategy-cross-links a:hover{background:#f3efff}.workspace-tabs{display:flex;gap:8px;overflow-x:auto;padding:4px 0 14px;margin:14px 0;border-bottom:1px solid #dfe3ec}.workspace-tab{white-space:nowrap;padding:9px 13px;border:1px solid #cbd5e1;background:#fff;border-radius:9px;cursor:pointer;font-weight:700;color:#344054}.workspace-tab.active{background:#5d18d6;color:#fff;border-color:#5d18d6}.workspace-tab:focus-visible,.strategy-kpi-card:focus-visible,.strategy-cross-links a:focus-visible{outline:3px solid #f59e0b;outline-offset:2px}.workspace-tab-panel{min-height:180px}.readable-evidence{margin-top:18px}.readable-evidence summary{font-weight:800;cursor:pointer}.strategy-kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}.strategy-kpi-card{background:#fff;border:1px solid #dfe3ec;border-radius:14px;padding:18px;text-align:left;color:#101828;cursor:pointer}.strategy-kpi-card.active{outline:3px solid #8b5cf6}.strategy-kpi-card span,.strategy-kpi-card small,.strategy-kpi-card em{display:block;margin-top:8px}.strategy-kpi-card em{color:#5d18d6;font-style:normal;font-weight:800}.strategy-analysis-grid{display:grid;grid-template-columns:1fr 1fr;gap:22px}.registry-detail-grid{margin-top:18px}.metric-table{width:100%;border-collapse:collapse}.metric-table th{text-align:left}.metric-table td{text-align:right}.strategy-decision-panel{margin-top:18px;border-top:1px solid #dfe3ec;padding-top:18px}.strategy-decision-panel .strategy-decision-journal{max-width:none}.strategy-decision-panel .journal-heading,.strategy-decision-panel .decision-card{background:#fff;border:1px solid #dbe3ef;border-radius:14px;padding:18px;margin-bottom:14px}.strategy-decision-panel .journal-heading{display:flex;justify-content:space-between;gap:18px}.strategy-decision-panel .journal-meta span,.strategy-decision-panel .status,.strategy-decision-panel .decision-type{display:inline-block;padding:5px 9px;border-radius:999px;background:#eef2ff;color:#344054!important;margin:3px;font-size:12px;font-weight:800;line-height:1.2;white-space:nowrap}.strategy-decision-panel .decision-card header .decision-type{background:#ede9fe;color:#5b21b6!important}.strategy-decision-panel .decision-card header .status{background:#e2e8f0;color:#334155!important}.strategy-decision-panel .journal-cross-links{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}.strategy-decision-panel .journal-search,.strategy-decision-panel .journal-filters{display:flex;flex-wrap:wrap;align-items:end;gap:8px;margin:14px 0}.strategy-decision-panel .journal-search label{display:grid;gap:5px;min-width:210px;flex:1}.strategy-decision-panel .journal-search label span{font-size:12px;font-weight:700;color:#475467}.strategy-decision-panel .journal-search input,.strategy-decision-panel .journal-search select{width:100%;padding:10px;border:1px solid #cbd5e1;border-radius:9px;background:#fff}.strategy-decision-panel .journal-search button,.strategy-decision-panel .journal-filters button{padding:9px 13px;border:1px solid #cbd5e1;background:#fff;color:#344054!important;border-radius:9px;cursor:pointer;font-weight:700;opacity:1}.strategy-decision-panel .journal-search button:hover,.strategy-decision-panel .journal-filters button:hover{background:#f3efff;border-color:#8b5cf6;color:#5d18d6!important}.strategy-decision-panel .journal-search button:focus-visible,.strategy-decision-panel .journal-filters button:focus-visible{outline:3px solid #f59e0b;outline-offset:2px}.strategy-decision-panel .journal-search strong{padding:10px;color:#475467}.strategy-decision-panel .lifecycle-overview{margin:18px 0}.strategy-decision-panel .lifecycle-overview>header p{color:#64748b}.strategy-decision-panel .lifecycle-summary-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:10px}.strategy-decision-panel .lifecycle-summary-card{background:#fff;border:1px solid #dbe3ef;border-radius:12px;padding:12px;min-width:0;overflow:hidden}.strategy-decision-panel .lifecycle-summary-card header{display:grid;grid-template-columns:1fr;gap:5px;background:#0b1d3a;color:#fff;padding:10px 12px;margin:-12px -12px 10px;overflow:hidden}.strategy-decision-panel .lifecycle-summary-card header .type{color:#c4b5fd}.strategy-decision-panel .lifecycle-stage-badge{display:block;width:fit-content;max-width:100%;height:auto;padding:4px 7px;border-radius:7px;background:#eef2ff;color:#4338ca!important;font-size:11px;font-weight:800;white-space:normal;overflow-wrap:anywhere}.strategy-decision-panel .lifecycle-summary-card h3{margin:0;color:#fff;font-size:16px;line-height:1.2;overflow-wrap:anywhere}.strategy-decision-panel .lifecycle-rationale{margin:9px 0;font-size:13px;line-height:1.35}.strategy-decision-panel .lifecycle-more{margin:8px 0}.strategy-decision-panel .lifecycle-more summary{font-size:13px}.strategy-decision-panel .lifecycle-summary-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:12px 0}.strategy-decision-panel .lifecycle-summary-grid div{background:#f8fafc;border:1px solid #e5e7eb;border-radius:9px;padding:8px}.strategy-decision-panel .lifecycle-summary-grid dt{font-size:11px;color:#64748b}.strategy-decision-panel .lifecycle-summary-grid dd{margin:3px 0 0;font-weight:700}.strategy-decision-panel [data-lifecycle-search]{padding:9px 13px;border:1px solid #8b5cf6;background:#fff;color:#5d18d6!important;border-radius:9px;font-weight:700;cursor:pointer}.strategy-decision-panel .lifecycle-controls{display:flex;flex-wrap:wrap;align-items:end;gap:10px;margin:14px 0}.strategy-decision-panel .lifecycle-controls label{display:grid;gap:5px;min-width:220px;flex:1}.strategy-decision-panel .lifecycle-controls input,.strategy-decision-panel .lifecycle-controls select{padding:10px;border:1px solid #cbd5e1;border-radius:9px;background:#fff}.strategy-decision-panel .lifecycle-pagination{display:flex;justify-content:center;align-items:center;gap:12px;margin:14px 0}.strategy-decision-panel .lifecycle-pagination button{padding:9px 13px;border:1px solid #cbd5e1;background:#fff;color:#344054!important;border-radius:9px;font-weight:700}.strategy-decision-panel .journal-cross-links a{padding:8px 11px;border:1px solid #cbd5e1;background:#fff;border-radius:9px;color:#5d18d6;text-decoration:none;font-weight:700}.strategy-decision-panel .journal-cross-links a[aria-current="page"]{background:#5d18d6;color:#fff}.strategy-decision-panel table{width:100%;border-collapse:collapse}.strategy-decision-panel th,.strategy-decision-panel td{border-bottom:1px solid #e5e7eb;padding:9px;text-align:left}.strategy-decision-panel .committee-evidence-timeline{margin-top:18px}.strategy-decision-panel .committee-timeline{list-style:none;margin:12px 0 0;padding:0 0 0 18px;border-left:3px solid #c4b5fd}.strategy-decision-panel .committee-step{position:relative;display:grid;grid-template-columns:34px 1fr;gap:10px;margin:0 0 16px -36px}.strategy-decision-panel .committee-sequence{display:grid;place-items:center;width:30px;height:30px;border-radius:50%;background:#5b21b6;color:#fff;font-weight:800}.strategy-decision-panel .committee-step-content{background:#f8fafc;border:1px solid #dbe3ef;border-radius:12px;padding:12px}.strategy-decision-panel .committee-step-content header{display:flex;justify-content:space-between;gap:12px}.strategy-decision-panel .committee-vote{font-size:12px;font-weight:800;color:#5b21b6}.strategy-decision-panel .committee-step-content dl{display:flex;flex-wrap:wrap;gap:14px;margin:10px 0}.strategy-decision-panel .committee-step-content dl div{display:flex;gap:5px}.strategy-decision-panel .committee-step-content dt{color:#64748b}.strategy-decision-panel .committee-step-content dd{margin:0;font-weight:700}.strategy-decision-panel .image-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}.strategy-decision-panel .evidence-image{margin:0;background:#f8fafc;border:1px solid #dbe3ef;border-radius:12px;overflow:hidden;text-align:left;color:inherit;padding:0;text-decoration:none}.strategy-decision-panel a.evidence-image{cursor:pointer}.strategy-decision-panel .evidence-image img{width:100%;height:160px;object-fit:cover;display:block}.strategy-decision-panel .evidence-image span,.strategy-decision-panel .evidence-image p{display:block;padding:10px;margin:0}.strategy-decision-panel .image-unavailable{height:160px;display:grid;place-items:center;background:#eef2f7;color:#64748b}.ai-commentary{margin-top:18px;background:#fffaf0;border:1px solid #f4cc73;border-radius:12px;padding:18px}.ai-commentary strong{color:#e66b00}
@media(max-width:900px){.portal-frame{grid-template-columns:1fr}.enterprise-sidebar{position:static;min-height:0}.primary-navigation,.registered-strategy-links{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.strategy-analysis-grid{grid-template-columns:1fr}.workspace-tabs{scroll-snap-type:x proximity}.workspace-tab{scroll-snap-align:start}}@media(max-width:520px){.primary-navigation,.registered-strategy-links{grid-template-columns:1fr}.strategy-cross-links{display:grid}.journal-heading{display:block}}

:root{--cio-navy:#081a36;--cio-purple:#6528e0;--cio-violet:#8b5cf6;--cio-blue:#2563eb;--cio-cyan:#0891b2;--cio-green:#059669;--cio-amber:#d97706;--cio-red:#dc2626;--cio-surface:#f4f7fc;--cio-border:#d9e2f0}
.portal-frame{background:linear-gradient(145deg,#f8faff 0%,#eef3fb 100%);border-radius:18px;padding:18px}
.enterprise-sidebar{background:linear-gradient(180deg,var(--cio-navy) 0%,#102a56 100%);box-shadow:0 18px 45px rgba(8,26,54,.22)}
.enterprise-content>.panel,.strategy-analysis.panel{border:1px solid var(--cio-border);box-shadow:0 10px 28px rgba(30,50,90,.08)}
.enterprise-content>.grid .card{position:relative;overflow:hidden;border:1px solid var(--cio-border);box-shadow:0 8px 22px rgba(30,50,90,.08)}.enterprise-content>.grid .card:before{content:'';position:absolute;inset:0 0 auto;height:5px;background:var(--card-accent,var(--cio-purple))}.enterprise-content>.grid .card:nth-child(1){--card-accent:var(--cio-blue)}.enterprise-content>.grid .card:nth-child(2){--card-accent:var(--cio-cyan)}.enterprise-content>.grid .card:nth-child(3){--card-accent:var(--cio-purple)}.enterprise-content>.grid .card:nth-child(4){--card-accent:var(--cio-green)}.enterprise-content>.grid .card:nth-child(5){--card-accent:#4f46e5}.enterprise-content>.grid .card:nth-child(6){--card-accent:var(--cio-amber)}.enterprise-content>.grid .card .value{color:var(--card-accent,var(--cio-purple));font-size:1.55rem;font-weight:900}
.strategy-kpi-card{position:relative;overflow:hidden;box-shadow:0 8px 22px rgba(30,50,90,.08);transition:transform .18s ease,box-shadow .18s ease}
.strategy-kpi-card:before{content:'';position:absolute;inset:0 auto 0 0;width:6px;background:linear-gradient(180deg,var(--cio-purple),var(--cio-cyan))}
.strategy-kpi-card:hover{transform:translateY(-2px);box-shadow:0 14px 30px rgba(45,30,110,.15)}
.strategy-kpi-card.active{background:linear-gradient(135deg,#fff 0%,#f4efff 100%);outline:3px solid var(--cio-violet)}
.data-availability{display:flex;align-items:flex-start;gap:14px;margin:14px 0;padding:14px 16px;border-radius:12px;border:1px solid}.data-availability strong,.data-availability span{display:block}.data-availability strong{white-space:nowrap}.data-availability-pending{background:#fff7e8;border-color:#f7c66b;color:#713f12}.data-availability-ready{background:#eafbf3;border-color:#7ed9b0;color:#065f46}
.workspace-tabs{padding:8px;background:#edf1f8;border:1px solid var(--cio-border);border-radius:12px}.workspace-tab{border:0;box-shadow:0 2px 6px rgba(15,23,42,.08)}
.workspace-tab[data-workspace-tab-target='executive-summary'].active{background:var(--cio-purple)}.workspace-tab[data-workspace-tab-target='portfolio'].active{background:var(--cio-blue)}.workspace-tab[data-workspace-tab-target='watchlist'].active{background:var(--cio-cyan)}.workspace-tab[data-workspace-tab-target='holdings'].active{background:#4f46e5}.workspace-tab[data-workspace-tab-target='income'].active{background:var(--cio-green)}.workspace-tab[data-workspace-tab-target='performance'].active{background:#7c3aed}.workspace-tab[data-workspace-tab-target='alerts'].active{background:var(--cio-amber)}.workspace-tab[data-workspace-tab-target='decisions'].active{background:#be185d}
.workspace-tab-panel{background:#fff;border:1px solid var(--cio-border);border-radius:14px;padding:18px}.workspace-tab-panel h3{margin-top:0;color:var(--cio-navy)}
.metric-table{overflow:hidden;border:1px solid var(--cio-border);border-radius:10px}.metric-table th,.metric-table td{padding:11px 12px;border-bottom:1px solid #e7edf6}.metric-table tr:last-child th,.metric-table tr:last-child td{border-bottom:0}.metric-table tr:nth-child(even){background:#f8faff}.metric-table td{font-weight:800;color:#27364f}.metric-table td .metric-positive{color:#087443!important}.metric-table td .metric-negative{color:#b42318!important}.metric-table td .metric-neutral{color:#475569!important}
.strategy-alert-list{display:grid;gap:12px}.strategy-alert-card{border:1px solid #f2c46d;border-left:5px solid var(--cio-amber);border-radius:12px;background:#fffaf0;padding:14px 16px}.strategy-alert-card header{display:flex;justify-content:space-between;gap:12px;align-items:center}.strategy-alert-card header span{padding:4px 8px;border-radius:999px;background:#ffedd5;color:#9a3412;font-size:12px;font-weight:800}.strategy-alert-card p{margin:10px 0;color:#344054}.strategy-alert-evidence{margin:8px 0 0;padding-left:20px;color:#475467}.strategy-alert-evidence li{margin:5px 0}\n.empty-state{padding:18px;border:1px dashed #b8c5d9;border-radius:10px;background:#f8fafc;color:#64748b;text-align:center}
@media(max-width:700px){.data-availability{display:block}.data-availability strong{margin-bottom:6px}.portal-frame{padding:10px}}
</style>"""
    return base_css + holdings_ui_css() + watchlist_ui_css()
