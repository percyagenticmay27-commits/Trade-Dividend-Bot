"""Compatibility wrapper upgrading strategy Holdings and Income tabs.

The underlying strategy workspace remains owned by enterprise_portal_strategy_ui.
This wrapper replaces only the Holdings and Income panel bodies and appends their
dedicated styles, keeping the change narrow and reversible.

Panel replacement deliberately uses balanced <section> matching rather than a
non-greedy regular expression. Holdings and Income renderers contain nested
<section> elements, so stopping at the first </section> corrupts the surrounding
workspace DOM and can collapse the page into a narrow column.
"""
from __future__ import annotations

import html
import re
from typing import Any, Mapping

from . import enterprise_portal_strategy_ui as _base
from .enterprise_holdings_purchase_date_ui import holdings_ui_css, render_holdings_panel
from .enterprise_income_ui import income_ui_css, render_income_panel

render_left_navigation = _base.render_left_navigation


def _find_matching_section_end(output: str, start: int) -> int | None:
    """Return the end offset of the section opened at *start*.

    The strategy panel contains nested semantic sections, so a simple
    ``.*?</section>`` replacement is unsafe. This lightweight scanner counts
    nested section tags and returns the matching outer close tag.
    """
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


def _replace_panel(output: str, *, sid: str, tab: str, body: str) -> str:
    """Replace only the body of one workspace tab panel without changing its DOM shell."""
    panel_id = f"panel-{sid}-{tab}"
    opening_pattern = re.compile(
        rf"<section\b[^>]*\bid=['\"]{re.escape(panel_id)}['\"][^>]*>",
        flags=re.IGNORECASE,
    )
    opening = opening_pattern.search(output)
    if opening is None:
        return output

    outer_end = _find_matching_section_end(output, opening.start())
    if outer_end is None:
        return output

    closing_start = output.rfind("</section", opening.end(), outer_end)
    if closing_start < opening.end():
        return output

    return output[: opening.end()] + body + output[closing_start:]


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
