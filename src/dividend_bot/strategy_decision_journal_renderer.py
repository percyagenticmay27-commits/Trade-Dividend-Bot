from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any, Mapping, Sequence

MODULE_NAME = "strategy_decision_journal_renderer"
MODULE_VERSION = "1.0.0"


def _timestamp(entry: Mapping[str, Any]) -> str:
    return str(entry.get("decision_timestamp") or entry.get("timestamp") or "")


def _sorted_entries(entries: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return sorted(entries, key=_timestamp, reverse=True)


def _text(value: Any, fallback: str = "Not reported") -> str:
    if value is None or value == "":
        return fallback
    return str(value)


def _render_images(images: Sequence[Mapping[str, Any]]) -> str:
    if not images:
        return '<p class="empty">No images reported for this decision.</p>'
    cards: list[str] = []
    for image in images:
        path = escape(_text(image.get("path"), ""))
        caption = escape(_text(image.get("caption"), "Evidence image"))
        image_type = escape(_text(image.get("image_type"), "EVIDENCE"))
        cards.append(
            f'<figure class="evidence-image"><img src="{path}" alt="{caption}">'
            f'<figcaption><strong>{image_type}</strong><br>{caption}</figcaption></figure>'
        )
    return '<div class="image-grid">' + "".join(cards) + "</div>"


def _render_committee_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    if not rows:
        return '<tr><td colspan="6">No committee evidence reported.</td></tr>'
    rendered: list[str] = []
    for row in rows:
        rendered.append(
            "<tr>"
            f"<td>{escape(_text(row.get('committee') or row.get('engine')))}</td>"
            f"<td>{escape(_text(row.get('score')))}</td>"
            f"<td>{escape(_text(row.get('confidence')))}</td>"
            f"<td>{escape(_text(row.get('vote') or row.get('decision')))}</td>"
            f"<td>{escape(_text(row.get('evidence_summary') or row.get('reason')))}</td>"
            f"<td>{escape(_text(row.get('evidence_status')))}</td>"
            "</tr>"
        )
    return "".join(rendered)


def _render_dividend_identity(entry: Mapping[str, Any]) -> str:
    nested = entry.get("ecosystem")
    ecosystem_data = nested if isinstance(nested, Mapping) else {}
    ecosystem = escape(
        _text(
            ecosystem_data.get("ecosystem_name")
            or entry.get("ecosystem_name"),
            "Dividend ecosystem",
        )
    )
    income_leg = escape(
        _text(ecosystem_data.get("income_leg") or entry.get("income_leg"))
    )
    leverage_leg = escape(
        _text(ecosystem_data.get("leverage_leg") or entry.get("leverage_leg"))
    )
    return (
        f'<div class="decision-object"><span class="type">ECOSYSTEM PAIR</span>'
        f'<h3>{ecosystem}</h3><div class="pair">'
        f'<span><b>Income ETF</b>{income_leg}</span><span class="plus">+</span>'
        f'<span><b>Leverage ETF</b>{leverage_leg}</span></div></div>'
    )


def _render_swing_identity(entry: Mapping[str, Any]) -> str:
    symbol = escape(_text(entry.get("symbol") or entry.get("investment"), "Swing opportunity"))
    rank = escape(_text(entry.get("committee_rank")))
    return (
        f'<div class="decision-object"><span class="type">SWING OPPORTUNITY</span>'
        f'<h3>{symbol}</h3><p>Committee rank: {rank}</p></div>'
    )


def render_strategy_decision_journal(journal: Mapping[str, Any]) -> str:
    """Render one strategy-owned, read-only Decision Journal HTML fragment."""
    strategy_id = _text(journal.get("strategy_id"), "UNKNOWN")
    strategy_type = _text(
        journal.get("strategy_type") or journal.get("strategy_kind"), "UNKNOWN"
    ).upper()
    entries_raw = journal.get("decisions") or journal.get("entries") or []
    entries = _sorted_entries([e for e in entries_raw if isinstance(e, Mapping)])

    cards: list[str] = []
    for index, entry in enumerate(entries):
        entry_strategy_id = _text(entry.get("strategy_id"), strategy_id)
        if entry_strategy_id != strategy_id:
            raise ValueError("Decision Journal entry belongs to a different strategy")

        identity = (
            _render_dividend_identity(entry)
            if strategy_type == "DIVIDEND"
            else _render_swing_identity(entry)
        )
        timestamp = escape(_text(entry.get("decision_timestamp") or entry.get("timestamp")))
        decision_type = escape(_text(entry.get("decision_type") or entry.get("decision")))
        status = escape(_text(entry.get("status"), "RECORDED"))
        rationale = escape(_text(entry.get("final_rationale") or entry.get("reason")))
        alternatives = entry.get("alternatives") or []
        alternatives_text = ", ".join(escape(_text(item)) for item in alternatives) or "None reported"
        committee_rows = _render_committee_rows(entry.get("committee_evidence") or [])
        images = _render_images(entry.get("images") or [])

        cards.append(
            f'<article class="decision-card" data-order="{index}" data-timestamp="{timestamp}">'
            f'<header><div><span class="decision-type">{decision_type}</span>'
            f'<span class="status">{status}</span></div><time>{timestamp}</time></header>'
            f'{identity}<p class="rationale"><b>Final rationale:</b> {rationale}</p>'
            f'<p><b>Alternatives considered:</b> {alternatives_text}</p>'
            '<details><summary>Committee scores and evidence</summary>'
            '<table><thead><tr><th>Committee</th><th>Score</th><th>Confidence</th>'
            '<th>Vote</th><th>Evidence</th><th>Status</th></tr></thead>'
            f'<tbody>{committee_rows}</tbody></table></details>'
            f'<details><summary>Images and supporting visuals</summary>{images}</details>'
            '</article>'
        )

    empty = '<div class="empty-state">No decisions reported for this strategy.</div>' if not cards else ""
    title = escape(_text(journal.get("strategy_name"), strategy_id))
    generated_at = escape(
        _text(
            journal.get("generated_at"),
            datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        )
    )

    return f'''<section class="strategy-decision-journal" data-strategy-id="{escape(strategy_id)}">
<header class="journal-heading"><div><p class="eyebrow">STRATEGY-OWNED · NEWEST FIRST</p>
<h2>{title} Decision Journal</h2><p>Only decisions and evidence owned by {escape(strategy_id)} are shown.</p></div>
<div class="journal-meta"><span>PAPER ONLY</span><span>READ ONLY</span><small>Generated {generated_at}</small></div></header>
<div class="journal-filters"><button data-filter="ALL">All</button><button data-filter="BUY">Buy</button>
<button data-filter="SELL">Sell</button><button data-filter="REPLACE">Replace</button>
<button data-filter="WATCHLIST">Watchlist</button></div>
<div class="decision-timeline">{''.join(cards)}{empty}</div></section>'''


def render_strategy_decision_journal_document(journal: Mapping[str, Any]) -> str:
    body = render_strategy_decision_journal(journal)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Strategy Decision Journal</title>
<style>
body{{font-family:Arial,sans-serif;background:#f5f7fb;color:#101828;margin:0;padding:24px}}.strategy-decision-journal{{max-width:1400px;margin:auto}}
.journal-heading,.decision-card{{background:#fff;border:1px solid #dbe3ef;border-radius:16px;padding:20px;margin-bottom:16px}}
.journal-heading{{display:flex;justify-content:space-between;gap:20px}}.eyebrow,.type{{color:#5b21b6;font-weight:700;font-size:12px}}
.journal-meta span,.status,.decision-type{{display:inline-block;padding:5px 9px;border-radius:999px;background:#eef2ff;margin:3px;font-size:12px;font-weight:700}}
.journal-filters{{display:flex;gap:8px;margin:16px 0}}button{{padding:9px 14px;border:1px solid #cbd5e1;background:#fff;border-radius:9px}}
.decision-card header{{display:flex;justify-content:space-between}}.pair{{display:flex;align-items:center;gap:16px;margin:12px 0}}.pair span:not(.plus){{background:#f8fafc;border:1px solid #dbe3ef;padding:12px 18px;border-radius:12px}}.pair b{{display:block;font-size:11px;color:#64748b}}
table{{width:100%;border-collapse:collapse;margin-top:12px}}th,td{{border-bottom:1px solid #e5e7eb;padding:10px;text-align:left}}details{{margin-top:14px}}summary{{font-weight:700;cursor:pointer}}
.image-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin-top:14px}}.evidence-image{{margin:0;background:#f8fafc;border-radius:12px;overflow:hidden}}.evidence-image img{{width:100%;height:160px;object-fit:cover}}figcaption{{padding:10px}}.empty,.empty-state{{color:#64748b;padding:18px}}
</style></head><body>{body}</body></html>'''
