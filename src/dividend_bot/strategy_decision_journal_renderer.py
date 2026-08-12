from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any, Mapping, Sequence
from urllib.parse import quote

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


def _safe_image_path(value: Any) -> str:
    path = _text(value, "").strip()
    lowered = path.lower()
    if lowered.startswith(("javascript:", "vbscript:", "data:text/html")):
        return ""
    return path


def _render_images(
    images: Sequence[Mapping[str, Any]],
    *,
    decision_id: str,
) -> str:
    if not images:
        return '<p class="empty">No images reported for this decision.</p>'
    cards: list[str] = []
    for index, image in enumerate(images):
        raw_path = _safe_image_path(image.get("path"))
        caption = escape(_text(image.get("caption"), "Evidence image"))
        image_type = escape(_text(image.get("image_type"), "EVIDENCE"))
        if not raw_path:
            cards.append(
                '<article class="evidence-image unavailable">'
                f'<div class="image-unavailable">Image unavailable</div>'
                f'<p><strong>{image_type}</strong><br>{caption}</p></article>'
            )
            continue
        path = escape(raw_path, quote=True)
        cards.append(
            f'<a class="evidence-image journal-gallery-thumb" '
            f'data-gallery-decision="{escape(decision_id, quote=True)}" '
            f'data-gallery-index="{index}" href="{path}" target="_blank" '
            f'rel="noopener noreferrer" aria-label="Open full-size image: {caption}">'
            f'<img src="{path}" alt="{caption}" loading="lazy">'
            f'<span><strong>{image_type}</strong><br>{caption}</span></a>'
        )
    return (
        f'<div class="image-grid" data-decision-gallery="{escape(decision_id, quote=True)}">'
        + "".join(cards)
        + "</div>"
    )



