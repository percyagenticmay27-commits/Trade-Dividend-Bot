"""Compatibility wrapper upgrading strategy-specific Enterprise workspace tabs.

SWING-001 receives strategy-owned workspace extensions while the base Enterprise
renderer remains shared. Manual Strategy handles creation/editing; Strategy
Assignments shows Direct/Shadow relationships and is the only tab allowed to
surface an explicit user promotion control.
"""
from __future__ import annotations

import html
import re
from typing import Any, Mapping

from . import enterprise_portal_strategy_ui as _base
from .enterprise_holdings_purchase_date_ui import holdings_ui_css, render_holdings_panel
from .enterprise_income_ui import income_ui_css, render_income_panel
from .enterprise_manual_strategy_ui import manual_strategy_ui_css, render_manual_strategy_panel
from .enterprise_position_history_ui import position_history_ui_css, render_position_history_panel
from .enterprise_strategy_assignments_ui import strategy_assignments_ui_css, render_strategy_assignments_panel
from .enterprise_trade_analytics_ui import trade_analytics_ui_css, render_trade_analytics_panel
from .enterprise_swing_alerts_ui import render_swing_alerts_panel, swing_alerts_ui_css
from .enterprise_swing_decision_journal_ui import render_swing_decision_journal_panel, swing_decision_journal_ui_css

render_left_navigation = _base.render_left_navigation


def _find_matching_section_end(output: str, start: int) -> int | None:
    token_pattern = re.compile(r"<section\b[^>]*>|</section\s*>", flags=re.IGNORECASE)
    depth = 0
    for match in token_pattern.finditer(output, start):
        token = match.group(0).lower()
        if token.startswith("<section"):
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return match.end()
    return None


def _panel_bounds(output: str, *, sid: str, tab: str) -> tuple[int, int, int] | None:
    panel_id = f"panel-{sid}-{tab}"
    opening_pattern = re.compile(
        rf"<section\b[^>]*\bid=['\"]{re.escape(panel_id)}['\"][^>]*>",
        flags=re.IGNORECASE,
    )
    opening = opening_pattern.search(output)
    if opening is None:
        return None
    outer_end = _find_matching_section_end(output, opening.start())
    if outer_end is None:
        return None
    closing_start = output.rfind("</section", opening.end(), outer_end)
    if closing_start < opening.end():
        return None
    return opening.end(), closing_start, outer_end


def _replace_panel(output: str, *, sid: str, tab: str, body: str) -> str:
    bounds = _panel_bounds(output, sid=sid, tab=tab)
    if bounds is None:
        return output
    body_start, closing_start, _ = bounds
    return output[:body_start] + body + output[closing_start:]


def _append_panel(output: str, *, sid: str, tab: str, body: str) -> str:
    bounds = _panel_bounds(output, sid=sid, tab=tab)
    if bounds is None:
        return output
    _, closing_start, _ = bounds
    return output[:closing_start] + body + output[closing_start:]


def _insert_workspace_tab(output: str, *, sid: str, tab_id: str, label: str, body: str) -> str:
    if f"id='tab-{sid}-{tab_id}'" in output:
        return output
    strategy_start = output.find(f"<section id='strategy-{sid}'")
    if strategy_start < 0:
        return output
    tab_nav_start = output.find("<nav class='workspace-tabs'", strategy_start)
    if tab_nav_start < 0:
        return output
    tab_nav_end = output.find("</nav>", tab_nav_start)
    if tab_nav_end < 0:
        return output
    button = (
        f"<button type='button' class='workspace-tab' "
        f"data-workspace-strategy='{sid}' data-workspace-tab-target='{tab_id}' "
        f"id='tab-{sid}-{tab_id}' role='tab' aria-controls='panel-{sid}-{tab_id}' "
        f"aria-selected='false' tabindex='-1'>{html.escape(label)}</button>"
    )
    output = output[:tab_nav_end] + button + output[tab_nav_end:]
    details_marker = "<details class='readable-evidence'>"
    details_start = output.find(details_marker, tab_nav_end + len(button))
    if details_start < 0:
        return output
    panel = (
        f"<section class='workspace-tab-panel' hidden "
        f"data-workspace-strategy-panel='{sid}' data-workspace-tab-panel='{tab_id}' "
        f"id='panel-{sid}-{tab_id}' role='tabpanel' aria-labelledby='tab-{sid}-{tab_id}'>"
        f"{body}</section>"
    )
    return output[:details_start] + panel + output[details_start:]


def _insert_swing_extension_tabs(output: str, *, sid: str, row: Mapping[str, Any]) -> str:
    capabilities = row.get("capabilities")
    if isinstance(capabilities, list) and "manual_strategy" in capabilities:
        output = _insert_workspace_tab(
            output,
            sid=sid,
            tab_id="manual-strategy",
            label="Manual Strategy",
            body=render_manual_strategy_panel(row),
        )
        # Strategy Assignments is intentionally a separate governance surface.
        output = _insert_workspace_tab(
            output,
            sid=sid,
            tab_id="strategy-assignments",
            label="Strategy Assignments",
            body=render_strategy_assignments_panel(row),
        )
    return output


def render_strategy_workspace(report: Mapping[str, Any], *, audience: str) -> str:
    output = _base.render_strategy_workspace(report, audience=audience)
    strategies = report.get("strategy_kpis")
    if not isinstance(strategies, list):
        return output

    for index, row in enumerate(strategies):
        if not isinstance(row, Mapping):
            continue
        raw_sid = str(row.get("strategy_id") or f"strategy-{index}")
        sid = html.escape(raw_sid, quote=True)
        holdings_body = render_holdings_panel(row)
        if raw_sid.upper() == "SWING-001":
            holdings_body += render_trade_analytics_panel(row)
        output = _replace_panel(output, sid=sid, tab="holdings", body=holdings_body)
        if raw_sid.upper() == "SWING-001":
            output = _replace_panel(output, sid=sid, tab="income", body=render_trade_analytics_panel(row))
            output = _replace_panel(output, sid=sid, tab="alerts", body=render_swing_alerts_panel(row))
            output = _replace_panel(output, sid=sid, tab="decisions", body=render_swing_decision_journal_panel(row))
            output = output.replace(
                f"id='tab-{sid}-income' role='tab'",
                f"id='tab-{sid}-income' role='tab' data-section-kind='trade-analytics'",
                1,
            )
            tab_start = output.find(f"id='tab-{sid}-income'")
            if tab_start >= 0:
                label_start = output.find(">", tab_start) + 1
                label_end = output.find("</button>", label_start)
                if label_start > 0 and label_end >= label_start:
                    output = output[:label_start] + "Trade Analytics" + output[label_end:]
            output = _insert_swing_extension_tabs(output, sid=sid, row=row)
        else:
            output = _replace_panel(output, sid=sid, tab="income", body=render_income_panel(row))
        output = _append_panel(output, sid=sid, tab="performance", body=render_position_history_panel(row))
    return output


def strategy_ui_css() -> str:
    return (
        _base.strategy_ui_css()
        + holdings_ui_css()
        + income_ui_css()
        + position_history_ui_css()
        + trade_analytics_ui_css()
        + swing_alerts_ui_css()
        + swing_decision_journal_ui_css()
        + manual_strategy_ui_css()
        + strategy_assignments_ui_css()
    )
