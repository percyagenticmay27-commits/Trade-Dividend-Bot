from __future__ import annotations

import pytest

from src.dividend_bot.strategy_decision_journal import (
    BROKER_EXECUTION_ENABLED,
    LIVE_TRADING_ENABLED,
    PAPER_TRADE_MODE,
    READ_ONLY,
    DecisionJournalError,
    build_strategy_decision_journal,
)


def _dividend(decision_id: str, timestamp: str) -> dict:
    return {
        "decision_id": decision_id,
        "decision_timestamp": timestamp,
        "strategy_id": "DIVIDEND-001",
        "strategy_kind": "DIVIDEND",
        "decision_type": "SELECT_PAIR",
        "status": "APPROVED",
        "summary": "Selected the highest-ranked NVIDIA income ecosystem pair.",
        "final_rationale": "NVDY and NVDX ranked above qualified alternatives by role.",
        "ecosystem_id": "NVIDIA-INCOME",
        "ecosystem_name": "NVIDIA Income Ecosystem",
        "ecosystem_mode": "PAIR",
        "income_leg": "NVDY",
        "leverage_leg": "NVDX",
        "income_alternatives": ["NVDW"],
        "leverage_alternatives": ["NVDU"],
        "income_leg_reason": "Best qualified income-side evidence among candidates.",
        "leverage_leg_reason": "Best qualified leverage-side evidence among candidates.",
        "pair_compatibility_reason": "Combined income and recovery profile met pair gates.",
        "selection_comparison": [
            {"candidate": "NVDY", "role": "INCOME", "rank": 1},
            {"candidate": "NVDW", "role": "INCOME", "rank": 2},
            {"candidate": "NVDX", "role": "LEVERAGE", "rank": 1},
            {"candidate": "NVDU", "role": "LEVERAGE", "rank": 2},
        ],
        "committee_evidence": [{"committee": "Income", "score": 91}],
        "images": [
            {
                "path": "docs/decisions/2026/08/images/nvidia-pair-scorecard.png",
                "caption": "Income and leverage candidate scorecard",
                "image_type": "SCORECARD",
            }
        ],
    }


def _swing(decision_id: str, timestamp: str) -> dict:
    return {
        "decision_id": decision_id,
        "decision_timestamp": timestamp,
        "strategy_id": "SWING-001",
        "strategy_kind": "SWING",
        "decision_type": "PROMOTE",
        "status": "APPROVED",
        "summary": "Promoted AMD after Swing committee review.",
        "final_rationale": "AMD was the highest qualified Swing opportunity.",
        "symbol": "AMD",
        "committee_rank": 1,
        "opportunity_quality": 87,
        "entry_score": 74,
        "committee_evidence": [{"committee": "Swing Opportunity", "score": 87}],
        "images": [],
    }


def test_dividend_journal_is_newest_first() -> None:
    journal = build_strategy_decision_journal(
        strategy_id="DIVIDEND-001",
        strategy_kind="DIVIDEND",
        strategy_name="Dividend Income Strategy",
        decisions=[
            _dividend("older", "2026-08-01T10:00:00Z"),
            _dividend("newer", "2026-08-01T12:00:00Z"),
        ],
    )
    assert [row["decision_id"] for row in journal["decisions"]] == ["newer", "older"]
    assert journal["sort_order"] == "NEWEST_FIRST"


def test_dividend_decision_preserves_pair_and_role_alternatives() -> None:
    journal = build_strategy_decision_journal(
        strategy_id="DIVIDEND-001",
        strategy_kind="DIVIDEND",
        strategy_name="Dividend Income Strategy",
        decisions=[_dividend("pair", "2026-08-01T12:00:00Z")],
    )
    ecosystem = journal["decisions"][0]["ecosystem"]
    assert ecosystem["income_leg"] == "NVDY"
    assert ecosystem["leverage_leg"] == "NVDX"
    assert ecosystem["income_alternatives"] == ["NVDW"]
    assert ecosystem["leverage_alternatives"] == ["NVDU"]


def test_dividend_pair_rejects_underlying_only_decision() -> None:
    entry = _dividend("bad", "2026-08-01T12:00:00Z")
    entry.pop("income_leg")
    entry["underlying_context"] = {"symbol": "NVDA", "reason": "Strong company"}
    with pytest.raises(DecisionJournalError, match="income_leg is required"):
        build_strategy_decision_journal(
            strategy_id="DIVIDEND-001",
            strategy_kind="DIVIDEND",
            strategy_name="Dividend Income Strategy",
            decisions=[entry],
        )


def test_self_funded_dividend_requires_explicit_reason() -> None:
    entry = _dividend("self", "2026-08-01T12:00:00Z")
    entry["ecosystem_mode"] = "SELF_FUNDED"
    entry["primary_instrument"] = "MSTY"
    entry["alternatives"] = ["MSTX"]
    for field in (
        "income_leg",
        "leverage_leg",
        "income_alternatives",
        "leverage_alternatives",
        "income_leg_reason",
        "leverage_leg_reason",
        "pair_compatibility_reason",
    ):
        entry.pop(field, None)
    with pytest.raises(DecisionJournalError, match="self_funding_reason is required"):
        build_strategy_decision_journal(
            strategy_id="DIVIDEND-001",
            strategy_kind="DIVIDEND",
            strategy_name="Dividend Income Strategy",
            decisions=[entry],
        )


def test_cross_strategy_decision_is_rejected() -> None:
    with pytest.raises(DecisionJournalError, match="Cross-strategy decision rejected"):
        build_strategy_decision_journal(
            strategy_id="SWING-001",
            strategy_kind="SWING",
            strategy_name="Swing Trading Strategy",
            decisions=[_dividend("wrong", "2026-08-01T12:00:00Z")],
        )


def test_swing_journal_contains_only_swing_opportunity_fields() -> None:
    journal = build_strategy_decision_journal(
        strategy_id="SWING-001",
        strategy_kind="SWING",
        strategy_name="Swing Trading Strategy",
        decisions=[_swing("amd", "2026-08-01T12:00:00Z")],
    )
    decision = journal["decisions"][0]
    assert decision["decision_object_type"] == "SWING_OPPORTUNITY"
    assert decision["symbol"] == "AMD"
    assert "ecosystem" not in decision


def test_image_references_are_preserved_for_journal_detail() -> None:
    journal = build_strategy_decision_journal(
        strategy_id="DIVIDEND-001",
        strategy_kind="DIVIDEND",
        strategy_name="Dividend Income Strategy",
        decisions=[_dividend("pair", "2026-08-01T12:00:00Z")],
    )
    image = journal["decisions"][0]["images"][0]
    assert image["path"].endswith("nvidia-pair-scorecard.png")
    assert image["image_type"] == "SCORECARD"


def test_journal_safety_is_locked() -> None:
    assert PAPER_TRADE_MODE is True
    assert LIVE_TRADING_ENABLED is False
    assert BROKER_EXECUTION_ENABLED is False
    assert READ_ONLY is True
