from __future__ import annotations

import pandas as pd

from src.dividend_bot.dividend_entry_strategy_signals import (
    _cross_above,
    _cross_below,
    _entered_level,
    build_strategy_signals,
)


def _frame(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"Close": closes, "High": [v + 2.0 for v in closes], "Low": [v - 2.0 for v in closes]})


def _patched(monkeypatch, *, osc_k, osc_d, rsi, srsi_k, srsi_d):
    import src.dividend_bot.dividend_entry_strategy_signals as signals
    monkeypatch.setattr(signals, "_stochastic_oscillator", lambda _frame: (pd.Series(osc_k), pd.Series(osc_d)))
    monkeypatch.setattr(signals, "_stochastic_rsi", lambda _close: (pd.Series(rsi), pd.Series(srsi_k), pd.Series(srsi_d)))
    return build_strategy_signals(_frame([100.0 + i * 0.1 for i in range(90)]))["strategy_a"]


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
    evidence = build_strategy_signals(_frame([100.0 + i * 0.5 for i in range(90)]))["strategy_b"]
    assert evidence["price"] > evidence["ema20"] > evidence["ema50"]
    assert evidence["buy_eligible"] is True
    assert evidence["sell_trigger"] is False


def test_strategy_b_sell_when_price_below_ema20() -> None:
    evidence = build_strategy_signals(_frame([100.0 + i * 0.4 for i in range(89)] + [90.0]))["strategy_b"]
    assert evidence["price"] < evidence["ema20"]
    assert evidence["sell_trigger"] is True


def test_strategy_a_publishes_exact_indicator_settings() -> None:
    strategy_a = build_strategy_signals(_frame([100.0 + i * 0.25 for i in range(90)]))["strategy_a"]
    assert strategy_a["stoch_oscillator"]["settings"] == "14,3,3"
    assert strategy_a["stoch_rsi"]["settings"] == "14,7,3,3"
    assert "sell_warning" in strategy_a
    assert "exit_buffer_active" in strategy_a


def test_strategy_a_buy_does_not_require_fresh_stoch_rsi_cross(monkeypatch) -> None:
    strategy_a = _patched(monkeypatch,
        osc_k=[60.0]*90, osc_d=[55.0]*90, rsi=[55.0]*90,
        srsi_k=[60.0]*88+[65.0,70.0], srsi_d=[50.0]*90)
    assert strategy_a["entry_armed"] is True
    assert strategy_a["stoch_rsi"]["k_above_d"] is True
    assert strategy_a["stoch_rsi"]["k_rising"] is True
    assert "STOCH_RSI_K_CROSSED_ABOVE_D" not in strategy_a["buy_reasons"]
    assert strategy_a["buy_trigger"] is True


def test_strategy_a_rsi_above_50_keeps_mechanism_armed(monkeypatch) -> None:
    strategy_a = _patched(monkeypatch,
        osc_k=[45.0]*90, osc_d=[50.0]*90, rsi=[60.0]*90,
        srsi_k=[65.0]*88+[68.0,72.0], srsi_d=[55.0]*90)
    assert strategy_a["entry_armed"] is True
    assert "RSI14_AT_OR_ABOVE_50" in strategy_a["arming_reasons"]
    assert strategy_a["buy_trigger"] is True


def test_strategy_a_oscillator_arm_requires_both_lines_at_or_above_50(monkeypatch) -> None:
    strategy_a = _patched(monkeypatch,
        osc_k=[55.0]*90, osc_d=[49.0]*90, rsi=[45.0]*90,
        srsi_k=[60.0]*88+[65.0,70.0], srsi_d=[50.0]*90)
    assert strategy_a["entry_armed"] is False
    assert strategy_a["buy_trigger"] is False


def test_strategy_a_buy_requires_fast_k_rising(monkeypatch) -> None:
    strategy_a = _patched(monkeypatch,
        osc_k=[60.0]*90, osc_d=[55.0]*90, rsi=[60.0]*90,
        srsi_k=[70.0]*88+[72.0,71.0], srsi_d=[50.0]*90)
    assert strategy_a["stoch_rsi"]["k_above_d"] is True
    assert strategy_a["stoch_rsi"]["k_rising"] is False
    assert strategy_a["buy_trigger"] is False


def test_stoch_rsi_bearish_cross_is_warning_not_sell(monkeypatch) -> None:
    strategy_a = _patched(monkeypatch,
        osc_k=[65.0]*90, osc_d=[60.0]*90, rsi=[60.0]*90,
        srsi_k=[70.0]*89+[60.0], srsi_d=[50.0]*89+[65.0])
    assert strategy_a["sell_warning"] is True
    assert strategy_a["sell_trigger"] is False
    assert strategy_a["exit_buffer_active"] is True
    assert strategy_a["exit_warning_active"] is True
    assert strategy_a["exit_buffered"] is True
    assert strategy_a["exit_warning_reasons"] == strategy_a["warning_reasons"]
    assert "STOCH_RSI_D_CROSSED_ABOVE_K_EARLY_WARNING" in strategy_a["warning_reasons"]


def test_stoch_osc_bearish_cross_below_80_confirms_sell(monkeypatch) -> None:
    strategy_a = _patched(monkeypatch,
        osc_k=[70.0]*89+[60.0], osc_d=[60.0]*89+[65.0], rsi=[60.0]*90,
        srsi_k=[70.0]*90, srsi_d=[50.0]*90)
    assert strategy_a["stoch_oscillator"]["both_below_80"] is True
    assert strategy_a["sell_trigger"] is True
    assert strategy_a["exit_buffer_active"] is False


def test_stoch_osc_bearish_cross_at_or_above_80_is_buffered(monkeypatch) -> None:
    strategy_a = _patched(monkeypatch,
        osc_k=[95.0]*89+[85.0], osc_d=[90.0]*89+[88.0], rsi=[70.0]*90,
        srsi_k=[70.0]*90, srsi_d=[50.0]*90)
    assert strategy_a["stoch_oscillator"]["both_below_80"] is False
    assert strategy_a["sell_trigger"] is False
    assert strategy_a["exit_buffer_active"] is True
    assert strategy_a["exit_warning_active"] is True
    assert strategy_a["exit_buffered"] is True
    assert strategy_a["exit_warning_reasons"] == strategy_a["warning_reasons"]
    assert "STOCH_OSC_BEARISH_CROSS_BUFFERED_AT_OR_ABOVE_80" in strategy_a["warning_reasons"]
