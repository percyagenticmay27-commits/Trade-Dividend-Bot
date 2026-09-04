"""Central read-only market data service for the Dividend Bot.

This layer coordinates provider access, local caching, freshness rules, and stale-cache
fallback. It supplies normalized market data to analysis engines while preserving the
paper-only architecture.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from market_data_cache import MarketDataCache
from yahoo_finance_provider import MarketDataProviderError, YahooFinanceProvider

MODULE_NAME = "market_data_provider"
MODULE_VERSION = "1.1.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
READ_ONLY_MARKET_DATA = True

DEFAULT_QUOTE_TTL_SECONDS = 300
DEFAULT_HISTORY_TTL_SECONDS = 21600
DEFAULT_DIVIDEND_TTL_SECONDS = 86400
DEFAULT_FINANCIAL_HEALTH_TTL_SECONDS = 86400
DEFAULT_MIN_REQUEST_INTERVAL_SECONDS = 0.25


@dataclass
class MarketDataService:
    root_path: str = "."
    provider: Any = field(default_factory=YahooFinanceProvider)
    quote_ttl_seconds: int = DEFAULT_QUOTE_TTL_SECONDS
    history_ttl_seconds: int = DEFAULT_HISTORY_TTL_SECONDS
    dividend_ttl_seconds: int = DEFAULT_DIVIDEND_TTL_SECONDS
    financial_health_ttl_seconds: int = DEFAULT_FINANCIAL_HEALTH_TTL_SECONDS
    min_request_interval_seconds: float = DEFAULT_MIN_REQUEST_INTERVAL_SECONDS

    def __post_init__(self) -> None:
        self.cache = MarketDataCache(self.root_path)
        self._last_request_monotonic: Optional[float] = None

    def _throttle(self) -> None:
        if self._last_request_monotonic is not None:
            elapsed = time.monotonic() - self._last_request_monotonic
            remaining = self.min_request_interval_seconds - elapsed
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_monotonic = time.monotonic()

    def _fetch_with_cache(
        self,
        namespace: str,
        key: str,
        ttl_seconds: int,
        fetcher,
        force_refresh: bool,
    ) -> dict[str, Any]:
        if not force_refresh:
            cached = self.cache.read(namespace, key, max_age_seconds=ttl_seconds)
            if cached is not None:
                result = dict(cached)
                result["data_source"] = "CACHE_FRESH"
                result["is_stale"] = False
                return result
        try:
            self._throttle()
            payload = dict(fetcher())
            payload["data_source"] = "LIVE_PROVIDER"
            payload["is_stale"] = False
            self.cache.write(namespace, key, payload)
            return payload
        except (MarketDataProviderError, OSError, RuntimeError, ValueError) as exc:
            stale = self.cache.read_stale(namespace, key)
            if stale is None:
                raise MarketDataProviderError(f"No live or cached data available for {key}: {exc}") from exc
            result = dict(stale)
            result["data_source"] = "CACHE_STALE_FALLBACK"
            result["is_stale"] = True
            result["provider_warning"] = str(exc)
            return result

    def get_quote(self, symbol: str, force_refresh: bool = False) -> dict[str, Any]:
        ticker = symbol.strip().upper()
        if not ticker:
            raise ValueError("symbol is required")
        return self._fetch_with_cache(
            "quote",
            ticker,
            self.quote_ttl_seconds,
            lambda: self.provider.get_quote(ticker),
            force_refresh,
        )

    def get_financial_health_inputs(self, symbol: str, force_refresh: bool = False) -> dict[str, Any]:
        ticker = symbol.strip().upper()
        if not ticker:
            raise ValueError("symbol is required")
        return self._fetch_with_cache(
            "financial_health",
            ticker,
            self.financial_health_ttl_seconds,
            lambda: self.provider.get_financial_health_inputs(ticker),
            force_refresh,
        )

    def get_history(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        ticker = symbol.strip().upper()
        if not ticker:
            raise ValueError("symbol is required")
        key = f"{ticker}:{period}:{interval}"
        return self._fetch_with_cache(
            "history",
            key,
            self.history_ttl_seconds,
            lambda: self.provider.get_history(ticker, period=period, interval=interval),
            force_refresh,
        )

    def get_dividends(self, symbol: str, period: str = "5y", force_refresh: bool = False) -> dict[str, Any]:
        ticker = symbol.strip().upper()
        if not ticker:
            raise ValueError("symbol is required")
        key = f"{ticker}:{period}"
        return self._fetch_with_cache(
            "dividends",
            key,
            self.dividend_ttl_seconds,
            lambda: self.provider.get_dividends(ticker, period=period),
            force_refresh,
        )

    def get_quotes(self, symbols: Iterable[str], force_refresh: bool = False) -> list[dict[str, Any]]:
        return [self.get_quote(symbol, force_refresh=force_refresh) for symbol in symbols]


def build_market_snapshot(
    symbols: Iterable[str],
    root_path: str = ".",
    force_refresh: bool = False,
    provider: Any = None,
) -> dict[str, Any]:
    service = MarketDataService(root_path=root_path, provider=provider or YahooFinanceProvider())
    quotes: list[dict[str, Any]] = []
    warnings: list[str] = []
    for symbol in symbols:
        try:
            quotes.append(service.get_quote(symbol, force_refresh=force_refresh))
        except (MarketDataProviderError, ValueError) as exc:
            warnings.append(str(exc))
    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "read_only_market_data": True,
        "symbols_requested": [str(symbol).strip().upper() for symbol in symbols],
        "quotes": quotes,
        "warnings": warnings,
        "status": "COMPLETE" if quotes and not warnings else ("PARTIAL" if quotes else "ERROR"),
    }
