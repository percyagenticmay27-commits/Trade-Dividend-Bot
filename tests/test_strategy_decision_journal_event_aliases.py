from __future__ import annotations

import json
from pathlib import Path

from src.dividend_bot.strategy_decision_event_publisher import (
    publish_strategy_decision_event,
)
from src.dividend_bot.strategy_decision_journal import build_strategy_decision_journal
from src.dividend_bot.strategy_decision_journal_generator import (
    generate_all_strategy_decision_journals,
)


def _alias_dividend_event() -> dict:
    return {
        "decision_id": "DIV-ALIAS-1",
        "decision_timestamp": "2026-08-01T22:00:00Z",
        "strategy_id": "DIVIDEND-001",
        "strategy_kind": "DIVIDEND",
        "decision_type": "SELECT_PAIR",
        "status": "APPROVED",
        "summary": "Selected an NVIDIA income ecosystem pair.",
        "final_rationale": "The selected pair beat the recorded same-ecosystem alternatives.",
        "ecosystem": "NVDA",
        "ecosystem_node": "PAIR",
        "income_leg": "NVDY",
        "leverage_leg": "NVDX",
        "income_alternatives": ["NVDW"],
        "leverage_alternatives": ["NVDU"],
        "income_leg_reason": "NVDY had the best reported income evidence.",
        "leverage_leg_reason": "NVDX had the best reported leverage evidence.",
        "pair_compatibility_reason": "The pair had the best combined evidence.",
        "selection_comparison": [],
        "committee_evidence": [],
        "images": [],
    }


def test_alias_fields_normalize_to_canonical_ecosystem() -> None:
    journal = build_strategy_decision_journal(
        strategy_id="DIVIDEND-001",
        strategy_kind="DIVIDEND",
        strategy_name="Dividend Income Strategy",
        decisions=[_alias_dividend_event()],
    )

    ecosystem = journal["decisions"][0]["ecosystem"]
    assert ecosystem["ecosystem_id"] == "NVDA"
    assert ecosystem["ecosystem_name"] == "NVDA"
    assert ecosystem["mode"] == "PAIR"
    assert ecosystem["income_leg"] == "NVDY"
    assert ecosystem["leverage_leg"] == "NVDX"


def test_published_alias_event_populates_generated_journal(tmp_path: Path) -> None:
    publish_strategy_decision_event(_alias_dividend_event(), results_dir=tmp_path)
    summary = generate_all_strategy_decision_journals(results_dir=tmp_path)

    payload = json.loads(
        Path(summary["paths"]["dividend_decision_journal"]).read_text(
            encoding="utf-8"
        )
    )
    assert payload["decision_count"] == 1
    ecosystem = payload["decisions"][0]["ecosystem"]
    assert ecosystem == {
        "ecosystem_id": "NVDA",
        "ecosystem_name": "NVDA",
        "income_alternatives": ["NVDW"],
        "income_leg": "NVDY",
        "income_leg_reason": "NVDY had the best reported income evidence.",
        "leverage_alternatives": ["NVDU"],
        "leverage_leg": "NVDX",
        "leverage_leg_reason": "NVDX had the best reported leverage evidence.",
        "mode": "PAIR",
        "pair_compatibility_reason": "The pair had the best combined evidence.",
    }
