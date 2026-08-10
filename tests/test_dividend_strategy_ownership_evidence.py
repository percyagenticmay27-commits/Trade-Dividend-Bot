from __future__ import annotations

from src.dividend_bot.dividend_strategy_ownership_evidence import (
    build_strategy_ownership_index,
    enrich_holdings_with_strategy_ownership,
    enrich_lifecycle_with_strategy_ownership,
)


def _state() -> dict:
    return {
        "pairs": {
            "AAA / BBB": {
                "strategy_owner": "STRATEGY_A",
                "a_strategy_owner": "STRATEGY_A",
                "b_strategy_owner": "STRATEGY_A",
                "strategy_ownership_source": "QUALIFIED_ENTRY_GATE",
            },
            "CCC / DDD": {
                "strategy_owner": None,
                "a_strategy_owner": None,
                "b_strategy_owner": None,
                "strategy_ownership_source": "CLOSED_TO_SGOV",
                "last_exit_strategy_owner": "STRATEGY_B",
                "last_exit_strategy_reasons": ["PRICE_BELOW_EMA20"],
            },
        }
    }


def test_index_normalizes_current_and_last_exit_ownership() -> None:
    index = build_strategy_ownership_index(_state())
    assert index["AAA"]["strategy_owner"] == "STRATEGY_A"
    assert index["BBB"]["entry_method"] == "STRATEGY_A"
    assert index["CCC"]["strategy_owner"] is None
    assert index["CCC"]["last_exit_strategy_owner"] == "STRATEGY_B"
    assert index["CCC"]["last_exit_reason"] == "PRICE_BELOW_EMA20"


def test_current_holdings_receive_persisted_entry_method() -> None:
    rows = enrich_holdings_with_strategy_ownership(
        [{"symbol": "AAA", "position_status": "OPEN"}, {"symbol": "SGOV", "sleeve": "RESERVE"}],
        _state(),
    )
    by_symbol = {row["symbol"]: row for row in rows}
    assert by_symbol["AAA"]["strategy_owner"] == "STRATEGY_A"
    assert by_symbol["AAA"]["entry_method"] == "STRATEGY_A"
    assert by_symbol["AAA"]["strategy_ownership_source"] == "QUALIFIED_ENTRY_GATE"
    assert "strategy_owner" not in by_symbol["SGOV"]


def test_historical_lifecycle_receives_owner_controlled_exit_evidence() -> None:
    rows = enrich_lifecycle_with_strategy_ownership(
        [{
            "symbol": "CCC",
            "lifecycle_status": "PARKED_IN_SGOV",
            "is_current_holding": False,
            "last_exit_action": "PAPER_SELL_TO_SGOV",
        }],
        _state(),
    )
    row = rows[0]
    assert row["entry_method"] == "STRATEGY_B"
    assert row["last_exit_strategy_owner"] == "STRATEGY_B"
    assert row["exit_method"] == "STRATEGY_B"
    assert row["last_exit_strategy_reasons"] == ["PRICE_BELOW_EMA20"]
    assert row["last_exit_reason"] == "PRICE_BELOW_EMA20"
    assert row["strategy_exit_evidence_source"] == "paper_state.json"


def test_missing_or_invalid_owner_is_not_fabricated() -> None:
    state = {"pairs": {"AAA / BBB": {"strategy_owner": "UNKNOWN"}}}
    index = build_strategy_ownership_index(state)
    assert index["AAA"]["strategy_owner"] is None
    assert index["BBB"]["entry_method"] is None
