from __future__ import annotations

from src.dividend_bot.dividend_strategy_ownership import (
    LEGACY_UNASSIGNED,
    STRATEGY_A,
    STRATEGY_B,
    legacy_unassigned_exit_signal,
    owned_exit_signal,
    resolve_strategy_ownership,
)


def _signals(
    *,
    a_buy: bool = False,
    b_buy: bool = False,
    a_sell: bool = False,
    b_sell: bool = False,
    a_warning: bool = False,
    a_buffered: bool = False,
) -> dict:
    return {
        "strategy_a": {
            "buy_trigger": a_buy,
            "sell_trigger": a_sell,
            "sell_reasons": ["STOCH_OSC_D_CROSSED_ABOVE_K_BELOW_80"] if a_sell else [],
            "exit_warning_active": a_warning,
            "exit_buffered": a_buffered,
            "exit_warning_reasons": ["STOCH_RSI_D_CROSSED_ABOVE_K"] if a_warning else [],
        },
        "strategy_b": {
            "buy_eligible": b_buy,
            "sell_trigger": b_sell,
            "sell_reason": "PRICE_BELOW_EMA20" if b_sell else None,
        },
    }


def test_single_strategy_a_entry_resolves_owner() -> None:
    result = resolve_strategy_ownership(_signals(a_buy=True))
    assert result["resolved"] is True
    assert result["strategy_owner"] == STRATEGY_A
    assert result["entry_allowed_by_ownership"] is True


def test_single_strategy_b_entry_resolves_owner() -> None:
    result = resolve_strategy_ownership(_signals(b_buy=True))
    assert result["resolved"] is True
    assert result["strategy_owner"] == STRATEGY_B
    assert result["entry_allowed_by_ownership"] is True


def test_no_active_strategy_waits_with_reason() -> None:
    result = resolve_strategy_ownership(_signals())
    assert result["resolved"] is False
    assert result["strategy_owner"] is None
    assert result["entry_allowed_by_ownership"] is False
    assert result["reason"] == "NO_ACTIVE_ENTRY_STRATEGY"


def test_both_active_strategies_fail_closed_until_selection_policy_exists() -> None:
    result = resolve_strategy_ownership(_signals(a_buy=True, b_buy=True))
    assert result["resolved"] is False
    assert result["strategy_owner"] is None
    assert result["eligible_strategies"] == [STRATEGY_A, STRATEGY_B]
    assert result["reason"] == "MULTIPLE_ACTIVE_ENTRY_STRATEGIES_REQUIRE_SELECTION_POLICY"
    assert result["entry_allowed_by_ownership"] is False


def test_existing_owner_is_sticky_even_if_other_strategy_now_has_buy_signal() -> None:
    result = resolve_strategy_ownership(_signals(a_buy=False, b_buy=True), existing_owner=STRATEGY_A)
    assert result["strategy_owner"] == STRATEGY_A
    assert result["reason"] == "EXISTING_POSITION_STRATEGY_OWNERSHIP_PRESERVED"


def test_legacy_unassigned_is_not_treated_as_new_entry_owner() -> None:
    result = resolve_strategy_ownership(_signals(), existing_owner=LEGACY_UNASSIGNED)
    assert result["resolved"] is False
    assert result["strategy_owner"] is None
    assert result["entry_allowed_by_ownership"] is False


def test_strategy_a_position_ignores_strategy_b_sell() -> None:
    result = owned_exit_signal(_signals(a_sell=False, b_sell=True), STRATEGY_A)
    assert result["strategy_owner"] == STRATEGY_A
    assert result["sell_trigger"] is False


def test_strategy_b_position_ignores_strategy_a_sell() -> None:
    result = owned_exit_signal(_signals(a_sell=True, b_sell=False), STRATEGY_B)
    assert result["strategy_owner"] == STRATEGY_B
    assert result["sell_trigger"] is False


