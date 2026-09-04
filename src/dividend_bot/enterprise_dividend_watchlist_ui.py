"""Dividend-owned collapsible watchlist rendering.

This is a presentation-only layer. It never manufactures PASS states or authorizes
paper entry. Missing gate evidence is rendered PENDING so the UI remains fail closed.
"""
from __future__ import annotations

import html
from typing import Any, Mapping


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first(item: Mapping[str, Any], *keys: str, default: str = "—") -> str:
    for key in keys:
        value = item.get(key)
        if value not in (None, "", [], {}):
            return str(value)
    return default


def _status_from(value: Any) -> tuple[str, str]:
    if isinstance(value, Mapping):
        raw = value.get("status")
    else:
        raw = value
    status = str(raw or "PENDING").strip().upper()
    if status in {"PASS", "READY", "ELIGIBLE", "APPROVED", "BUY", "PROMOTED"}:
        return status, "dividend-watch-status-pass"
    if status in {"FAIL", "REJECTED", "BLOCKED", "INELIGIBLE"}:
        return status, "dividend-watch-status-fail"
    return "PENDING" if status in {"", "NONE", "UNKNOWN", "NOT_REPORTED"} else status, "dividend-watch-status-pending"


def _gate(item: Mapping[str, Any], *keys: str) -> Mapping[str, Any]:
    for key in keys:
        value = item.get(key)
        if isinstance(value, Mapping):
            return value
        if value not in (None, "", [], {}):
            return {"status": value}
    return {}


def _detail_rows(gate: Mapping[str, Any]) -> str:
    if not gate:
        return "<div class='dividend-watch-note'>Authoritative evidence has not been published for this gate.</div>"
    rows: list[str] = []
    for label, key in (
        ("Value", "value"),
        ("Threshold", "threshold"),
        ("Reason", "reason"),
        ("Evidence", "evidence_source"),
        ("Provenance", "provenance"),
        ("As-of", "generated_at"),
    ):
        value = gate.get(key)
        if value not in (None, "", [], {}):
            rows.append(f"<div><span>{html.escape(label)}</span><strong>{html.escape(str(value))}</strong></div>")
    return "".join(rows) or "<div class='dividend-watch-note'>No additional authoritative detail was published.</div>"


def _gate_card(label: str, gate: Mapping[str, Any]) -> str:
    status, css = _status_from(gate)
    return (
        "<article class='dividend-watch-gate'>"
        f"<header><strong>{html.escape(label)}</strong><span class='{css}'>{html.escape(status)}</span></header>"
        f"<div class='dividend-watch-gate-body'>{_detail_rows(gate)}</div>"
        "</article>"
    )


def _promotion_status(item: Mapping[str, Any]) -> tuple[str, str]:
    readiness = _mapping(item.get("promotion_readiness"))
    value = readiness.get("promotion_ready") if readiness else item.get("promotion_ready")
    if value is True:
        return "YES", "dividend-watch-status-pass"
    if value is False:
        return "NO", "dividend-watch-status-fail"
    return "PENDING", "dividend-watch-status-pending"


