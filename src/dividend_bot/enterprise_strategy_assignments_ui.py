"""Render SWING-001 Primary/Shadow assignments from its registered artifact.

Read-only presentation only. The Enterprise host resolves the authoritative
Swing ``strategy_assignments`` artifact through Registry v2 metadata and never
rebuilds the frozen assignment registry from allocation, holdings, or legacy
shadow-report evidence.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Mapping

ASSIGNMENT_ARTIFACT_ID = "strategy_assignments"
ASSIGNMENT_ARTIFACT_TYPE = "strategy_assignments"
MAX_SHADOWS = 4


def _assignment_artifact(row: Mapping[str, Any]) -> tuple[Mapping[str, Any] | None, str]:
    """Return the single registered Swing assignment declaration or a reason."""
    if str(row.get("strategy_id") or "").upper() != "SWING-001":
        return None, "NOT_SWING_STRATEGY"

    declarations = row.get("published_artifacts")
    if not isinstance(declarations, list):
        return None, "ASSIGNMENT_ARTIFACT_NOT_DECLARED"

    matches = [
        item
        for item in declarations
        if isinstance(item, Mapping)
        and str(item.get("artifact_id") or "").strip().lower() == ASSIGNMENT_ARTIFACT_ID
        and str(item.get("artifact_type") or "").strip().lower() == ASSIGNMENT_ARTIFACT_TYPE
    ]
    if len(matches) != 1:
        return None, (
            "ASSIGNMENT_ARTIFACT_NOT_DECLARED"
            if not matches
            else "ASSIGNMENT_ARTIFACT_AMBIGUOUS"
        )
    return matches[0], "AVAILABLE"


def load_strategy_assignment_report(row: Mapping[str, Any]) -> tuple[Mapping[str, Any] | None, str]:
    """Load only the registered authoritative Swing strategy assignment artifact."""
    declaration, status = _assignment_artifact(row)
    if declaration is None:
        return None, status

    root_raw = row.get("evidence_root")
    if not isinstance(root_raw, str) or not root_raw.strip():
        return None, "EVIDENCE_ROOT_UNAVAILABLE"
    root = Path(root_raw).resolve(strict=False)

    raw_path = declaration.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None, "ASSIGNMENT_ARTIFACT_PATH_INVALID"
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    path = candidate.resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError:
        return None, "ASSIGNMENT_ARTIFACT_PATH_OUTSIDE_ROOT"

    if not path.is_file():
        return None, "ASSIGNMENT_ARTIFACT_MISSING"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, "ASSIGNMENT_ARTIFACT_UNREADABLE"

    if not isinstance(payload, Mapping):
        return None, "ASSIGNMENT_ARTIFACT_INVALID"
    if str(payload.get("strategy_id") or "").upper() != "SWING-001":
        return None, "ASSIGNMENT_ARTIFACT_STRATEGY_MISMATCH"
    if payload.get("paper_trade_mode") is not True:
        return None, "ASSIGNMENT_ARTIFACT_NOT_PAPER_ONLY"

    symbols = payload.get("symbols")
    strategies = payload.get("strategies")
    if not isinstance(symbols, list) or not isinstance(strategies, list):
        return None, "ASSIGNMENT_ARTIFACT_SCHEMA_INVALID"

    for stack in symbols:
        if not isinstance(stack, Mapping):
            return None, "ASSIGNMENT_ARTIFACT_SCHEMA_INVALID"
        shadows = stack.get("shadow_strategy_ids")
        if not isinstance(shadows, list):
            return None, "ASSIGNMENT_ARTIFACT_SCHEMA_INVALID"
        if len(shadows) > MAX_SHADOWS:
            return None, "SHADOW_GOVERNANCE_LIMIT_EXCEEDED"

    return payload, "AVAILABLE"


def _money(value: Any) -> str:
    return "—" if not isinstance(value, (int, float)) else f"${float(value):,.2f}"


def _metric(value: Any, suffix: str = "") -> str:
    if value in (None, ""):
        return "—"
    return html.escape(f"{value}{suffix}")


def _strategy_index(report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    strategies = report.get("strategies")
    if not isinstance(strategies, list):
        return {}
    return {
        str(item.get("strategy_id") or ""): item
        for item in strategies
        if isinstance(item, Mapping) and str(item.get("strategy_id") or "")
    }


def _strategy_row(
    *,
    symbol: str,
    strategy_id: str,
    role: str,
    metadata: Mapping[str, Any] | None,
) -> str:
    item = metadata or {}
    checkpoint = item.get("frozen_checkpoint") if isinstance(item.get("frozen_checkpoint"), Mapping) else {}
    name = str(item.get("name") or strategy_id)
    assignment_mode = str(item.get("assignment_mode") or role)
    role_class = "primary" if role == "PRIMARY" else "shadow"

    action = ""
    if role == "SHADOW":
        action = (
            "<form method='post' action='/strategy/shadow-promote' class='shadow-promotion-form'>"
            f"<input type='hidden' name='underlying_symbol' value='{html.escape(symbol, quote=True)}'>"
            f"<input type='hidden' name='strategy_id' value='{html.escape(strategy_id, quote=True)}'>"
            "<label class='promotion-confirm'><input type='checkbox' name='user_confirmed' value='yes' required> Confirm</label>"
            "<button type='submit' class='promote-strategy-button'>Promote</button>"
            "</form>"
        )

    return (
        "<tr>"
        f"<td><span class='assignment-role {role_class}'>{html.escape(role)}</span></td>"
        f"<td><strong>{html.escape(name)}</strong><small>{html.escape(strategy_id)}</small></td>"
        f"<td>{html.escape(str(item.get('signal_symbol') or '—'))}</td>"
        f"<td>{html.escape(str(item.get('vehicle_symbol') or symbol or '—'))}</td>"
        f"<td>{html.escape(str(item.get('timeframe') or '—'))}</td>"
        f"<td>{html.escape(str(item.get('engine_id') or '—'))}</td>"
        f"<td>{html.escape(assignment_mode)}</td>"
        f"<td>{_metric(checkpoint.get('trade_count'))}</td>"
        f"<td>{_metric(checkpoint.get('win_rate_percent'), '%')}</td>"
        f"<td>{_money(checkpoint.get('net_pl_dollars'))}</td>"
        f"<td>{_metric(checkpoint.get('profit_factor'))}</td>"
        f"<td>{_money(checkpoint.get('max_drawdown_dollars'))}</td>"
        f"<td>{html.escape(str(checkpoint.get('backtest_period') or '—'))}</td>"
        f"<td>{action}</td>"
        "</tr>"
    )


def render_strategy_assignments_panel(row: Mapping[str, Any]) -> str:
    report, status = load_strategy_assignment_report(row)
    if report is None:
        return (
            "<section class='strategy-assignments-panel'><header class='assignments-heading'>"
            "<div><h3>Strategy Assignments</h3><p>Authoritative Swing assignment evidence is unavailable.</p></div>"
            "<span class='user-promotion-badge'>USER PROMOTION ONLY</span></header>"
            "<div class='data-availability data-availability-pending'>"
            "<strong>Strategy assignment evidence unavailable</strong>"
            f"<span>Status: {html.escape(status)}. The Enterprise AI CIO does not fall back to legacy assignment, allocation, or holdings data.</span>"
            "</div></section>"
        )

    symbols = report.get("symbols") if isinstance(report.get("symbols"), list) else []
    index = _strategy_index(report)
    blocks: list[str] = []

    for stack in symbols:
        if not isinstance(stack, Mapping):
            continue
        symbol = str(stack.get("symbol") or "")
        primary_id = str(stack.get("primary_strategy_id") or "")
        shadow_ids = [str(value) for value in stack.get("shadow_strategy_ids", [])]
        research_status = str(stack.get("research_status") or "")

        strategy_rows = [
            _strategy_row(
                symbol=symbol,
                strategy_id=primary_id,
                role="PRIMARY",
                metadata=index.get(primary_id),
            )
        ] if primary_id else []
        strategy_rows.extend(
            _strategy_row(
                symbol=symbol,
                strategy_id=strategy_id,
                role="SHADOW",
                metadata=index.get(strategy_id),
            )
            for strategy_id in shadow_ids
        )

        blocks.append(
            "<article class='strategy-assignment-card'>"
            "<header><div>"
            f"<h4>{html.escape(symbol)}</h4>"
            f"<p>{html.escape(research_status or 'Published frozen strategy stack')}</p>"
            "</div>"
            f"<div class='direct-strategy'><span>PRIMARY</span><strong>{html.escape(primary_id or 'None assigned')}</strong>"
            f"<small>{len(shadow_ids)} Shadow{'s' if len(shadow_ids) != 1 else ''}</small></div></header>"
            "<div class='shadow-explanation'>Assignment truth comes from Swing's registered authoritative strategy_assignments artifact. Allocation and holdings are not used to determine this stack. Shadow strategies remain simulated research challengers.</div>"
            "<div class='assignment-table-wrap'><table><thead><tr>"
            "<th>Role</th><th>Strategy</th><th>Signal</th><th>Vehicle</th><th>Timeframe</th><th>Engine</th><th>Mode</th><th>Trades</th><th>Win Rate</th><th>Net P/L</th><th>PF</th><th>Max DD</th><th>Backtest</th><th>User Action</th>"
            f"</tr></thead><tbody>{''.join(strategy_rows)}</tbody></table></div>"
            "</article>"
        )

    content = "".join(blocks)
    if not content:
        content = (
            "<div class='data-availability data-availability-ready'>"
            "<strong>Published assignment registry is empty</strong>"
            "<span>The authoritative artifact was loaded successfully and currently publishes zero symbol stacks.</span>"
            "</div>"
        )

    return (
        "<section class='strategy-assignments-panel'><header class='assignments-heading'>"
        "<div><h3>Strategy Assignments</h3><p>See every authoritative frozen Primary strategy and background Shadow challenger published by SWING-001.</p></div>"
        "<span class='user-promotion-badge'>USER PROMOTION ONLY</span></header>"
        "<div class='promotion-policy'><strong>No automatic replacement:</strong> this read-only consumer does not change assignments. Promotion remains governed by the existing explicit user promotion workflow.</div>"
        f"{content}</section>"
    )


def strategy_assignments_ui_css() -> str:
    return """
