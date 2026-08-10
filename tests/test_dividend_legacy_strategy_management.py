from __future__ import annotations

from src.dividend_bot.dividend_legacy_strategy_management import mark_legacy_unassigned_open_positions
from src.dividend_bot.dividend_strategy_ownership import LEGACY_UNASSIGNED


def test_marks_open_preownership_pair_without_assigning_strategy_a_or_b() -> None:
    state = {
        "pairs": {
            "AMDW / AMDL": {
                "a_shares": 4.8,
                "b_shares": 3.1,
                "strategy_owner": None,
            }
        }
    }
    migrated, changes = mark_legacy_unassigned_open_positions(state)
    row = migrated["pairs"]["AMDW / AMDL"]
    assert row["strategy_owner"] == LEGACY_UNASSIGNED
    assert row["a_strategy_owner"] == LEGACY_UNASSIGNED
    assert row["b_strategy_owner"] == LEGACY_UNASSIGNED
    assert row["strategy_ownership_source"] == "LEGACY_PRE_OWNERSHIP_POSITION"
    assert changes[0]["management_policy"] == "REQUIRE_STRATEGY_A_AND_B_SELL_CONSENSUS"
    assert state["pairs"]["AMDW / AMDL"]["strategy_owner"] is None


def test_does_not_rewrite_valid_strategy_owned_position() -> None:
    state = {
        "pairs": {
            "AAA / BBB": {
                "a_shares": 1.0,
                "b_shares": 1.0,
                "strategy_owner": "STRATEGY_A",
                "strategy_ownership_source": "QUALIFIED_ENTRY_GATE",
            }
        }
    }
    migrated, changes = mark_legacy_unassigned_open_positions(state)
    assert changes == []
    assert migrated["pairs"]["AAA / BBB"]["strategy_owner"] == "STRATEGY_A"


def test_does_not_mark_closed_or_sgov_only_pair() -> None:
    state = {
        "pairs": {
            "AAA / BBB": {
                "a_shares": 0.0,
                "b_shares": 0.0,
                "sgov_balance": 100.0,
            }
        }
    }
    migrated, changes = mark_legacy_unassigned_open_positions(state)
    assert changes == []
    assert "strategy_owner" not in migrated["pairs"]["AAA / BBB"]


def test_does_not_override_explicit_unresolved_gate_state() -> None:
    state = {
        "pairs": {
            "AAA / BBB": {
                "a_shares": 1.0,
                "b_shares": 1.0,
                "strategy_owner": None,
                "strategy_ownership_source": "ENTRY_GATE_UNRESOLVED",
            }
        }
    }
    migrated, changes = mark_legacy_unassigned_open_positions(state)
    assert changes == []
    assert migrated["pairs"]["AAA / BBB"]["strategy_owner"] is None
