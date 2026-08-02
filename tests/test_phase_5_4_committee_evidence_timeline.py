from __future__ import annotations

from src.dividend_bot.strategy_decision_journal_renderer import (
    render_strategy_decision_journal,
    render_strategy_decision_journal_document,
)


def _journal(rows: list[dict]) -> dict:
    return {
        "strategy_id": "SWING-001",
        "strategy_name": "Swing Trading Strategy",
        "strategy_kind": "SWING",
        "decisions": [
            {
                "decision_id": "SWING-DECISION-1",
                "strategy_id": "SWING-001",
                "decision_timestamp": "2026-08-02T12:00:00Z",
                "decision_type": "ADD_TO_WATCHLIST",
                "status": "RECORDED",
                "symbol": "AMD",
                "committee_rank": 1,
                "final_rationale": "Committee evidence supports monitoring AMD.",
                "alternatives": [],
                "committee_evidence": rows,
                "images": [],
            }
        ],
    }


def _committees() -> list[dict]:
    return [
        {
            "committee": "Discovery Committee",
            "score": 94,
            "confidence": 91,
            "vote": "ADVANCE",
            "evidence_status": "AVAILABLE",
            "evidence_summary": "Highest evidence-backed discovery rank.",
        },
        {
            "committee": "Risk Committee",
            "score": 82,
            "confidence": 88,
            "vote": "APPROVE",
            "evidence_status": "AVAILABLE",
            "evidence_summary": "Paper allocation remains within limits.",
        },
    ]


def test_timeline_renders_committee_steps_in_source_order() -> None:
    value = render_strategy_decision_journal(_journal(_committees()))

    assert "Committee Evidence Timeline" in value
    assert value.index("Discovery Committee") < value.index("Risk Committee")
    assert 'aria-label="Committee step 1"' in value
    assert 'aria-label="Committee step 2"' in value


def test_timeline_renders_score_confidence_vote_status_and_rationale() -> None:
    value = render_strategy_decision_journal(_journal(_committees()))

    assert "94" in value
    assert "91" in value
    assert "ADVANCE" in value
    assert "AVAILABLE" in value
    assert "Highest evidence-backed discovery rank." in value


def test_timeline_is_scoped_to_decision_id() -> None:
    value = render_strategy_decision_journal(_journal(_committees()))

    assert 'data-committee-decision="SWING-DECISION-1"' in value


def test_empty_committee_timeline_is_explicit() -> None:
    value = render_strategy_decision_journal(_journal([]))

    assert "No committee evidence reported for this decision." in value
    assert "committee-timeline empty" in value


def test_existing_committee_table_remains_available() -> None:
    value = render_strategy_decision_journal(_journal(_committees()))

    assert "Committee scores and evidence table" in value
    assert "<table>" in value
    assert "<th>Committee</th>" in value


def test_timeline_escapes_untrusted_committee_evidence() -> None:
    rows = _committees()
    rows[0]["evidence_summary"] = "<script>alert(1)</script>"

    value = render_strategy_decision_journal(_journal(rows))

    assert "<script>alert(1)</script>" not in value
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in value


def test_standalone_document_contains_timeline_styles() -> None:
    value = render_strategy_decision_journal_document(_journal(_committees()))

    assert ".committee-timeline" in value
    assert ".committee-step" in value
    assert ".committee-sequence" in value
