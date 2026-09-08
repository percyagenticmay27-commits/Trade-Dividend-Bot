#!/usr/bin/env python3
"""Production refresh entry point with operation-aware provider failover."""
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


# Quotes prefer a fresh broker quote before cache. History prefers validated
# cache before the quota-controlled broker bridge. The base provider still
# performs strict freshness validation and rejects stale cache entries.
QUOTE_PROVIDER_ORDER = ("YFINANCE", "TWELVE_DATA", "ROBINHOOD_MCP", "LOCAL_CACHE")
HISTORY_PROVIDER_ORDER = ("YFINANCE", "TWELVE_DATA", "LOCAL_CACHE", "ROBINHOOD_MCP")
PRODUCTION_PROVIDER_ORDER = HISTORY_PROVIDER_ORDER
MARKET_DATA_PROVIDER_ORDER = PRODUCTION_PROVIDER_ORDER


class OperationAwareEnterpriseMarketDataProvider(EnterpriseMarketDataProvider):
    """Route quote and history operations through separate source sequences.

    This class changes provider selection only. Normalization, freshness
    validation, stale-data rejection, caching, evidence, and paper-only safety
    remain owned by ``EnterpriseMarketDataProvider``.
    """

    quote_sources: list[Any]
    history_sources: list[Any]

    def _resolve(
        self,
        operation: str,
        symbol: str,
        period: str = "1mo",
        interval: str = "1d",
    ) -> dict[str, Any]:
        selected = self.quote_sources if operation == "quote" else self.history_sources
        original = self.sources
        try:
            self.sources = selected
            return super()._resolve(operation, symbol, period, interval)
        finally:
            self.sources = original


def build_market_data_provider(
    results_dir: Path,
    cache_dir: Path,
    handoff_reader: Any | None = None,
    *,
    public_only: bool = False,
) -> EnterpriseMarketDataProvider:
    """Build the supported production provider with operation-aware routing.

    Twelve Data is included only when ``TWELVE_DATA_API_KEY`` is configured.
    Robinhood is omitted when ``public_only`` is true or no handoff reader is
    supplied. Cached quote and history payloads remain subject to the base
    provider's strict freshness policy and are never accepted when stale.
    """
    yfinance = YFinanceSource()
    local_cache = LocalCacheSource(cache_dir)

    public_sources: list[Any] = [yfinance]
    twelve_data_key = os.environ.get("TWELVE_DATA_API_KEY", "").strip()
    if twelve_data_key:
        public_sources.append(TwelveDataSource(twelve_data_key))

    robinhood = None
    if not public_only and handoff_reader is not None:
        robinhood = CodexRobinhoodSource(handoff_reader)

    quote_sources = list(public_sources)
    if robinhood is not None:
        quote_sources.append(robinhood)
    quote_sources.append(local_cache)

    history_sources = list(public_sources)
    history_sources.append(local_cache)
    if robinhood is not None:
        history_sources.append(robinhood)

    provider = OperationAwareEnterpriseMarketDataProvider(
        sources=history_sources,
        results_dir=results_dir,
        cache_dir=cache_dir,
    )
    provider.quote_sources = quote_sources
    provider.history_sources = history_sources
    return provider


def build_production_provider(
    results_dir: Path,
    cache_dir: Path,
    handoff_reader: Any | None,
) -> EnterpriseMarketDataProvider:
    """Backward-compatible wrapper for the stable production builder."""
    return build_market_data_provider(results_dir, cache_dir, handoff_reader)


# Preserve established orchestration while exposing stable public policy.
refresh.MARKET_DATA_PROVIDER_ORDER = MARKET_DATA_PROVIDER_ORDER
refresh.build_cost_aware_provider = build_market_data_provider


if __name__ == "__main__":
    raise SystemExit(refresh.main())
