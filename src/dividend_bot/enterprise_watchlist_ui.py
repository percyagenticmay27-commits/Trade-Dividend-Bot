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
        evidence = _first(item, ("entry_evidence_generated_at_utc",), "Not reported")
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
            f"<td class='watchlist-source'>{_missing(html.escape(evidence))}</td>"
            "</tr>"
        )
    return "".join(result)



def _lifecycle(item: Mapping[str, Any]) -> str:
    return _first(
        item,
        ("lifecycle_status", "lifecycle_state", "watchlist_status", "status"),
        "Not reported",
    ).upper()


def _pipeline_cell(value: Any) -> str:
    if value in (None, "", [], {}):
        return _missing("Not reported")
    if isinstance(value, bool):
        return "YES" if value else "NO"
    return html.escape(str(value))


def _pipeline_rows(items: list[Mapping[str, Any]]) -> str:
    rows: list[str] = []
    for index, item in enumerate(items, start=1):
        lifecycle = _lifecycle(item)
        _, status_class = _status({"status": lifecycle})
        rank = _first(item, ("watchlist_rank", "rank", "candidate_rank"), str(index))
        underlying = _first(
            item,
            ("underlying_symbol", "symbol", "underlying", "ticker"),
            "UNKNOWN",
        )
        leveraged = _first(
            item,
            ("leveraged_symbol", "leveraged_ticker", "paired_symbol"),
            "Not reported",
        )
        capacity = _first(
            item,
            ("capacity_status", "capacity", "allocation_capacity_status"),
            "Not reported",
        )
        composite = _score(_first(
            item,
            ("composite_score", "opportunity_quality", "opportunity_quality_score"),
            "",
        ))
        financial = _first(
            item,
            ("financial_health", "financial_health_score", "financial_status"),
            "Not reported",
        )
        theme = _first(item, ("theme", "theme_name", "sector_theme"), "Not reported")
        promotion = _first(
            item,
            ("promotion_eligible", "eligible_for_promotion", "promotion_status"),
            "Not reported",
        )
        sources = _first(
            item,
            ("source_count", "evidence_source_count", "sources_count"),
            "Not reported",
        )
        win_rate = _percent(_first(
            item,
            ("win_rate", "win_rate_percent", "win_rate_pct"),
            "",
        ))
        paper_return = _percent(_first(
            item,
            ("paper_return", "paper_return_percent", "paper_return_pct", "total_return_percent"),
            "",
        ))
        rows.append(
            "<tr>"
            f"<td class='num'>{html.escape(rank)}</td>"
            f"<td><strong>{html.escape(underlying)}</strong></td>"
            f"<td>{_pipeline_cell(leveraged)}</td>"
            f"<td><span class='watchlist-status {status_class}'>{html.escape(lifecycle)}</span></td>"
            f"<td>{_pipeline_cell(capacity)}</td>"
            f"<td class='num'>{_missing(composite)}</td>"
            f"<td>{_pipeline_cell(financial)}</td>"
            f"<td>{_pipeline_cell(theme)}</td>"
            f"<td>{_pipeline_cell(promotion)}</td>"
            f"<td class='num'>{_pipeline_cell(sources)}</td>"
            f"<td class='num'>{_missing(win_rate)}</td>"
            f"<td class='num'>{_missing(paper_return)}</td>"
            "</tr>"
        )
    return "".join(rows)


