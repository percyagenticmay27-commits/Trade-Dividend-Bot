"""Dividend-owned strategy assignment and shadow research UI.

Presentation only. This module cannot modify strategy assignments,
promote strategies, move capital, place orders, or enable live trading.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Mapping


DEFAULT_ASSIGNMENTS = Path(
    "state/dividend_pair_strategy_assignments.json"
)
DEFAULT_PERFORMANCE = Path(
    "results/dividend_strategy_shadow_performance.json"
)
DEFAULT_REQUESTS = Path(
    "state/dividend_strategy_promotion_requests.json"
)


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



def render_dividend_strategy_assignments(
    root: str | Path = ".",
) -> str:
    """Render Dividend primary/shadow assignments."""
    root = Path(root)

    assignments_doc = _read(root / DEFAULT_ASSIGNMENTS)
    performance_doc = _read(root / DEFAULT_PERFORMANCE)
    requests_doc = _read(root / DEFAULT_REQUESTS)

    assignments = assignments_doc.get("assignments", {})
    performance = (
        performance_doc.get("performance")
        or performance_doc.get("rows")
        or []
    )
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
        and str(row.get("status") or "").upper()
        == "PENDING_OWNER_REVIEW"
    }

    cards: list[str] = []

    for pair, raw_assignment in sorted(assignments.items()):
        if not isinstance(raw_assignment, Mapping):
            continue

        assignment = dict(raw_assignment)

        primary = str(
            assignment.get("primary_strategy")
            or "Not reported"
        )

        shadows = [
            str(value)
            for value in assignment.get("shadow_strategies", [])
            if value
        ]

        performance_rows: list[str] = []

        for result in by_pair.get(str(pair), []):
            strategy_id = str(
                result.get("strategy_id")
                or "Not reported"
            )

            role = (
                "PRIMARY"
                if strategy_id == primary
                else "SHADOW"
            )

            role_class = (
                "primary"
                if role == "PRIMARY"
                else "shadow"
            )

            performance_rows.append(
                "<tr>"
                f"<td><strong>{_text(strategy_id)}</strong>"
                f"<small>{_text(result.get('display_name'))}</small></td>"
                f"<td><span class='dividend-assignment-role {role_class}'>"
                f"{role}</span></td>"
                f"<td>{_money(result.get('virtual_capital_basis'))}</td>"
                f"<td>{_money(result.get('current_shadow_value'))}</td>"
                f"<td>{_pct(result.get('total_return_percent'))}</td>"
                f"<td>{_money(result.get('virtual_gain_loss'))}</td>"
                f"<td>{_pct(result.get('max_drawdown_percent'))}</td>"
                f"<td>{_text(result.get('completed_trade_count'))}</td>"
                f"<td>{_text(result.get('observation_count'))}</td>"
                f"<td>{_text(result.get('last_action'))}</td>"
                "</tr>"
            )

        if performance_rows:
            table = (
                "<div class='dividend-assignment-table-wrap'>"
                "<table class='dividend-assignment-table'>"
                "<thead><tr>"
                "<th>Strategy</th>"
                "<th>Assignment</th>"
                "<th>Capital Basis</th>"
                "<th>Current Value</th>"
                "<th>Return</th>"
                "<th>Gain / Loss</th>"
                "<th>Max Drawdown</th>"
                "<th>Closed Trades</th>"
                "<th>Observations</th>"
                "<th>Last Action</th>"
                "</tr></thead>"
                f"<tbody>{''.join(performance_rows)}</tbody>"
                "</table>"
                "</div>"
            )
        else:
            table = (
                "<p class='dividend-assignment-empty'>"
                "No shadow performance evidence is available "
                "for this pair yet."
                "</p>"
            )

        pending = pending_by_pair.get(str(pair))

        if pending:
            promotion = (
                "<div class='dividend-promotion pending'>"
                "<strong>Promotion review pending</strong>"
                f"<span>{_text(pending.get('proposed_primary_strategy'))} "
                "is challenging "
                f"{_text(pending.get('current_primary_strategy'))}.</span>"
                f"<span>Veto deadline: "
                f"{_text(pending.get('veto_deadline'))}</span>"
                "<span>Review or veto through the existing "
                "Dividend Strategy Review governance.</span>"
                "</div>"
            )
        else:
            promotion = (
                "<div class='dividend-promotion clear'>"
                "<strong>No promotion review pending</strong>"
                "<span>Shadow strategies continue accumulating "
                "qualification evidence.</span>"
                "</div>"
            )

        shadow_text = (
            ", ".join(shadows)
            if shadows
            else "None"
        )

        cards.append(
            "<article class='dividend-assignment-card'>"
            "<header>"
            "<div>"
            f"<h4>{_text(pair)}</h4>"
            f"<p>Primary: <strong>{_text(primary)}</strong>"
            f" · Shadows: {_text(shadow_text)}</p>"
            "</div>"
            "<span class='paper-lock'>PAPER ONLY</span>"
            "</header>"
            f"{table}"
            f"{promotion}"
            "</article>"
        )

    if cards:
        content = "".join(cards)
    else:
        content = (
            "<div class='data-availability "
            "data-availability-pending'>"
            "<strong>No Dividend strategy assignments available</strong>"
            "<span>The pair assignment artifact has not "
            "been published yet.</span>"
            "</div>"
        )

    return (
        "<section class='dividend-strategy-assignments'>"
        "<div class='dividend-assignment-intro'>"
        "<h3>Dividend Strategy Assignments</h3>"
        "<p>Compare each pair's active Primary strategy with "
        "isolated Shadow challengers. Shadow research cannot "
        "move capital, create paper positions, or place orders.</p>"
        "</div>"
        f"{content}"
        "</section>"
    )


def dividend_strategy_assignments_css() -> str:
    return """
