"""Read-only technical entry evidence derived from the shared market snapshot.

This module does not fetch market data and does not place or simulate orders. It
converts already-fetched daily OHLC history into symbol-specific entry-timing
metrics used by ``entry_score_engine``. Missing or stale evidence fails closed.

The legacy raw Fast Stochastic values are retained for compatibility/audit only.
Dividend Strategy A/B timing is published by ``dividend_entry_strategy_signals``.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

import pandas as pd

from .dividend_entry_strategy_signals import build_strategy_signals
from .indicators import calculate_indicators

MODULE_NAME = "dividend_technical_entry_evidence"
MODULE_VERSION = "1.1.0"
MIN_HISTORY_ROWS = 60
STOCH_PERIOD = 14
HMA_PERIOD = 50


def _records(snapshot: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    rows = snapshot.get("records") if isinstance(snapshot, Mapping) else []
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _history_rows(record: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    history = record.get("history") if isinstance(record.get("history"), Mapping) else {}
    rows = history.get("rows") or history.get("history") or history.get("prices") or history.get("records") or []
    return [row for row in rows if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _value(row: Mapping[str, Any], lower: str, upper: str) -> Any:
    return row.get(lower, row.get(upper))


def _frame(rows: list[Mapping[str, Any]]) -> pd.DataFrame:
    data = []
    for row in rows:
        data.append({
            "Close": _value(row, "close", "Close"),
            "High": _value(row, "high", "High"),
            "Low": _value(row, "low", "Low"),
        })
    frame = pd.DataFrame(data)
    for name in ("Close", "High", "Low"):
        frame[name] = pd.to_numeric(frame[name], errors="coerce")
    return frame.dropna(subset=["Close"]).reset_index(drop=True)


def _wma(series: pd.Series, period: int) -> pd.Series:
    weights = list(range(1, period + 1))
    denominator = float(sum(weights))
    return series.rolling(period).apply(
        lambda values: sum(float(value) * weight for value, weight in zip(values, weights)) / denominator,
        raw=True,
    )


def _hma(series: pd.Series, period: int = HMA_PERIOD) -> pd.Series:
    half = max(1, period // 2)
    root = max(1, int(math.sqrt(period)))
    raw = (2.0 * _wma(series, half)) - _wma(series, period)
    return _wma(raw, root)


def _fast_stochastic(frame: pd.DataFrame, period: int = STOCH_PERIOD) -> pd.Series:
    """Legacy raw Fast %K retained only for compatibility/audit."""
    highest = frame["High"].rolling(period).max()
    lowest = frame["Low"].rolling(period).min()
    spread = highest - lowest
    result = ((frame["Close"] - lowest) / spread) * 100.0
    return result.mask(spread == 0, 50.0)


def _rsi_score(value: float) -> float:
    if value < 45:
        return 10.0
    if value < 50:
        return 25.0
    if value <= 55:
        return 55.0
    if value <= 70:
        return 100.0
    if value <= 80:
        return 65.0
    return 35.0


def _status(score: float, blockers: list[str]) -> str:
    if any(reason.startswith("INSUFFICIENT_") for reason in blockers):
        return "UNKNOWN"
    if blockers:
        if score < 45:
            return "AVOID"
        if score < 60:
            return "WAIT"
        return "WATCH"
    if score >= 85:
        return "STRONG_ENTRY"
    if score >= 75:
        return "GOOD_ENTRY"
    if score >= 60:
        return "WATCH"
    if score >= 45:
        return "WAIT"
    return "AVOID"


def build_symbol_entry_evidence(record: Mapping[str, Any]) -> dict[str, Any]:
    symbol = str(record.get("symbol") or "").strip().upper()
    rows = _history_rows(record)
    stale = bool(record.get("is_stale"))
    blockers: list[str] = []
    warnings: list[str] = []

    if len(rows) < MIN_HISTORY_ROWS:
        blockers.append(f"INSUFFICIENT_HISTORY_{len(rows)}_ROWS")
    if stale:
        blockers.append("STALE_MARKET_DATA")

    frame = _frame(rows)
    if len(frame) < MIN_HISTORY_ROWS:
        if not any(reason.startswith("INSUFFICIENT_HISTORY") for reason in blockers):
            blockers.append(f"INSUFFICIENT_VALID_HISTORY_{len(frame)}_ROWS")
        return {
            "symbol": symbol,
            "entry_score": 0.0,
            "entry_status": "UNKNOWN",
            "timing_context": "UNKNOWN",
            "confidence": 0.0,
            "confidence_level": "LOW",
            "technical_signal": "UNKNOWN",
            "reasons": blockers,
            "requirements_for_buy": ["At least 60 valid daily OHLC rows", "Fresh market data"],
            "technical_evidence": {},
            "strategy_signals": {"available": False, "reason": "INSUFFICIENT_STRATEGY_SIGNAL_HISTORY"},
            "history_row_count": len(rows),
            "market_data_stale": stale,
            "source": "market_data_snapshot.json",
            "warnings": warnings,
        }

    indicators = calculate_indicators(frame)
    close = indicators["Close"]
    hma = _hma(close)
    legacy_fast_stochastic = _fast_stochastic(frame)
    strategy_signals = build_strategy_signals(frame)
    latest = indicators.iloc[-1]
    price = float(latest["Close"])
    ema20 = float(latest["EMA20"])
    ema50 = float(latest["EMA50"])
    rsi14 = float(latest["RSI14"])
    hma50 = float(hma.iloc[-1])
    hma50_prior = float(hma.iloc[-2])
    fast_k = float(legacy_fast_stochastic.iloc[-1])
    fast_prior = float(legacy_fast_stochastic.iloc[-2])
    fast_slope = fast_k - fast_prior

    ema_aligned = price > ema20 > ema50
    above_hma = price > hma50
    hma_rising = hma50 > hma50_prior
    five_day_up = len(close) >= 6 and float(close.iloc[-1]) > float(close.iloc[-6])

    # Legacy confirmation remains for Entry Score V1.1 compatibility. Raw Fast
    # Stochastic is no longer an entry blocker; Strategy A uses Stochastic
    # Oscillator 14,3,3 plus Stoch RSI 14,7,3,3 instead.
    if rsi14 < 50:
        blockers.append("RSI14_BELOW_50")
    elif rsi14 <= 55:
        blockers.append("RSI14_NOT_ABOVE_55")
    if not ema_aligned:
        blockers.append("EMA20_EMA50_BULLISH_ALIGNMENT_NOT_CONFIRMED")
    if not above_hma:
        blockers.append("PRICE_BELOW_HMA50")
    if not hma_rising:
        blockers.append("HMA50_NOT_RISING")

    ema_score = 100.0 if ema_aligned else (60.0 if price > ema20 else 20.0)
    hma_score = 100.0 if above_hma and hma_rising else (65.0 if above_hma else 20.0)
    trend_score = 100.0 if five_day_up else 35.0
    scores = {
        "rsi14": _rsi_score(rsi14),
        "ema_alignment": ema_score,
        "hma50": hma_score,
        "five_day_price_trend": trend_score,
    }
    score = round(sum(scores.values()) / len(scores), 2)
    status = _status(score, blockers)

    technical_signal = "BUY" if not blockers and status in {"GOOD_ENTRY", "STRONG_ENTRY"} else "HOLD"
    if rsi14 < 45 or price < ema20 or ema20 < ema50:
        technical_signal = "SELL"

    requirements: list[str] = []
    requirement_map = {
        "RSI14_BELOW_50": "RSI14 must recover above 55",
        "RSI14_NOT_ABOVE_55": "RSI14 must rise above 55",
        "EMA20_EMA50_BULLISH_ALIGNMENT_NOT_CONFIRMED": "Price > EMA20 > EMA50",
        "PRICE_BELOW_HMA50": "Price must close above HMA50",
        "HMA50_NOT_RISING": "HMA50 must turn upward",
        "STALE_MARKET_DATA": "Refresh market data",
    }
    for reason in blockers:
        requirement = requirement_map.get(reason)
        if requirement and requirement not in requirements:
            requirements.append(requirement)

    confidence = round(min(1.0, len(frame) / 200.0) * (0.5 if stale else 1.0), 4)
    confidence_level = "HIGH" if confidence >= 0.70 else ("MEDIUM" if confidence >= 0.40 else "LOW")
    timing_context = "TREND_CONTINUATION" if ema_aligned and above_hma else ("PULLBACK_ENTRY" if price > ema50 else "RANGE_BOUND")

    return {
        "symbol": symbol,
        "entry_score": score,
        "entry_status": status,
        "timing_context": timing_context,
        "confidence": confidence,
        "confidence_level": confidence_level,
        "technical_signal": technical_signal,
        "reasons": blockers or ["ENTRY_TECHNICAL_CONFIRMATION_COMPLETE"],
        "requirements_for_buy": requirements,
        "strategy_signals": strategy_signals,
        "technical_evidence": {
            "price": round(price, 6),
            "ema20": round(ema20, 6),
            "ema50": round(ema50, 6),
            "rsi14": round(rsi14, 4),
            "hma50": round(hma50, 6),
            "hma50_prior": round(hma50_prior, 6),
            "hma50_rising": hma_rising,
            "ema_bullish_alignment": ema_aligned,
            "price_above_hma50": above_hma,
            "five_day_price_up": five_day_up,
            "component_scores": scores,
            "legacy_fast_stochastic_audit": {
                "period": STOCH_PERIOD,
                "k": round(fast_k, 4),
                "k_previous": round(fast_prior, 4),
                "slope": round(fast_slope, 4),
                "entry_authority": False,
            },
        },
        "history_row_count": len(rows),
        "market_data_stale": stale,
        "source": "market_data_snapshot.json",
        "warnings": warnings,
    }


def build_technical_entry_evidence(snapshot: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    return [build_symbol_entry_evidence(record) for record in _records(snapshot) if str(record.get("symbol") or "").strip()]