<style>
.assignments-heading{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.user-promotion-badge{padding:6px 10px;border-radius:999px;background:#fff4e5;color:#b54708;font-size:11px;font-weight:900;white-space:nowrap}.promotion-policy,.shadow-explanation{padding:11px 13px;border-radius:10px;margin:12px 0;background:#f8fafc;border:1px solid #e2e8f0;color:#475569}.strategy-assignment-card{border:1px solid #dbe3ef;border-radius:12px;margin:14px 0;overflow:hidden}.strategy-assignment-card>header{display:flex;justify-content:space-between;gap:15px;padding:14px;background:#f8fafc}.strategy-assignment-card h4{margin:0 0 4px}.direct-strategy{display:grid;justify-items:end}.direct-strategy span{font-size:10px;font-weight:900;color:#067647}.assignment-table-wrap{overflow-x:auto}.assignment-table-wrap table{width:100%;min-width:1500px;border-collapse:collapse}.assignment-table-wrap th,.assignment-table-wrap td{padding:9px;border-bottom:1px solid #e5e7eb;text-align:left;font-size:12px;white-space:nowrap}.assignment-table-wrap small{display:block;color:#64748b;margin-top:2px}.assignment-role{display:inline-block;padding:4px 7px;border-radius:999px;font-size:10px;font-weight:900}.assignment-role.primary{background:#dbeafe;color:#1d4ed8}.assignment-role.shadow{background:#f3e8ff;color:#7e22ce}.shadow-promotion-form{display:grid;gap:6px}.promotion-confirm{display:flex!important;grid-template-columns:auto 1fr!important;gap:5px!important;align-items:center!important;font-size:11px}.promotion-confirm input{width:auto!important}.promote-strategy-button{border:0;border-radius:8px;padding:7px 10px;background:#b54708;color:#fff;font-weight:800}.workspace-tab[data-workspace-tab-target='strategy-assignments'].active{background:#b54708}
@media(max-width:700px){.assignments-heading,.strategy-assignment-card>header{display:block}.direct-strategy{justify-items:start;margin-top:8px}}
</style>"""
