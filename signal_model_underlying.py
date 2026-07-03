"""Underlying-asset signal model for mapped ETF pairs."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from indicators import DATA_DIR, calculate_symbol_signals
from pairs_config import UNDERLYING_SIGNAL_MAP


def get_underlying_signal_source(etf_symbol: str) -> str:
    """Return the approved underlying signal source for an ETF."""
    try:
        return UNDERLYING_SIGNAL_MAP[etf_symbol]
    except KeyError as exc:
        raise ValueError(
            f"No approved underlying signal source for {etf_symbol}. "
            "XXRP must use the ETF model independently."
        ) from exc


def generate_underlying_signals(
    underlying_symbol: str,
    data_dir: Path | None = None,
) -> pd.DataFrame:
    """Generate signals directly from an underlying asset's own indicators."""
    return calculate_symbol_signals(underlying_symbol, data_dir)


def generate_pair_signals(
    etf_symbol: str,
    data_dir: Path | None = None,
) -> pd.DataFrame:
    """Generate an ETF pair signal using its approved underlying source."""
    source = get_underlying_signal_source(etf_symbol)
    return generate_underlying_signals(source, data_dir)
