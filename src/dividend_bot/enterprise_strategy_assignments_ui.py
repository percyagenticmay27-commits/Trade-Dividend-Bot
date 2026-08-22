"""Render SWING-001 Direct/Shadow strategy assignments and user-only promotion controls."""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Mapping

REPORT_PATH = Path("results/strategy_assignment_shadow_report.json")


def load_strategy_assignment_report(row: Mapping[str, Any]) -> Mapping[str, Any] | None:
    if str(row.get("strategy_id") or "").upper() != "SWING-001":
        return None
    root_raw = row.get("evidence_root")
    if not isinstance(root_raw, str) or not root_raw.strip():
        return None
    root = Path(root_raw).resolve(strict=False)
    path = (root / REPORT_PATH).resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError:
        return None
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, Mapping):
        return None
    if payload.get("strategy_id") != "SWING-001" or payload.get("paper_trade_mode") is not True:
        return None
    return payload


def _money(value: Any) -> str:
    return "—" if not isinstance(value, (int, float)) else f"${float(value):,.2f}"


def _metric(value: Any, suffix: str = "") -> str:
    if value is None:
        return "—"
    return html.escape(f"{value}{suffix}")


def render_strategy_assignments_panel(row: Mapping[str, Any]) -> str:
    report = load_strategy_assignment_report(row)
    if report is None:
        return (
            "<section class='strategy-assignments-panel'><h3>Strategy Assignments</h3>"
            "<div class='data-availability data-availability-pending'><strong>Assignment report pending</strong>"
            "<span>Generate the Swing strategy assignment/shadow report to populate this tab.</span></div></section>"
        )

    rows = report.get("rows") if isinstance(report.get("rows"), list) else []
    blocks: list[str] = []
    for item in rows:
        if not isinstance(item, Mapping):
            continue
        symbol = str(item.get("underlying_symbol") or "")
        direct_id = str(item.get("direct_strategy_id") or "None assigned")
        direct_name = str(item.get("direct_strategy_name") or "")
        allocation = _money(item.get("current_swing_allocation"))
        shadows = item.get("shadow_strategies") if isinstance(item.get("shadow_strategies"), list) else []
        shadow_rows: list[str] = []
        for shadow in shadows:
            if not isinstance(shadow, Mapping):
                continue
            sid = str(shadow.get("strategy_id") or "")
            sname = str(shadow.get("strategy_name") or sid)
            recommended = shadow.get("promotion_recommended") is True
            recommendation = (
                "<span class='promotion-recommended'>PROMOTION RECOMMENDED</span>"
                if recommended else "<span class='research-only'>SHADOW RESEARCH</span>"
            )
            shadow_rows.append(
                "<tr>"
                f"<td><strong>{html.escape(sname)}</strong><small>{html.escape(sid)}</small></td>"
                f"<td>{html.escape(str(shadow.get('timeframe') or '—'))}</td>"
                f"<td>{_money(shadow.get('simulated_allocation'))}</td>"
                f"<td>{_metric(shadow.get('trade_count'))}</td>"
                f"<td>{_metric(shadow.get('win_rate'), '%')}</td>"
                f"<td>{_money(shadow.get('net_pl'))}</td>"
                f"<td>{_money(shadow.get('max_drawdown'))}</td>"
                f"<td>{_metric(shadow.get('profit_factor'))}</td>"
                f"<td>{recommendation}</td>"
                "<td>"
                "<form method='post' action='/strategy/shadow-promote' class='shadow-promotion-form'>"
                f"<input type='hidden' name='underlying_symbol' value='{html.escape(symbol, quote=True)}'>"
                f"<input type='hidden' name='strategy_id' value='{html.escape(sid, quote=True)}'>"
                "<label class='promotion-confirm'><input type='checkbox' name='user_confirmed' value='yes' required> Confirm</label>"
                "<button type='submit' class='promote-strategy-button'>Promote</button>"
                "</form></td></tr>"
            )
        shadows_html = "".join(shadow_rows) or "<tr><td colspan='10'>No Shadow strategies assigned to this symbol.</td></tr>"
        blocks.append(
            "<article class='strategy-assignment-card'>"
            f"<header><div><h4>{html.escape(symbol)}</h4><p>Current Swing allocation: <strong>{allocation}</strong></p></div>"
            f"<div class='direct-strategy'><span>DIRECT</span><strong>{html.escape(direct_name or direct_id)}</strong><small>{html.escape(direct_id if direct_name else '')}</small></div></header>"
            "<div class='shadow-explanation'>Shadow strategies use the same current Swing allocation only as simulated research capital. They do not reserve capital, move SGOV, create positions, or replace the Direct strategy automatically.</div>"
            "<div class='assignment-table-wrap'><table><thead><tr>"
            "<th>Shadow Strategy</th><th>Timeframe</th><th>Sim Allocation</th><th>Trades</th><th>Win Rate</th><th>Net P/L</th><th>Max DD</th><th>PF</th><th>Status</th><th>User Action</th>"
            f"</tr></thead><tbody>{shadows_html}</tbody></table></div></article>"
        )

    content = "".join(blocks) or "<p>No Direct or Shadow assignments have been created yet.</p>"
    return (
        "<section class='strategy-assignments-panel'><header class='assignments-heading'>"
        "<div><h3>Strategy Assignments</h3><p>See the active Direct strategy and every background Shadow challenger for each underlying.</p></div>"
        "<span class='user-promotion-badge'>USER PROMOTION ONLY</span></header>"
        "<div class='promotion-policy'><strong>No automatic replacement:</strong> performance evidence may recommend promotion, but only the Promote control on this tab can change a symbol's Direct strategy. The previous Direct is retained as Shadow.</div>"
        f"{content}</section>"
    )


