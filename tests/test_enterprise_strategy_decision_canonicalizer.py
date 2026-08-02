from __future__ import annotations

from copy import deepcopy

from src.dividend_bot.enterprise_strategy_decision_canonicalizer import (
    BROKER_EXECUTION_ENABLED,
    CAPITAL_MOVEMENT_ENABLED,
    LIVE_TRADING_ENABLED,
    PAPER_TRADE_MODE,
    canonicalize_strategy_decision_event,
)
from src.dividend_bot.strategy_decision_journal import normalize_decision


def _raw_dividend() -> dict:
    return {
        "decision_id": "DIV-CANON-1",
        "decision_timestamp": "2026-08-01T22:00:00Z",
        "strategy_id": "DIVIDEND-001",
        "strategy_kind": "DIVIDEND",
        "decision_type": "SELECT_PAIR",
        "status": "APPROVED",
        "summary": "Selected NVIDIA ecosystem pair.",
        "final_rationale": "The pair beat the recorded alternatives.",
        "ecosystem": "NVIDIA-INCOME",
        "ecosystem_node": "PAIR",
        "income_leg": "NVDY",
        "leverage_leg": "NVDX",
        "income_alternatives": ["NVDW"],
        "leverage_alternatives": ["NVDU"],
        "income_leg_reason": "Best recorded income evidence.",
        "leverage_leg_reason": "Best recorded leverage evidence.",
        "pair_compatibility_reason": "Best combined evidence.",
        "committee_evidence": [],
        "images": [],
    }


def test_compact_dividend_aliases_become_canonical_fields() -> None:
    canonical = canonicalize_strategy_decision_event(_raw_dividend())
    assert canonical["ecosystem_id"] == "NVIDIA-INCOME"
    assert canonical["ecosystem_name"] == "NVIDIA-INCOME"
    assert canonical["ecosystem_mode"] == "PAIR"
    assert canonical["income_leg"] == "NVDY"


def test_already_normalized_dividend_record_is_idempotent() -> None:
    first = normalize_decision(
        _raw_dividend(), strategy_id="DIVIDEND-001", strategy_kind="DIVIDEND"
    )
    second = normalize_decision(
        first, strategy_id="DIVIDEND-001", strategy_kind="DIVIDEND"
    )
    assert second == first
    assert second["ecosystem"]["income_leg"] == "NVDY"
    assert second["ecosystem"]["leverage_leg"] == "NVDX"


def test_swing_payload_is_not_rewritten() -> None:
    event = {
        "strategy_id": "SWING-001",
        "strategy_kind": "SWING",
        "symbol": "AMD",
        "entry_score": 72,
    }
    original = deepcopy(event)
    canonical = canonicalize_strategy_decision_event(event)
    assert canonical == original
    assert canonical is not event


def test_canonicalizer_does_not_mutate_input() -> None:
    event = _raw_dividend()
    original = deepcopy(event)
    canonicalize_strategy_decision_event(event)
    assert event == original


def test_safety_metadata_is_locked() -> None:
    assert PAPER_TRADE_MODE is True
    assert LIVE_TRADING_ENABLED is False
    assert BROKER_EXECUTION_ENABLED is False
    assert CAPITAL_MOVEMENT_ENABLED is False
