"""Professional read-only Watchlist UI for Enterprise strategy workspaces."""
from __future__ import annotations

import html
from typing import Any, Mapping, Sequence


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first(item: Mapping[str, Any], keys: Sequence[str], default: str = "Not reported") -> str:
    for key in keys:
        value = item.get(key)
        if value not in (None, "", [], {}):
            return str(value)
    return default


def _percent(value: Any) -> str:
    number = _number(value)
    return f"{number:,.2f}%" if number is not None else "Not reported"


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


def _rows(items: list[Mapping[str, Any]]) -> str:
    result: list[str] = []
    for index, item in enumerate(items, start=1):
        rank = _first(item, ("rank", "watchlist_rank", "candidate_rank"), str(index))
        symbol = html.escape(_first(item, ("symbol", "candidate_id"), "UNKNOWN"))
        name = _missing(_first(item, ("name", "security_name", "display_name", "instrument_name")))
        status, status_class = _status(item)
        entry_status = _first(item, ("entry_status",), status).upper()
        entry_score = _missing(_score(item.get("entry_score")))
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
        result.append(
            "<tr>"
            f"<td class='num'>{html.escape(rank)}</td>"
            f"<td><strong>{symbol}</strong><small class='watchlist-candidate-name'>{name}</small></td>"
            f"<td><span class='watchlist-status {status_class}'>{html.escape(entry_status)}</span></td>"
            f"<td class='num'>{entry_score}</td>"
            f"<td>{_missing(confidence_text)}</td>"
            f"<td>{_missing(html.escape(timing))}</td>"
            f"<td class='watchlist-explanation'><strong>{html.escape(progress)}</strong></td>"
            f"<td class='watchlist-explanation'>{html.escape(next_step)}</td>"
            f"<td><span class='watchlist-status {market_class}'>{_missing(market_state)}</span></td>"
            f"<td>{_missing(held)}</td>"
            f"<td class='watchlist-source'>{_missing(evidence)}</td>"
            "</tr>"
        )
    return "".join(result)


def _lifecycle(item: Mapping[str, Any]) -> str:
    return _first(item, ("lifecycle_status", "lifecycle_state", "watchlist_status", "status"), "Not reported").upper()


def _pipeline_cell(value: Any, *, missing: str = "—") -> str:
    if value in (None, "", [], {}):
        return html.escape(missing)
    if isinstance(value, bool):
        return "YES" if value else "NO"
    return html.escape(str(value))


def _gate_status(gate: Any) -> tuple[str, str]:
    if not isinstance(gate, Mapping):
        return "PENDING", "watchlist-status-neutral"
    status = str(gate.get("status") or "PENDING").strip().upper()
    if status == "PASS":
        return status, "watchlist-status-ready"
    if status == "FAIL":
        return status, "watchlist-status-blocked"
    return "PENDING", "watchlist-status-neutral"


def _exact_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _compact_number(value: Any, *, one_decimal: bool = False) -> str | None:
    number = _number(value)
    if number is None:
        return None
    if one_decimal:
        return f"{number:,.1f}"
    if float(number).is_integer():
        return f"{int(number):,}"
    return f"{number:g}"


def _evidence_values(gate: Mapping[str, Any]) -> list[tuple[str, Any]]:
    fields: list[tuple[str, Any]] = []
    for label, keys in (
        ("Evidence availability", ("evidence_availability", "evidence_available", "evidence_status")),
        ("Evidence source", ("evidence_source", "source", "source_path")),
        ("Provenance", ("provenance", "evidence_provenance")),
        ("Sources", ("sources", "source_names", "source_details")),
    ):
        for key in keys:
            value = gate.get(key)
            if value not in (None, "", [], {}):
                fields.append((label, value))
                break
    return fields