def test_owner_specific_sell_reason_is_preserved() -> None:
    a_result = owned_exit_signal(_signals(a_sell=True), STRATEGY_A)
    b_result = owned_exit_signal(_signals(b_sell=True), STRATEGY_B)
    assert a_result["sell_trigger"] is True
    assert a_result["sell_reasons"] == ["STOCH_OSC_D_CROSSED_ABOVE_K_BELOW_80"]
    assert a_result["exit_state"] == "SELL_CONFIRMED"
    assert b_result["sell_trigger"] is True
    assert b_result["sell_reasons"] == ["PRICE_BELOW_EMA20"]
    assert b_result["exit_state"] == "SELL_CONFIRMED"


def test_strategy_a_fast_warning_is_preserved_without_authorizing_sell() -> None:
    result = owned_exit_signal(_signals(a_warning=True, a_buffered=True), STRATEGY_A)
    assert result["strategy_owner"] == STRATEGY_A
    assert result["sell_trigger"] is False
    assert result["exit_warning_active"] is True
    assert result["exit_buffered"] is True
    assert result["exit_warning_reasons"] == ["STOCH_RSI_D_CROSSED_ABOVE_K"]
    assert result["exit_state"] == "WARNING_BUFFERED"


def test_strategy_a_hold_has_no_warning_state() -> None:
    result = owned_exit_signal(_signals(), STRATEGY_A)
    assert result["sell_trigger"] is False
    assert result["exit_warning_active"] is False
    assert result["exit_buffered"] is False
    assert result["exit_state"] == "HOLD"


def test_strategy_b_does_not_inherit_strategy_a_warning() -> None:
    result = owned_exit_signal(_signals(a_warning=True, a_buffered=True), STRATEGY_B)
    assert result["sell_trigger"] is False
    assert result["exit_warning_active"] is False
    assert result["exit_buffered"] is False
    assert result["exit_warning_reasons"] == []
    assert result["exit_state"] == "HOLD"


def test_unknown_owner_cannot_generate_sell() -> None:
    result = owned_exit_signal(_signals(a_sell=True, b_sell=True), None)
    assert result["sell_trigger"] is False
    assert result["exit_state"] == "UNKNOWN"
    assert result["reason"] == "STRATEGY_OWNERSHIP_UNKNOWN_FAIL_CLOSED"


def test_legacy_unassigned_requires_both_strategy_sell_confirmations() -> None:
    a_only = owned_exit_signal(_signals(a_sell=True), LEGACY_UNASSIGNED)
    b_only = owned_exit_signal(_signals(b_sell=True), LEGACY_UNASSIGNED)
    assert a_only["sell_trigger"] is False
    assert a_only["exit_state"] == "WARNING_BUFFERED"
    assert a_only["strategy_a_sell_trigger"] is True
    assert a_only["strategy_b_sell_trigger"] is False
    assert b_only["sell_trigger"] is False
    assert b_only["exit_state"] == "WARNING_BUFFERED"
    assert b_only["strategy_a_sell_trigger"] is False
    assert b_only["strategy_b_sell_trigger"] is True


def test_legacy_unassigned_consensus_allows_exit_without_fabricating_a_b_owner() -> None:
    result = legacy_unassigned_exit_signal(_signals(a_sell=True, b_sell=True))
    assert result["strategy_owner"] == LEGACY_UNASSIGNED
    assert result["sell_trigger"] is True
    assert result["exit_state"] == "SELL_CONFIRMED"
    assert result["reason"] == "LEGACY_UNASSIGNED_A_B_EXIT_CONSENSUS"
    assert result["legacy_management_policy"] == "REQUIRE_STRATEGY_A_AND_B_SELL_CONSENSUS"
    assert result["sell_reasons"] == [
        "STOCH_OSC_D_CROSSED_ABOVE_K_BELOW_80",
        "PRICE_BELOW_EMA20",
    ]


def test_legacy_unassigned_preserves_fast_strategy_a_warning() -> None:
    result = owned_exit_signal(
        _signals(a_warning=True, a_buffered=True),
        LEGACY_UNASSIGNED,
    )
    assert result["sell_trigger"] is False
    assert result["exit_state"] == "WARNING_BUFFERED"
    assert result["exit_warning_reasons"] == ["STOCH_RSI_D_CROSSED_ABOVE_K"]
