from __future__ import annotations

import json
from pathlib import Path

from src.dividend_bot.strategy_decision_event_publisher import publish_strategy_decision_event
from src.dividend_bot.strategy_decision_journal_generator import (
    generate_all_strategy_decision_journals,
)


def test_published_swing_event_populates_generated_journal(tmp_path: Path) -> None:
    event = {
        "decision_id": "SWING-PIPELINE-1",
        "decision_timestamp": "2026-08-01T21:30:00Z",
        "strategy_id": "SWING-001",
        "strategy_kind": "SWING",
        "decision_type": "ADD_TO_WATCHLIST",
        "status": "APPROVED",
        "summary": "AMD promoted by the Swing committee.",
        "final_rationale": "AMD ranked first using recorded Swing evidence.",
        "symbol": "AMD",
        "committee_rank": 1,
        "opportunity_quality": 88,
        "entry_score": 72,
        "alternatives": [{"symbol": "NVDA", "rank": 2}],
        "committee_evidence": [{"committee": "Opportunity Quality", "score": 88}],
        "images": [],
    }
    publish_strategy_decision_event(event, results_dir=tmp_path)
    summary = generate_all_strategy_decision_journals(results_dir=tmp_path)

    swing_path = Path(summary["paths"]["swing_decision_journal"])
    payload = json.loads(swing_path.read_text(encoding="utf-8"))
    assert payload["decision_count"] == 1
    assert payload["decisions"][0]["decision_id"] == "SWING-PIPELINE-1"
    assert payload["decisions"][0]["symbol"] == "AMD"
    assert payload["journal_scope"] == "SELECTED_STRATEGY_ONLY"


def test_published_dividend_pair_populates_generated_journal(tmp_path: Path) -> None:
    event = {
        "decision_id": "DIV-PIPELINE-1",
        "decision_timestamp": "2026-08-01T22:00:00Z",
        "strategy_id": "DIVIDEND-001",
        "strategy_kind": "DIVIDEND",
        "decision_type": "SELECT_PAIR",
        "status": "APPROVED",
        "summary": "Selected an NVIDIA income ecosystem pair.",
        "final_rationale": "The selected pair beat the recorded same-ecosystem alternatives.",
        "ecosystem_id": "NVIDIA-INCOME",
        "ecosystem_name": "NVIDIA Income Ecosystem",
        "ecosystem_mode": "PAIR",
        "income_leg": "NVDY",
        "leverage_leg": "NVDX",
        "income_alternatives": ["NVDW"],
        "leverage_alternatives": ["NVDU"],
        "income_leg_reason": "NVDY had the best reported income evidence.",
        "leverage_leg_reason": "NVDX had the best reported leverage evidence.",
        "pair_compatibility_reason": "The pair had the best combined evidence.",
        "selection_comparison": [],
        "committee_evidence": [],
        "images": [{"path": "docs/decisions/2026/08/images/nvidia-pair.png", "caption": "NVIDIA ecosystem pair comparison", "image_type": "PAIR_COMPARISON"}],
    }
    publish_strategy_decision_event(event, results_dir=tmp_path)
    summary = generate_all_strategy_decision_journals(results_dir=tmp_path)

    payload = json.loads(
        Path(summary["paths"]["dividend_decision_journal"]).read_text(encoding="utf-8")
    )
    decision = payload["decisions"][0]
    assert decision["ecosystem"]["income_leg"] == "NVDY"
    assert decision["ecosystem"]["leverage_leg"] == "NVDX"
    assert decision["images"][0]["image_type"] == "PAIR_COMPARISON"
