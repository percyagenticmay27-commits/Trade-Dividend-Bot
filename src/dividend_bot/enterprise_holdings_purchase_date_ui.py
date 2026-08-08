"""Narrow presentation upgrade adding current-position purchase dates to Holdings."""
from __future__ import annotations

import html
import re
from typing import Any, Mapping, Sequence

from .enterprise_holdings_ui import holdings_ui_css, render_holdings_panel as _render_base


def _purchase_date(item: Mapping[str, Any]) -> str:
    value = item.get("purchase_date")
    if value in (None, ""):
        return "<span class='not-reported'>Not reported</span>"
    return html.escape(str(value))


def render_holdings_panel(row: Mapping[str, Any]) -> str:
    """Render base Holdings UI with Purchase Date in Position Analytics.

    Purchase Date means the first buy in the currently open position. It is not
    the instrument's first historical purchase and resets after a full exit and
    later re-entry. Missing evidence remains Not reported.
    """
    output = _render_base(row)
    marker = "<table class='holdings-table holdings-analytics-table'>"
    start = output.find(marker)
    if start < 0:
        return output
    end = output.find("</table>", start)
    if end < 0:
        return output
    end += len("</table>")
    table = output[start:end]
    table = table.replace(
        "<thead><tr><th>Symbol</th><th>Cost Basis</th>",
        "<thead><tr><th>Symbol</th><th>Purchase Date</th><th>Cost Basis</th>",
        1,
    )

    raw_holdings = row.get("holdings") or row.get("positions")
    holdings = (
        [item for item in raw_holdings if isinstance(item, Mapping)]
        if isinstance(raw_holdings, Sequence) and not isinstance(raw_holdings, (str, bytes))
        else []
    )
    dates = {
        str(item.get("symbol") or "UNKNOWN").strip().upper(): _purchase_date(item)
        for item in holdings
    }

    row_pattern = re.compile(r"<tr><td><strong>([^<]+)</strong></td>")

    def add_date(match: re.Match[str]) -> str:
        symbol = html.unescape(match.group(1)).strip().upper()
        return match.group(0) + f"<td>{dates.get(symbol, '<span class=\'not-reported\'>Not reported</span>')}</td>"

    table = row_pattern.sub(add_date, table)
    return output[:start] + table + output[end:]


__all__ = ["holdings_ui_css", "render_holdings_panel"]
