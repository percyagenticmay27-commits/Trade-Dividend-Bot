"""Dividend-owned strategy assignment and shadow research UI.

Presentation only. This module cannot modify strategy assignments,
promote strategies, move capital, place orders, or enable live trading.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Mapping


DEFAULT_ASSIGNMENTS = Path("state/dividend_pair_strategy_assignments.json")
DEFAULT_PERFORMANCE = Path("results/dividend_strategy_shadow_performance.json")
DEFAULT_REQUESTS = Path("state/dividend_strategy_promotion_requests.json")
DEFAULT_VISIBLE_PAIR_LIMIT = 5


def _read(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    if value in (None, ""):
        value = "—"
    return html.escape(str(value))


def _money(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "—"


def _pct(value: Any) -> str:
    try:
        return f"{float(value):+.2f}%"
    except (TypeError, ValueError):
        return "—"


def _pair_search_terms(pair: str) -> str:
    parts = [part.strip() for part in pair.replace("/", " ").split() if part.strip()]
    return " ".join([pair, *parts]).lower()


def render_dividend_strategy_assignments(
    root: str | Path = ".",
) -> str:
    """Render one searchable Dividend primary/shadow assignment table."""
    root = Path(root)

    assignments_doc = _read(root / DEFAULT_ASSIGNMENTS)
    performance_doc = _read(root / DEFAULT_PERFORMANCE)
    requests_doc = _read(root / DEFAULT_REQUESTS)

    assignments = assignments_doc.get("assignments", {})
    performance = performance_doc.get("performance") or performance_doc.get("rows") or []
    requests = requests_doc.get("requests", [])

    if not isinstance(assignments, Mapping):
        assignments = {}
    if not isinstance(performance, list):
        performance = []
    if not isinstance(requests, list):
        requests = []

    by_pair: dict[str, list[Mapping[str, Any]]] = {}
    for row in performance:
        if isinstance(row, Mapping):
            pair = str(row.get("pair") or "")
            if pair:
                by_pair.setdefault(pair, []).append(row)

    pending_by_pair = {
        str(row.get("pair") or ""): row
        for row in requests
        if isinstance(row, Mapping)
        and str(row.get("status") or "").upper() == "PENDING_OWNER_REVIEW"
    }

    rows: list[str] = []
    pair_names: list[str] = []

    for pair_index, (pair, raw_assignment) in enumerate(sorted(assignments.items())):
        if not isinstance(raw_assignment, Mapping):
            continue

        assignment = dict(raw_assignment)
        primary = str(assignment.get("primary_strategy") or "Not reported")
        shadows = [
            str(value)
            for value in assignment.get("shadow_strategies", [])
            if value
        ]
        pair_names.append(str(pair))

        pending = pending_by_pair.get(str(pair))
        if pending:
            promotion_label = "PENDING REVIEW"
            promotion_detail = (
                f"{_text(pending.get('proposed_primary_strategy'))} challenging "
                f"{_text(pending.get('current_primary_strategy'))}; veto deadline "
                f"{_text(pending.get('veto_deadline'))}"
            )
            promotion_class = "pending"
        else:
            promotion_label = "NO REVIEW"
            promotion_detail = "No promotion review pending"
            promotion_class = "clear"

        result_rows = by_pair.get(str(pair), [])
        if not result_rows:
            result_rows = [
                {
                    "strategy_id": primary,
                    "display_name": primary,
                }
            ]

        for result in result_rows:
            strategy_id = str(result.get("strategy_id") or "Not reported")
            role = "PRIMARY" if strategy_id == primary else "SHADOW"
            role_class = "primary" if role == "PRIMARY" else "shadow"
            search_terms = " ".join(
                [
                    _pair_search_terms(str(pair)),
                    strategy_id.lower(),
                    str(result.get("display_name") or "").lower(),
                    primary.lower(),
                    " ".join(shadows).lower(),
                ]
            )

            rows.append(
                "<tr class='dividend-assignment-row' "
                f"data-pair-index='{pair_index}' "
                f"data-pair='{html.escape(str(pair), quote=True)}' "
                f"data-search='{html.escape(search_terms, quote=True)}'>"
                f"<td class='pair-cell'><strong>{_text(pair)}</strong>"
                "<span class='paper-lock compact'>PAPER ONLY</span>"
                f"<small>Primary: {_text(primary)}</small></td>"
                f"<td><strong>{_text(strategy_id)}</strong>"
                f"<small>{_text(result.get('display_name'))}</small></td>"
                f"<td><span class='dividend-assignment-role {role_class}'>{role}</span></td>"
                f"<td>{_money(result.get('virtual_capital_basis'))}</td>"
                f"<td>{_money(result.get('current_shadow_value'))}</td>"
                f"<td>{_pct(result.get('total_return_percent'))}</td>"
                f"<td>{_money(result.get('virtual_gain_loss'))}</td>"
                f"<td>{_pct(result.get('max_drawdown_percent'))}</td>"
                f"<td>{_text(result.get('completed_trade_count'))}</td>"
                f"<td>{_text(result.get('observation_count'))}</td>"
                f"<td>{_text(result.get('last_action'))}</td>"
                f"<td><span class='promotion-chip {promotion_class}'>{promotion_label}</span>"
                f"<small>{promotion_detail}</small></td>"
                "</tr>"
            )

    if rows:
        table = (
            "<div class='dividend-assignment-controls'>"
            "<label><span>Search symbol, pair, or strategy</span>"
            "<input type='search' class='dividend-assignment-search' "
            "placeholder='AMD, AMDW, AMDL, STRATEGY_C' autocomplete='off'></label>"
            "<div class='dividend-assignment-control-actions'>"
            "<button type='button' class='secondary-action dividend-assignment-clear'>Clear</button>"
            "<button type='button' class='secondary-action dividend-assignment-show-all'>Show all pairs</button>"
            "</div></div>"
            f"<p class='dividend-assignment-summary'>Showing the first {DEFAULT_VISIBLE_PAIR_LIMIT} pairs until you search or choose Show all pairs.</p>"
            "<div class='dividend-assignment-table-wrap'>"
            "<table class='dividend-assignment-table'>"
            "<thead><tr>"
            "<th>Pair</th><th>Strategy</th><th>Assignment</th><th>Capital Basis</th>"
            "<th>Current Value</th><th>Return</th><th>Gain / Loss</th><th>Max Drawdown</th>"
            "<th>Closed Trades</th><th>Observations</th><th>Last Action</th><th>Promotion</th>"
            "</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            "</table>"
            "<div class='dividend-assignment-empty-filter' hidden>No matching pair or strategy.</div>"
            "</div>"
        )
    else:
        table = (
            "<div class='data-availability data-availability-pending'>"
            "<strong>No Dividend strategy assignments available</strong>"
            "<span>The pair assignment artifact has not been published yet.</span>"
            "</div>"
        )

    return (
        "<section class='dividend-strategy-assignments' data-dividend-assignment-search-root>"
        "<div class='dividend-assignment-intro'>"
        "<h3>Dividend Strategy Assignments</h3>"
        "<p>Search by symbol, pair, or strategy to compare the active Primary strategy with isolated Shadow challengers. "
        "Shadow research cannot move capital, create paper positions, or place orders.</p>"
        "</div>"
        f"{table}"
        "<script>"
        "(() => {"
        "const root=document.currentScript&&document.currentScript.closest('[data-dividend-assignment-search-root]');"
        "if(!root)return;"
        "const search=root.querySelector('.dividend-assignment-search');"
        "const clear=root.querySelector('.dividend-assignment-clear');"
        "const showAllButton=root.querySelector('.dividend-assignment-show-all');"
        "const summary=root.querySelector('.dividend-assignment-summary');"
        "const empty=root.querySelector('.dividend-assignment-empty-filter');"
        "const rows=[...root.querySelectorAll('.dividend-assignment-row')];"
        f"const pairLimit={DEFAULT_VISIBLE_PAIR_LIMIT};"
        "let showAll=false;"
        "const apply=()=>{"
        "const query=(search&&search.value||'').trim().toLowerCase();"
        "let visible=0;"
        "rows.forEach(row=>{"
        "const pairIndex=Number(row.dataset.pairIndex||0);"
        "const matches=!query||(row.dataset.search||'').includes(query);"
        "const withinDefault=showAll||query||pairIndex<pairLimit;"
        "const display=matches&&withinDefault;"
        "row.hidden=!display;if(display)visible+=1;"
        "});"
        "if(empty)empty.hidden=visible!==0;"
        "if(summary){"
        "if(query)summary.textContent=visible+' matching strategy row'+(visible===1?'':'s')+' for “'+search.value.trim()+'”.';"
        "else if(showAll)summary.textContent='Showing all assignment pairs.';"
        f"else summary.textContent='Showing the first {DEFAULT_VISIBLE_PAIR_LIMIT} pairs. Search for a symbol or choose Show all pairs.';"
        "}"
        "if(showAllButton)showAllButton.textContent=showAll&&!query?'Show first 5 pairs':'Show all pairs';"
        "};"
        "if(search)search.addEventListener('input',apply);"
        "if(clear)clear.addEventListener('click',()=>{if(search)search.value='';showAll=false;apply();if(search)search.focus();});"
        "if(showAllButton)showAllButton.addEventListener('click',()=>{showAll=!showAll;apply();});"
        "apply();"
        "})();"
        "</script>"
        "</section>"
    )


def dividend_strategy_assignments_css() -> str:
    return """
