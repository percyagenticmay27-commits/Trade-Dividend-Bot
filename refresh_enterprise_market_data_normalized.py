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


def build_production_provider(
    results_dir: Path,
    cache_dir: Path,
    handoff_reader: Any | None,
) -> EnterpriseMarketDataProvider:
    """Use YFinance, configured Twelve Data, cache, then quota-controlled Robinhood."""
    sources: list[Any] = [YFinanceSource()]
    twelve_data_key = os.environ.get("TWELVE_DATA_API_KEY", "").strip()
    if twelve_data_key:
        sources.append(TwelveDataSource(twelve_data_key))
    sources.append(LocalCacheSource(cache_dir))
    if handoff_reader is not None:
        sources.append(CodexRobinhoodSource(handoff_reader))
    return EnterpriseMarketDataProvider(sources=sources, results_dir=results_dir, cache_dir=cache_dir)


# Preserve the established orchestration and output contract while replacing
# the provider builder and published precedence for production execution.
refresh.MARKET_DATA_PROVIDER_ORDER = PRODUCTION_PROVIDER_ORDER
refresh.build_cost_aware_provider = build_production_provider


if __name__ == "__main__":
    raise SystemExit(refresh.main())
