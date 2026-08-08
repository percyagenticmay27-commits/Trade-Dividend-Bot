"""Compatibility wrapper upgrading strategy Holdings and Income tabs.

The underlying strategy workspace remains owned by enterprise_portal_strategy_ui.
This wrapper replaces only the Holdings and Income panel bodies and appends their
dedicated styles, keeping the change narrow and reversible.
"""
from __future__ import annotations

import html
import re
from typing import Any, Mapping

from . import enterprise_portal_strategy_ui as _base
from .enterprise_holdings_purchase_date_ui import holdings_ui_css, render_holdings_panel
from .enterprise_income_ui import income_ui_css, render_income_panel

render_left_navigation = _base.render_left_navigation


def _replace_panel(output: str, *, sid: str, tab: str, body: str) -> str:
    panel_id = re.escape(f"panel-{sid}-{tab}")
    pattern = re.compile(
        rf"(<section class='workspace-tab-panel'[^>]*id='{panel_id}'[^>]*>).*?(</section>)",
        flags=re.DOTALL,
    )
    replacement = rf"\1{body}\2"
    output, _ = pattern.subn(replacement, output, count=1)
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
        output = _replace_panel(output, sid=sid, tab="holdings", body=render_holdings_panel(row))
        output = _replace_panel(output, sid=sid, tab="income", body=render_income_panel(row))
    return output


def strategy_ui_css() -> str:
    return _base.strategy_ui_css() + holdings_ui_css() + income_ui_css()
