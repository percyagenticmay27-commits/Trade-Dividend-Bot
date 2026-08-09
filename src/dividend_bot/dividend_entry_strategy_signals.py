"""Strategy-owned Dividend entry/exit signal evidence.

This module is analysis-only. It consumes already-fetched daily OHLC history and
publishes the two Dividend timing strategies without placing or simulating any
orders.

Strategy A
----------
Arming mechanism:
* Stochastic Oscillator (14, 3, 3): %K > %D and %K >= 50, OR
* RSI(14) is >= 50.

Execution lever while armed:
* Stochastic RSI (14, 7, 3, 3) %K > %D.
* A fresh %K/%D crossover is NOT required for BUY. If RSI or Stochastic
  Oscillator keeps the mechanism armed and Stochastic RSI %K is already above
  %D and moving upward, the setup remains BUY-active.

Exit:
* Stochastic RSI %D crosses above %K, OR
* Stochastic Oscillator %D crosses above %K.

Strategy B
----------
Entry eligible while Price > EMA20 > EMA50.
Exit when Price is below EMA20.

Exit crosses require a real side change. Equality/touching alone is not a cross.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

MODULE_NAME = "dividend_entry_strategy_signals"
MODULE_VERSION = "1.0.1"

STOCH_OSC_LENGTH = 14
STOCH_OSC_K_SMOOTH = 3
STOCH_OSC_D_SMOOTH = 3
RSI_LENGTH = 14
STOCH_RSI_LENGTH = 7
STOCH_RSI_K_SMOOTH = 3
STOCH_RSI_D_SMOOTH = 3
ARM_LEVEL = 50.0
LEVER_LEVELS = (50.0, 80.0)


def _cross_above(previous_left: float, previous_right: float, current_left: float, current_right: float) -> bool:
    return previous_left <= previous_right and current_left > current_right


def _cross_below(previous_left: float, previous_right: float, current_left: float, current_right: float) -> bool:
    return previous_left >= previous_right and current_left < current_right


def _entered_level(previous_value: float, current_value: float, level: float) -> bool:
    return previous_value < level <= current_value


def _rsi(close: pd.Series, period: int = RSI_LENGTH) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta.clip(upper=0.0))
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0.0, pd.NA)
    result = 100.0 - (100.0 / (1.0 + rs))
    return result.fillna(100.0).where(avg_gain.notna())


def _stochastic_oscillator(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    highest = frame["High"].rolling(STOCH_OSC_LENGTH).max()
    lowest = frame["Low"].rolling(STOCH_OSC_LENGTH).min()
    spread = highest - lowest
    raw_k = ((frame["Close"] - lowest) / spread.replace(0.0, pd.NA)) * 100.0
    raw_k = raw_k.fillna(50.0)
    k = raw_k.rolling(STOCH_OSC_K_SMOOTH).mean()
    d = k.rolling(STOCH_OSC_D_SMOOTH).mean()
    return k, d


def _stochastic_rsi(close: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    rsi = _rsi(close, RSI_LENGTH)
    lowest = rsi.rolling(STOCH_RSI_LENGTH).min()
    highest = rsi.rolling(STOCH_RSI_LENGTH).max()
    spread = highest - lowest
    raw = ((rsi - lowest) / spread.replace(0.0, pd.NA)) * 100.0
    raw = raw.fillna(50.0)
    k = raw.rolling(STOCH_RSI_K_SMOOTH).mean()
    d = k.rolling(STOCH_RSI_D_SMOOTH).mean()
    return rsi, k, d


def _ema(close: pd.Series, period: int) -> pd.Series:
    return close.ewm(span=period, adjust=False).mean()


def build_strategy_signals(frame: pd.DataFrame) -> dict[str, Any]:
    """Build current-bar Strategy A/B evidence from daily OHLC history."""
    required = {"Close", "High", "Low"}
    if not required.issubset(frame.columns) or len(frame) < 60:
        return {
            "available": False,
            "reason": "INSUFFICIENT_STRATEGY_SIGNAL_HISTORY",
            "strategy_a": {"entry_armed": False, "buy_trigger": False, "sell_trigger": False},
            "strategy_b": {"buy_eligible": False, "sell_trigger": False},
        }

    close = pd.to_numeric(frame["Close"], errors="coerce")
    ema20 = _ema(close, 20)
    ema50 = _ema(close, 50)
    stoch_k, stoch_d = _stochastic_oscillator(frame)
    rsi14, stoch_rsi_k, stoch_rsi_d = _stochastic_rsi(close)

    idx = len(frame) - 1
    prev = idx - 1
    values = [
        close.iloc[idx], ema20.iloc[idx], ema50.iloc[idx], rsi14.iloc[idx], rsi14.iloc[prev],
        stoch_k.iloc[idx], stoch_k.iloc[prev], stoch_d.iloc[idx], stoch_d.iloc[prev],
        stoch_rsi_k.iloc[idx], stoch_rsi_k.iloc[prev], stoch_rsi_d.iloc[idx], stoch_rsi_d.iloc[prev],
    ]
    if any(pd.isna(value) for value in values):
        return {
            "available": False,
            "reason": "INCOMPLETE_STRATEGY_SIGNAL_VALUES",
            "strategy_a": {"entry_armed": False, "buy_trigger": False, "sell_trigger": False},
            "strategy_b": {"buy_eligible": False, "sell_trigger": False},
        }

    price = float(close.iloc[idx])
    ema20_now = float(ema20.iloc[idx])
    ema50_now = float(ema50.iloc[idx])
    rsi_now = float(rsi14.iloc[idx])
    rsi_prev = float(rsi14.iloc[prev])
    osc_k = float(stoch_k.iloc[idx])
    osc_k_prev = float(stoch_k.iloc[prev])
    osc_d = float(stoch_d.iloc[idx])
    osc_d_prev = float(stoch_d.iloc[prev])
    srsi_k = float(stoch_rsi_k.iloc[idx])
    srsi_k_prev = float(stoch_rsi_k.iloc[prev])
    srsi_d = float(stoch_rsi_d.iloc[idx])
    srsi_d_prev = float(stoch_rsi_d.iloc[prev])

    oscillator_armed = osc_k > osc_d and osc_k >= ARM_LEVEL
    rsi_above_50 = rsi_now >= ARM_LEVEL
    rsi_entered_50 = _entered_level(rsi_prev, rsi_now, ARM_LEVEL)
    entry_armed = oscillator_armed or rsi_above_50

    srsi_k_above_d = srsi_k > srsi_d
    srsi_k_rising = srsi_k > srsi_k_prev
    srsi_k_cross_above_d = _cross_above(srsi_k_prev, srsi_d_prev, srsi_k, srsi_d)
    srsi_entered_50 = _entered_level(srsi_k_prev, srsi_k, 50.0)
    srsi_entered_80 = _entered_level(srsi_k_prev, srsi_k, 80.0)
    strategy_a_buy = entry_armed and srsi_k_above_d

    srsi_d_cross_above_k = _cross_above(srsi_d_prev, srsi_k_prev, srsi_d, srsi_k)
    osc_d_cross_above_k = _cross_above(osc_d_prev, osc_k_prev, osc_d, osc_k)
    strategy_a_sell = srsi_d_cross_above_k or osc_d_cross_above_k

    strategy_b_buy = price > ema20_now > ema50_now
    strategy_b_sell = price < ema20_now

    return {
        "available": True,
        "source_timeframe": "DAILY",
        "strategy_a": {
            "name": "OSCILLATOR_MOMENTUM",
            "entry_armed": entry_armed,
            "arming_reasons": [
                reason for reason, met in (
                    ("STOCH_OSC_K_ABOVE_D_AND_AT_OR_ABOVE_50", oscillator_armed),
                    ("RSI14_AT_OR_ABOVE_50", rsi_above_50),
                    ("RSI14_ENTERED_50", rsi_entered_50),
                ) if met
            ],
            "buy_trigger": strategy_a_buy,
            "sell_trigger": strategy_a_sell,
            "buy_reasons": [
                reason for reason, met in (
                    ("STOCH_RSI_K_ABOVE_D", srsi_k_above_d),
                    ("STOCH_RSI_K_RISING", srsi_k_rising),
                    ("STOCH_RSI_K_CROSSED_ABOVE_D", srsi_k_cross_above_d),
                    ("STOCH_RSI_K_ENTERED_50", srsi_entered_50),
                    ("STOCH_RSI_K_ENTERED_80", srsi_entered_80),
                ) if met
            ],
            "sell_reasons": [
                reason for reason, met in (
                    ("STOCH_RSI_D_CROSSED_ABOVE_K", srsi_d_cross_above_k),
                    ("STOCH_OSC_D_CROSSED_ABOVE_K", osc_d_cross_above_k),
                ) if met
            ],
            "rsi14": round(rsi_now, 4),
            "rsi14_previous": round(rsi_prev, 4),
            "stoch_oscillator": {
                "settings": "14,3,3",
                "k": round(osc_k, 4),
                "d": round(osc_d, 4),
                "k_previous": round(osc_k_prev, 4),
                "d_previous": round(osc_d_prev, 4),
            },
            "stoch_rsi": {
                "settings": "14,7,3,3",
                "k": round(srsi_k, 4),
                "d": round(srsi_d, 4),
                "k_previous": round(srsi_k_prev, 4),
                "d_previous": round(srsi_d_prev, 4),
                "k_above_d": srsi_k_above_d,
                "k_rising": srsi_k_rising,
            },
        },
        "strategy_b": {
            "name": "EMA_TREND",
            "buy_eligible": strategy_b_buy,
            "sell_trigger": strategy_b_sell,
            "buy_reason": "PRICE_ABOVE_EMA20_ABOVE_EMA50" if strategy_b_buy else None,
            "sell_reason": "PRICE_BELOW_EMA20" if strategy_b_sell else None,
            "price": round(price, 6),
            "ema20": round(ema20_now, 6),
            "ema50": round(ema50_now, 6),
        },
    }