def _detail_value(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return ", ".join(html.escape(str(item)) for item in value if item not in (None, "")) or "—"
    if isinstance(value, Mapping):
        return "; ".join(
            f"{html.escape(str(key))}: {html.escape(str(item))}"
            for key, item in value.items()
            if item not in (None, "", [], {})
        ) or "—"
    return html.escape(_exact_value(value))


def _qa_rows(gate: Any, *, include_evidence: bool = True) -> str:
    if not isinstance(gate, Mapping):
        return "<div class='watchlist-qa-note'>Authoritative gate evidence is unavailable.</div>"
    status, _ = _gate_status(gate)
    rows: list[tuple[str, Any]] = [("Status", status)]
    if "value" in gate:
        rows.append(("Exact value", gate.get("value")))
    if "threshold" in gate:
        rows.append(("Threshold", gate.get("threshold")))
    if gate.get("reason") not in (None, ""):
        rows.append(("Reason", gate.get("reason")))
    if include_evidence:
        rows.extend(_evidence_values(gate))
    return "<dl class='watchlist-qa-list'>" + "".join(
        f"<div><dt>{html.escape(label)}</dt><dd>{_detail_value(value) if value is not None else '—'}</dd></div>"
        for label, value in rows
    ) + "</dl>"


def _details(summary_html: str, body_html: str, *, label: str) -> str:
    return (
        "<details class='watchlist-qa-details'>"
        f"<summary aria-label='{html.escape(label, quote=True)}'>{summary_html}</summary>"
        f"<div class='watchlist-qa-body'>{body_html}</div></details>"
    )


def _gate_cell(readiness: Mapping[str, Any], key: str, *, mode: str, detail_id: str) -> str:
    gate = readiness.get(key)
    status, status_class = _gate_status(gate)
    value = gate.get("value") if isinstance(gate, Mapping) else None
    if status == "PENDING":
        label = "PENDING"
    elif mode == "status":
        label = status
    else:
        compact = _compact_number(value, one_decimal=(mode == "oq"))
        prefix = f"{compact} " if compact is not None else ""
        label = f"{prefix}{status}"
    return (
        "<button type='button' class='watchlist-detail-toggle' "
        f"aria-expanded='false' aria-controls='{html.escape(detail_id, quote=True)}' "
        f"aria-label='Open {html.escape(key.replace('_', ' '), quote=True)} details' "
        f"data-qa-label='Open {html.escape(key.replace('_', ' '), quote=True)} QA evidence' "
        "title='Show Promotion Readiness details'>"
        f"<span class='watchlist-status {status_class}'>{html.escape(label)}</span>"
        "</button>"
    )


def _promotion_summary(readiness: Mapping[str, Any] | None, *, detail_id: str) -> str:
    if readiness is None or "promotion_ready" not in readiness or readiness.get("promotion_ready") is None:
        promotion = "PENDING"
        status_class = "watchlist-status-neutral"
    elif readiness.get("promotion_ready") is True:
        promotion = "YES"
        status_class = "watchlist-status-ready"
    else:
        promotion = "NO"
        status_class = "watchlist-status-blocked"
    unavailable_note = (
        "<span class='watchlist-sr-only'>Authoritative Promotion Readiness evidence is unavailable.</span>"
        if readiness is None else ""
    )
    return (
        "<button type='button' class='watchlist-promotion-toggle' "
        f"aria-expanded='false' aria-controls='{html.escape(detail_id, quote=True)}' "
        "aria-label='Open Promotion QA evidence' title='Show Promotion Readiness details'>"
        f"<span class='watchlist-status {status_class}'>{html.escape(promotion)}</span>"
        f"{unavailable_note}</button>"
    )


def _promotion_detail_body(
    readiness: Mapping[str, Any] | None,
    *,
    underlying: str,
    leveraged: str,
) -> str:
    if readiness is None:
        return (
            "<div class='watchlist-promotion-panel'>"
            "<div class='watchlist-qa-note'>Authoritative Promotion Readiness evidence is unavailable.</div>"
            "</div>"
        )
    gate_labels = (
        ("Trusted Sources", "trusted_sources"),
        ("Financial Health", "financial_health"),
        ("Theme Strength", "theme_strength"),
        ("Opportunity Quality", "opportunity_quality"),
        ("Thesis Integrity", "thesis_integrity"),
        ("Entry Readiness", "entry"),
    )
    cards: list[str] = []
    for label, key in gate_labels:
        gate = readiness.get(key)
        status, gate_class = _gate_status(gate)
        lines: list[str] = []
        if isinstance(gate, Mapping):
            if "value" in gate:
                value = gate.get("value")
                lines.append(
                    "<div class='watchlist-promotion-line'><span>Value:</span> <strong>"
                    + (_detail_value(value) if value is not None else "—")
                    + "</strong></div>"
                )
            if "threshold" in gate:
                threshold = gate.get("threshold")
                lines.append(
                    "<div class='watchlist-promotion-line'><span>Threshold:</span> <strong>"
                    + (_detail_value(threshold) if threshold is not None else "—")
                    + "</strong></div>"
                )
            if gate.get("reason") not in (None, ""):
                lines.append(
                    "<div class='watchlist-promotion-line watchlist-promotion-reason'><span>Reason:</span> "
                    + _detail_value(gate.get("reason"))
                    + "</div>"
                )
            for evidence_label, raw in _evidence_values(gate):
                lines.append(
                    "<div class='watchlist-promotion-line watchlist-promotion-evidence'><span>"
                    + html.escape(evidence_label)
                    + ":</span> "
                    + _detail_value(raw)
                    + "</div>"
                )
        else:
            lines.append("<div class='watchlist-qa-note'>Authoritative gate evidence is unavailable.</div>")
        cards.append(
            "<article class='watchlist-promotion-gate-card'>"
            "<div class='watchlist-promotion-gate-header'>"
            f"<strong>{html.escape(label)}</strong> "
            f"<span class='watchlist-status {gate_class}'>{html.escape(status)}</span>"
            "</div>"
            f"<div class='watchlist-promotion-gate-content'>{''.join(lines)}</div>"
            "</article>"
        )
    reasons = readiness.get("blocking_reasons")
    if isinstance(reasons, list) and any(str(reason).strip() for reason in reasons):
        blocking = "<ul class='watchlist-blocking-list'>" + "".join(
            f"<li>{html.escape(str(reason))}</li>" for reason in reasons if str(reason).strip()
        ) + "</ul>"
    elif readiness.get("promotion_ready") is True:
        blocking = "<div class='watchlist-qa-note'>No blocking reasons were published.</div>"
    else:
        blocking = "<div class='watchlist-qa-note'>No authoritative blocking reasons were published.</div>"
    vehicle_label = leveraged if leveraged not in ("", "—") else "No leveraged vehicle"
    return (
        "<div class='watchlist-promotion-panel'>"
        "<div class='watchlist-promotion-panel-heading'>"
        f"<strong>Promotion Readiness — {html.escape(underlying)} ({html.escape(vehicle_label)})</strong>"
        "<span>Click any OQ, Thesis, Entry, or Promotion value to collapse.</span>"
        "</div>"
        "<div class='watchlist-promotion-section-title'>Six-gate Promotion Readiness</div>"
        "<div class='watchlist-promotion-gates-wrap'>"
        f"<div class='watchlist-promotion-gates'>{''.join(cards)}</div>"
        "</div>"
        "<div class='watchlist-promotion-blockers'><strong>Blocking reasons</strong>"
        f"{blocking}</div></div>"
    )


def _pipeline_rows(items: list[Mapping[str, Any]]) -> str:
    rows: list[str] = []
    for index, item in enumerate(items, start=1):
        lifecycle = _lifecycle(item)
        _, status_class = _status({"status": lifecycle})
        rank = _first(item, ("watchlist_rank", "rank", "candidate_rank"), "—") if lifecycle == "WATCHLIST" else "—"
        underlying = _first(item, ("underlying_symbol", "symbol", "underlying", "ticker"), "UNKNOWN")
        leveraged = _first(item, ("leveraged_symbol", "leveraged_ticker", "paired_symbol"), "—")
        theme = _first(item, ("theme", "themes", "theme_name", "sector_theme"), "—")
        raw_readiness = item.get("promotion_readiness")
        readiness = raw_readiness if isinstance(raw_readiness, Mapping) else None
        gate_readiness: Mapping[str, Any] = readiness or {}
        detail_id = f"watchlist-promotion-detail-{index}"
        rows.append(
            "<tr class='watchlist-candidate-row'>"
            f"<td class='num'>{html.escape(rank)}</td>"
            f"<td><strong>{html.escape(underlying)}</strong></td>"
            f"<td>{_pipeline_cell(leveraged)}</td>"
            f"<td><span class='watchlist-status {status_class}'>{html.escape(lifecycle)}</span></td>"
            f"<td>{_pipeline_cell(theme)}</td>"
            f"<td>{_gate_cell(gate_readiness, 'opportunity_quality', mode='oq', detail_id=detail_id)}</td>"
            f"<td>{_gate_cell(gate_readiness, 'thesis_integrity', mode='status', detail_id=detail_id)}</td>"
            f"<td>{_gate_cell(gate_readiness, 'entry', mode='entry', detail_id=detail_id)}</td>"
            f"<td>{_promotion_summary(readiness, detail_id=detail_id)}</td>"
            "</tr>"
            f"<tr id='{detail_id}' class='watchlist-promotion-detail-row' hidden><td colspan='9'>"
            f"{_promotion_detail_body(readiness, underlying=underlying, leveraged=leveraged)}"
            "</td></tr>"
        )
    return "".join(rows)


def _render_candidate_pipeline(row: Mapping[str, Any], items: list[Mapping[str, Any]]) -> str:
    count_value = _number(row.get("watchlist_count"))
    total = int(count_value) if count_value is not None else len(items)
    active = sum(_lifecycle(item) == "WATCHLIST" for item in items)
    discovery = sum(_lifecycle(item) == "DISCOVERY" for item in items)
    removed = sum(_lifecycle(item) == "REMOVED" for item in items)
    heading = (
        "<div class='watchlist-heading'><div><h3>Candidate Pipeline</h3>"
        "<p>All strategy-owned Swing candidate lifecycle records, including discovery and removed records.</p></div>"
        f"<span class='watchlist-count'>{total} records</span></div>"
    )
    summary = (
        "<div class='watchlist-summary-grid'>"
        f"<div class='watchlist-summary-card'><span>Total Candidate Records</span><strong>{total}</strong></div>"
        f"<div class='watchlist-summary-card'><span>Active Watchlist</span><strong>{active}</strong></div>"
        f"<div class='watchlist-summary-card'><span>Discovery</span><strong>{discovery}</strong></div>"
        f"<div class='watchlist-summary-card'><span>Removed</span><strong>{removed}</strong></div>"
        "</div>"
    )
    table = (
        "<div class='watchlist-table-wrap'><table class='watchlist-table candidate-pipeline-table'>"
        "<thead><tr><th>Rank</th><th>Symbol</th><th>Vehicle</th><th>Status</th><th>Theme</th>"
        "<th>OQ</th><th>Thesis</th><th>Entry</th><th>Promotion</th></tr></thead>"
        f"<tbody>{_pipeline_rows(items)}</tbody></table></div>"
    )
    behavior = """
<script>
(function(){
  const script = document.currentScript;
  const root = script ? script.closest('.candidate-pipeline') : null;
  if (!root) return;
  root.addEventListener('click', function(event){
    const toggle = event.target.closest('.watchlist-detail-toggle, .watchlist-promotion-toggle');
    if (!toggle || !root.contains(toggle)) return;
    const targetId = toggle.getAttribute('aria-controls');
    const detailRow = targetId ? document.getElementById(targetId) : null;
    if (!detailRow) return;
    const expanded = toggle.getAttribute('aria-expanded') === 'true';
    const nextExpanded = !expanded;
    root.querySelectorAll('[aria-controls="' + targetId + '"]').forEach(function(control){
      control.setAttribute('aria-expanded', nextExpanded ? 'true' : 'false');
      control.setAttribute('title', nextExpanded ? 'Hide Promotion Readiness details' : 'Show Promotion Readiness details');
    });
    detailRow.hidden = !nextExpanded;
  });
})();
</script>
"""
    return (
        "<section class='watchlist-pro candidate-pipeline'>" + heading + summary + table + behavior
        + "<p class='watchlist-footnote'>Rows are rendered from SWING-001 authoritative published evidence. "
        "The Enterprise host preserves lifecycle states and does not infer candidates from the summary count.</p></section>"
    )


def render_watchlist_panel(row: Mapping[str, Any]) -> str:
    raw = row.get("watchlist")
    items = [x for x in raw if isinstance(x, Mapping)] if isinstance(raw, list) else []
    count_value = _number(row.get("watchlist_count"))
    count = int(count_value) if count_value is not None else len(items)
    if str(row.get("strategy_id") or "").upper() == "SWING-001" and items:
        return _render_candidate_pipeline(row, items)
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
            "<section class='watchlist-pro'>" + heading + summary
            + "<div class='watchlist-empty'><strong>No active strategy watchlist candidates.</strong>"
            f"<span>{html.escape(explanation)}</span></div></section>"
        )
    table = (
        "<div class='watchlist-table-wrap'><table class='watchlist-table'>"
        "<thead><tr><th>Rank</th><th>Candidate</th><th>Entry Status</th><th>Entry Score</th><th>Confidence</th>"
        "<th>Timing</th><th>Why It Has Not Progressed</th><th>What Happens Next</th><th>Market Data</th><th>Held</th><th>Evidence As-Of</th></tr></thead>"
        f"<tbody>{_rows(items)}</tbody></table></div>"
    )
    return (
        "<section class='watchlist-pro'>" + heading + summary + table
        + "<p class='watchlist-footnote'>Entry decisions come from the current symbol-level Entry Score report. The Enterprise host explains published blockers but does not weaken qualification rules or authorize purchases.</p></section>"
    )