def _details(item: Mapping[str, Any], symbol: str) -> str:
    readiness = _mapping(item.get("promotion_readiness"))
    sources = _gate(item, "trusted_sources", "source_trust", "evidence_quality")
    financial = _gate(item, "financial_health")
    income = _gate(item, "dividend_suitability", "income_suitability", "suitability")
    safety = _gate(item, "dividend_safety", "income_safety", "payout_safety")
    valuation = _gate(item, "valuation", "valuation_suitability", "price_suitability")
    thesis = _gate(item, "opportunity_thesis", "theme_opportunity", "thesis_integrity")
    entry = _mapping(readiness.get("entry")) or _gate(item, "entry_readiness", "entry")
    cards = "".join((
        _gate_card("Trusted Sources / Evidence", sources),
        _gate_card("Financial Health", financial),
        _gate_card("Dividend / Income Suitability", income),
        _gate_card("Dividend Safety / Sustainability", safety),
        _gate_card("Valuation / Price Suitability", valuation),
        _gate_card("Theme / Opportunity Evidence", thesis),
        _gate_card("Entry Readiness", entry),
    ))
    blockers = readiness.get("blocking_reasons") if readiness else item.get("blocking_reasons")
    if isinstance(blockers, list) and blockers:
        blocker_html = "<ul>" + "".join(f"<li>{html.escape(str(x))}</li>" for x in blockers) + "</ul>"
    else:
        blocker_html = "<div class='dividend-watch-note'>No authoritative blocking reasons were published.</div>"
    return (
        "<div class='dividend-watch-detail-panel'>"
        f"<div class='dividend-watch-detail-heading'><strong>Dividend Promotion Readiness — {html.escape(symbol)}</strong>"
        "<span>Pre-trade gates only; post-entry strategy performance is not used here.</span></div>"
        f"<div class='dividend-watch-gates'>{cards}</div>"
        f"<div class='dividend-watch-blockers'><strong>Blocking reasons</strong>{blocker_html}</div>"
        "</div>"
    )


def render_dividend_watchlist_panel(row: Mapping[str, Any]) -> str:
    raw = row.get("watchlist")
    items = [item for item in raw if isinstance(item, Mapping)] if isinstance(raw, list) else []
    if not items:
        count = row.get("watchlist_count", 0)
        return (
            "<section class='dividend-watchlist'><div class='dividend-watch-heading'><div><h3>Dividend Watchlist</h3>"
            "<p>Qualified income candidates waiting for complete pre-trade evidence and a viable entry.</p></div>"
            f"<span>{html.escape(str(count))} candidates</span></div>"
            "<div class='dividend-watch-empty'>No detailed Dividend watchlist records are currently published.</div></section>"
        )
    rows: list[str] = []
    for index, item in enumerate(items, start=1):
        symbol = _first(item, "underlying_symbol", "symbol", "ticker", default="UNKNOWN")
        status = _first(item, "lifecycle_status", "watchlist_status", "status", default="WATCHLIST").upper()
        rank = _first(item, "watchlist_rank", "rank", "candidate_rank", default=str(index))
        entry_gate = _mapping(_mapping(item.get("promotion_readiness")).get("entry")) or _gate(item, "entry_readiness", "entry")
        entry_status, entry_css = _status_from(entry_gate)
        promotion, promotion_css = _promotion_status(item)
        detail_id = f"dividend-watch-detail-{index}"
        rows.append(
            "<tr class='dividend-watch-row'>"
            f"<td>{html.escape(rank)}</td><td><strong>{html.escape(symbol)}</strong></td>"
            f"<td>{html.escape(status)}</td>"
            f"<td><span class='{entry_css}'>{html.escape(entry_status)}</span></td>"
            f"<td><button type='button' class='dividend-watch-toggle' aria-expanded='false' aria-controls='{detail_id}' title='Show Dividend promotion details'><span class='{promotion_css}'>{html.escape(promotion)}</span></button></td>"
            "</tr>"
            f"<tr id='{detail_id}' class='dividend-watch-detail-row' hidden><td colspan='5'>{_details(item, symbol)}</td></tr>"
        )
    behavior = """
<script>(function(){const s=document.currentScript;const root=s?s.closest('.dividend-watchlist'):null;if(!root)return;root.addEventListener('click',function(e){const b=e.target.closest('.dividend-watch-toggle');if(!b)return;const id=b.getAttribute('aria-controls');const r=id?document.getElementById(id):null;if(!r)return;const open=b.getAttribute('aria-expanded')!=='true';b.setAttribute('aria-expanded',open?'true':'false');b.setAttribute('title',open?'Hide Dividend promotion details':'Show Dividend promotion details');r.hidden=!open;});})();</script>
"""
    return (
        "<section class='dividend-watchlist'><div class='dividend-watch-heading'><div><h3>Dividend Watchlist</h3>"
        "<p>Each symbol expands to the Dividend Bot's pre-trade qualification record.</p></div>"
        f"<span>{len(items)} records</span></div>"
        "<div class='dividend-watch-table-wrap'><table class='dividend-watch-table'><thead><tr><th>Rank</th><th>Symbol</th><th>Status</th><th>Entry</th><th>Promotion</th></tr></thead><tbody>"
        + "".join(rows) + "</tbody></table></div>" + behavior
        + "<p class='dividend-watch-footnote'>Missing evidence stays PENDING. This UI does not authorize purchases or apply post-entry Win Rate / return / drawdown gates.</p></section>"
    )