<style>
.dividend-strategy-assignments{display:grid;gap:16px;min-width:0}
.dividend-assignment-intro p{margin-top:4px;color:#64748b}
.dividend-assignment-controls{display:flex;gap:12px;align-items:end;justify-content:space-between;flex-wrap:wrap;padding:14px;border:1px solid #dbe3ef;border-radius:12px;background:#f8fafc}
.dividend-assignment-controls label{display:grid;gap:6px;min-width:min(100%,360px);flex:1}
.dividend-assignment-controls label>span{font-weight:800;color:#344054}
.dividend-assignment-search{width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid #cbd5e1;border-radius:9px;background:#fff}
.dividend-assignment-control-actions{display:flex;gap:8px;flex-wrap:wrap}
.dividend-assignment-summary{margin:0;color:#64748b;font-size:.86rem}
.dividend-assignment-table-wrap{width:100%;max-width:100%;overflow-x:auto;overflow-y:hidden;-webkit-overflow-scrolling:touch;padding-bottom:6px;border:1px solid #dbe3ef;border-radius:12px;background:#fff}
.dividend-assignment-table{width:max-content;min-width:1380px;border-collapse:collapse;table-layout:auto}
.dividend-assignment-table th,.dividend-assignment-table td{padding:10px 12px;border-bottom:1px solid #e5e7eb;text-align:left;white-space:nowrap;font-size:.86rem;line-height:1.35;vertical-align:top}
.dividend-assignment-table th{font-size:.72rem;text-transform:uppercase;color:#64748b;background:#f8fafc;position:sticky;top:0;z-index:1}
.dividend-assignment-table td small{display:block;margin-top:3px;color:#64748b;font-size:.76rem}
.dividend-assignment-table .pair-cell{min-width:180px}
.dividend-assignment-table th:nth-child(2),.dividend-assignment-table td:nth-child(2){min-width:130px}
.dividend-assignment-table th:nth-child(3),.dividend-assignment-table td:nth-child(3){min-width:100px}
.dividend-assignment-table th:nth-child(4),.dividend-assignment-table td:nth-child(4),.dividend-assignment-table th:nth-child(5),.dividend-assignment-table td:nth-child(5){min-width:105px}
.dividend-assignment-table th:nth-child(6),.dividend-assignment-table td:nth-child(6),.dividend-assignment-table th:nth-child(7),.dividend-assignment-table td:nth-child(7),.dividend-assignment-table th:nth-child(8),.dividend-assignment-table td:nth-child(8){min-width:95px}
.dividend-assignment-table th:nth-child(9),.dividend-assignment-table td:nth-child(9),.dividend-assignment-table th:nth-child(10),.dividend-assignment-table td:nth-child(10){min-width:95px}
.dividend-assignment-table th:nth-child(11),.dividend-assignment-table td:nth-child(11){min-width:120px}
.dividend-assignment-table th:nth-child(12),.dividend-assignment-table td:nth-child(12){min-width:190px}
.paper-lock{display:inline-block;font-size:.72rem;font-weight:800;padding:5px 8px;border-radius:999px;background:#dcfce7;color:#166534;white-space:nowrap}
.paper-lock.compact{font-size:.64rem;padding:3px 6px;margin-left:7px;vertical-align:1px}
.dividend-assignment-role{display:inline-block;padding:4px 7px;border-radius:999px;font-size:.72rem;font-weight:800}
.dividend-assignment-role.primary{background:#dbeafe;color:#1d4ed8}
.dividend-assignment-role.shadow{background:#f3e8ff;color:#7e22ce}
.promotion-chip{display:inline-block;padding:4px 7px;border-radius:999px;font-size:.68rem;font-weight:800}
.promotion-chip.clear{background:#f1f5f9;color:#475569}
.promotion-chip.pending{background:#fff7ed;color:#9a3412}
.dividend-assignment-empty-filter{padding:24px;text-align:center;color:#64748b}
.dividend-assignment-row[hidden]{display:none}
@media(max-width:700px){.dividend-assignment-controls{align-items:stretch}.dividend-assignment-control-actions{width:100%}.dividend-assignment-control-actions button{flex:1}.dividend-assignment-table{min-width:1280px}}
</style>
"""