def watchlist_ui_css() -> str:
    return """
<style>
.watchlist-pro{color:#10213b}.watchlist-heading{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;margin-bottom:14px}.watchlist-heading h3{margin:0 0 5px;font-size:1.2rem}.watchlist-heading p{margin:0;color:#64748b}.watchlist-count{background:#eef2ff;color:#5b21b6;border:1px solid #d8ccff;border-radius:999px;padding:7px 11px;font-weight:800;white-space:nowrap}.watchlist-summary-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:16px}.watchlist-summary-card{background:linear-gradient(180deg,#fff,#f8faff);border:1px solid #dbe4f0;border-radius:12px;padding:13px 14px;box-shadow:0 5px 14px rgba(23,43,77,.06)}.watchlist-summary-card span{display:block;color:#64748b}.watchlist-summary-card strong{display:block;margin-top:5px;font-size:1.15rem}.watchlist-table-wrap{overflow-x:auto;border:1px solid #dbe4f0;border-radius:13px;background:#fff;box-shadow:0 7px 18px rgba(23,43,77,.06)}.watchlist-table{width:100%;min-width:1180px;border-collapse:collapse}.candidate-pipeline-table{min-width:0;table-layout:fixed;font-size:.84rem}.candidate-pipeline .watchlist-table-wrap{overflow-x:visible}.candidate-pipeline-table th{padding:9px 10px;font-size:.68rem}.candidate-pipeline-table td{padding:10px;overflow-wrap:anywhere}.candidate-pipeline-table th:nth-child(1),.candidate-pipeline-table td:nth-child(1){width:6%}.candidate-pipeline-table th:nth-child(2),.candidate-pipeline-table td:nth-child(2){width:8%}.candidate-pipeline-table th:nth-child(3),.candidate-pipeline-table td:nth-child(3){width:9%}.candidate-pipeline-table th:nth-child(4),.candidate-pipeline-table td:nth-child(4){width:12%}.candidate-pipeline-table th:nth-child(5),.candidate-pipeline-table td:nth-child(5){width:25%}.candidate-pipeline-table th:nth-child(6),.candidate-pipeline-table td:nth-child(6){width:11%}.candidate-pipeline-table th:nth-child(7),.candidate-pipeline-table td:nth-child(7){width:10%}.candidate-pipeline-table th:nth-child(8),.candidate-pipeline-table td:nth-child(8){width:10%}.candidate-pipeline-table th:nth-child(9),.candidate-pipeline-table td:nth-child(9){width:9%}.watchlist-table th{padding:11px 12px;text-align:left;background:#f4f7fc;color:#53627a;font-size:.72rem;text-transform:uppercase;letter-spacing:.035em;border-bottom:1px solid #dbe4f0;white-space:nowrap}.watchlist-table td{padding:12px;border-bottom:1px solid #edf1f6;vertical-align:middle;white-space:nowrap}.watchlist-table tbody tr:last-child td{border-bottom:0}.watchlist-table td.num{text-align:right;font-variant-numeric:tabular-nums}.watchlist-candidate-name{display:block;margin-top:4px;color:#64748b;white-space:normal}.watchlist-explanation{min-width:250px;max-width:360px;white-space:normal!important;line-height:1.35}.watchlist-explanation strong{color:#334155}.watchlist-status,.watchlist-not-reported{display:inline-block;border-radius:999px;padding:5px 8px;font-size:.75rem;font-weight:800}.watchlist-status-ready,.watchlist-market-fresh{background:#e9f9f0;color:#087443}.watchlist-status-watch{background:#fff7df;color:#8a4b08}.watchlist-status-blocked,.watchlist-market-stale{background:#fff0f0;color:#b42318}.watchlist-status-neutral,.watchlist-not-reported{background:#f1f5f9;color:#7a8798}.watchlist-source{color:#64748b;font-size:.82rem}.watchlist-empty{padding:24px;border:1px dashed #b9c7db;border-radius:12px;background:#f8fafc;text-align:center;color:#64748b}.watchlist-empty strong,.watchlist-empty span{display:block}.watchlist-empty strong{color:#334155;margin-bottom:7px}.watchlist-footnote{margin:12px 2px 0;color:#718096;font-size:.8rem}.watchlist-qa-details{position:relative}.watchlist-qa-details summary{cursor:pointer;list-style:none}.watchlist-qa-details summary::-webkit-details-marker{display:none}.watchlist-qa-details[open] .watchlist-qa-body{display:block}.watchlist-qa-body{min-width:260px;max-width:390px;margin-top:7px;padding:10px;border:1px solid #dbe4f0;border-radius:9px;background:#f8fafc;white-space:normal;line-height:1.35}.watchlist-qa-list{margin:0}.watchlist-qa-list div{display:grid;grid-template-columns:120px 1fr;gap:8px;padding:3px 0}.watchlist-qa-list dt{font-weight:700;color:#53627a}.watchlist-qa-list dd{margin:0;overflow-wrap:anywhere}.watchlist-qa-note{color:#64748b;white-space:normal}.watchlist-blocking-list{margin:6px 0 0;padding-left:18px}.watchlist-blocking-list li{margin:3px 0;white-space:normal}.watchlist-qa-evidence{color:#64748b;font-size:.78rem;overflow-wrap:anywhere}.watchlist-sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}.watchlist-detail-toggle,.watchlist-promotion-toggle{appearance:none;border:0;background:transparent;padding:0;margin:0;font:inherit;cursor:pointer}.watchlist-detail-toggle:focus-visible,.watchlist-promotion-toggle:focus-visible{outline:2px solid #5925dc;outline-offset:2px;border-radius:999px}.watchlist-promotion-detail-row[hidden]{display:none}.watchlist-promotion-detail-row td{padding:0!important;background:#f8fbff;white-space:normal!important;border-bottom:1px solid #dbe4f0}.watchlist-promotion-panel{margin:8px 10px 12px;padding:12px;border:1px solid #cfe0f5;border-radius:10px;background:linear-gradient(180deg,#f8fbff,#fff);box-shadow:inset 0 1px 0 #fff;font-size:.76rem}.watchlist-promotion-panel-heading{display:flex;justify-content:space-between;gap:14px;align-items:center;padding-bottom:8px;margin-bottom:8px;border-bottom:1px solid #dbe4f0}.watchlist-promotion-panel-heading>strong{font-size:.92rem;color:#10213b}.watchlist-promotion-panel-heading>span{font-size:.70rem;color:#64748b}.watchlist-promotion-section-title{font-size:.78rem;font-weight:800;color:#10213b;margin:0 0 8px}.watchlist-promotion-gates-wrap{overflow:visible}.watchlist-promotion-gates{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;width:100%;min-width:0}.watchlist-promotion-gate-card{border:1px solid #dbe4f0;border-radius:8px;background:#fff;padding:9px;min-width:0}.watchlist-promotion-gate-header{display:flex;justify-content:space-between;gap:5px;align-items:flex-start;margin-bottom:7px;background:transparent!important;color:#10213b!important;padding:0!important}.watchlist-promotion-gate-header>strong{font-size:.74rem;line-height:1.2}.watchlist-promotion-gate-card .watchlist-status{padding:3px 6px;font-size:.64rem}.watchlist-promotion-gate-content{display:grid;gap:4px;color:#334155}.watchlist-promotion-line{font-size:.69rem;line-height:1.28;white-space:normal;overflow-wrap:anywhere}.watchlist-promotion-line>span{color:#64748b;font-weight:600}.watchlist-promotion-line>strong{font-weight:600;color:#334155}.watchlist-promotion-reason,.watchlist-promotion-evidence{border-top:1px solid #edf1f6;padding-top:4px}.watchlist-promotion-blockers{margin-top:8px;padding:8px 10px;border-radius:7px;background:#fff4f2;border:1px solid #fee4e2}.watchlist-promotion-blockers>strong{color:#b42318;font-size:.72rem}main:has(.candidate-pipeline){max-width:1760px;width:100%}.portal-frame:has(.candidate-pipeline){grid-template-columns:210px minmax(0,1fr);gap:16px}.candidate-pipeline .watchlist-status{padding:4px 7px;font-size:.70rem}@media(max-width:900px){.watchlist-summary-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:520px){.watchlist-heading{display:block}.watchlist-count{display:inline-block;margin-top:10px}.watchlist-summary-grid{grid-template-columns:1fr}}
</style>
"""