<style>
.dividend-strategy-assignments {
  display:grid;
  gap:16px;
}

.dividend-assignment-intro p {
  margin-top:4px;
  color:#64748b;
}

.dividend-assignment-card {
  border:1px solid #dbe3ef;
  border-radius:14px;
  padding:16px;
  background:#fff;
}

.dividend-assignment-card > header {
  display:flex;
  justify-content:space-between;
  gap:16px;
  align-items:flex-start;
  margin-bottom:14px;
}

.dividend-assignment-card h4 {
  margin:0;
  font-size:1.05rem;
}

.dividend-assignment-card header p {
  margin:5px 0 0;
  color:#64748b;
}

.paper-lock {
  font-size:.72rem;
  font-weight:800;
  padding:5px 8px;
  border-radius:999px;
  background:#dcfce7;
  color:#166534;
  white-space:nowrap;
}

.dividend-assignment-table-wrap {
  overflow-x:auto;
}

.dividend-assignment-table {
  width:100%;
  min-width:1050px;
  border-collapse:collapse;
}

.dividend-assignment-table th,
.dividend-assignment-table td {
  padding:9px 10px;
  border-bottom:1px solid #e5e7eb;
  text-align:left;
  white-space:nowrap;
}

.dividend-assignment-table td small {
  display:block;
  margin-top:3px;
  color:#64748b;
}

.dividend-assignment-table th {
  font-size:.76rem;
  text-transform:uppercase;
  color:#64748b;
}

.dividend-assignment-role {
  display:inline-block;
  padding:4px 7px;
  border-radius:999px;
  font-size:.72rem;
  font-weight:800;
}

.dividend-assignment-role.primary {
  background:#dbeafe;
  color:#1d4ed8;
}

.dividend-assignment-role.shadow {
  background:#f3e8ff;
  color:#7e22ce;
}

.dividend-promotion {
  display:flex;
  gap:10px;
  flex-wrap:wrap;
  margin-top:14px;
  padding:11px 12px;
  border-radius:10px;
}

.dividend-promotion.clear {
  background:#f8fafc;
  color:#475569;
}

.dividend-promotion.pending {
  background:#fff7ed;
  color:#9a3412;
}

@media(max-width:700px) {
  .dividend-assignment-card > header {
    display:block;
  }

  .paper-lock {
    display:inline-block;
    margin-top:8px;
  }
}
</style>
"""
