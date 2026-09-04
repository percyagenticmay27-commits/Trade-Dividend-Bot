"""Dividend-owned watchlist rendering with collapsible pre-trade readiness detail.

The Dividend table preserves the existing Watchlist columns and published values.
The only extension is a collapsible record immediately below each symbol row.
Missing gate evidence remains PENDING and this presentation layer never authorizes entry.
"""
from __future__ import annotations

import html
from typing import Any, Mapping


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first(item: Mapping[str, Any], keys: tuple[str, ...], default: str = "Not reported") -> str:
    for key in keys:
        value = item.get(key)
        if value not in (None, "", [], {}):
            return str(value)
    return default


def _score(value: Any) -> str:
    number = _number(value)
    return f"{number:,.1f}" if number is not None else "Not reported"


def _missing(value: str) -> str:
    return "<span class='watchlist-not-reported'>Not reported</span>" if value == "Not reported" else html.escape(value)


def _plain_reason(value: Any) -> str:
    return str(value).replace("_", " ").strip().capitalize()


def _reason_list(value: Any) -> list[str]:
    return [_plain_reason(item) for item in value if item not in (None, "")] if isinstance(value, list) else []


def _progress(item: Mapping[str, Any]) -> tuple[str, str]:
    explicit_entry_status = item.get("entry_status")
    status = str(explicit_entry_status or item.get("status") or "WATCH").upper()
    requirements = _reason_list(item.get("requirements_for_buy"))
    reasons = _reason_list(item.get("entry_reasons"))
    if explicit_entry_status in (None, "") and item.get("entry_score") is None:
        return "Current symbol-level entry evidence is unavailable.", "Generate a current Entry Score report before evaluating progression."
    if status in {"BUY", "READY", "PROMOTED", "APPROVED"}:
        return "Entry requirements satisfied.", "Await paper allocation/entry authorization."
    if requirements:
        return "Waiting for " + "; ".join(requirements) + ".", "Re-evaluate after the listed requirements are satisfied."
    if reasons:
        return "; ".join(reasons) + ".", "Continue monitoring for a qualified entry signal."
    if status == "EVIDENCE_UNAVAILABLE":
        return "Current symbol-level entry evidence is unavailable.", "Generate a current Entry Score report."
    return "Candidate remains under observation; no explicit blocker was published.", "Continue monitoring until the strategy publishes an entry decision."


def _status(item: Mapping[str, Any]) -> tuple[str, str]:
    raw = _first(item, ("status", "watchlist_status", "candidate_status"), "WATCH").upper()
    if raw in {"READY", "READY_FOR_SCORING", "PROMOTED", "BUY"}:
        return raw, "watchlist-status-ready"
    if raw in {"WATCH", "WATCHLIST", "DISCOVERY", "MONITOR", "HOLD"}:
        return raw, "watchlist-status-watch"
    if raw in {"REMOVED", "REJECTED", "BLOCKED"}:
        return raw, "watchlist-status-blocked"
    return raw, "watchlist-status-neutral"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _gate(item: Mapping[str, Any], readiness: Mapping[str, Any], *keys: str) -> Mapping[str, Any]:
    for key in keys:
        value = readiness.get(key)
        if isinstance(value, Mapping):
            return value
        value = item.get(key)
        if isinstance(value, Mapping):
            return value
        if value not in (None, "", [], {}):
            return {"status": value}
    return {}


def _gate_status(gate: Mapping[str, Any]) -> tuple[str, str]:
    status = str(gate.get("status") or "PENDING").strip().upper() if gate else "PENDING"
    if status in {"PASS", "READY", "ELIGIBLE", "APPROVED", "BUY", "PROMOTED"}:
        return status, "watchlist-status-ready"
    if status in {"FAIL", "REJECTED", "BLOCKED", "INELIGIBLE"}:
        return status, "watchlist-status-blocked"
    return "PENDING", "watchlist-status-neutral"


