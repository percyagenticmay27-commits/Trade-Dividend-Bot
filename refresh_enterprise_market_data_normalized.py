#!/usr/bin/env python3
"""Production refresh entry point with cost-aware public-provider failover."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import refresh_enterprise_market_data as refresh
from src.dividend_bot.enterprise_market_data_provider import (
    CodexRobinhoodSource,
    EnterpriseMarketDataProvider,
    LocalCacheSource,
    YFinanceSource,
)
from src.dividend_bot.twelve_data_market_data_source import TwelveDataSource


PRODUCTION_PROVIDER_ORDER = ("YFINANCE", "TWELVE_DATA", "LOCAL_CACHE", "ROBINHOOD_MCP")
# Stable public alias for tests, orchestration, and future consumers.
MARKET_DATA_PROVIDER_ORDER = PRODUCTION_PROVIDER_ORDER


def build_market_data_provider(
    results_dir: Path,
    cache_dir: Path,
    handoff_reader: Any | None = None,
    *,
    public_only: bool = False,
) -> EnterpriseMarketDataProvider:
    """Build the supported production provider chain.

    Twelve Data is included only when ``TWELVE_DATA_API_KEY`` is configured.
    Robinhood is omitted when ``public_only`` is true or no handoff reader is
    supplied. This is the stable public builder for production and tests.
    """
    sources: list[Any] = [YFinanceSource()]
    twelve_data_key = os.environ.get("TWELVE_DATA_API_KEY", "").strip()
    if twelve_data_key:
        sources.append(TwelveDataSource(twelve_data_key))
    sources.append(LocalCacheSource(cache_dir))
    if not public_only and handoff_reader is not None:
        sources.append(CodexRobinhoodSource(handoff_reader))
    return EnterpriseMarketDataProvider(sources=sources, results_dir=results_dir, cache_dir=cache_dir)


def build_production_provider(
    results_dir: Path,
    cache_dir: Path,
    handoff_reader: Any | None,
) -> EnterpriseMarketDataProvider:
    """Backward-compatible wrapper for the stable production builder."""
    return build_market_data_provider(results_dir, cache_dir, handoff_reader)


# Preserve established orchestration while exposing a stable public API here.
refresh.MARKET_DATA_PROVIDER_ORDER = MARKET_DATA_PROVIDER_ORDER
refresh.build_cost_aware_provider = build_market_data_provider


if __name__ == "__main__":
    raise SystemExit(refresh.main())