def dividend_watchlist_ui_css() -> str:
    return """
<style>
.dividend-watchlist{color:#10213b}.dividend-watch-heading{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:14px}.dividend-watch-heading h3{margin:0 0 5px}.dividend-watch-heading p{margin:0;color:#64748b}.dividend-watch-heading>span{background:#eef2ff;color:#5b21b6;border:1px solid #d8ccff;border-radius:999px;padding:7px 11px;font-weight:800}.dividend-watch-table-wrap{overflow-x:auto;border:1px solid #dbe4f0;border-radius:12px;background:#fff}.dividend-watch-table{width:100%;border-collapse:collapse}.dividend-watch-table th{background:#f4f7fc;color:#53627a;text-align:left;padding:10px 12px;font-size:.72rem;text-transform:uppercase}.dividend-watch-table td{padding:11px 12px;border-top:1px solid #edf1f6}.dividend-watch-toggle{appearance:none;border:0;background:transparent;padding:0;cursor:pointer}.dividend-watch-status-pass,.dividend-watch-status-fail,.dividend-watch-status-pending{display:inline-block;border-radius:999px;padding:5px 8px;font-size:.72rem;font-weight:800}.dividend-watch-status-pass{background:#e9f9f0;color:#087443}.dividend-watch-status-fail{background:#fff0f0;color:#b42318}.dividend-watch-status-pending{background:#f1f5f9;color:#64748b}.dividend-watch-detail-row[hidden]{display:none}.dividend-watch-detail-row td{padding:0!important;background:#f8fbff}.dividend-watch-detail-panel{margin:9px;padding:12px;border:1px solid #cfe0f5;border-radius:10px;background:#fff}.dividend-watch-detail-heading{display:flex;justify-content:space-between;gap:12px;padding-bottom:9px;border-bottom:1px solid #dbe4f0}.dividend-watch-detail-heading span{color:#64748b;font-size:.75rem}.dividend-watch-gates{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:10px}.dividend-watch-gate{border:1px solid #dbe4f0;border-radius:8px;padding:9px;min-width:0}.dividend-watch-gate header{display:flex;justify-content:space-between;gap:6px;align-items:flex-start}.dividend-watch-gate-body{display:grid;gap:4px;margin-top:7px;font-size:.72rem}.dividend-watch-gate-body div{display:grid;grid-template-columns:75px 1fr;gap:6px}.dividend-watch-gate-body span{color:#64748b}.dividend-watch-gate-body strong{overflow-wrap:anywhere}.dividend-watch-note{color:#64748b;font-size:.72rem}.dividend-watch-blockers{margin-top:9px;padding:9px 10px;border:1px solid #fee4e2;border-radius:8px;background:#fff4f2}.dividend-watch-footnote{color:#718096;font-size:.8rem}.dividend-watch-empty{padding:22px;border:1px dashed #b9c7db;border-radius:10px;color:#64748b;text-align:center}@media(max-width:1000px){.dividend-watch-gates{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){.dividend-watch-gates{grid-template-columns:1fr}.dividend-watch-detail-heading{display:block}}
</style>
"""
