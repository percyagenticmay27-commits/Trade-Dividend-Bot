"""Read-only SWING-001 stock/position/candidate Decision Journal UI."""
from __future__ import annotations

import html
from typing import Any, Mapping

_ALLOWED_DECISIONS = {"HOLD", "WAITING_FOR_ENTRY", "ENTRY_REVIEW", "EXIT_REVIEW"}


def _text(value: Any, default: str = "Not reported") -> str:
    if value in (None, ""):
        return default
    return html.escape(str(value))


def _items(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _timeline(decision: Mapping[str, Any]) -> str:
    steps = _items(decision.get("timeline"))
    if not steps:
        return "<p class='swing-decision-empty'>No committee timeline was reported.</p>"
    rendered: list[str] = []
    for index, step in enumerate(steps, start=1):
        reason_codes = step.get("reason_codes")
        reasons = ", ".join(
            _text(item) for item in reason_codes
        ) if isinstance(reason_codes, list) and reason_codes else "Not reported"
        sequence = _text(step.get("sequence"), str(index))
        rendered.append(
            "<li class='swing-decision-step'>"
            f"<span class='swing-decision-sequence'>{sequence}</span>"
            "<div><header>"
            f"<strong>{_text(step.get('owner'))}</strong>"
            f"<span>{_text(step.get('status'))}</span>"
            "</header>"
            f"<p><b>Reason codes:</b> {reasons}</p>"
            f"<p><b>Evidence timestamp:</b> {_text(step.get('evidence_timestamp'))}</p>"
            "</div></li>"
        )
    return "<ol class='swing-decision-timeline'>" + "".join(rendered) + "</ol>"


def _decision_card(decision: Mapping[str, Any]) -> str:
    alternatives = decision.get("alternatives_considered")
    alternative_text = ", ".join(
        _text(item) for item in alternatives
    ) if isinstance(alternatives, list) and alternatives else "None reported"
    current_decision = str(decision.get("current_decision") or "").upper()
    return (
        "<article class='swing-decision-card'>"
        "<header>"
        f"<div><span class='swing-decision-scope'>{_text(decision.get('decision_scope'))}</span>"
        f"<h4>{_text(decision.get('symbol'))}</h4></div>"
        f"<span class='swing-current-decision swing-decision-{html.escape(current_decision.lower().replace('_', '-'))}'>{_text(current_decision)}</span>"
        "</header>"
        "<dl class='swing-decision-facts'>"
        f"<div><dt>Current state</dt><dd>{_text(decision.get('current_state'))}</dd></div>"
        f"<div><dt>Current owner</dt><dd>{_text(decision.get('current_owner'))}</dd></div>"
        f"<div><dt>Evidence timestamp</dt><dd>{_text(decision.get('evidence_timestamp'))}</dd></div>"
        "</dl>"
        f"<p><b>Rationale:</b> {_text(decision.get('rationale'))}</p>"
        f"<p><b>Alternatives considered:</b> {alternative_text}</p>"
        "<details><summary>Committee Evidence Timeline</summary>"
        f"{_timeline(decision)}</details>"
        "</article>"
    )


def _section(title: str, description: str, decisions: list[Mapping[str, Any]]) -> str:
    cards = "".join(_decision_card(item) for item in decisions)
    if not cards:
        cards = "<p class='swing-decision-empty'>No authoritative decisions are currently reported in this category.</p>"
    return (
        "<section class='swing-decision-group'>"
        f"<header><h3>{html.escape(title)}</h3><p>{html.escape(description)}</p></header>"
        f"<div class='swing-decision-grid'>{cards}</div>"
        "</section>"
    )


def render_swing_decision_journal_panel(row: Mapping[str, Any]) -> str:
    if str(row.get("strategy_id") or "").upper() != "SWING-001":
        return ""
    report = row.get("decision_journal")
    if not isinstance(report, Mapping):
        return (
            "<section class='swing-decision-journal swing-decision-unavailable'>"
            "<h3>Swing Decision Journal unavailable</h3>"
            "<p>No current authoritative SWING-001 Decision Journal evidence was reported. "
            "No decision was inferred or fabricated.</p></section>"
        )
    if (
        str(report.get("strategy_id") or "").upper() != "SWING-001"
        or report.get("decision_authority_policy")
        != "CURRENT_MATCHED_AUTHORITATIVE_EVIDENCE_ONLY"
        or report.get("paper_trade_mode") is not True
        or report.get("advisory_only") is not True
    ):
        return (
            "<section class='swing-decision-journal swing-decision-unavailable'>"
            "<h3>Swing Decision Journal unavailable</h3>"
            "<p>Unsafe or cross-strategy Decision Journal evidence was rejected.</p></section>"
        )

    positions = _items(report.get("position_decisions"))
    candidates = _items(report.get("candidate_decisions"))
    decisions = [*positions, *candidates]
    if any(
        str(item.get("current_decision") or "").upper() not in _ALLOWED_DECISIONS
        for item in decisions
    ):
        return (
            "<section class='swing-decision-journal swing-decision-unavailable'>"
            "<h3>Swing Decision Journal unavailable</h3>"
            "<p>The report contained a decision outside the registered advisory contract. "
            "No BUY, SELL, sale, exit, or closure was inferred.</p></section>"
        )

    warnings = report.get("evidence_warnings")
    warning_items = (
        "".join(f"<li>{_text(item)}</li>" for item in warnings if item not in (None, ""))
        if isinstance(warnings, list)
        else ""
    )
    disclosures = (
        "<section class='swing-decision-disclosures'><h3>Evidence Disclosures</h3>"
        f"<ul>{warning_items}</ul></section>"
        if warning_items
        else ""
    )
    total = len(decisions)
    zero = ""
    if total == 0:
        zero = (
            "<p class='swing-decision-zero'>"
            + _text(
                report.get("no_decisions_message"),
                "Current authoritative Swing evidence was evaluated and no reportable decisions were found.",
            )
            + "</p>"
        )

    return (
        "<section class='swing-decision-journal' data-strategy-id='SWING-001'>"
        "<header class='swing-decision-heading'><div>"
        "<p class='swing-decision-eyebrow'>STRATEGY-OWNED · CURRENT AUTHORITATIVE EVIDENCE</p>"
        "<h2>Trade Swing Bot Decision Journal</h2>"
        "<p>Open-position decisions and candidate decisions are reported separately.</p>"
        "</div><div class='swing-decision-badges'><span>PAPER ONLY</span>"
        "<span>ADVISORY ONLY</span><span>READ ONLY</span></div></header>"
        "<dl class='swing-decision-summary'>"
        f"<div><dt>Authority policy</dt><dd>{_text(report.get('decision_authority_policy'))}</dd></div>"
        f"<div><dt>Evaluation status</dt><dd>{_text(report.get('evaluation_status'))}</dd></div>"
        f"<div><dt>Position decisions</dt><dd>{len(positions)}</dd></div>"
        f"<div><dt>Candidate decisions</dt><dd>{len(candidates)}</dd></div>"
        "</dl>"
        f"{zero}"
        + _section(
            "Open Position Decisions",
            "Current decisions for authentic open Swing paper positions.",
            positions,
        )
        + _section(
            "Candidate Decisions",
            "Current committee-owned candidate lifecycle decisions.",
            candidates,
        )
        + disclosures
        + "<p class='swing-decision-planning-note'>Planning calculations such as "
        "rebalance_actions.json are excluded and are not treated as executed decisions.</p>"
        "</section>"
    )


def swing_decision_journal_ui_css() -> str:
    return """
.swing-decision-journal{display:grid;gap:14px}
.swing-decision-heading{display:flex;justify-content:space-between;gap:18px;padding:18px;background:#0b1d3a;color:#fff;border-radius:12px}
.swing-decision-heading h2{margin:4px 0;color:#fff}.swing-decision-heading p{color:#fff;margin:4px 0}
.swing-decision-eyebrow{font-size:11px;font-weight:800;letter-spacing:.04em}
.swing-decision-badges{display:flex;flex-wrap:wrap;align-content:flex-start;justify-content:flex-end;gap:6px}
.swing-decision-badges span,.swing-current-decision,.swing-decision-scope{display:inline-block;padding:5px 8px;border-radius:999px;font-size:11px;font-weight:800}
.swing-decision-badges span{background:#fff;color:#312e81}
.swing-decision-summary,.swing-decision-facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;margin:0}
.swing-decision-summary div,.swing-decision-facts div{border:1px solid #dbe3ef;background:#f8fafc;border-radius:9px;padding:9px}
.swing-decision-summary dt,.swing-decision-facts dt{font-size:11px;color:#64748b}.swing-decision-summary dd,.swing-decision-facts dd{margin:3px 0 0;font-weight:800;overflow-wrap:anywhere}
.swing-decision-group{border:1px solid #dbe3ef;border-radius:12px;padding:14px}.swing-decision-group>header h3{margin:0}.swing-decision-group>header p{color:#475467}
.swing-decision-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:10px}
.swing-decision-card{border:1px solid #dbe3ef;border-radius:11px;padding:12px;background:#fff;min-width:0}
.swing-decision-card>header{display:flex;justify-content:space-between;gap:10px}.swing-decision-card h4{font-size:20px;margin:5px 0}
.swing-decision-scope{background:#eef2ff;color:#4338ca}.swing-current-decision{background:#ecfdf3;color:#067647;height:fit-content}
.swing-decision-waiting-for-entry,.swing-decision-entry-review,.swing-decision-exit-review{background:#fff7ed;color:#b54708}
.swing-decision-card p{overflow-wrap:anywhere}.swing-decision-card details{margin-top:12px}
.swing-decision-timeline{list-style:none;border-left:3px solid #c4b5fd;margin:12px 0 0;padding-left:18px}
.swing-decision-step{display:grid;grid-template-columns:28px 1fr;gap:8px;margin:0 0 12px -34px}
.swing-decision-sequence{display:grid;place-items:center;width:26px;height:26px;border-radius:50%;background:#5b21b6;color:#fff;font-weight:800}
.swing-decision-step>div{border:1px solid #dbe3ef;border-radius:9px;padding:9px;background:#f8fafc}.swing-decision-step header{display:flex;justify-content:space-between;gap:8px}
.swing-decision-disclosures{border:1px solid #f5c26b;background:#fffaeb;border-radius:11px;padding:13px}.swing-decision-disclosures h3{margin-top:0;color:#93370d}
.swing-decision-zero{border:1px solid #86efac;background:#f0fdf4;color:#166534;border-radius:10px;padding:12px;font-weight:700}
.swing-decision-empty,.swing-decision-planning-note,.swing-decision-unavailable p{color:#475467}
.swing-decision-unavailable{border:1px solid #dbe3ef;border-radius:12px;padding:16px}
@media(max-width:700px){.swing-decision-heading{display:block}.swing-decision-badges{justify-content:flex-start;margin-top:10px}.swing-decision-grid{grid-template-columns:1fr}}
"""
