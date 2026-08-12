from __future__ import annotations

import pytest

from src.dividend_bot.strategy_decision_journal_renderer import (
    render_strategy_decision_journal,
    render_strategy_decision_journal_document,
)


def _dividend_journal():
    return {
        "strategy_id": "DIVIDEND-001",
        "strategy_name": "Dividend Income Strategy",
        "strategy_type": "DIVIDEND",
        "paper_trade_mode": True,
        "read_only": True,
        "decisions": [
            {
                "strategy_id": "DIVIDEND-001",
                "decision_timestamp": "2026-07-31T15:00:00Z",
                "decision_type": "SELECT_PAIR",
                "status": "APPROVED",
                "ecosystem_name": "AMD Income Ecosystem",
                "income_leg": "AMDY",
                "leverage_leg": "AMDL",
                "alternatives": ["AMDW", "AMZU"],
                "final_rationale": "Best income and leverage compatibility.",
                "committee_evidence": [],
                "images": [],
            },
            {
                "strategy_id": "DIVIDEND-001",
                "decision_timestamp": "2026-08-01T15:00:00Z",
                "decision_type": "REVIEW_PAIR",
                "status": "MONITORING",
                "ecosystem_name": "NVIDIA Income Ecosystem",
                "income_leg": "NVDY",
                "leverage_leg": "NVDX",
                "alternatives": ["NVDW", "NVDU"],
                "final_rationale": "NVDY beat NVDW and NVDX beat NVDU.",
                "committee_evidence": [
                    {
                        "committee": "Income Committee",
                        "score": 91,
                        "confidence": 88,
                        "vote": "APPROVE",
                        "evidence_summary": "Higher income quality.",
                        "evidence_status": "AVAILABLE",
                    }
                ],
                "images": [
                    {
                        "path": "images/nvdy-nvdx.png",
                        "caption": "Income and leverage comparison",
                        "image_type": "PAIR_COMPARISON",
                    }
                ],
            },
        ],
    }


def _swing_journal():
    return {
        "strategy_id": "SWING-001",
        "strategy_name": "Swing Trading Strategy",
        "strategy_type": "SWING",
        "decisions": [
            {
                "strategy_id": "SWING-001",
                "decision_timestamp": "2026-08-01T12:00:00Z",
                "decision_type": "ADD_TO_WATCHLIST",
                "symbol": "AMD",
                "committee_rank": 2,
                "final_rationale": "Strong evidence with entry pending.",
            }
        ],
    }


def test_dividend_renders_ecosystem_pair_and_alternatives():
    html = render_strategy_decision_journal(_dividend_journal())
    assert "NVIDIA Income Ecosystem" in html
    assert "NVDY" in html
    assert "NVDX" in html
    assert "NVDW, NVDU" in html
    assert "ECOSYSTEM PAIR" in html


def test_entries_are_newest_first():
    html = render_strategy_decision_journal(_dividend_journal())
    assert html.index("NVIDIA Income Ecosystem") < html.index("AMD Income Ecosystem")


def test_swing_renders_opportunity_not_dividend_pair():
    html = render_strategy_decision_journal(_swing_journal())
    assert "SWING OPPORTUNITY" in html
    assert "AMD" in html
    assert "ECOSYSTEM PAIR" not in html


def test_rejects_cross_strategy_entry():
    journal = _swing_journal()
    journal["decisions"][0]["strategy_id"] = "DIVIDEND-001"
    with pytest.raises(ValueError, match="different strategy"):
        render_strategy_decision_journal(journal)


def test_renders_committee_evidence_and_image_gallery():
    html = render_strategy_decision_journal(_dividend_journal())
    assert "Income Committee" in html
    assert "Higher income quality" in html
    assert "images/nvdy-nvdx.png" in html
    assert "PAIR_COMPARISON" in html


def test_empty_journal_is_safe_and_explanatory():
    journal = {
        "strategy_id": "SWING-001",
        "strategy_name": "Swing Trading Strategy",
        "strategy_type": "SWING",
        "decisions": [],
    }
    html = render_strategy_decision_journal(journal)
    assert "No decisions reported for this strategy" in html
    assert "SWING-001" in html


def test_document_is_standalone_read_only_html():
    html = render_strategy_decision_journal_document(_dividend_journal())
    assert html.startswith("<!doctype html>")
    assert "PAPER ONLY" in html
    assert "READ ONLY" in html
    assert "<style>" in html
    assert "applyFilters" in html


def test_renderer_escapes_untrusted_text():
    journal = _swing_journal()
    journal["decisions"][0]["final_rationale"] = "<script>alert(1)</script>"
    html = render_strategy_decision_journal(journal)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_renders_stock_pair_search_and_working_filter_controls():
    html = render_strategy_decision_journal(_dividend_journal())

    assert 'type="search"' in html
    assert "Search stock, pair, reason, or decision" in html
    assert 'data-journal-type' in html
    assert 'data-journal-clear' in html
    assert 'data-filter="SELL"' in html
    assert 'data-filter="HOLD"' in html
    assert 'data-decision-type="REVIEW_PAIR"' in html
    assert 'data-journal-search-text=' in html
    assert "<script>" not in html
    assert ">2 decisions shown</strong>" in html


def test_search_index_contains_pair_symbols_and_rationale():
    html = render_strategy_decision_journal(_dividend_journal())

    marker = 'data-journal-search-text="'
    start = html.index(marker) + len(marker)
    search_text = html[start:html.index('"', start)]
    assert "nvidia income ecosystem" in search_text
    assert "nvdy" in search_text
    assert "nvdx" in search_text
    assert "higher income quality" in search_text


def test_renders_pair_lifecycle_overview_from_recorded_evidence():
    journal = _dividend_journal()
    html = render_strategy_decision_journal(journal)

    assert "Pair Lifecycle Overview" in html
    assert "Earliest recorded strategy" in html
    assert "Current evidence owner" in html
    assert "Latest score" in html
    assert "Latest confidence" in html
    assert "Why it is at this stage" in html
    assert 'data-lifecycle-search="NVDY / NVDX"' in html


def test_lifecycle_overview_groups_multiple_events_for_same_pair():
    journal = _dividend_journal()
    journal["decisions"].append({
        "strategy_id": "DIVIDEND-001",
        "decision_timestamp": "2026-08-02T15:00:00Z",
        "decision_type": "HOLD",
        "status": "MONITOR",
        "ecosystem_name": "NVIDIA Income Ecosystem",
        "income_leg": "NVDY",
        "leverage_leg": "NVDX",
        "final_rationale": "The current exit warning remains buffered.",
        "committee_evidence": [{
            "engine": "STRATEGY_A",
            "score": 74,
            "confidence": "HIGH",
            "evidence_status": "AVAILABLE",
        }],
    })

    html = render_strategy_decision_journal(journal)

    overview_end = html.index('<div class="journal-search"')
    overview = html[:overview_end]
    assert overview.count("<h3>NVDY / NVDX</h3>") == 1
    assert "SELECT_PAIR, REVIEW_PAIR" not in overview
    assert "REVIEW_PAIR, HOLD" in overview
    assert "74" in overview
    assert "HIGH" in overview
