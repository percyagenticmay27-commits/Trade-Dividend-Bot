"""ETF-own-indicator signal model for configured ETF pairs."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from indicators import DATA_DIR, calculate_symbol_signals
from pairs_config import ETF_SIGNAL_SOURCE_MAP


def get_etf_signal_source(etf_symbol: str) -> str:
    """Return the approved ETF-own-indicator source for a pair member."""
    try:
        return ETF_SIGNAL_SOURCE_MAP[etf_symbol]
    except KeyError as exc:
        raise ValueError(f"No approved ETF signal source for {etf_symbol}") from exc


def generate_etf_signals(
    etf_symbol: str,
    data_dir: Path | None = None,
) -> pd.DataFrame:
    """Generate a pair signal using the approved ETF source's indicators."""
    source = get_etf_signal_source(etf_symbol)
    return calculate_symbol_signals(source, data_dir)
