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


def _status(item: Mapping[str, Any]) -> tuple[str, str]:
    raw = _first(item, ("status", "watchlist_status", "candidate_status"), "WATCH").upper()
    if raw in {"READY", "READY_FOR_SCORING", "PROMOTED", "BUY"}:
        return raw, "watchlist-status-ready"
    if raw in {"WATCH", "MONITOR", "HOLD"}:
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
        score = _missing(_score(item.get("opportunity_quality") or item.get("opportunity_score") or item.get("score")))
        conviction = _missing(_score(item.get("conviction_score") or item.get("conviction")))
        momentum = _missing(_score(item.get("momentum_score") or item.get("momentum")))
        daily_change = _missing(_percent(item.get("daily_change_percent") or item.get("daily_change_pct")))
        market_state = "STALE" if item.get("market_data_stale") is True else "FRESH" if item.get("market_data_stale") is False else "Not reported"
        market_class = "watchlist-market-stale" if market_state == "STALE" else "watchlist-market-fresh" if market_state == "FRESH" else "watchlist-status-neutral"
        held = "YES" if item.get("currently_held") is True else "NO" if item.get("currently_held") is False else "Not reported"
        sources = item.get("sources")
        source_text = ", ".join(str(x) for x in sources) if isinstance(sources, list) and sources else _first(item, ("source",), "Not reported")
        result.append(
            "<tr>"
            f"<td class='num'>{html.escape(rank)}</td>"
            f"<td><strong>{symbol}</strong></td>"
            f"<td class='watchlist-name'>{name}</td>"
            f"<td><span class='watchlist-status {status_class}'>{html.escape(status)}</span></td>"
            f"<td class='num'>{score}</td>"
            f"<td class='num'>{conviction}</td>"
            f"<td class='num'>{momentum}</td>"
            f"<td class='num'>{daily_change}</td>"
            f"<td><span class='watchlist-status {market_class}'>{_missing(market_state)}</span></td>"
            f"<td>{_missing(held)}</td>"
            f"<td class='watchlist-source'>{_missing(source_text)}</td>"
            "</tr>"
        )
    return "".join(result)


def render_watchlist_panel(row: Mapping[str, Any]) -> str:
    raw = row.get("watchlist")
    items = [x for x in raw if isinstance(x, Mapping)] if isinstance(raw, list) else []
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
        return (
            "<section class='watchlist-pro'>" + heading + summary +
            "<div class='watchlist-empty'><strong>No active strategy watchlist candidates.</strong>"
            "<span>The strategy currently reports a watchlist count of 0. Candidates will appear here only when the strategy explicitly marks them for watchlist monitoring.</span></div></section>"
        )
    table = (
        "<div class='watchlist-table-wrap'><table class='watchlist-table'>"
        "<thead><tr><th>Rank</th><th>Symbol</th><th>Name</th><th>Status</th><th>Opportunity</th>"
        "<th>Conviction</th><th>Momentum</th><th>Daily Change</th><th>Market Data</th><th>Held</th><th>Evidence</th></tr></thead>"
        f"<tbody>{_rows(items)}</tbody></table></div>"
    )
    return (
        "<section class='watchlist-pro'>" + heading + summary + table +
        "<p class='watchlist-footnote'>Read-only strategy evidence. Missing scores remain Not reported; the Enterprise host does not promote or remove candidates.</p></section>"
    )


def watchlist_ui_css() -> str:
    return """
<style>
.watchlist-pro{color:#10213b}.watchlist-heading{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;margin-bottom:14px}.watchlist-heading h3{margin:0 0 5px;font-size:1.2rem}.watchlist-heading p{margin:0;color:#64748b}.watchlist-count{background:#eef2ff;color:#5b21b6;border:1px solid #d8ccff;border-radius:999px;padding:7px 11px;font-weight:800;white-space:nowrap}.watchlist-summary-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:16px}.watchlist-summary-card{background:linear-gradient(180deg,#fff,#f8faff);border:1px solid #dbe4f0;border-radius:12px;padding:13px 14px;box-shadow:0 5px 14px rgba(23,43,77,.06)}.watchlist-summary-card span{display:block;color:#64748b}.watchlist-summary-card strong{display:block;margin-top:5px;font-size:1.15rem}.watchlist-table-wrap{overflow-x:auto;border:1px solid #dbe4f0;border-radius:13px;background:#fff;box-shadow:0 7px 18px rgba(23,43,77,.06)}.watchlist-table{width:100%;min-width:1180px;border-collapse:collapse}.watchlist-table th{padding:11px 12px;text-align:left;background:#f4f7fc;color:#53627a;font-size:.72rem;text-transform:uppercase;letter-spacing:.035em;border-bottom:1px solid #dbe4f0;white-space:nowrap}.watchlist-table td{padding:12px;border-bottom:1px solid #edf1f6;vertical-align:middle;white-space:nowrap}.watchlist-table tbody tr:last-child td{border-bottom:0}.watchlist-table td.num{text-align:right;font-variant-numeric:tabular-nums}.watchlist-name{min-width:180px;max-width:220px;white-space:normal!important}.watchlist-status,.watchlist-not-reported{display:inline-block;border-radius:999px;padding:5px 8px;font-size:.75rem;font-weight:800}.watchlist-status-ready,.watchlist-market-fresh{background:#e9f9f0;color:#087443}.watchlist-status-watch{background:#fff7df;color:#8a4b08}.watchlist-status-blocked,.watchlist-market-stale{background:#fff0f0;color:#b42318}.watchlist-status-neutral,.watchlist-not-reported{background:#f1f5f9;color:#7a8798}.watchlist-source{color:#64748b;font-size:.82rem}.watchlist-empty{padding:24px;border:1px dashed #b9c7db;border-radius:12px;background:#f8fafc;text-align:center;color:#64748b}.watchlist-empty strong,.watchlist-empty span{display:block}.watchlist-empty strong{color:#334155;margin-bottom:7px}.watchlist-footnote{margin:12px 2px 0;color:#718096;font-size:.8rem}@media(max-width:900px){.watchlist-summary-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:520px){.watchlist-heading{display:block}.watchlist-count{display:inline-block;margin-top:10px}.watchlist-summary-grid{grid-template-columns:1fr}}
</style>
"""