def strategy_assignments_ui_css() -> str:
    return """
<style>
.assignments-heading{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.user-promotion-badge{padding:6px 10px;border-radius:999px;background:#fff4e5;color:#b54708;font-size:11px;font-weight:900;white-space:nowrap}.promotion-policy,.shadow-explanation{padding:11px 13px;border-radius:10px;margin:12px 0;background:#f8fafc;border:1px solid #e2e8f0;color:#475569}.strategy-assignment-card{border:1px solid #dbe3ef;border-radius:12px;margin:14px 0;overflow:hidden}.strategy-assignment-card>header{display:flex;justify-content:space-between;gap:15px;padding:14px;background:#f8fafc}.strategy-assignment-card h4{margin:0 0 4px}.direct-strategy{display:grid;justify-items:end}.direct-strategy span{font-size:10px;font-weight:900;color:#067647}.assignment-table-wrap{overflow-x:auto}.assignment-table-wrap table{width:100%;min-width:1100px;border-collapse:collapse}.assignment-table-wrap th,.assignment-table-wrap td{padding:9px;border-bottom:1px solid #e5e7eb;text-align:left;font-size:12px}.assignment-table-wrap small{display:block;color:#64748b}.promotion-recommended{display:inline-block;padding:4px 7px;border-radius:999px;background:#ecfdf3;color:#067647;font-size:10px;font-weight:900}.research-only{display:inline-block;padding:4px 7px;border-radius:999px;background:#eef2f6;color:#475467;font-size:10px;font-weight:900}.shadow-promotion-form{display:grid;gap:6px}.promotion-confirm{display:flex!important;grid-template-columns:auto 1fr!important;gap:5px!important;align-items:center!important;font-size:11px}.promotion-confirm input{width:auto!important}.promote-strategy-button{border:0;border-radius:8px;padding:7px 10px;background:#b54708;color:#fff;font-weight:800}.workspace-tab[data-workspace-tab-target='strategy-assignments'].active{background:#b54708}
@media(max-width:700px){.assignments-heading,.strategy-assignment-card>header{display:block}.direct-strategy{justify-items:start;margin-top:8px}}
</style>"""
