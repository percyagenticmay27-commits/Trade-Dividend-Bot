"""Central read-only market data service for the Dividend Bot.

This layer coordinates provider access, local caching, freshness rules, provider-chain
fallback, and stale-cache fallback while preserving the paper-only architecture.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from market_data_cache import MarketDataCache
from yahoo_finance_provider import MarketDataProviderError, YahooFinanceProvider

MODULE_NAME = "market_data_provider"
MODULE_VERSION = "1.1.0"
SCHEMA_VERSION = "1.1"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
ORDER_PLACEMENT_ENABLED = False
READ_ONLY_MARKET_DATA = True

DEFAULT_QUOTE_TTL_SECONDS = 300
DEFAULT_HISTORY_TTL_SECONDS = 21600
DEFAULT_DIVIDEND_TTL_SECONDS = 86400
DEFAULT_MIN_REQUEST_INTERVAL_SECONDS = 0.25


@dataclass
class MarketDataService:
    root_path: str = "."
    provider: Any = field(default_factory=YahooFinanceProvider)
    fallback_provider: Any = None
    quote_ttl_seconds: int = DEFAULT_QUOTE_TTL_SECONDS
    history_ttl_seconds: int = DEFAULT_HISTORY_TTL_SECONDS
    dividend_ttl_seconds: int = DEFAULT_DIVIDEND_TTL_SECONDS
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

    @staticmethod
    def _provider_name(provider: Any) -> str:
        return str(
            getattr(provider, "provider_name", None)
            or getattr(provider, "PROVIDER_NAME", None)
            or provider.__class__.__name__
        )

    def _call_provider(self, provider: Any, fetcher_name: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        if provider is None:
            raise MarketDataProviderError("fallback provider is not configured")
        fetcher = getattr(provider, fetcher_name, None)
        if not callable(fetcher):
            raise MarketDataProviderError(
                f"{self._provider_name(provider)} does not support {fetcher_name}"
            )
        self._throttle()
        return dict(fetcher(*args, **kwargs))

    def _fetch_with_cache(
        self,
        namespace: str,
        key: str,
        ttl_seconds: int,
        primary_fetcher,
        force_refresh: bool,
        fallback_fetcher=None,
    ) -> dict[str, Any]:
        if not force_refresh:
            cached = self.cache.read(namespace, key, max_age_seconds=ttl_seconds)
            if cached is not None:
                result = dict(cached)
                result["data_source"] = "CACHE_FRESH"
                result["is_stale"] = False
                return result

        attempts: list[dict[str, str]] = []
        try:
            self._throttle()
            payload = dict(primary_fetcher())
            attempts.append({"provider": self._provider_name(self.provider), "status": "SUCCESS"})
            payload["data_source"] = "LIVE_PROVIDER_PRIMARY"
            payload["is_stale"] = False
            payload["provider_attempts"] = attempts
            self.cache.write(namespace, key, payload)
            return payload
        except (MarketDataProviderError, OSError, RuntimeError, TypeError, ValueError) as primary_exc:
            attempts.append({
                "provider": self._provider_name(self.provider),
                "status": "FAILED",
                "error": str(primary_exc),
            })

        if fallback_fetcher is not None and self.fallback_provider is not None:
            try:
                payload = dict(fallback_fetcher())
                attempts.append({
                    "provider": self._provider_name(self.fallback_provider),
                    "status": "SUCCESS",
                })
                payload["data_source"] = "LIVE_PROVIDER_FALLBACK"
                payload["is_stale"] = False
                payload["provider_attempts"] = attempts
                self.cache.write(namespace, key, payload)
                return payload
            except (MarketDataProviderError, OSError, RuntimeError, TypeError, ValueError) as fallback_exc:
                attempts.append({
                    "provider": self._provider_name(self.fallback_provider),
                    "status": "FAILED",
                    "error": str(fallback_exc),
                })

        stale = self.cache.read_stale(namespace, key)
        if stale is None:
            summary = "; ".join(
                f"{row['provider']}: {row.get('error', row['status'])}" for row in attempts
            )
            raise MarketDataProviderError(f"No live or cached data available for {key}: {summary}")
        result = dict(stale)
        result["data_source"] = "CACHE_STALE_FALLBACK"
        result["is_stale"] = True
        result["provider_attempts"] = attempts
        result["provider_warning"] = "; ".join(
            f"{row['provider']}: {row.get('error', row['status'])}" for row in attempts
        )
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
            fallback_fetcher=(
                (lambda: self._call_provider(self.fallback_provider, "get_quote", ticker))
                if self.fallback_provider is not None
                else None
            ),
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
            fallback_fetcher=(
                lambda: self._call_provider(
                    self.fallback_provider,
                    "get_history",
                    ticker,
                    period=period,
                    interval=interval,
                )
                if self.fallback_provider is not None
                else None
            ),
        )

    def get_dividends(self, symbol: str, period: str = "5y", force_refresh: bool = False) -> dict[str, Any]:
        """Dividend events remain Yahoo/cache sourced.

        The verified Robinhood historical operation supplies OHLCV only and must not be
        treated as a dividend or corporate-action source.
        """
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
            fallback_fetcher=None,
        )

    def get_quotes(self, symbols: Iterable[str], force_refresh: bool = False) -> list[dict[str, Any]]:
        return [self.get_quote(symbol, force_refresh=force_refresh) for symbol in symbols]


def build_market_snapshot(
    symbols: Iterable[str],
    root_path: str = ".",
    force_refresh: bool = False,
    provider: Any = None,
    fallback_provider: Any = None,
) -> dict[str, Any]:
    service = MarketDataService(
        root_path=root_path,
        provider=provider or YahooFinanceProvider(),
        fallback_provider=fallback_provider,
    )
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
        "order_placement_enabled": False,
        "read_only_market_data": True,
        "provider_chain": [
            self_name
            for self_name in [
                MarketDataService._provider_name(provider or YahooFinanceProvider()),
                MarketDataService._provider_name(fallback_provider) if fallback_provider is not None else None,
                "CACHE_STALE_FALLBACK",
            ]
            if self_name
        ],
        "symbols_requested": [str(symbol).strip().upper() for symbol in symbols],
        "quotes": quotes,
        "warnings": warnings,
        "status": "COMPLETE" if quotes and not warnings else ("PARTIAL" if quotes else "ERROR"),
    }