def _detail_value(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return ", ".join(html.escape(str(item)) for item in value if item not in (None, "")) or "—"
    if isinstance(value, Mapping):
        return "; ".join(
            f"{html.escape(str(key))}: {html.escape(str(item))}"
            for key, item in value.items()
            if item not in (None, "", [], {})
        ) or "—"
    if isinstance(value, bool):
        return "true" if value else "false"
    return html.escape(str(value))


def _gate_card(label: str, gate: Mapping[str, Any]) -> str:
    status, css = _gate_status(gate)
    lines: list[str] = []
    if gate:
        for field_label, keys in (
            ("Value", ("value",)),
            ("Threshold", ("threshold",)),
            ("Reason", ("reason",)),
            ("Evidence source", ("evidence_source", "source", "source_path")),
            ("Provenance", ("provenance", "evidence_provenance")),
            ("As-of", ("generated_at", "generated_at_utc", "as_of")),
        ):
            raw = next((gate.get(key) for key in keys if gate.get(key) not in (None, "", [], {})), None)
            if raw is not None:
                lines.append(
                    "<div class='dividend-promotion-line'><span>"
                    + html.escape(field_label)
                    + ":</span> <strong>"
                    + _detail_value(raw)
                    + "</strong></div>"
                )
    if not lines:
        lines.append("<div class='dividend-promotion-note'>Authoritative gate evidence is unavailable.</div>")
    return (
        "<article class='dividend-promotion-gate-card'>"
        "<div class='dividend-promotion-gate-header'>"
        f"<strong>{html.escape(label)}</strong><span class='watchlist-status {css}'>{html.escape(status)}</span>"
        "</div>"
        f"<div class='dividend-promotion-gate-content'>{''.join(lines)}</div>"
        "</article>"
    )


def _promotion_detail_body(item: Mapping[str, Any], symbol: str) -> str:
    readiness = _mapping(item.get("promotion_readiness"))
    gates = (
        ("Trusted Sources / Evidence", _gate(item, readiness, "trusted_sources", "source_trust", "evidence_quality")),
        ("Financial Health", _gate(item, readiness, "financial_health")),
        ("Dividend / Income Suitability", _gate(item, readiness, "dividend_suitability", "income_suitability", "suitability")),
        ("Dividend Safety / Sustainability", _gate(item, readiness, "dividend_safety", "income_safety", "payout_safety")),
        ("Valuation / Price Suitability", _gate(item, readiness, "valuation", "valuation_suitability", "price_suitability")),
        ("Theme / Opportunity Evidence", _gate(item, readiness, "opportunity_thesis", "theme_opportunity", "thesis_integrity")),
        ("Entry Readiness", _gate(item, readiness, "entry", "entry_readiness")),
    )
    cards = "".join(_gate_card(label, gate) for label, gate in gates)
    blockers = readiness.get("blocking_reasons") if readiness else item.get("blocking_reasons")
    if isinstance(blockers, list) and any(str(reason).strip() for reason in blockers):
        blocking = "<ul class='watchlist-blocking-list'>" + "".join(
            f"<li>{html.escape(str(reason))}</li>" for reason in blockers if str(reason).strip()
        ) + "</ul>"
    elif readiness.get("promotion_ready") is True:
        blocking = "<div class='dividend-promotion-note'>No blocking reasons were published.</div>"
    else:
        blocking = "<div class='dividend-promotion-note'>No authoritative blocking reasons were published.</div>"
    return (
        "<div class='dividend-promotion-panel'>"
        "<div class='dividend-promotion-panel-heading'>"
        f"<strong>Promotion Readiness — {html.escape(symbol)}</strong>"
        "<span>Click the candidate, Entry Status, or Entry Score value to collapse.</span>"
        "</div>"
        "<div class='dividend-promotion-section-title'>Dividend pre-trade Promotion Readiness</div>"
        f"<div class='dividend-promotion-gates'>{cards}</div>"
        "<div class='dividend-promotion-blockers'><strong>Blocking reasons</strong>"
        f"{blocking}</div></div>"
    )


def _toggle(content: str, detail_id: str, label: str, css_class: str = "dividend-watch-detail-toggle") -> str:
    return (
        f"<button type='button' class='{css_class}' aria-expanded='false' "
        f"aria-controls='{html.escape(detail_id, quote=True)}' "
        f"aria-label='Open {html.escape(label, quote=True)} Promotion Readiness details' "
        "title='Show Promotion Readiness details'>"
        f"{content}</button>"
    )


def _rows(items: list[Mapping[str, Any]]) -> str:
    result: list[str] = []
    for index, item in enumerate(items, start=1):
        rank = _first(item, ("rank", "watchlist_rank", "candidate_rank"), str(index))
        symbol_raw = _first(item, ("symbol", "candidate_id"), "UNKNOWN")
        symbol = html.escape(symbol_raw)
        name = _missing(_first(item, ("name", "security_name", "display_name", "instrument_name")))
        status, status_class = _status(item)
        entry_status = _first(item, ("entry_status",), status).upper()
        entry_score_text = _score(item.get("entry_score"))
        entry_score = _missing(entry_score_text)
        confidence_value = item.get("entry_confidence")
        confidence = _score(confidence_value)
        confidence_level = _first(item, ("entry_confidence_level",), "")
        confidence_text = confidence + (f" ({confidence_level.replace('_', ' ').title()})" if confidence_level else "")
        progress, next_step = _progress(item)
        timing = _first(item, ("timing_context",), "Not reported").replace("_", " ").title()
        market_state = "STALE" if item.get("market_data_stale") is True else "FRESH" if item.get("market_data_stale") is False else "Not reported"
        market_class = "watchlist-market-stale" if market_state == "STALE" else "watchlist-market-fresh" if market_state == "FRESH" else "watchlist-status-neutral"
        held = "YES" if item.get("currently_held") is True else "NO" if item.get("currently_held") is False else "Not reported"
        evidence_at = _first(item, ("entry_evidence_generated_at_utc",), "")
        source_value = item.get("sources")
        if isinstance(source_value, list):
            evidence_sources = ", ".join(str(value) for value in source_value if value)
        else:
            evidence_sources = _first(item, ("evidence_source", "source", "source_path"), "")
        evidence_parts = [value for value in (evidence_sources, evidence_at) if value]
        evidence = " · ".join(evidence_parts) if evidence_parts else "Not reported"
        detail_id = f"dividend-watch-detail-{index}"

        candidate_content = f"<strong>{symbol}</strong><small class='watchlist-candidate-name'>{name}</small>"
        candidate_toggle = _toggle(candidate_content, detail_id, symbol_raw)
        entry_status_content = f"<span class='watchlist-status {status_class}'>{html.escape(entry_status)}</span>"
        entry_status_toggle = _toggle(entry_status_content, detail_id, symbol_raw)
        entry_score_toggle = _toggle(entry_score, detail_id, symbol_raw)

        result.append(
            "<tr class='dividend-watch-candidate-row'>"
            f"<td class='num'>{html.escape(rank)}</td>"
            f"<td>{candidate_toggle}</td>"
            f"<td>{entry_status_toggle}</td>"
            f"<td class='num'>{entry_score_toggle}</td>"
            f"<td>{_missing(confidence_text)}</td>"
            f"<td>{_missing(html.escape(timing))}</td>"
            f"<td class='watchlist-explanation'><strong>{html.escape(progress)}</strong></td>"
            f"<td class='watchlist-explanation'>{html.escape(next_step)}</td>"
            f"<td><span class='watchlist-status {market_class}'>{_missing(market_state)}</span></td>"
            f"<td>{_missing(held)}</td>"
            f"<td class='watchlist-source'>{_missing(evidence)}</td>"
            "</tr>"
            f"<tr id='{detail_id}' class='dividend-watch-detail-row' hidden><td colspan='11'>"
            f"{_promotion_detail_body(item, symbol_raw)}"
            "</td></tr>"
        )
    return "".join(result)


def render_dividend_watchlist_panel(row: Mapping[str, Any]) -> str:
    raw = row.get("watchlist")
    items = [item for item in raw if isinstance(item, Mapping)] if isinstance(raw, list) else []
    count_value = _number(row.get("watchlist_count"))
    count = int(count_value) if count_value is not None else len(items)
    stale = sum(1 for item in items if item.get("market_data_stale") is True)
    held = sum(1 for item in items if item.get("currently_held") is True)
    ready = sum(1 for item in items if str(item.get("status") or "").upper() in {"READY", "READY_FOR_SCORING", "PROMOTED", "BUY"})
    heading = (
        "<div class='watchlist-heading'><div><h3>Watchlist</h3>"
        "<p>Strategy-owned candidates being monitored before promotion or allocation.</p></div>"
        f"<span class='watchlist-count'>{count} candidates</span></div>"
    )
    summary = (
        "<div class='watchlist-summary-grid'>"
        f"<div class='watchlist-summary-card'><span>Total Watchlist</span><strong>{count}</strong></div>"
        f"<div class='watchlist-summary-card'><span>Ready / Promoted</span><strong>{ready}</strong></div>"
        f"<div class='watchlist-summary-card'><span>Currently Held</span><strong>{held}</strong></div>"
        f"<div class='watchlist-summary-card'><span>Stale Market Data</span><strong>{stale}</strong></div>"
        "</div>"
    )
    if not items:
        explanation = (
            f"The strategy reports {count} candidate records, but no detailed strategy-owned rows are available. Candidate rows are never fabricated from the summary count."
            if count else "The strategy currently reports a watchlist count of 0. Candidates will appear here only when the strategy explicitly marks them for watchlist monitoring."
        )
        return (
            "<section class='watchlist-pro dividend-watchlist'>" + heading + summary
            + "<div class='watchlist-empty'><strong>No active strategy watchlist candidates.</strong>"
            f"<span>{html.escape(explanation)}</span></div></section>"
        )
    table = (
        "<div class='watchlist-table-wrap'><table class='watchlist-table'>"
        "<thead><tr><th>Rank</th><th>Candidate</th><th>Entry Status</th><th>Entry Score</th><th>Confidence</th>"
        "<th>Timing</th><th>Why It Has Not Progressed</th><th>What Happens Next</th><th>Market Data</th><th>Held</th><th>Evidence As-Of</th></tr></thead>"
        f"<tbody>{_rows(items)}</tbody></table></div>"
    )
    behavior = """
<script>
(function(){
  const script=document.currentScript;
  const root=script?script.closest('.dividend-watchlist'):null;
  if(!root)return;
  root.addEventListener('click',function(event){
    const toggle=event.target.closest('.dividend-watch-detail-toggle');
    if(!toggle||!root.contains(toggle))return;
    const targetId=toggle.getAttribute('aria-controls');
    const detailRow=targetId?document.getElementById(targetId):null;
    if(!detailRow)return;
    const nextExpanded=toggle.getAttribute('aria-expanded')!=='true';
    root.querySelectorAll('[aria-controls="'+targetId+'"]').forEach(function(control){
      control.setAttribute('aria-expanded',nextExpanded?'true':'false');
      control.setAttribute('title',nextExpanded?'Hide Promotion Readiness details':'Show Promotion Readiness details');
    });
    detailRow.hidden=!nextExpanded;
  });
})();
</script>
"""
    return (
        "<section class='watchlist-pro dividend-watchlist'>" + heading + summary + table + behavior
        + "<p class='watchlist-footnote'>Entry decisions come from the current symbol-level Entry Score report. The collapsible record adds Dividend pre-trade gate evidence without changing the original Watchlist columns or published values.</p></section>"
    )


def dividend_watchlist_ui_css() -> str:
    return """
<style>
.dividend-watch-detail-toggle{appearance:none;border:0;background:transparent;padding:0;margin:0;font:inherit;color:inherit;text-align:inherit;cursor:pointer}.dividend-watch-detail-toggle:focus-visible{outline:2px solid #5925dc;outline-offset:2px;border-radius:6px}.dividend-watch-detail-toggle .watchlist-candidate-name{display:block}.dividend-watch-detail-row[hidden]{display:none}.dividend-watch-detail-row td{padding:0!important;background:#f8fbff;white-space:normal!important;border-bottom:1px solid #dbe4f0}.dividend-promotion-panel{margin:8px 10px 12px;padding:12px;border:1px solid #cfe0f5;border-radius:10px;background:linear-gradient(180deg,#f8fbff,#fff);box-shadow:inset 0 1px 0 #fff;font-size:.76rem}.dividend-promotion-panel-heading{display:flex;justify-content:space-between;gap:14px;align-items:center;padding-bottom:8px;margin-bottom:8px;border-bottom:1px solid #dbe4f0}.dividend-promotion-panel-heading>strong{font-size:.92rem;color:#10213b}.dividend-promotion-panel-heading>span{font-size:.70rem;color:#64748b}.dividend-promotion-section-title{font-size:.78rem;font-weight:800;color:#10213b;margin:0 0 8px}.dividend-promotion-gates{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:8px;width:100%;min-width:0}.dividend-promotion-gate-card{border:1px solid #dbe4f0;border-radius:8px;background:#fff;padding:9px;min-width:0}.dividend-promotion-gate-header{display:flex;justify-content:space-between;gap:5px;align-items:flex-start;margin-bottom:7px}.dividend-promotion-gate-header>strong{font-size:.72rem;line-height:1.2}.dividend-promotion-gate-card .watchlist-status{padding:3px 6px;font-size:.64rem}.dividend-promotion-gate-content{display:grid;gap:4px;color:#334155}.dividend-promotion-line{font-size:.69rem;line-height:1.28;white-space:normal;overflow-wrap:anywhere}.dividend-promotion-line>span{color:#64748b;font-weight:600}.dividend-promotion-line>strong{font-weight:600;color:#334155}.dividend-promotion-note{color:#64748b;white-space:normal}.dividend-promotion-blockers{margin-top:8px;padding:8px 10px;border-radius:7px;background:#fff4f2;border:1px solid #fee4e2}.dividend-promotion-blockers>strong{color:#b42318;font-size:.72rem}@media(max-width:1200px){.dividend-promotion-gates{grid-template-columns:repeat(4,minmax(0,1fr))}}@media(max-width:800px){.dividend-promotion-gates{grid-template-columns:repeat(2,minmax(0,1fr))}.dividend-promotion-panel-heading{display:block}}@media(max-width:520px){.dividend-promotion-gates{grid-template-columns:1fr}}
</style>
"""