def _render_candidate_pipeline(
    row: Mapping[str, Any],
    items: list[Mapping[str, Any]],
) -> str:
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
        "<thead><tr><th>Watchlist Rank</th><th>Underlying Symbol</th><th>Leveraged Symbol</th>"
        "<th>Lifecycle Status</th><th>Capacity Status</th><th>Composite Score</th>"
        "<th>Financial Health</th><th>Theme</th><th>Promotion Eligible</th>"
        "<th>Source Count</th><th>Win Rate</th><th>Paper Return</th></tr></thead>"
        f"<tbody>{_pipeline_rows(items)}</tbody></table></div>"
    )
    return (
        "<section class='watchlist-pro candidate-pipeline'>" + heading + summary + table
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
        return (
            "<section class='watchlist-pro'>" + heading + summary +
            "<div class='watchlist-empty'><strong>No active strategy watchlist candidates.</strong>"
            f"<span>The strategy reports {count} candidate records, but no detailed strategy-owned rows are available. Candidate rows are never fabricated from the summary count.</span></div></section>"
        )
    table = (
        "<div class='watchlist-table-wrap'><table class='watchlist-table'>"
        "<thead><tr><th>Rank</th><th>Candidate</th><th>Entry Status</th><th>Entry Score</th><th>Confidence</th>"
        "<th>Timing</th><th>Why It Has Not Progressed</th><th>What Happens Next</th><th>Market Data</th><th>Held</th><th>Evidence As-Of</th></tr></thead>"
        f"<tbody>{_rows(items)}</tbody></table></div>"
    )
    return (
        "<section class='watchlist-pro'>" + heading + summary + table +
        "<p class='watchlist-footnote'>Entry decisions come from the current symbol-level Entry Score report. The Enterprise host explains published blockers but does not weaken qualification rules or authorize purchases.</p></section>"
    )


def watchlist_ui_css() -> str:
    return """
<style>
.watchlist-pro{color:#10213b}.watchlist-heading{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;margin-bottom:14px}.watchlist-heading h3{margin:0 0 5px;font-size:1.2rem}.watchlist-heading p{margin:0;color:#64748b}.watchlist-count{background:#eef2ff;color:#5b21b6;border:1px solid #d8ccff;border-radius:999px;padding:7px 11px;font-weight:800;white-space:nowrap}.watchlist-summary-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:16px}.watchlist-summary-card{background:linear-gradient(180deg,#fff,#f8faff);border:1px solid #dbe4f0;border-radius:12px;padding:13px 14px;box-shadow:0 5px 14px rgba(23,43,77,.06)}.watchlist-summary-card span{display:block;color:#64748b}.watchlist-summary-card strong{display:block;margin-top:5px;font-size:1.15rem}.watchlist-table-wrap{overflow-x:auto;border:1px solid #dbe4f0;border-radius:13px;background:#fff;box-shadow:0 7px 18px rgba(23,43,77,.06)}.watchlist-table{width:100%;min-width:1180px;border-collapse:collapse}.candidate-pipeline-table{min-width:1450px}.watchlist-table th{padding:11px 12px;text-align:left;background:#f4f7fc;color:#53627a;font-size:.72rem;text-transform:uppercase;letter-spacing:.035em;border-bottom:1px solid #dbe4f0;white-space:nowrap}.watchlist-table td{padding:12px;border-bottom:1px solid #edf1f6;vertical-align:middle;white-space:nowrap}.watchlist-table tbody tr:last-child td{border-bottom:0}.watchlist-table td.num{text-align:right;font-variant-numeric:tabular-nums}.watchlist-candidate-name{display:block;margin-top:4px;color:#64748b;white-space:normal}.watchlist-explanation{min-width:250px;max-width:360px;white-space:normal!important;line-height:1.35}.watchlist-explanation strong{color:#334155}.watchlist-status,.watchlist-not-reported{display:inline-block;border-radius:999px;padding:5px 8px;font-size:.75rem;font-weight:800}.watchlist-status-ready,.watchlist-market-fresh{background:#e9f9f0;color:#087443}.watchlist-status-watch{background:#fff7df;color:#8a4b08}.watchlist-status-blocked,.watchlist-market-stale{background:#fff0f0;color:#b42318}.watchlist-status-neutral,.watchlist-not-reported{background:#f1f5f9;color:#7a8798}.watchlist-source{color:#64748b;font-size:.82rem}.watchlist-empty{padding:24px;border:1px dashed #b9c7db;border-radius:12px;background:#f8fafc;text-align:center;color:#64748b}.watchlist-empty strong,.watchlist-empty span{display:block}.watchlist-empty strong{color:#334155;margin-bottom:7px}.watchlist-footnote{margin:12px 2px 0;color:#718096;font-size:.8rem}@media(max-width:900px){.watchlist-summary-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:520px){.watchlist-heading{display:block}.watchlist-count{display:inline-block;margin-top:10px}.watchlist-summary-grid{grid-template-columns:1fr}}
</style>
"""
