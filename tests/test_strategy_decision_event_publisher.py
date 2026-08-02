from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.dividend_bot.strategy_decision_event_publisher import (
    DecisionEventPublicationError,
    publish_strategy_decision_event,
)


def _dividend_event(decision_id: str = "DIV-1") -> dict:
    return {
        "decision_id": decision_id,
        "decision_timestamp": "2026-08-01T20:00:00Z",
        "strategy_id": "DIVIDEND-001",
        "strategy_kind": "DIVIDEND",
        "decision_type": "SELECT_PAIR",
        "status": "APPROVED",
        "summary": "Selected the highest-qualified income and leverage pair.",
        "final_rationale": "NVDY and NVDX provided the best recorded pair compatibility.",
        "ecosystem_id": "NVIDIA-INCOME",
        "ecosystem_name": "NVIDIA Income Ecosystem",
        "ecosystem_mode": "PAIR",
        "income_leg": "NVDY",
        "leverage_leg": "NVDX",
        "income_alternatives": ["NVDW"],
        "leverage_alternatives": ["NVDU"],
        "income_leg_reason": "Best reported income-side evidence.",
        "leverage_leg_reason": "Best reported leverage-side evidence.",
        "pair_compatibility_reason": "The two selected legs had the strongest combined evidence.",
        "committee_evidence": [],
        "images": [],
    }


def _swing_event(decision_id: str = "SW-1") -> dict:
    return {
        "decision_id": decision_id,
        "decision_timestamp": "2026-08-01T21:00:00Z",
        "strategy_id": "SWING-001",
        "strategy_kind": "SWING",
        "decision_type": "ADD_TO_WATCHLIST",
        "status": "APPROVED",
        "summary": "Added AMD to the Swing watchlist.",
        "final_rationale": "AMD ranked highest among the recorded Swing candidates.",
        "symbol": "AMD",
        "committee_rank": 1,
        "opportunity_quality": 88,
        "entry_score": 71,
        "alternatives": [{"symbol": "NVDA", "rank": 2}],
        "committee_evidence": [],
        "images": [],
    }


def test_publishes_dividend_event_to_strategy_source(tmp_path: Path) -> None:
    summary = publish_strategy_decision_event(_dividend_event(), results_dir=tmp_path)
    payload = json.loads((tmp_path / "dividend_strategy_decisions.json").read_text())
    assert summary["publication_status"] == "PUBLISHED"
    assert payload["decision_count"] == 1
    assert payload["decisions"][0]["ecosystem"]["income_leg"] == "NVDY"


def test_publishes_swing_event_to_separate_source(tmp_path: Path) -> None:
    publish_strategy_decision_event(_swing_event(), results_dir=tmp_path)
    assert (tmp_path / "swing_strategy_decisions.json").is_file()
    assert not (tmp_path / "dividend_strategy_decisions.json").exists()


def test_duplicate_identical_event_is_idempotent(tmp_path: Path) -> None:
    publish_strategy_decision_event(_swing_event(), results_dir=tmp_path)
    summary = publish_strategy_decision_event(_swing_event(), results_dir=tmp_path)
    assert summary["publication_status"] == "ALREADY_PUBLISHED"
    assert summary["decision_count"] == 1


def test_conflicting_duplicate_is_rejected(tmp_path: Path) -> None:
    publish_strategy_decision_event(_swing_event(), results_dir=tmp_path)
    changed = _swing_event()
    changed["summary"] = "Changed summary"
    with pytest.raises(DecisionEventPublicationError, match="Conflicting duplicate"):
        publish_strategy_decision_event(changed, results_dir=tmp_path)


def test_explicit_replace_updates_existing_event(tmp_path: Path) -> None:
    publish_strategy_decision_event(_swing_event(), results_dir=tmp_path)
    changed = _swing_event()
    changed["summary"] = "Updated recorded summary"
    summary = publish_strategy_decision_event(
        changed, results_dir=tmp_path, replace_existing=True
    )
    assert summary["publication_status"] == "REPLACED"


def test_cross_strategy_or_unknown_strategy_is_rejected(tmp_path: Path) -> None:
    event = _swing_event()
    event["strategy_id"] = "OPTIONS-001"
    with pytest.raises(DecisionEventPublicationError, match="Unsupported strategy_id"):
        publish_strategy_decision_event(event, results_dir=tmp_path)


def test_newest_event_is_written_first(tmp_path: Path) -> None:
    older = _swing_event("SW-OLD")
    older["decision_timestamp"] = "2026-08-01T18:00:00Z"
    publish_strategy_decision_event(older, results_dir=tmp_path)
    publish_strategy_decision_event(_swing_event("SW-NEW"), results_dir=tmp_path)
    payload = json.loads((tmp_path / "swing_strategy_decisions.json").read_text())
    assert [row["decision_id"] for row in payload["decisions"]] == ["SW-NEW", "SW-OLD"]


def test_safety_metadata_is_locked(tmp_path: Path) -> None:
    summary = publish_strategy_decision_event(_dividend_event(), results_dir=tmp_path)
    assert summary["paper_trade_mode"] is True
    assert summary["live_trading_enabled"] is False
    assert summary["broker_execution_enabled"] is False
    assert summary["capital_movement_enabled"] is False
