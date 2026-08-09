from __future__ import annotations

import pandas as pd

from src.dividend_bot.dividend_entry_strategy_signals import (
    _cross_above,
    _cross_below,
    _entered_level,
    build_strategy_signals,
)


def _frame(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame({
        "Close": closes,
        "High": [value + 2.0 for value in closes],
        "Low": [value - 2.0 for value in closes],
    })


def test_cross_requires_real_side_change_not_touching() -> None:
    assert _cross_above(40.0, 50.0, 51.0, 50.0) is True
    assert _cross_above(50.0, 50.0, 50.0, 50.0) is False
    assert _cross_below(60.0, 50.0, 49.0, 50.0) is True
    assert _cross_below(50.0, 50.0, 50.0, 50.0) is False


def test_entered_level_requires_movement_from_below() -> None:
    assert _entered_level(49.9, 50.0, 50.0) is True
    assert _entered_level(50.0, 50.0, 50.0) is False
    assert _entered_level(81.0, 82.0, 80.0) is False


def test_strategy_b_buy_requires_price_above_ema20_above_ema50() -> None:
    closes = [100.0 + index * 0.5 for index in range(90)]
    evidence = build_strategy_signals(_frame(closes))
    strategy_b = evidence["strategy_b"]
    assert evidence["available"] is True
    assert strategy_b["price"] > strategy_b["ema20"] > strategy_b["ema50"]
    assert strategy_b["buy_eligible"] is True
    assert strategy_b["sell_trigger"] is False
    assert strategy_b["buy_reason"] == "PRICE_ABOVE_EMA20_ABOVE_EMA50"


def test_strategy_b_sell_when_price_below_ema20() -> None:
    closes = [100.0 + index * 0.4 for index in range(89)] + [90.0]
    evidence = build_strategy_signals(_frame(closes))
    strategy_b = evidence["strategy_b"]
    assert strategy_b["price"] < strategy_b["ema20"]
    assert strategy_b["sell_trigger"] is True
    assert strategy_b["sell_reason"] == "PRICE_BELOW_EMA20"


def test_strategy_a_publishes_exact_indicator_settings() -> None:
    closes = [100.0 + index * 0.25 for index in range(90)]
    evidence = build_strategy_signals(_frame(closes))
    strategy_a = evidence["strategy_a"]
    assert strategy_a["stoch_oscillator"]["settings"] == "14,3,3"
    assert strategy_a["stoch_rsi"]["settings"] == "14,7,3,3"
    assert "entry_armed" in strategy_a
    assert "buy_trigger" in strategy_a
    assert "sell_trigger" in strategy_a