def _render_committee_timeline(
    rows: Sequence[Mapping[str, Any]],
    *,
    decision_id: str,
) -> str:
    if not rows:
        return (
            '<div class="committee-timeline empty" '
            f'data-committee-decision="{escape(decision_id, quote=True)}">'
            "No committee evidence reported for this decision.</div>"
        )
    steps: list[str] = []
    for index, row in enumerate(rows, start=1):
        committee = escape(_text(row.get("committee") or row.get("engine")))
        score = escape(_text(row.get("score")))
        confidence = escape(_text(row.get("confidence")))
        vote = escape(_text(row.get("vote") or row.get("decision")))
        status = escape(_text(row.get("evidence_status")))
        rationale = escape(
            _text(row.get("evidence_summary") or row.get("reason"))
        )
        steps.append(
            '<li class="committee-step">'
            f'<span class="committee-sequence" aria-label="Committee step {index}">{index}</span>'
            '<div class="committee-step-content">'
            f'<header><strong>{committee}</strong>'
            f'<span class="committee-vote">{vote}</span></header>'
            '<dl>'
            f'<div><dt>Score</dt><dd>{score}</dd></div>'
            f'<div><dt>Confidence</dt><dd>{confidence}</dd></div>'
            f'<div><dt>Evidence</dt><dd>{status}</dd></div>'
            '</dl>'
            f'<p>{rationale}</p></div></li>'
        )
    return (
        '<ol class="committee-timeline" '
        f'data-committee-decision="{escape(decision_id, quote=True)}">'
        + "".join(steps)
        + "</ol>"
    )


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
        committee_evidence = entry.get("committee_evidence") or []
        committee_rows = _render_committee_rows(committee_evidence)
        decision_id = _text(entry.get("decision_id"), f"decision-{index}")
        nested_identity = entry.get("ecosystem")
        identity_data = nested_identity if isinstance(nested_identity, Mapping) else {}
        search_values = [
            decision_id,
            timestamp,
            decision_type,
            status,
            rationale,
            entry.get("symbol"),
            entry.get("ecosystem_name"),
            entry.get("income_leg"),
            entry.get("leverage_leg"),
            identity_data.get("ecosystem_name"),
            identity_data.get("income_leg"),
            identity_data.get("leverage_leg"),
        ]
        for evidence in committee_evidence:
            if isinstance(evidence, Mapping):
                search_values.extend([
                    evidence.get("committee") or evidence.get("engine"),
                    evidence.get("evidence_summary") or evidence.get("reason"),
                    evidence.get("vote") or evidence.get("decision"),
                ])
        search_text = escape(
            " ".join(_text(value, "") for value in search_values).lower(),
            quote=True,
        )
        committee_timeline = _render_committee_timeline(
            committee_evidence,
            decision_id=decision_id,
        )
        images = _render_images(
            entry.get("images") or [],
            decision_id=decision_id,
        )

        cards.append(
            f'<article class="decision-card" data-order="{index}" data-timestamp="{timestamp}" '
            f'data-decision-type="{decision_type}" data-journal-search-text="{search_text}">'
            f'<header><div><span class="decision-type">{decision_type}</span>'
            f'<span class="status">{status}</span></div><time>{timestamp}</time></header>'
            f'{identity}<p class="rationale"><b>Final rationale:</b> {rationale}</p>'
            f'<p><b>Alternatives considered:</b> {alternatives_text}</p>'
            '<section class="committee-evidence-timeline"><h4>Committee Evidence Timeline</h4>'
            f'{committee_timeline}</section>'
            '<details><summary>Committee scores and evidence table</summary>'
            '<table><thead><tr><th>Committee</th><th>Score</th><th>Confidence</th>'
            '<th>Vote</th><th>Evidence</th><th>Status</th></tr></thead>'
            f'<tbody>{committee_rows}</tbody></table></details>'
            f'<details><summary>Images and supporting visuals</summary>{images}</details>'
            '</article>'
        )

    empty = '<div class="empty-state">No decisions reported for this strategy.</div>' if not cards else ""
    title = escape(_text(journal.get("strategy_name"), strategy_id))
    encoded_strategy_id = quote(strategy_id, safe="")
    strategy_anchor = escape(strategy_id, quote=True)
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
<nav class="journal-cross-links" aria-label="{title} Enterprise links">
<a href="/executive-dashboard?strategy={encoded_strategy_id}#strategy-{strategy_anchor}">Executive Dashboard</a>
<a href="/investor-dashboard?strategy={encoded_strategy_id}#strategy-{strategy_anchor}">Investor Dashboard</a>
<a href="/executive-dashboard?strategy={encoded_strategy_id}#strategy-{strategy_anchor}">Strategy Workspace</a>
<a href="/executive-dashboard?strategy={encoded_strategy_id}&amp;tab=decisions#strategy-{strategy_anchor}" aria-current="page">Decision Journal</a>
</nav>
<div class="journal-search" role="search" aria-label="Search decision lifecycle">
<label><span>Search stock, pair, reason, or decision</span>
<input type="search" data-journal-search placeholder="Example: NVDW, AMDW / AMDL, price below EMA20"></label>
<label><span>Decision type</span><select data-journal-type>
<option value="ALL">All decisions</option><option value="BUY">Buy</option>
<option value="SELL">Sell</option><option value="HOLD">Hold</option>
<option value="WATCHLIST">Watchlist</option><option value="REPLACE">Replace</option>
</select></label><button type="button" data-journal-clear>Clear</button>
<strong data-journal-count>{len(cards)} decisions shown</strong></div>
<div class="journal-filters" aria-label="Quick decision filters"><button type="button" data-filter="ALL">All</button><button type="button" data-filter="BUY">Buy</button>
<button type="button" data-filter="SELL">Sell</button><button type="button" data-filter="HOLD">Hold</button>
<button type="button" data-filter="REPLACE">Replace</button><button type="button" data-filter="WATCHLIST">Watchlist</button></div>
<div class="decision-timeline">{''.join(cards)}{empty}</div>
<script>
(function() {{
  document.querySelectorAll('.strategy-decision-journal').forEach(function(root) {{
    if (root.dataset.filtersReady === 'true') return;
    root.dataset.filtersReady = 'true';
    var search = root.querySelector('[data-journal-search]');
    var type = root.querySelector('[data-journal-type]');
    var clear = root.querySelector('[data-journal-clear]');
    var count = root.querySelector('[data-journal-count]');
    var cards = Array.prototype.slice.call(root.querySelectorAll('.decision-card'));
    function applyFilters() {{
      var query = search ? search.value.trim().toLowerCase() : '';
      var selected = type ? type.value : 'ALL';
      var visible = 0;
      cards.forEach(function(card) {{
        var matchesQuery = !query || (card.dataset.journalSearchText || '').indexOf(query) !== -1;
        var matchesType = selected === 'ALL' || card.dataset.decisionType === selected;
        card.hidden = !(matchesQuery && matchesType);
        if (!card.hidden) visible += 1;
      }});
      if (count) count.textContent = visible + (visible === 1 ? ' decision shown' : ' decisions shown');
    }}
    if (search) search.addEventListener('input', applyFilters);
    if (type) type.addEventListener('change', applyFilters);
    root.querySelectorAll('[data-filter]').forEach(function(button) {{
      button.addEventListener('click', function() {{
        if (type) type.value = button.dataset.filter || 'ALL';
        applyFilters();
      }});
    }});
    if (clear) clear.addEventListener('click', function() {{
      if (search) search.value = '';
      if (type) type.value = 'ALL';
      applyFilters();
      if (search) search.focus();
    }});
    applyFilters();
  }});
}})();
</script></section>'''


def render_strategy_decision_journal_document(journal: Mapping[str, Any]) -> str:
    body = render_strategy_decision_journal(journal)
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Strategy Decision Journal</title>
<style>
body{{font-family:Arial,sans-serif;background:#f5f7fb;color:#101828;margin:0;padding:24px}}.strategy-decision-journal{{max-width:1400px;margin:auto}}
.journal-heading,.decision-card{{background:#fff;border:1px solid #dbe3ef;border-radius:16px;padding:20px;margin-bottom:16px}}
.journal-heading{{display:flex;justify-content:space-between;gap:20px}}.eyebrow,.type{{color:#5b21b6;font-weight:700;font-size:12px}}
.journal-meta span,.status,.decision-type{{display:inline-block;padding:5px 9px;border-radius:999px;background:#eef2ff;margin:3px;font-size:12px;font-weight:700}}
.journal-cross-links,.journal-filters,.journal-search{{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0;align-items:end}}.journal-search label{{display:grid;gap:5px;min-width:210px;flex:1}}.journal-search label span{{font-size:12px;font-weight:700;color:#475467}}.journal-search input,.journal-search select{{width:100%;padding:10px;border:1px solid #cbd5e1;border-radius:9px;background:#fff}}.journal-search strong{{padding:10px;color:#475467}}.journal-cross-links a{{padding:9px 12px;border:1px solid #cbd5e1;background:#fff;border-radius:9px;color:#5b21b6;text-decoration:none;font-weight:700}}.journal-cross-links a[aria-current="page"]{{background:#5b21b6;color:#fff}}button{{padding:9px 14px;border:1px solid #cbd5e1;background:#fff;border-radius:9px}}
.decision-card header{{display:flex;justify-content:space-between}}.pair{{display:flex;align-items:center;gap:16px;margin:12px 0}}.pair span:not(.plus){{background:#f8fafc;border:1px solid #dbe3ef;padding:12px 18px;border-radius:12px}}.pair b{{display:block;font-size:11px;color:#64748b}}
table{{width:100%;border-collapse:collapse;margin-top:12px}}th,td{{border-bottom:1px solid #e5e7eb;padding:10px;text-align:left}}details{{margin-top:14px}}summary{{font-weight:700;cursor:pointer}}.committee-evidence-timeline{{margin-top:18px}}.committee-timeline{{list-style:none;margin:12px 0 0;padding:0 0 0 18px;border-left:3px solid #c4b5fd}}.committee-step{{position:relative;display:grid;grid-template-columns:34px 1fr;gap:10px;margin:0 0 16px -36px}}.committee-sequence{{display:grid;place-items:center;width:30px;height:30px;border-radius:50%;background:#5b21b6;color:#fff;font-weight:800}}.committee-step-content{{background:#f8fafc;border:1px solid #dbe3ef;border-radius:12px;padding:12px}}.committee-step-content header{{display:flex;justify-content:space-between;gap:12px}}.committee-vote{{font-size:12px;font-weight:800;color:#5b21b6}}.committee-step-content dl{{display:flex;flex-wrap:wrap;gap:14px;margin:10px 0}}.committee-step-content dl div{{display:flex;gap:5px}}.committee-step-content dt{{color:#64748b}}.committee-step-content dd{{margin:0;font-weight:700}}
.image-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin-top:14px}}.evidence-image{{margin:0;background:#f8fafc;border:1px solid #dbe3ef;border-radius:12px;overflow:hidden;text-align:left;color:inherit;padding:0;text-decoration:none}}a.evidence-image{{cursor:pointer}}.evidence-image img{{width:100%;height:160px;object-fit:cover;display:block}}.evidence-image span,.evidence-image p{{display:block;padding:10px;margin:0}}.image-unavailable{{height:160px;display:grid;place-items:center;background:#eef2f7;color:#64748b}}.empty,.empty-state{{color:#64748b;padding:18px}}
</style></head><body>{body}</body></html>'''
