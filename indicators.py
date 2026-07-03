"""Technical indicators and approved signal rules for downloaded daily data."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd


DATA_DIR = Path("historical_data") / "daily"
DATA_DIR_ENV = "AGENTIC_ETF_DATA_DIR"
EMA_FAST_PERIOD = 20
EMA_SLOW_PERIOD = 50
RSI_PERIOD = 14


def active_data_dir(data_dir: Path | None = None) -> Path:
    """Resolve an explicit, runtime, or default historical-data directory."""
    if data_dir is not None:
        return Path(data_dir)
    return Path(os.environ.get(DATA_DIR_ENV, DATA_DIR))


def load_symbol_data(
    symbol: str,
    data_dir: Path | None = None,
) -> pd.DataFrame:
    """Load one downloaded symbol CSV and return a date-indexed dataframe."""
    path = active_data_dir(data_dir) / f"{symbol}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Downloaded data not found for {symbol}: {path}")

    data = pd.read_csv(path, parse_dates=["date"])
    data = data.sort_values("date").set_index("date")

    if "Close" not in data.columns:
        raise ValueError(f"{path} does not contain a Close column")

    return data


def calculate_rsi(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    """Calculate Wilder RSI for a closing-price series."""
    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)

    average_gain = gains.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()
    average_loss = losses.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    relative_strength = average_gain / average_loss
    rsi = 100 - (100 / (1 + relative_strength))
    rsi = rsi.mask((average_loss == 0) & (average_gain > 0), 100)
    rsi = rsi.mask((average_loss == 0) & (average_gain == 0), 50)
    return rsi


def calculate_indicators(data: pd.DataFrame) -> pd.DataFrame:
    """Add EMA20, EMA50, and RSI14 columns to daily symbol data."""
    output = data.copy()
    close = pd.to_numeric(output["Close"], errors="coerce")

    output["EMA20"] = close.ewm(
        span=EMA_FAST_PERIOD,
        adjust=False,
        min_periods=EMA_FAST_PERIOD,
    ).mean()
    output["EMA50"] = close.ewm(
        span=EMA_SLOW_PERIOD,
        adjust=False,
        min_periods=EMA_SLOW_PERIOD,
    ).mean()
    output["RSI14"] = calculate_rsi(close)
    return output


def apply_approved_signal_rules(data: pd.DataFrame) -> pd.DataFrame:
    """Apply the approved strict BUY/SELL/HOLD rules."""
    output = calculate_indicators(data)
    ready = output[["Close", "EMA20", "EMA50", "RSI14"]].notna().all(axis=1)

    buy = (
        ready
        & (output["Close"] > output["EMA20"])
        & (output["EMA20"] > output["EMA50"])
        & (output["RSI14"] > 55)
    )
    sell = ready & (
        (output["Close"] < output["EMA20"])
        | (output["EMA20"] < output["EMA50"])
        | (output["RSI14"] < 45)
    )

    output["Signal"] = np.select(
        [buy, sell],
        ["BUY", "SELL"],
        default="HOLD",
    )
    return output


def calculate_symbol_signals(
    symbol: str,
    data_dir: Path | None = None,
) -> pd.DataFrame:
    """Load a downloaded symbol and calculate its indicators and signals."""
    return apply_approved_signal_rules(load_symbol_data(symbol, data_dir))
